"""Hernando County, FL — Property Appraiser "HernandoBuilders" open-permits
layer.

VERIFIED (live fetch, see README section 1):
  https://services2.arcgis.com/x5zvhhxfUuRDntRe/arcgis/rest/services/HernandoBuilders/FeatureServer/63
  Layer 63 = "Open Permits". No authentication required.

Important limitation: this layer is sourced from the Property Appraiser's
office (parcel-linked permit records for valuation purposes), not the
building department directly. It has NO occupancy-type / commercial-vs-
residential flag — PERMIT_USE_DESC only gives a trade/work description
(e.g. "PLUMBING", "REROOF", "COMM ADDITION"). Scoring for this source
therefore leans more heavily on keyword matching over PERMIT_USE_DESC than
for sources with an explicit commercial flag. Geometry is parcel polygon,
not a point address — there is also no separate street-address field, only
a PARCEL_KEY, so address enrichment would require joining to the county's
parcel/GIS layer separately (not done here; parcel_number is populated,
address is not).
"""
from __future__ import annotations

from typing import List

from connectors.base import BaseConnector, clean_float, clean_str
from core.arcgis_client import epoch_ms_to_iso_sane, query_layer
from core.schema import PermitRecord

LAYER_URL = (
    "https://services2.arcgis.com/x5zvhhxfUuRDntRe/arcgis/rest/services/"
    "HernandoBuilders/FeatureServer/63"
)


class HernandoCountyConnector(BaseConnector):
    name = "hernando_county"
    jurisdiction = "Hernando County"
    source_dataset_url = LAYER_URL
    is_permit_of_record = True

    def fetch_raw(self) -> List[dict]:
        # CONFIRMED LIVE (2026-07-13): EditDate reflects Property Appraiser
        # GIS sync events, not real permit activity — filtering on it
        # returned records with permit dates scattered years in the past
        # (and one clearly-erroneous future-dated record). APPLICATION_DATE
        # is the genuine permit-filed date and is used instead.
        since_str = self.since_datetime().strftime("%Y-%m-%d")
        where = f"APPLICATION_DATE>='{since_str}'"
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
                permit_number=clean_str(r.get("PERMIT_NUMBER"))
                or clean_str(r.get("APPLICATION_NUMBER"))
                or "",
                application_date=epoch_ms_to_iso_sane(r.get("APPLICATION_DATE")),
                issue_date=epoch_ms_to_iso_sane(r.get("ISSUE_DATE")),
                expiration_date=None,
                status=clean_str(r.get("PERMIT_STATUS")),
                address=None,  # not published on this layer; only PARCEL_KEY
                city=None,
                state="FL",
                zip_code=None,
                parcel_number=clean_str(r.get("PARCEL_KEY")),
                permit_type=clean_str(r.get("PERMIT_USE_DESC")),
                permit_subtype=clean_str(r.get("PERMIT_USE_CODE")),
                work_description=clean_str(r.get("PERMIT_USE_DESC")),
                project_value=clean_float(r.get("PERMIT_VALUE")),
                square_footage=None,
                contractor_name=None,
                contractor_company=None,
                applicant_name=clean_str(r.get("APPLICANT")),
                owner_name=clean_str(r.get("APPLICANT")),  # PA data: applicant is usually the owner of record
                business_name=None,
                architect=None,
                engineer=None,
                source_record_url=None,
                source_dataset_url=self.source_dataset_url,
            )
            out.append(record)
        return out
