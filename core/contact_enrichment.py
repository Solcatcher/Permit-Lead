"""Contact enrichment lookup table — phone/email found for a lead's business
or owner, so it can show up as extra columns in the dashboard for Derek to
reach out manually.

This is intentionally NOT wired into the unattended daily collection run.
Looking up contacts costs Apollo credits and Apollo's own tools require an
explicit human confirmation (with exact wording) before every paid call, so
enrichment can only happen in a live session where that confirmation is
possible — see enrich_contacts.py for the on-demand CLI used for that.

Also intentionally NOT committed to the public GitHub repo / Vercel site:
data/contact_enrichment.csv is gitignored. Publishing a real person's phone
number and email on an unauthenticated public webpage is a privacy risk that
has nothing to do with permit data being public record, so this file only
ever lives in the private Cowork-connected folder. The GitHub Actions build
path (ci_build_dashboard.py) never loads it, so the public dashboard's
Contact column is always blank by construction — not by developer
discipline that could later slip.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Tuple

from core.config import AppConfig

FIELDNAMES = [
    "jurisdiction",
    "permit_number",
    "search_name",
    "match_type",  # "organization" | "person" | "none"
    "company_name",
    "contact_name",
    "contact_title",
    "contact_phone",
    "contact_email",
    "enriched_at",
]

EnrichmentKey = Tuple[str, str]


def _path(cfg: AppConfig) -> Path:
    return cfg.data_path("contact_enrichment.csv")


def load_enrichment(cfg: AppConfig) -> Dict[EnrichmentKey, dict]:
    """Returns {(jurisdiction, permit_number): row_dict}. Empty dict if the
    file doesn't exist yet (e.g. on a fresh GitHub Actions checkout, or
    before enrich_contacts.py has ever been run).
    """
    path = _path(cfg)
    if not path.exists():
        return {}
    out: Dict[EnrichmentKey, dict] = {}
    with open(path, "r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row.get("jurisdiction", ""), row.get("permit_number", ""))
            out[key] = row
    return out


def save_row(cfg: AppConfig, row: dict) -> None:
    """Append or update one row, keyed by (jurisdiction, permit_number)."""
    path = _path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_enrichment(cfg)
    key = (row.get("jurisdiction", ""), row.get("permit_number", ""))
    existing[key] = {k: row.get(k, "") for k in FIELDNAMES}
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in existing.values():
            writer.writerow(r)


def merge_into_leads(leads: List[dict], enrichment: Dict[EnrichmentKey, dict]) -> List[dict]:
    """Adds contact_name / contact_phone / contact_email / company_name
    (empty string if not enriched) onto each scored lead dict in place.
    """
    for lead in leads:
        key = (lead.get("jurisdiction", ""), lead.get("permit_number", ""))
        match = enrichment.get(key)
        lead["contact_name"] = match.get("contact_name", "") if match else ""
        lead["contact_title"] = match.get("contact_title", "") if match else ""
        lead["contact_phone"] = match.get("contact_phone", "") if match else ""
        lead["contact_email"] = match.get("contact_email", "") if match else ""
        lead["enriched_company_name"] = match.get("company_name", "") if match else ""
    return leads
