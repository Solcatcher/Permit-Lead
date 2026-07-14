#!/usr/bin/env python3
"""On-demand contact enrichment helper — NOT part of the unattended daily
run (see core/contact_enrichment.py for why).

This script only does the deterministic bookkeeping. The actual Apollo
lookups happen interactively in a live Cowork chat: Claude calls this
script's `list-candidates` command, shows the user the exact leads and
credit cost, waits for explicit confirmation (Apollo's own tools enforce
this per-call), runs the Apollo searches/enrichment, then calls `save` once
per result to persist it.

Usage:
  python3 enrich_contacts.py list-candidates [--min-priority High]
      Prints JSON: leads in the active window at or above --min-priority
      that don't already have a contact_enrichment.csv row, each with a
      best-effort candidate search_name pulled from whichever of
      business_name / contractor_company / owner_name / applicant_name is
      populated first (in that priority order).

  python3 enrich_contacts.py save --jurisdiction "..." --permit-number "..."
      --search-name "..." --match-type organization|person|none
      [--company-name "..."] [--contact-name "..."] [--contact-title "..."]
      [--contact-phone "..."] [--contact-email "..."]
      Appends/updates one row in data/contact_enrichment.csv.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.config import load_config
from core.contact_enrichment import load_enrichment, save_row
from core.rollup import ACTIVE_WINDOW_DAYS, filter_active_window, load_all_normalized
from scoring.scorer import CATEGORY_ORDER, score_records


def _candidate_search_name(lead: dict) -> str:
    for field in ("business_name", "contractor_company", "owner_name", "applicant_name", "contractor_name"):
        val = (lead.get(field) or "").strip()
        if val:
            return val
    return ""


def cmd_list_candidates(args: argparse.Namespace) -> int:
    cfg = load_config()
    all_records = load_all_normalized(cfg)
    active_records = filter_active_window(all_records, ACTIVE_WINDOW_DAYS)
    active_scored = score_records(active_records, cfg.scoring)

    min_rank = CATEGORY_ORDER.index(args.min_priority)
    already = load_enrichment(cfg)

    candidates = []
    for lead in active_scored:
        if CATEGORY_ORDER.index(lead["priority_category"]) > min_rank:
            continue
        key = (lead.get("jurisdiction", ""), lead.get("permit_number", ""))
        if key in already:
            continue
        search_name = _candidate_search_name(lead)
        candidates.append({
            "jurisdiction": lead.get("jurisdiction"),
            "permit_number": lead.get("permit_number"),
            "priority_category": lead.get("priority_category"),
            "score": lead.get("score"),
            "address": lead.get("address"),
            "city": lead.get("city"),
            "business_name": lead.get("business_name"),
            "search_name": search_name,
            "searchable": bool(search_name),
        })

    print(json.dumps({"count": len(candidates), "candidates": candidates}, indent=2))
    return 0


def cmd_save(args: argparse.Namespace) -> int:
    cfg = load_config()
    row = {
        "jurisdiction": args.jurisdiction,
        "permit_number": args.permit_number,
        "search_name": args.search_name,
        "match_type": args.match_type,
        "company_name": args.company_name or "",
        "contact_name": args.contact_name or "",
        "contact_title": args.contact_title or "",
        "contact_phone": args.contact_phone or "",
        "contact_email": args.contact_email or "",
        "enriched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_row(cfg, row)
    print(json.dumps({"status": "ok", "saved": row}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list-candidates")
    p_list.add_argument("--min-priority", default="High", choices=CATEGORY_ORDER)
    p_list.set_defaults(func=cmd_list_candidates)

    p_save = sub.add_parser("save")
    p_save.add_argument("--jurisdiction", required=True)
    p_save.add_argument("--permit-number", required=True)
    p_save.add_argument("--search-name", required=True)
    p_save.add_argument("--match-type", required=True, choices=["organization", "person", "none"])
    p_save.add_argument("--company-name", default="")
    p_save.add_argument("--contact-name", default="")
    p_save.add_argument("--contact-title", default="")
    p_save.add_argument("--contact-phone", default="")
    p_save.add_argument("--contact-email", default="")
    p_save.set_defaults(func=cmd_save)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
