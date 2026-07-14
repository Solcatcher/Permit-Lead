"""Shared "active lead pipeline" rollup logic, used by both the Cowork
adapter (cowork_collect.py) and the GitHub Actions path (ci_build_dashboard.py).

Both paths eventually append newly-normalized PermitRecords into the same
data/normalized/permits_normalized.csv master file (via
core.storage.append_normalized_csv). This module reads that accumulated
file back and produces the "currently active" lead list — everything
collected within ACTIVE_WINDOW_DAYS, freshly re-scored — so a run that
finds zero new leads doesn't blank out a dashboard/CSV that still has
real, recent leads in it.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from typing import List

from core.schema import NORMALIZED_FIELDS, PermitRecord

# How far back a lead stays visible in the "active" list after it's first
# collected. Intentionally separate from run.lookback_days (which controls
# how far back each connector *fetches* from its source). The scorer's own
# recency decay (0-15 pts, full score <=30 days, zero at >=180 days) already
# pushes older leads down in rank, so a slightly generous window here is safe.
ACTIVE_WINDOW_DAYS = 30


def load_all_normalized(cfg) -> List[PermitRecord]:
    """Read the full accumulated permits_normalized.csv (every distinct
    lead ever collected, across all runs) back into PermitRecord objects.
    """
    path = cfg.data_path("normalized", "permits_normalized.csv")
    if not path.exists():
        return []
    records: List[PermitRecord] = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kwargs = {}
            for field_name in NORMALIZED_FIELDS:
                value = row.get(field_name)
                if value == "":
                    value = None
                if field_name in ("project_value", "square_footage") and value is not None:
                    try:
                        value = float(value)
                    except ValueError:
                        value = None
                kwargs[field_name] = value
            kwargs["jurisdiction"] = kwargs.get("jurisdiction") or ""
            kwargs["permit_number"] = kwargs.get("permit_number") or ""
            kwargs["date_collected"] = kwargs.get("date_collected") or ""
            records.append(PermitRecord(**kwargs))
    return records


def _best_date(record: PermitRecord) -> str:
    """The most meaningful date for recency filtering: prefer issue_date,
    then application_date, then fall back to the date we collected it (so
    records with no source-provided date don't get silently dropped).
    """
    for candidate in (record.issue_date, record.application_date):
        if candidate:
            return candidate
    return (record.date_collected or "")[:10]


def filter_active_window(records: List[PermitRecord], window_days: int = ACTIVE_WINDOW_DAYS) -> List[PermitRecord]:
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=window_days)).isoformat()
    out = []
    for r in records:
        d = _best_date(r)
        if not d or d >= cutoff:
            out.append(r)
    return out
