"""Lead trend reporting — daily volume/quality history and per-jurisdiction
totals, computed from the full accumulated data/normalized/permits_normalized.csv
(every record ever collected, not just the 30-day active window).

Shared by both build paths (cowork_collect.py and ci_build_dashboard.py) so
the private Cowork dashboard and the public Vercel site show identical trend
data — unlike contact_enrichment.py, trend counts carry no personal
information, so there's no reason for this one to differ between them.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import List

from core.config import AppConfig
from core.schema import PermitRecord
from scoring.scorer import CATEGORY_ORDER, score_record

TREND_DAYS = 7  # how many trailing days of daily history to report (the past week)
TREND_WEEKS = 12  # how many trailing ISO weeks of weekly history to report


def _collected_date(record: PermitRecord):
    raw = (record.date_collected or "")[:10]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _week_start(d):
    """Monday of the ISO week containing d, as an ISO date string."""
    return (d - timedelta(days=d.isoweekday() - 1)).strftime("%Y-%m-%d")


def compute_trend(records: List[PermitRecord], cfg: AppConfig) -> dict:
    """Returns:
      {
        "daily": [ {date, total, very_high, high, medium, low, not_relevant}, ... ]
                 sorted oldest -> newest, last TREND_DAYS days that have data
        "weekly": [ {week_start, total, very_high, high, medium, low, not_relevant}, ... ]
                 sorted oldest -> newest, last TREND_WEEKS ISO weeks (Mon-start)
                 that have data
        "by_jurisdiction": [ {jurisdiction, total, very_high, high}, ... ]
                 all-time cumulative, sorted by total desc
      }
    Each record is scored "as of" its own date_collected day (see
    scoring/scorer.py's as_of parameter) so a lead's priority reflects how
    fresh it was the day it was found, not how stale it looks against today.
    """
    daily: dict[str, dict[str, int]] = defaultdict(lambda: {c: 0 for c in CATEGORY_ORDER})
    weekly: dict[str, dict[str, int]] = defaultdict(lambda: {c: 0 for c in CATEGORY_ORDER})
    by_jurisdiction: dict[str, dict[str, int]] = defaultdict(lambda: {c: 0 for c in CATEGORY_ORDER})

    for record in records:
        collected = _collected_date(record)
        as_of = collected  # None is fine — score_record falls back to today
        scored = score_record(record, cfg.scoring, as_of=as_of)
        cat = scored["priority_category"]

        day_key = collected.strftime("%Y-%m-%d") if collected else "unknown"
        daily[day_key][cat] += 1

        week_key = _week_start(collected) if collected else "unknown"
        weekly[week_key][cat] += 1

        jurisdiction = record.jurisdiction or "Unknown"
        by_jurisdiction[jurisdiction][cat] += 1

    def _rows(bucket, key_name, limit):
        out = []
        for key in sorted(k for k in bucket.keys() if k != "unknown")[-limit:]:
            counts = bucket[key]
            out.append({
                key_name: key,
                "total": sum(counts.values()),
                "very_high": counts["Very High"],
                "high": counts["High"],
                "medium": counts["Medium"],
                "low": counts["Low"],
                "not_relevant": counts["Not Relevant"],
            })
        return out

    daily_rows = _rows(daily, "date", TREND_DAYS)
    weekly_rows = _rows(weekly, "week_start", TREND_WEEKS)

    jurisdiction_rows = []
    for jurisdiction, counts in by_jurisdiction.items():
        jurisdiction_rows.append({
            "jurisdiction": jurisdiction,
            "total": sum(counts.values()),
            "very_high": counts["Very High"],
            "high": counts["High"],
        })
    jurisdiction_rows.sort(key=lambda r: r["total"], reverse=True)

    return {"daily": daily_rows, "weekly": weekly_rows, "by_jurisdiction": jurisdiction_rows}
