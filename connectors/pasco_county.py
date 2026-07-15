"""Pasco County, FL — "Project Pipeline" development-review layer.

Like hillsborough_dev_review.py, this is NOT an issued-permit feed — it's
the county's pre-permit land-development review pipeline (site plans,
rezonings, subdivisions) surfacing on the "Find a Project: Project
Pipeline" dashboard linked from pascocountyfl.gov's Business page. No
dedicated public building-permit ArcGIS layer could be found for Pasco
County (unlike Hillsborough/Hernando, its Accela permitting system —
PascoGateway — does not expose an open GIS feed of individual building
permits); this Project Pipeline layer was the only verified, live, no-auth
public data source with genuinely recent CaptiveAire-relevant activity
(Type_of_Development includes Commercial, Mixed Use, Institutional, etc.,
with building square footage and proposed-use fields).

VERIFIED (live fetch, 2026-07-15):
  https://services6.arcgis.com/Mo4MddfRHpFwT7UF/arcgis/rest/services/BOCC_BI_Development_Under_Review_Intersects/FeatureServer/13
  Discovered via the ArcGIS Web Map backing Pasco's own "Project Pipeline"
  dashboard (pascogis.pascocountyfl.net/giswebeportal/apps/dashboards/
  539b2c0b75d048a1ba31d63a93fa6efa) — this is a public ArcGIS Online hosted
  service (services6.arcgis.com), not the county's internal on-prem portal,
  so it's reachable with no authentication. 992 total records at
  verification time — small enough to fetch in full every run.
  No authentication required.

IMPORTANT QUIRK: Application_Accepted (and Approved_Date) are stored as
esriFieldTypeString, not a real ArcGIS date field, so the standard
build_date_where() TIMESTAMP-comparison WHERE clause does not apply here.
Instead we fetch the whole (small) table each run and filter by lookback
window in Python after parsing the "M/D/YYYY" text date.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from connectors.base import BaseConnector, clean_float, clean_str
from core.arcgis_client import query_layer
from core.schema import PermitRecord

LAYER_URL = (
    "https://services6.arcgis.com/Mo4MddfRHpFwT7UF/arcgis/rest/services/"
    "BOCC_BI_Development_Under_Review_Intersects/FeatureServer/13"
)

# No per-record deep link is available on this layer (no Accela capID or
# equivalent). Point at the county's general Planning search tool instead,
# same "partial/no-auth entry point, not a direct link" pattern used for
# Lakeland — build_dashboard.py labels any CapHome.aspx (module home, no
# specific record) URL as "Search" rather than "Open" for this reason.
PUBLIC_SEARCH_URL = "https://aca-prod.accela.com/PASCO/Cap/CapHome.aspx?module=Planning"


def _parse_text_date(value) -> Optional[str]:
    """Parse this layer's string-typed date fields. Application_Accepted is
    'M/D/YYYY' (no zero-padding); Approved_Date, when present, is already
    'YYYY-MM-DD HH:MM:SS'. Returns ISO 'YYYY-MM-DD' or None if unparseable
    or blank.
    """
    s = clean_str(value)
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


class PascoCountyConnector(BaseConnector):
    name = "pasco_county"
    jurisdiction = "Pasco County"
    source_dataset_url = LAYER_URL
    is_permit_of_record = False

    def fetch_raw(self) -> List[dict]:
        since_date = self.since_datetime().date()
        all_records = list(
            query_layer(
                self.client,
                LAYER_URL,
                where="1=1",
                out_fields="*",
                page_size=2000,
            )
        )
        # Application_Accepted is a text field, so the lookback window has
        # to be applied client-side after parsing, rather than in the
        # ArcGIS WHERE clause like every other connector.
        recent = []
        for r in all_records:
            accepted = _parse_text_date(r.get("Application_Accepted"))
            if accepted is None:
                # Can't confirm recency — include it rather than silently
                # dropping a record dedup hasn't seen before.
                recent.append(r)
                continue
            try:
                accepted_date = datetime.strptime(accepted, "%Y-%m-%d").date()
            except ValueError:
                recent.append(r)
                continue
            if accepted_date >= since_date:
                recent.append(r)
        return recent

    def normalize(self, raw_records: List[dict]) -> List[PermitRecord]:
        out: List[PermitRecord] = []
        for r in raw_records:
            record = PermitRecord(
                jurisdiction=self.jurisdiction,
                permit_number=clean_str(r.get("RECORD_ID")) or "",
                application_date=_parse_text_date(r.get("Application_Accepted")),
                issue_date=_parse_text_date(r.get("Approved_Date")),
                expiration_date=None,
                status=clean_str(r.get("RECORD_STATUS")),
                address=clean_str(r.get("Location")),
                city=None,
                state="FL",
                zip_code=None,
                parcel_number=clean_str(r.get("PARCEL_NUMBER")),
                permit_type=clean_str(r.get("RECORD_TYPE")),
                permit_subtype=clean_str(r.get("Type_of_Development")),
                work_description=clean_str(r.get("Proposed_Use")),
                project_value=None,  # not tracked at this pre-permit stage
                square_footage=clean_float(r.get("Building_Sq_Ft")),
                contractor_name=None,
                contractor_company=None,
                applicant_name=clean_str(r.get("CONTACT_NAME")),
                owner_name=None,
                business_name=clean_str(r.get("PROJECT_NAME")),
                architect=None,
                engineer=None,
                source_record_url=PUBLIC_SEARCH_URL,
                source_dataset_url=self.source_dataset_url,
            )
            out.append(record)
        return out
