#!/usr/bin/env python3
"""CaptiveAire Permit Lead-Gen System — daily orchestrator.

Runs every enabled connector, saves raw data, normalizes into the shared
schema, deduplicates against all prior runs, writes normalized CSV/SQLite,
scores every NEW record for CaptiveAire relevance, and writes a scored
leads CSV for that run.

Usage:
    python main.py                      # run all enabled connectors
    python main.py --only tampa_city    # run just one connector
    python main.py --dry-run            # fetch + normalize but don't write
    python main.py --config path/to/config.yaml
"""
from __future__ import annotations

import argparse
import logging
import sys
import traceback
from typing import List

from connectors import ALL_CONNECTORS
from core.config import load_config
from core.dedup import DedupIndex
from core.logging_utils import send_alert, setup_logging
from core.schema import PermitRecord
from core.storage import append_normalized_csv, save_raw, write_scored_csv, write_sqlite
from scoring.scorer import score_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CaptiveAire permit lead collector")
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Run only these connector names (space-separated), e.g. --only tampa_city lakeland",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and normalize but do not write raw/normalized/scored output or update the dedup index",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    logger = setup_logging(cfg, run_name="collect")

    enabled_names = [
        name
        for name, conn_cfg in cfg.connectors.items()
        if conn_cfg.enabled and name in ALL_CONNECTORS
    ]
    if args.only:
        enabled_names = [n for n in enabled_names if n in args.only]

    if not enabled_names:
        logger.warning("No connectors enabled/selected — nothing to do.")
        return 0

    logger.info("Running connectors: %s", ", ".join(enabled_names))

    dedup_index = DedupIndex(cfg.data_path("dedup_index.csv"))
    all_new_records: List[PermitRecord] = []
    failures: List[str] = []

    for name in enabled_names:
        connector_cls = ALL_CONNECTORS[name]
        connector = connector_cls(cfg)
        try:
            raw, normalized = connector.run()
        except Exception as exc:  # noqa: BLE001 - one bad connector must not kill the run
            logger.error("[%s] FAILED: %s", name, exc)
            logger.debug(traceback.format_exc())
            failures.append(f"{name}: {exc}")
            continue

        if not args.dry_run and raw:
            save_raw(cfg, name, raw)

        new_records = dedup_index.filter_new(normalized) if not args.dry_run else normalized
        logger.info("[%s] %d new records after dedup", name, len(new_records))
        all_new_records.extend(new_records)

    if not args.dry_run and all_new_records:
        append_normalized_csv(cfg, all_new_records)
        if "sqlite" in cfg.storage.backends:
            write_sqlite(cfg, all_new_records)

    scored = score_records(all_new_records, cfg.scoring)
    if not args.dry_run:
        write_scored_csv(cfg, scored)

    very_high = sum(1 for r in scored if r["priority_category"] == "Very High")
    high = sum(1 for r in scored if r["priority_category"] == "High")
    logger.info(
        "Run complete: %d new records total | %d Very High | %d High | %d connector failure(s)",
        len(all_new_records),
        very_high,
        high,
        len(failures),
    )

    if failures:
        send_alert(
            cfg,
            subject="CaptiveAire permit collector: connector failures",
            message="\n".join(failures),
        )

    return 1 if failures and not all_new_records else 0


if __name__ == "__main__":
    sys.exit(main())
