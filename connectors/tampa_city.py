"""City of Tampa — Commercial Construction/Permit Inspections layer.

VERIFIED (live fetch, see README section 1 for full detail):
  MapServer root: https://arcgis.tampagov.net/arcgis/rest/services/Planning/ConstructionInspections/MapServer
  Layer 0 = "Commercial" (point layer) — this is what we pull.
  (Layer 1 = Townhouses, Layer 2 = Residential — not pulled here; add them
  the same way if you also want those verticals.)

Public app this data powers: "Active Residential / Commercial Permits"
https://city-tampa.opendata.arcgis.com/apps/tampa::active-residential-commercial-permits-1
Data refreshed every 24 hours per the service's own description.
No authentication required.
"""
from __future__ import annotations

from typing import List

from connectors.base import BaseConnector, clean_float, clean_str
from core.arcgis_client import build_date_where, epoch_ms_to_iso, query_layer
from core.schema import PermitRecord

LAYER_URL = (
    "https://arcgis.tampagov.net/arcgis/rest/services/"
    "Planning/ConstructionInspections/MapServer/0"
)


class TampaCityConnector(BaseConnector):
    name = "tampa_city"
    jurisdiction = "City of Tampa"
    source_dataset_url = LAYER_URL
    is_permit_of_record = True

    def fetch_raw(self) -> List[dict]:
        where = build_date_where("LASTUPDATE", self.since_datetime())
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
            address = clean_str(r.get("ADDRESS"))
            unit = clean_str(r.get("UNIT"))
            full_address = f"{address} {unit}".strip() if unit else address

            business_name = clean_str(r.get("PROJECTNAME1")) or clean_str(
                r.get("PROJECTNAME2")
            )

            record = PermitRecord(
                jurisdiction=self.jurisdiction,
                permit_number=clean_str(r.get("RECORD_ID")) or "",
                application_date=epoch_ms_to_iso(r.get("CREATEDDATE")),
                # No dedicated "issue date" field is published on this layer;
                # LASTUPDATE is the best available proxy and is only a true
                # issue date when PROJECTSTATUS == "Issued". See README
                # "Known limitations" for detail.
                issue_date=epoch_ms_to_iso(r.get("LASTUPDATE")),
                expiration_date=None,
                status=clean_str(r.get("PROJECTSTATUS")),
                address=full_address,
                city="Tampa",
                state="FL",
                zip_code=clean_str(r.get("ZIP")),
                parcel_number=None,  # not present on this layer
                permit_type=clean_str(r.get("RECORDTYPE")),
                permit_subtype=clean_str(r.get("OCCUPANCYTYPE")) or clean_str(r.get("OCCUPANCYCATEGORY")),
                work_description=clean_str(r.get("PROJECTDESCRIPTION")),
                project_value=None,  # not present on this layer
                square_footage=clean_float(r.get("NEWCONSTRUCTIONSF")),
                contractor_name=None,
                contractor_company=None,
                applicant_name=None,
                owner_name=None,
                business_name=business_name,
                architect=None,
                engineer=None,
                source_record_url=clean_str(r.get("URL")),
                source_dataset_url=self.source_dataset_url,
            )
            out.append(record)
        return out
