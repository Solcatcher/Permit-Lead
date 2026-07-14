"""Pinellas County — Development Review Services (DRS) Site Plans layer.

VERIFIED (live fetch, see README section 1):
  https://egis.pinellas.gov/gis/rest/services/DRS/SitePlans/MapServer/0
  No authentication required.

Important limitation: this is SITE-PLAN / development-review data for
unincorporated Pinellas County only — NOT issued building permits. There is
no permit number, contractor, or valuation field. It is included as a
secondary/leading-indicator source only (a commercial site plan getting
approved often precedes permits by months) — see README section 11 for why
Pinellas County and City of Clearwater have no verified issued-permit feed
today. CREATED_DATE/LAST_EDITED_DATE were null on sampled records, so the
since-filter below uses DIST_DATE (plan distribution date) as the best
available recency field; if it is null on older records they will simply
not match a tight lookback window.
"""
from __future__ import annotations

from typing import List

from connectors.base import BaseConnector, clean_str
from core.arcgis_client import build_date_where, epoch_ms_to_iso, query_layer
from core.schema import PermitRecord

LAYER_URL = "https://egis.pinellas.gov/gis/rest/services/DRS/SitePlans/MapServer/0"


class PinellasDRSConnector(BaseConnector):
    name = "pinellas_drs"
    jurisdiction = "Pinellas County (Development Review - Site Plans)"
    source_dataset_url = LAYER_URL
    is_permit_of_record = False

    def fetch_raw(self) -> List[dict]:
        where = build_date_where("DIST_DATE", self.since_datetime())
        records = list(
            query_layer(
                self.client,
                LAYER_URL,
                where=where,
                out_fields="*",
                page_size=1000,
            )
        )
        return records

    def normalize(self, raw_records: List[dict]) -> List[PermitRecord]:
        out: List[PermitRecord] = []
        for r in raw_records:
            record = PermitRecord(
                jurisdiction=self.jurisdiction,
                permit_number=clean_str(r.get("SITE_PLAN")) or "",
                application_date=epoch_ms_to_iso(r.get("DIST_DATE")),
                issue_date=epoch_ms_to_iso(r.get("FAA_DATE")),
                expiration_date=None,
                status=clean_str(r.get("STATUS")),
                address=None,  # not published; PARCEL_NO is the join key
                city=None,
                state="FL",
                zip_code=None,
                parcel_number=clean_str(r.get("PARCEL_NO")),
                permit_type="Site Plan Review",
                permit_subtype=clean_str(r.get("PROPOSED_USE")) or clean_str(r.get("V_USE")),
                work_description=clean_str(r.get("PLAN_NAME")) or clean_str(r.get("V_DESCRIPTION")),
                project_value=None,
                square_footage=None,  # BLDG_AREA is present but stored as text/unreliable units; left blank rather than guessed
                contractor_name=None,
                contractor_company=None,
                applicant_name=None,
                owner_name=None,
                business_name=clean_str(r.get("PLAN_NAME")),
                architect=None,
                engineer=None,
                source_record_url=None,
                source_dataset_url=self.source_dataset_url,
            )
            out.append(record)
        return out
