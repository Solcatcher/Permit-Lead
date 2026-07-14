"""CaptiveAire opportunity scoring.

Pure rule-based scoring (no LLM) over the normalized PermitRecord fields.
Produces a 0-100 score, a priority category, and a human-readable list of
the specific reasons behind the score (for sales-team trust/debuggability
and for spotting scoring-rule bugs).

Score components (see README section 9 for a worked example):
  - Keyword relevance   (0-50): highest tier of keyword hit found across
                                 permit_type + permit_subtype + work_description,
                                 plus a small bonus for multiple distinct hits.
  - Commercial signal    (0-15): permit_type/subtype text matches a
                                 commercial-occupancy indicator.
  - Project value         (0-10): bonus if a known project_value clears the
                                 configured threshold; smaller bonus if a
                                 value is known at all (vs. unknown).
  - Contact completeness  (0-10): any of contractor/applicant/owner/business
                                 /architect/engineer is populated, i.e. this
                                 is an actionable lead, not just an address.
  - Project-nature signal  (0-5): description clearly says new construction,
                                 renovation, build-out, etc.
  - Recency               (0-15): linear decay from full score at
                                 <= recency_full_score_days old down to 0 at
                                 >= recency_zero_score_days old.

Total is capped at 100.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from core.config import ScoringConfig
from core.schema import PermitRecord
from scoring.keywords import (
    COMMERCIAL_INDICATORS,
    PROJECT_NATURE_KEYWORDS,
    TIER_A_KEYWORDS,
    TIER_B_KEYWORDS,
    TIER_C_KEYWORDS,
    find_matches,
)

CATEGORY_ORDER = ["Very High", "High", "Medium", "Low", "Not Relevant"]


def _combined_text(record: PermitRecord) -> str:
    parts = [
        record.permit_type or "",
        record.permit_subtype or "",
        record.work_description or "",
        record.business_name or "",
    ]
    return " | ".join(p for p in parts if p)


def _keyword_score(text: str) -> tuple[int, List[str]]:
    reasons: List[str] = []
    tier_a_hits = find_matches(text, TIER_A_KEYWORDS)
    tier_b_hits = find_matches(text, TIER_B_KEYWORDS)
    tier_c_hits = find_matches(text, TIER_C_KEYWORDS)

    if tier_a_hits:
        base = 40
        reasons.append(f"Tier-A ventilation/fire-suppression keyword match: {', '.join(tier_a_hits[:4])}")
    elif tier_b_hits:
        base = 28
        reasons.append(f"Tier-B foodservice venue keyword match: {', '.join(tier_b_hits[:4])}")
    elif tier_c_hits:
        base = 10
        reasons.append(f"Tier-C general HVAC/mechanical keyword match: {', '.join(tier_c_hits[:4])}")
    else:
        return 0, []

    distinct_hits = len(set(tier_a_hits + tier_b_hits + tier_c_hits))
    bonus = min(10, max(0, distinct_hits - 1) * 3)
    if bonus:
        reasons.append(f"+{bonus} bonus for {distinct_hits} distinct keyword matches")

    return min(50, base + bonus), reasons


def _commercial_score(record: PermitRecord) -> tuple[int, List[str]]:
    text = f"{record.permit_type or ''} {record.permit_subtype or ''}".lower()
    hits = find_matches(text, COMMERCIAL_INDICATORS)
    if hits:
        return 15, [f"Commercial occupancy indicator: {hits[0]}"]
    return 0, []


def _value_score(record: PermitRecord, cfg: ScoringConfig) -> tuple[int, List[str]]:
    if record.project_value is None:
        return 0, []
    if record.project_value >= cfg.value_bonus_threshold:
        return 10, [f"Project value ${record.project_value:,.0f} >= ${cfg.value_bonus_threshold:,.0f} threshold"]
    return 5, [f"Project value known (${record.project_value:,.0f}) but below threshold"]


def _contact_score(record: PermitRecord) -> tuple[int, List[str]]:
    contact_fields = [
        record.contractor_name,
        record.contractor_company,
        record.applicant_name,
        record.owner_name,
        record.business_name,
        record.architect,
        record.engineer,
    ]
    if any(f for f in contact_fields):
        return 10, ["At least one contact/business name present (actionable lead)"]
    return 0, []


def _project_nature_score(text: str) -> tuple[int, List[str]]:
    hits = find_matches(text, PROJECT_NATURE_KEYWORDS)
    if hits:
        return 5, [f"Clear project-nature signal: {hits[0]}"]
    return 0, []


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _recency_score(record: PermitRecord, cfg: ScoringConfig) -> tuple[int, List[str]]:
    candidate_dates = [
        d
        for d in (_parse_date(record.issue_date), _parse_date(record.application_date))
        if d is not None
    ]
    if not candidate_dates:
        return 0, []
    most_recent = max(candidate_dates)
    age_days = (date.today() - most_recent).days

    if age_days <= cfg.recency_full_score_days:
        return 15, [f"Recent record ({age_days} days old)"]
    if age_days >= cfg.recency_zero_score_days:
        return 0, []

    span = cfg.recency_zero_score_days - cfg.recency_full_score_days
    remaining = cfg.recency_zero_score_days - age_days
    score = round(15 * (remaining / span))
    return score, [f"Record is {age_days} days old (partial recency score)"]


def categorize(score: int, cfg: ScoringConfig) -> str:
    t = cfg.thresholds
    if score >= t.get("very_high", 75):
        return "Very High"
    if score >= t.get("high", 55):
        return "High"
    if score >= t.get("medium", 35):
        return "Medium"
    if score >= t.get("low", 15):
        return "Low"
    return "Not Relevant"


def score_record(record: PermitRecord, cfg: ScoringConfig) -> dict:
    """Score one PermitRecord. Returns the record as a dict plus score,
    priority_category, and score_reasons — ready to hand to
    core.storage.write_scored_csv.
    """
    text = _combined_text(record)

    kw_score, kw_reasons = _keyword_score(text)
    comm_score, comm_reasons = _commercial_score(record)
    val_score, val_reasons = _value_score(record, cfg)
    contact_score, contact_reasons = _contact_score(record)
    nature_score, nature_reasons = _project_nature_score(text)
    recency_score, recency_reasons = _recency_score(record, cfg)

    total = min(
        100,
        kw_score + comm_score + val_score + contact_score + nature_score + recency_score,
    )

    all_reasons = (
        kw_reasons + comm_reasons + val_reasons + contact_reasons + nature_reasons + recency_reasons
    )
    if not kw_reasons:
        all_reasons.insert(0, "No CaptiveAire-relevant keywords found in permit type/subtype/description")

    row = record.to_dict()
    row["score"] = total
    row["priority_category"] = categorize(total, cfg)
    row["score_reasons"] = "; ".join(all_reasons)
    return row


def score_records(records: List[PermitRecord], cfg: ScoringConfig) -> List[dict]:
    scored = [score_record(r, cfg) for r in records]
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored
