"""Hillsborough County — merged Issued Permits + Certificate-of-Occupancy
feed powering the public "Building Construction Activity Viewer" dashboard.

VERIFIED (live fetch, see README section 1):
  https://services.arcgis.com/apTfC6SUmnNfnxuF/arcgis/rest/services/AccelaDashBoard_MapService20211019/FeatureServer/0
  Layer name: GIS_Dashboard_Issued_CO_Merged
  No authentication required (anonymous query enabled).

Coverage note: this is Hillsborough County's own permitting system
(largely unincorporated county + county-permitted areas) and is DISTINCT
from City of Tampa's permits (tampa_city.py) — do not assume overlap
without checking PARCEL/folio ranges. It does not cover Plant City or
Temple Terrace, which have no verified machine-readable source (see README
section 11).
"""
from __future__ import annotations

from typing import List

from connectors.base import BaseConnector, clean_float, clean_str
from core.arcgis_client import build_date_where, epoch_ms_to_iso, query_layer
from core.schema import PermitRecord

LAYER_URL = (
    "https://services.arcgis.com/apTfC6SUmnNfnxuF/arcgis/rest/services/"
    "AccelaDashBoard_MapService20211019/FeatureServer/0"
)


class HillsboroughCountyConnector(BaseConnector):
    name = "hillsborough_county"
    jurisdiction = "Hillsborough County"
    source_dataset_url = LAYER_URL
    is_permit_of_record = True

    def fetch_raw(self) -> List[dict]:
        where = build_date_where("COMBINED_DATE", self.since_datetime())
        records = list(
            query_layer(
                self.client,
                LAYER_URL,
                where=where,
                out_fields="*",
                page_size=2000,
            )
        )
        return records

    def normalize(self, raw_records: List[dict]) -> List[PermitRecord]:
        out: List[PermitRecord] = []
        for r in raw_records:
            sf = (
                clean_float(r.get("SF_Total"))
                or clean_float(r.get("SF_Cover"))
                or clean_float(r.get("SF_Living"))
            )
            record = PermitRecord(
                jurisdiction=self.jurisdiction,
                permit_number=clean_str(r.get("PERMIT__")) or "",
                # No application-date field is published on this merged
                # layer (only issue/CO/combined dates) — see README
                # "Known limitations."
                application_date=None,
                issue_date=epoch_ms_to_iso(r.get("ISSUED_DATE")),
                expiration_date=None,
                status=clean_str(r.get("STATUS_1")),
                address=clean_str(r.get("ADDRESS")),
                city=clean_str(r.get("CITY_1")),
                state="FL",
                zip_code=None,  # not present on this layer
                parcel_number=clean_str(r.get("PARCEL")),
                permit_type=clean_str(r.get("TYPE2")),
                permit_subtype=clean_str(r.get("TYPE")),
                work_description=clean_str(r.get("DESCRIPTION")),
                project_value=clean_float(r.get("Value")),
                square_footage=sf,
                contractor_name=None,
                contractor_company=None,
                applicant_name=None,
                owner_name=None,
                business_name=None,
                architect=None,
                engineer=None,
                source_record_url=clean_str(r.get("ACA_LINK")),
                source_dataset_url=self.source_dataset_url,
            )
            out.append(record)
        return out
