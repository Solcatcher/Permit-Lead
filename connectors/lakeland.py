"""City of Lakeland, FL — IMS Projects & Permits feature layer.

VERIFIED (live fetch, see README section 1):
  https://services1.arcgis.com/mcbQY5xNGGGM1vBX/arcgis/rest/services/IMS_Projects_Permits/FeatureServer/6
  Layer 6 mixes "Permit" and "Project" records (TYPE field) — we keep both,
  since a permit-scoped consumer can filter TYPE='Permit' downstream, and
  "Project" rows can still carry an early-stage restaurant/foodservice
  build-out signal.
  No authentication required.
"""
from __future__ import annotations

from typing import List

from connectors.base import BaseConnector, clean_float, clean_str
from core.arcgis_client import epoch_ms_to_iso, query_layer
from core.schema import PermitRecord

LAYER_URL = (
    "https://services1.arcgis.com/mcbQY5xNGGGM1vBX/arcgis/rest/services/"
    "IMS_Projects_Permits/FeatureServer/6"
)

# This ArcGIS layer has no per-record detail URL field, and the city's iMS
# permitting portal (ims.lakelandgov.net) that actually issues these permits
# is session-gated — even "Continue as Guest" sets a cookie first, and the
# search results page (Find3?cat=Permits) has no URL parameter to jump
# straight to one permit; it's a manual search form. CONFIRMED (2026-07-14):
# fetching the search URL directly with no prior session just redirects to
# the login page. So this is NOT a per-permit deep link — it's the public,
# no-login entry point into Lakeland's permit search tool. The dashboard
# labels this "Search" rather than "Open" to make that distinction clear.
PUBLIC_SEARCH_URL = "https://ims.lakelandgov.net/ims/Account/Anonymous?returnUrl=%2Fims%2FFind3%3Fcat%3DPermits"


class LakelandConnector(BaseConnector):
    name = "lakeland"
    jurisdiction = "City of Lakeland"
    source_dataset_url = LAYER_URL
    is_permit_of_record = True

    def fetch_raw(self) -> List[dict]:
        # CONFIRMED LIVE (2026-07-13): LAST_EDITED_DATE reflects GIS sync
        # events, not real permit activity — a bulk resync on this date
        # touched thousands of permits going back to 2024, which would have
        # flooded the lead feed with false "new today" records if used as
        # the filter. APPLIED/ISSUED are the genuine permit-activity dates
        # and were confirmed to return correctly recent records instead.
        since = self.since_datetime()
        since_str = since.strftime("%Y-%m-%d")
        where = f"APPLIED>='{since_str}' OR ISSUED>='{since_str}'"
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
                permit_number=clean_str(r.get("PERMIT_NO")) or "",
                application_date=epoch_ms_to_iso(r.get("APPLIED")),
                issue_date=epoch_ms_to_iso(r.get("ISSUED")),
                expiration_date=None,
                status=None,  # not a direct field; APPROVED/ISSUED dates imply status
                address=clean_str(r.get("SITE_ADDR")),
                city=clean_str(r.get("SITE_CITY")) or "Lakeland",
                state=clean_str(r.get("SITE_STATE")) or "FL",
                zip_code=clean_str(r.get("SITE_ZIP")),
                parcel_number=clean_str(r.get("ADDRESSID")),
                permit_type=clean_str(r.get("TYPE")),
                permit_subtype=clean_str(r.get("PERMITORPROJECTTYPE")),
                work_description=clean_str(r.get("DESCRIPTION")),
                project_value=clean_float(r.get("JOBVALUE")),
                square_footage=None,  # not present on this layer
                contractor_name=None,
                contractor_company=None,
                applicant_name=clean_str(r.get("APPLICANT_NAME")),
                owner_name=None,
                business_name=None,
                architect=None,
                engineer=None,
                source_record_url=PUBLIC_SEARCH_URL,
                source_dataset_url=self.source_dataset_url,
            )
            out.append(record)
        return out
