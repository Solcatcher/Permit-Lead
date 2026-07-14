"""Storage layer: raw source data, normalized CSV, optional SQLite, and
scored-leads CSV. CSV is the default/required output; SQLite is an easy
opt-in upgrade path (both can run side by side).
"""
from __future__ import annotations

import csv
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from core.config import AppConfig
from core.schema import NORMALIZED_FIELDS, PermitRecord

logger = logging.getLogger(__name__)

SQLITE_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS permits (
    {', '.join(f'{c} TEXT' for c in NORMALIZED_FIELDS if c not in ('project_value', 'square_footage'))},
    project_value REAL,
    square_footage REAL,
    UNIQUE(jurisdiction, permit_number, address, application_date, issue_date)
);
"""

SCORED_FIELDS = NORMALIZED_FIELDS + ["score", "priority_category", "score_reasons"]


def save_raw(cfg: AppConfig, connector_name: str, raw_records: List[dict]) -> Path:
    """Persist the untouched, as-fetched raw records for this run, separate
    from normalized data, so nothing is ever lost to a normalization bug and
    so field-mapping issues can be debugged against the original payload.
    """
    raw_dir = cfg.data_path("raw", connector_name)
    raw_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = raw_dir / f"{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(raw_records, f, indent=2, default=str)
    logger.info("Saved %d raw records for %s -> %s", len(raw_records), connector_name, out_path)
    return out_path


def append_normalized_csv(cfg: AppConfig, records: List[PermitRecord]) -> Path:
    out_dir = cfg.data_path("normalized")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "permits_normalized.csv"
    write_header = not out_path.exists()

    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=NORMALIZED_FIELDS)
        if write_header:
            writer.writeheader()
        for record in records:
            writer.writerow(record.to_dict())

    logger.info("Appended %d normalized records -> %s", len(records), out_path)
    return out_path


def write_sqlite(cfg: AppConfig, records: List[PermitRecord]) -> Path:
    db_path = Path(cfg.storage.sqlite_path)
    if not db_path.is_absolute():
        from core.config import PROJECT_ROOT

        db_path = PROJECT_ROOT / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(SQLITE_SCHEMA)
        cols = NORMALIZED_FIELDS
        placeholders = ", ".join("?" for _ in cols)
        col_list = ", ".join(cols)
        sql = (
            f"INSERT OR IGNORE INTO permits ({col_list}) VALUES ({placeholders})"
        )
        rows = [tuple(r.to_dict()[c] for c in cols) for r in records]
        cursor = conn.executemany(sql, rows)
        conn.commit()
        logger.info(
            "SQLite: attempted %d inserts into %s (duplicates silently ignored)",
            len(rows),
            db_path,
        )
    finally:
        conn.close()
    return db_path


def write_scored_csv(cfg: AppConfig, scored_records: List[dict], filename: str = "scored_leads.csv") -> Path:
    """Scored output is written as a fresh timestamped file per run (not
    appended) so each run's report is self-contained and easy to hand to
    sales as-is. The cumulative history lives in permits_normalized.csv /
    SQLite instead.
    """
    out_dir = cfg.data_path("scored")
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"{timestamp}_{filename}"

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SCORED_FIELDS)
        writer.writeheader()
        for row in scored_records:
            writer.writerow(row)

    # Also maintain a stable "latest" copy for easy scripting/BI hookup.
    latest_path = out_dir / f"latest_{filename}"
    with open(latest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SCORED_FIELDS)
        writer.writeheader()
        for row in scored_records:
            writer.writerow(row)

    logger.info("Wrote %d scored leads -> %s (and %s)", len(scored_records), out_path, latest_path)
    return out_path
