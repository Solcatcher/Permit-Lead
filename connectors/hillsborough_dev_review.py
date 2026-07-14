"""Hillsborough County — Site/Subdivision Development Review projects.

This is NOT an issued-permit feed — it's the pre-permit land-development
review pipeline (unincorporated Hillsborough County) for site plans,
commercial projects, subdivisions, etc. It is included because it (a) is a
verified, working, no-auth ArcGIS layer and (b) carries a coded ProjectType
field with directly relevant categories ("Retail/Restaurant", "Hotel",
"Commercial - Other", "Medical", etc.) PLUS named applicant/engineer contact
fields (ContactFirst/ContactLast/ContactEmail/ContactPhone) that most permit
feeds lack — genuinely useful for *early* outreach, before a building permit
is even filed. Scoring treats these as a lower base priority than an actual
issued permit (see scoring/scorer.py) since they represent projects in
review, not confirmed construction.

VERIFIED (live fetch, see README section 1):
  https://services.arcgis.com/apTfC6SUmnNfnxuF/arcgis/rest/services/Site-Subdivision_DevReview_View/FeatureServer/0
  No authentication required.
"""
from __future__ import annotations

from typing import List

from connectors.base import BaseConnector, clean_float, clean_str
from core.arcgis_client import build_date_where, epoch_ms_to_iso, query_layer
from core.schema import PermitRecord

LAYER_URL = (
    "https://services.arcgis.com/apTfC6SUmnNfnxuF/arcgis/rest/services/"
    "Site-Subdivision_DevReview_View/FeatureServer/0"
)


class HillsboroughDevReviewConnector(BaseConnector):
    name = "hillsborough_dev_review"
    jurisdiction = "Hillsborough County (Development Review)"
    source_dataset_url = LAYER_URL
    is_permit_of_record = False

    def fetch_raw(self) -> List[dict]:
        where = build_date_where("SubmissionDate", self.since_datetime())
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
            contact_first = clean_str(r.get("ContactFirst"))
            contact_last = clean_str(r.get("ContactLast"))
            contact_name = (
                f"{contact_first or ''} {contact_last or ''}".strip() or None
            )

            record = PermitRecord(
                jurisdiction=self.jurisdiction,
                permit_number=clean_str(r.get("RecordNum")) or "",
                application_date=epoch_ms_to_iso(r.get("SubmissionDate")),
                issue_date=epoch_ms_to_iso(r.get("ProjectApprovalDate"))
                or epoch_ms_to_iso(r.get("ReviewApprovalDate")),
                expiration_date=epoch_ms_to_iso(r.get("ExpireDate")),
                status=clean_str(r.get("status")) or clean_str(r.get("dbstatus")),
                address=clean_str(r.get("Address")) or clean_str(r.get("RoadFullName")),
                city=clean_str(r.get("City")),
                state=clean_str(r.get("State")) or "FL",
                zip_code=clean_str(r.get("Zip")),
                parcel_number=clean_str(r.get("ParentFolio")) or clean_str(r.get("folio")),
                permit_type=clean_str(r.get("ApplicationGroup")),
                permit_subtype=clean_str(r.get("ProjectType")) or clean_str(r.get("MajorUse")),
                work_description=clean_str(r.get("description")) or clean_str(r.get("Comments")),
                project_value=None,  # not tracked at this pre-permit stage
                square_footage=clean_float(r.get("FootageProposedBldg"))
                or clean_float(r.get("FootageTotal")),
                contractor_name=None,
                contractor_company=None,
                applicant_name=contact_name,
                owner_name=None,
                business_name=clean_str(r.get("ProjectName")) or clean_str(r.get("ICPName")),
                architect=None,
                engineer=contact_name,  # DRS contact is very often the civil engineer of record
                source_record_url=clean_str(r.get("hillsgovhub")),
                source_dataset_url=self.source_dataset_url,
            )
            out.append(record)
        return out
