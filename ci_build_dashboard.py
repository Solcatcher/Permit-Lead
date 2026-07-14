#!/usr/bin/env python3
"""GitHub Actions counterpart to cowork_collect.py.

Run this AFTER main.py in the daily workflow. main.py already fetched live
(GitHub Actions runners have normal, unrestricted internet access — no
Cowork-sandbox network limits), normalized, deduped, and appended any new
records into data/normalized/permits_normalized.csv.

This script reads that same accumulated file, builds the rolling
active-lead window (core/rollup.py — shared with the Cowork path so both
environments produce identically-shaped output), writes a summary.json,
and renders public/index.html via build_dashboard.py so a Vercel project
pointed at the `public/` folder auto-redeploys with fresh data whenever
this workflow commits the result back to the repo.

Usage:
    python ci_build_dashboard.py --out-dir public
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from build_dashboard import build as build_dashboard_html
from core.config import load_config
from core.rollup import ACTIVE_WINDOW_DAYS, filter_active_window, load_all_normalized
from scoring.scorer import score_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the public dashboard from accumulated normalized data")
    parser.add_argument("--out-dir", default="public", help="Folder to write index.html + latest_summary.json into")
    args = parser.parse_args()

    cfg = load_config()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_records = load_all_normalized(cfg)
    active_records = filter_active_window(all_records, ACTIVE_WINDOW_DAYS)
    active_scored = score_records(active_records, cfg.scoring)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_today = [r for r in active_records if (r.date_collected or "")[:10] == today]

    # main.py writes data/last_run_counts.json at the end of its run, with
    # one entry per connector (including ones that fetched 0 / found 0 new)
    # — this is the authoritative source-status list. Prefer it; only fall
    # back to reconstructing counts from today's records (which silently
    # omits any source that had zero new results, making it look like that
    # source wasn't checked at all) if main.py hasn't run yet in this
    # environment.
    counts_path = cfg.data_path("last_run_counts.json")
    if counts_path.exists():
        with open(counts_path, "r", encoding="utf-8") as f:
            per_source_counts = json.load(f)
    else:
        per_source_counts = {}
        for r in new_today:
            key = r.jurisdiction or "unknown"
            per_source_counts.setdefault(key, {"jurisdiction": key, "fetched": 0, "new": 0})
            per_source_counts[key]["new"] += 1
            per_source_counts[key]["fetched"] += 1

    summary = {
        "run_date": today,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "per_source_counts": per_source_counts,
        "total_new": len(new_today),
        "active_window_days": ACTIVE_WINDOW_DAYS,
        "active_total": len(active_scored),
        "very_high": sum(1 for r in active_scored if r["priority_category"] == "Very High"),
        "high": sum(1 for r in active_scored if r["priority_category"] == "High"),
        "medium": sum(1 for r in active_scored if r["priority_category"] == "Medium"),
        "low": sum(1 for r in active_scored if r["priority_category"] == "Low"),
        "not_relevant": sum(1 for r in active_scored if r["priority_category"] == "Not Relevant"),
        "new_today": len(new_today),
        "leads": active_scored,
    }

    summary_path = out_dir / "latest_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    build_dashboard_html(summary_path, out_dir / "index.html")

    print(json.dumps({
        "status": "ok",
        "new_today": summary["new_today"],
        "active_total": summary["active_total"],
        "very_high": summary["very_high"],
        "high": summary["high"],
        "out_dir": str(out_dir),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
