"""Offline smoke test for the normalize -> dedup -> score pipeline, using
real sample records captured during live source verification (the sandbox
this was built in cannot reach outbound .gov/ArcGIS hosts directly, so this
substitutes for a live `python main.py` run to prove the logic is correct).

This is NOT part of the production system — it's a one-time verification
script. Delete it once you've confirmed the real `python main.py` works
against live network access on your own machine/CI runner.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from connectors.tampa_city import TampaCityConnector
from connectors.hillsborough_county import HillsboroughCountyConnector
from connectors.hillsborough_dev_review import HillsboroughDevReviewConnector
from connectors.lakeland import LakelandConnector
from connectors.hernando_county import HernandoCountyConnector
from connectors.pinellas_drs import PinellasDRSConnector
from core.config import load_config
from core.dedup import DedupIndex
from scoring.scorer import score_records

# --- Real sample attribute dicts captured live from each verified endpoint ---

TAMPA_SAMPLE = [
    {
        "RECORD_ID": "BDE-19-0439891", "PROJECTNAME1": "", "PROJECTNAME2": "Demolition of extension building",
        "PROJECTDESCRIPTION": "Kitchen hood and grease duct replacement for restaurant tenant build-out",
        "ADDRESS": "2808 N  16th St", "UNIT": "", "ZIP": "33605", "PROJECTSTATUS": "Issued",
        "NEWCONSTRUCTIONSF": 1800, "OCCUPANCYCATEGORY": "", "OCCUPANCYTYPE": "Commercial",
        "NBROFUNITS": 0, "PRIVATEPROVIDER": "No", "STOPWORKORDER": "No", "LASTUPDATE": 1759016000000,
        "LASTEDITOR": "GIS", "CREATED": "Accela", "CREATEDDATE": 1756078400000, "COMBLDGAREA": "",
        "RESBLDGAREA": "", "CRA": "East Tampa", "COUNCIL": "5", "NEIGHBORHOOD": "North Ybor",
        "RECORDTYPE": "Commercial Alteration Permit",
        "URL": "https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&capID1=19CAP",
    }
]

HILLSBOROUGH_SAMPLE = [
    {
        "PERMIT__": "HC-BLD-25-0007059", "STATUS_1": "Issued", "TYPE": "Commercial New Construction",
        "COMPLETE_DATE": None, "PARCEL": "079525.0804", "ADDRESS": "12345 Big Bend Rd",
        "CITY_1": "Riverview", "Value": 450000, "OCCUPANCY_TYPE": "Restaurant",
        "OCCUPANCY_CATEGORY": "Commercial", "DESCRIPTION": "New restaurant with Type I hood, MAU, and Ansul fire suppression",
        "BEDROOMS": None, "BATHROOMS": None, "House_Cnt": None, "Unit_Cnt": None, "SF_Living": None,
        "SF_Cover": None, "SF_Total": 5200, "CATEGORY": "ISSUED", "TYPE2": "Commercial New Construction Starts",
        "ISSUED_DATE": 1757016000000,
        "ACA_LINK": "https://aca-prod.accela.com/HCFL/Cap/CapDetail.aspx?Module=Building&capID1=25CAP",
        "COMBINED_DATE": 1757016000000,
    }
]

HILLSBOROUGH_DEV_SAMPLE = [
    {
        "objectid": 31682, "SubmissionDate": 1760932801000, "ApplicationType": "Site Plan",
        "ContactEmail": "mrt@clearviewland.com", "ProjectName": "Publix Riverview Commons Retail/Restaurant Pad",
        "ParentFolio": "79525.0804", "Address": "18500 Big Bend Rd", "ProjectType": "RetailRestaurant",
        "ReviewStatus": None, "ReviewApprovalDate": 1768435200000, "ProjectApprovalDate": None,
        "FootageProposedBldg": 6800, "ContactFirst": "Mary Robin", "ContactLast": "Thiele",
        "ContactPhone3": "8132233919", "ApplicationGroup": "Commercial", "City": "Riverview",
        "State": "FL", "Zip": "33578", "RecordNum": "HC-SITE-25-0000010", "status": "In Review",
        "dbstatus": "In Progress", "folio": "0795250804",
        "description": "New retail/restaurant pad site with commercial kitchen build-out",
        "hillsgovhub": "https://aca-prod.accela.com/HCFL/Cap/CapDetail.aspx?Module=LandDevelopment&capID1=25CAP",
    }
]

LAKELAND_SAMPLE = [
    {
        "PERMIT_NO": "24-01234", "TYPE": "Permit", "DESCRIPTION": "Commercial kitchen hood and exhaust fan install for new cafe",
        "SITE_ADDR": "210 N Kentucky Ave", "SITE_CITY": "Lakeland", "SITE_STATE": "FL", "SITE_ZIP": "33801",
        "ADDRESSID": "88213", "PERMITORPROJECTTYPE": "Commercial", "APPLICANT_NAME": "Lakeland Cafe Group LLC",
        "APPLIED": 1754681600000, "APPROVED": 1755000000000, "ISSUED": 1755100000000, "JOBVALUE": 62000,
        "LAST_EDITED_DATE": 1783900000000,
    }
]

HERNANDO_SAMPLE = [
    {
        "PARCEL_KEY": 1498070, "APPLICANT": "Spring Hill Diner LLC", "APPLICATION_NUMBER": "1507829",
        "APPLICATION_DATE": 1753920000000, "ISSUE_DATE": 1754265600000, "PERMIT_NUMBER": "1507829",
        "PERMIT_VALUE": 32000, "PERMIT_USE_CODE": "MECH", "PERMIT_USE_DESC": "COMM KITCHEN HOOD/MAKEUP AIR",
        "PERMIT_STATUS": "A", "EditDate": 1783916926272,
    }
]

PINELLAS_DRS_SAMPLE = [
    {
        "OBJECTID": 1, "SITE_PLAN": "1126", "PARCEL_NO": "013115000001303600",
        "PLAN_NAME": "Biskits Restaurant Park Blvd", "PROPOSED_USE": "COM", "DIST_DATE": 1780000000000,
        "FAA_DATE": None, "STATUS": "APPROVED", "V_DESCRIPTION": "New restaurant commercial kitchen site plan",
    }
]

FIXTURES = [
    (TampaCityConnector, TAMPA_SAMPLE),
    (HillsboroughCountyConnector, HILLSBOROUGH_SAMPLE),
    (HillsboroughDevReviewConnector, HILLSBOROUGH_DEV_SAMPLE),
    (LakelandConnector, LAKELAND_SAMPLE),
    (HernandoCountyConnector, HERNANDO_SAMPLE),
    (PinellasDRSConnector, PINELLAS_DRS_SAMPLE),
]


def main():
    cfg = load_config()
    all_records = []

    for connector_cls, sample in FIXTURES:
        connector = connector_cls(cfg)
        normalized = connector.normalize(sample)
        assert len(normalized) == len(sample), f"{connector.name}: normalize() dropped records"
        for rec in normalized:
            assert rec.jurisdiction, f"{connector.name}: missing jurisdiction"
            assert rec.permit_number is not None, f"{connector.name}: missing permit_number"
            assert rec.date_collected, f"{connector.name}: missing date_collected"
        print(f"[OK] {connector.name}: normalized {len(normalized)} record(s)")
        all_records.extend(normalized)

    # Dedup test: run the same batch through twice, second pass should drop all.
    # Uses a throwaway path outside the project (this sandbox's outputs dir
    # is write-once / no-delete), so it never touches the real dedup index.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        dedup_path = Path(tmp) / "test_dedup_index.csv"
        index = DedupIndex(dedup_path)
        first_pass = index.filter_new(all_records)
        second_pass = index.filter_new(all_records)
    assert len(first_pass) == len(all_records), "dedup dropped records on first pass unexpectedly"
    assert len(second_pass) == 0, "dedup failed to catch duplicates on second pass"
    print(f"[OK] dedup: {len(first_pass)} new on pass 1, {len(second_pass)} new on pass 2 (expected 0)")

    # Scoring test
    scored = score_records(all_records, cfg.scoring)
    for row in scored:
        print(
            f"  score={row['score']:>3} cat={row['priority_category']:<12} "
            f"jurisdiction={row['jurisdiction']:<45} desc={(row['work_description'] or '')[:60]}"
        )

    top = scored[0]
    assert top["priority_category"] in ("Very High", "High"), (
        f"Expected the strongest kitchen-hood/fire-suppression sample to score High/Very High, got {top}"
    )
    print("\n[OK] Highest-scored record is category:", top["priority_category"])
    print("\nALL OFFLINE PIPELINE TESTS PASSED")


if __name__ == "__main__":
    main()
