#!/usr/bin/env python3
"""Adapter for running the collector inside a Cowork scheduled-task session.

Why this exists: Cowork's bash sandbox only allows outbound network calls to
an allowlisted set of hosts (package registries, etc) — arcgis.tampagov.net
and similar government/ArcGIS hosts are blocked there. Cowork's separate
`web_fetch` agent tool CAN reach those hosts. So the daily flow splits in two:

  1. The agent (following the scheduled task prompt) calls `web_fetch` on
     each of the 6 verified source query URLs and saves the raw JSON
     response(s) to <raw-input-dir>/<connector_name>_page<N>.json
     (page2, page3, ... only needed if a source's response had
     "exceededTransferLimit": true, in which case the agent re-fetches
     with resultOffset advanced and saves the next page).
  2. This script reads those files, extracts each feature's `attributes`,
     runs them through the exact same connector.normalize() methods used
     by the full main.py pipeline, then dedupes against the persisted
     index, scores, and writes:
       - a dated CSV and a "latest" CSV into --output-dir (your connected
         folder)
       - latest_summary.json (counts + full scored lead list) which the
         agent then uses to rebuild the dashboard artifact's HTML

This script does NOT make any network calls itself — it only reads local
JSON files already fetched by the agent. That's what makes it safe to run
via bash inside the sandbox.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from connectors.hernando_county import HernandoCountyConnector
from connectors.hillsborough_county import HillsboroughCountyConnector
from connectors.hillsborough_dev_review import HillsboroughDevReviewConnector
from connectors.lakeland import LakelandConnector
from connectors.pinellas_drs import PinellasDRSConnector
from connectors.tampa_city import TampaCityConnector
from core.config import load_config
from core.contact_enrichment import load_enrichment, merge_into_leads
from core.dedup import DedupIndex
from core.rollup import ACTIVE_WINDOW_DAYS, filter_active_window, load_all_normalized
from core.storage import append_normalized_csv
from core.trends import compute_trend
from scoring.scorer import score_records

CONNECTORS = {
    "tampa_city": TampaCityConnector,
    "hillsborough_county": HillsboroughCountyConnector,
    "hillsborough_dev_review": HillsboroughDevReviewConnector,
    "lakeland": LakelandConnector,
    "hernando_county": HernandoCountyConnector,
    "pinellas_drs": PinellasDRSConnector,
}


def load_raw_attributes(raw_input_dir: Path, name: str) -> list[dict]:
    """Read every <name>_page*.json in raw_input_dir, pull out each
    feature's `attributes` dict (the ArcGIS response shape), and return
    the combined list. Silently skips files that don't parse as the
    expected ArcGIS query-response shape (logged to stderr) rather than
    crashing the whole run over one bad page.
    """
    attrs: list[dict] = []
    files = sorted(raw_input_dir.glob(f"{name}_page*.json"))
    if not files:
        print(f"  [warn] no raw input files found for '{name}' (expected {name}_page1.json etc)", file=sys.stderr)
        return attrs

    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  [warn] could not read {f}: {exc}", file=sys.stderr)
            continue

        if "error" in data:
            print(f"  [warn] {f} contains an ArcGIS error response: {data['error']}", file=sys.stderr)
            continue

        for feature in data.get("features", []):
            a = feature.get("attributes")
            if a:
                attrs.append(a)

    return attrs


def main() -> int:
    parser = argparse.ArgumentParser(description="Process pre-fetched ArcGIS JSON into scored leads")
    parser.add_argument("--raw-input-dir", default="raw_input", help="Folder containing <connector>_page*.json files")
    parser.add_argument("--output-dir", required=True, help="Folder to write the CSV/summary into (your connected folder)")
    args = parser.parse_args()

    cfg = load_config()
    raw_input_dir = Path(args.raw_input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dedup_index = DedupIndex(cfg.data_path("dedup_index.csv"))
    all_new = []
    per_source_counts: dict[str, dict] = {}

    for name, cls in CONNECTORS.items():
        attrs = load_raw_attributes(raw_input_dir, name)
        connector = cls(cfg)
        normalized = connector.normalize(attrs)
        new_records = dedup_index.filter_new(normalized)
        per_source_counts[name] = {
            "jurisdiction": connector.jurisdiction,
            "fetched": len(attrs),
            "new": len(new_records),
        }
        all_new.extend(new_records)
        print(f"  [{name}] fetched={len(attrs)} new={len(new_records)}")

    if all_new:
        append_normalized_csv(cfg, all_new)

    # "Today's new" scored list — this is what's genuinely fresh from this
    # specific run, and is what the dated per-day CSV represents.
    new_scored = score_records(all_new, cfg.scoring)

    # "Latest" / dashboard list — the full rolling active-lead pipeline
    # (everything collected in the last ACTIVE_WINDOW_DAYS days, re-scored),
    # so a run with 0 new leads doesn't wipe out visibility of leads found
    # on a previous run.
    all_records = load_all_normalized(cfg)
    active_records = filter_active_window(all_records, ACTIVE_WINDOW_DAYS)
    active_scored = score_records(active_records, cfg.scoring)

    # Contact enrichment is on-demand only (see core/contact_enrichment.py)
    # — this just merges in whatever's already been looked up via
    # enrich_contacts.py, adding empty contact_* fields to everything else
    # so every row has the same columns regardless of enrichment status.
    enrichment = load_enrichment(cfg)
    active_scored = merge_into_leads(active_scored, enrichment)
    new_scored = merge_into_leads(new_scored, enrichment)

    # Trend history uses ALL records ever collected (not just the 30-day
    # active window) — see core/trends.py.
    trend = compute_trend(all_records, cfg)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fieldnames = list(active_scored[0].keys()) if active_scored else (
        list(new_scored[0].keys()) if new_scored else [
            "jurisdiction", "permit_number", "status", "address", "work_description",
            "score", "priority_category",
        ]
    )

    def write_csv(path: Path, rows: list[dict]):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    dated_csv = output_dir / f"CaptiveAire_Leads_{today}.csv"
    latest_csv = output_dir / "CaptiveAire_Leads_Latest.csv"
    write_csv(dated_csv, new_scored)
    write_csv(latest_csv, active_scored)

    summary = {
        "run_date": today,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "per_source_counts": per_source_counts,
        "total_new": len(all_new),
        "active_window_days": ACTIVE_WINDOW_DAYS,
        "active_total": len(active_scored),
        "very_high": sum(1 for r in active_scored if r["priority_category"] == "Very High"),
        "high": sum(1 for r in active_scored if r["priority_category"] == "High"),
        "medium": sum(1 for r in active_scored if r["priority_category"] == "Medium"),
        "low": sum(1 for r in active_scored if r["priority_category"] == "Low"),
        "not_relevant": sum(1 for r in active_scored if r["priority_category"] == "Not Relevant"),
        "new_today": len(new_scored),
        "leads": active_scored,
        "trend": trend,
    }
    summary_path = output_dir / "latest_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    print(json.dumps({
        "status": "ok",
        "new_today": len(all_new),
        "active_total": summary["active_total"],
        "active_window_days": ACTIVE_WINDOW_DAYS,
        "very_high": summary["very_high"],
        "high": summary["high"],
        "dated_csv": str(dated_csv),
        "latest_csv": str(latest_csv),
        "summary_json": str(summary_path),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
