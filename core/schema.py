"""The normalized permit record schema every connector maps into.

This is the exact 27-field schema requested for the system: one flat,
jurisdiction-agnostic record shape so downstream scoring/storage/reporting
never needs to know which source a record came from.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timezone
from typing import Optional

NORMALIZED_FIELDS = [
    "jurisdiction",
    "permit_number",
    "application_date",
    "issue_date",
    "expiration_date",
    "status",
    "address",
    "city",
    "state",
    "zip_code",
    "parcel_number",
    "permit_type",
    "permit_subtype",
    "work_description",
    "project_value",
    "square_footage",
    "contractor_name",
    "contractor_company",
    "applicant_name",
    "owner_name",
    "business_name",
    "architect",
    "engineer",
    "source_record_url",
    "source_dataset_url",
    "date_collected",
]


@dataclass
class PermitRecord:
    jurisdiction: str = ""
    permit_number: str = ""
    application_date: Optional[str] = None
    issue_date: Optional[str] = None
    expiration_date: Optional[str] = None
    status: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    parcel_number: Optional[str] = None
    permit_type: Optional[str] = None
    permit_subtype: Optional[str] = None
    work_description: Optional[str] = None
    project_value: Optional[float] = None
    square_footage: Optional[float] = None
    contractor_name: Optional[str] = None
    contractor_company: Optional[str] = None
    applicant_name: Optional[str] = None
    owner_name: Optional[str] = None
    business_name: Optional[str] = None
    architect: Optional[str] = None
    engineer: Optional[str] = None
    source_record_url: Optional[str] = None
    source_dataset_url: Optional[str] = None
    date_collected: str = ""

    def __post_init__(self):
        if not self.date_collected:
            self.date_collected = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

    def to_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def dedup_key(self) -> tuple:
        """See core/dedup.py for the rationale behind this key."""
        return (
            (self.jurisdiction or "").strip().lower(),
            (self.permit_number or "").strip().upper(),
            (self.address or "").strip().lower(),
            (self.application_date or ""),
            (self.issue_date or ""),
        )
