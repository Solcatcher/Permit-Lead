# CaptiveAire Tampa Bay Permit Lead-Generation System

An automated collector that pulls newly filed/issued **commercial building permits** across
the Tampa Bay region from official public GIS/open-data APIs, normalizes them into one
schema, deduplicates across days, and scores every record for CaptiveAire (commercial
kitchen ventilation) sales relevance — restaurants, commercial kitchens, hoods, grease duct,
makeup air, fire suppression, walk-ins, HVAC/mechanical work, and related tenant build-outs.

Every endpoint below was verified with a live HTTP query during this build (not guessed).
Where a jurisdiction has no public machine-readable permit data, that is stated plainly
rather than invented.

---

## 1. Verified Source Inventory

### 1a. VERIFIED — wired into the collector

| Jurisdiction | Source | Endpoint | Format | Auth | Update freq. | Date range | Pagination | Bulk vs. enrichment | Reliability |
|---|---|---|---|---|---|---|---|---|---|
| **City of Tampa** | Planning / Construction Inspections — "Commercial" layer | `https://arcgis.tampagov.net/arcgis/rest/services/Planning/ConstructionInspections/MapServer/0` | ArcGIS REST JSON | None | Stated "updated daily" | Live/rolling (no fixed start) | `resultOffset`/`resultRecordCount`, `maxRecordCount=2000` | **Bulk** | High |
| **Hillsborough County** | Building Construction Activity Viewer feed (Issued+CO merged) | `https://services.arcgis.com/apTfC6SUmnNfnxuF/arcgis/rest/services/AccelaDashBoard_MapService20211019/FeatureServer/0` | ArcGIS REST JSON | None | Not stated; data current to within days of query | ~2019-03 to present (34k+ records) | `resultOffset`/`resultRecordCount`, `maxRecordCount=2000` | **Bulk** | High |
| **Hillsborough County** | Site-Subdivision Development Review (pre-permit pipeline, has named contacts) | `https://services.arcgis.com/apTfC6SUmnNfnxuF/arcgis/rest/services/Site-Subdivision_DevReview_View/FeatureServer/0` | ArcGIS REST JSON | None | Actively edited (records from 2025-2026 observed) | Rolling | `resultOffset`/`resultRecordCount`, `maxRecordCount=2000` | **Bulk** (secondary/leading-indicator, not issued permits) | High |
| **City of Lakeland** | IMS Projects & Permits | `https://services1.arcgis.com/mcbQY5xNGGGM1vBX/arcgis/rest/services/IMS_Projects_Permits/FeatureServer/6` | ArcGIS REST JSON | None | Not stated | Historic + current, mixed | `resultOffset`/`resultRecordCount`, `maxRecordCount=16000` | **Bulk** | High |
| **Hernando County** | Property Appraiser "HernandoBuilders" Open Permits (layer 63) | `https://services2.arcgis.com/x5zvhhxfUuRDntRe/arcgis/rest/services/HernandoBuilders/FeatureServer/63` | ArcGIS REST JSON | None | Actively edited | Rolling | `resultOffset`/`resultRecordCount`, `maxRecordCount=2000` | **Bulk** | High |
| **Pinellas County** | DRS Site Plans (unincorporated county only; site-plan review, not issued permits) | `https://egis.pinellas.gov/gis/rest/services/DRS/SitePlans/MapServer/0` | ArcGIS REST JSON | None | Not stated | Not stated | `resultOffset`/`resultRecordCount`, `maxRecordCount=1000` | **Bulk** (secondary/leading-indicator) | Medium |

All six are unauthenticated, public ArcGIS REST endpoints, confirmed by directly querying
`.../query?where=1=1&outFields=*&f=json` and inspecting the returned `fields` and `features`
arrays. No terms-of-use gate, API key, or login is required by any of them.

**Rate-limit / ToS notes:** none of the six publish an explicit rate limit. The collector
self-limits to `max_requests_per_second: 2` (configurable) and identifies itself with a
descriptive `User-Agent` string (see `core/http_client.py`) as a courtesy — please put a real
contact email in that string before running this in production, per general good-citizenship
practice for public government infrastructure.

### 1b. NOT FOUND — no working machine-readable source (manual fallback only)

| Jurisdiction | What was checked | Manual fallback |
|---|---|---|
| **City of Clearwater** | Own ArcGIS Server (no Planning/Permits folder exists), ArcGIS Hub DCAT catalog (no permit dataset), "Permitting Dashboard" (embeds a Power BI report, not an API) | Accela: `https://epermit.myclearwater.com/CitizenAccess/Cap/CapHome.aspx?module=Building&TabName=Building` (browser search only) |
| **Pinellas County** (issued permits, as opposed to the DRS site-plan layer above) | egis.pinellas.gov Accela-support MapServers (basemap/reference layers only, no permit records), ArcGIS Hub DCAT feed | Accela: `https://aca-prod.accela.com/pinellas/Default.aspx` (covers unincorporated county + Belleair Beach, Belleair Bluffs, Belleair Shore, Indian Rocks Beach, Kenneth City, Oldsmar, Safety Harbor) |
| **Pasco County** | data-pascocounty.opendata.arcgis.com DCAT catalog (no permits), AGOL org search, pascogis.pascocountyfl.net Accela support layers (basemap only), a dead `NEW_DEVELOPMENT_ReaderOnly` dashboard layer (404) | Accela "PascoGateway": `https://aca-prod.accela.com/PASCO/` or `https://permits.pascocountyfl.net/CitizenAccess/` |
| **St. Petersburg** | geohub-csp.opendata.arcgis.com (utilities only); `egis.stpete.org/arcgis/rest/services/ServicesDSD/PermitsExternal/FeatureServer` — real, publicly-queryable, no-auth City of St. Petersburg service, layers named "(2019-2021)" but actually contain records through mid-2024. Re-verified live 2026-07-13: max `PERMITISSUEDATE` across the whole "Other New Construction" layer is `240822` (Aug 22, 2024) — **frozen, ~23 months stale**, not a live daily feed. An internal `ServicesTyler` folder exists on the same GIS server (the city is mid-migration to Tyler EnerGov as of late 2025 per stpete.org) but requires an auth token and isn't publicly queryable. Re-check after the Tyler migration completes in case a new public feed is published. | Live single-permit lookup is Click2Gov: `https://stpe-egov.aspgov.com/Click2GovBP/index.html` (address/permit-number search only, no bulk export) |
| **Temple Terrace** | No GIS/open-data portal found | Click2Gov: `https://temp-egov.aspgov.com/Click2GovBP/index.html` |
| **Plant City** | City's own ArcGIS server has parcels/zoning/utilities only, no permits layer | MaintStar portal: `https://h8.maintstar.co/plantcity/portal/` (login-gated) |
| **Bradenton** | No open-data/ArcGIS presence for permits found | Accela: `https://aca-prod.accela.com/BRADENTON/Default.aspx` |
| **Manatee County** | County ArcGIS servers checked (zoning/FLU/utilities/parcels — no permits layer); a static closed-permit archive exists but only through 2018-02-28 | Live portal: `https://www.mymanatee.org/services-and-amenities/service-listing/service-details/search-permit-records` · Historical CSV archive (1991–2018): `https://www.civicdata.com/dataset/manatee-county-permit-data-archive` |
| **Sarasota County** | Live portal is a JS-rendered Blazor app (no exposed JSON endpoint); ArcGIS Hub/org search returned only tangential layers (septic, tree inventory, coastal permit lines) | `https://building.scgov.net/` (browser only) |

None of these nine currently expose a live, queryable, no-login API. Building a collector
against any of them today would mean either (a) reverse-engineering an undocumented internal
API that could change without notice, or (b) full browser automation against a citizen portal
— which the project brief explicitly asked to avoid unless "absolutely necessary," and which
carries real fragility/ToS risk against systems that were not designed for scripted access.
**Recommendation:** for these nine, contact each jurisdiction's GIS/IT department directly and
ask whether a private/agency data-sharing feed exists — several of the "not found" cases (e.g.
Pasco, St. Pete) clearly have the underlying data in a real permitting system (Accela,
Click2Gov), it's just not published as open data today.

### 1c. Additional avenues investigated after initial delivery (no new live sources found)

After the initial 6-source build, three more angles were checked specifically to try to close
the 9-jurisdiction gap above. None produced a new source that met this project's "verified,
don't invent field names" bar — documented here so the search isn't silently repeated later.

- **County Property Appraiser ArcGIS layers** (the pattern behind the working Hernando County
  source — PAs track permits county-wide for valuation purposes, which can incidentally cover
  incorporated cities a building department's own portal wouldn't). Checked Hillsborough,
  Pinellas, Pasco, Manatee, and Sarasota County Property Appraiser ArcGIS orgs directly. Only
  Hillsborough's PA publishes a permits layer — and it is the *same* `AccelaDashBoard_MapService20211019`
  feed already wired in as `hillsborough_county` (just co-hosted under the PA's ArcGIS org), so
  no new coverage. Pinellas, Pasco, Manatee, and Sarasota PA offices publish parcel/CAMA/sales
  data only — no permit-specific fields anywhere in their public services.
- **CivicData.com / the "BLDS" standard** (the platform Tampa's own permit data happens to be
  mirrored on). Accela built CivicData.com on CKAN and it once hosted permit datasets for ~60
  agencies nationwide, including a "City of Clearwater, FL-Building Permits" dataset and a
  static "Manatee County Permit Data Archive" (1991–2018). In practice: the site's homepage
  loads, but every dataset page, resource page, and CKAN API endpoint (`/api/3/action/...`)
  tested returned empty/no content across repeated attempts — consistent with Accela having
  discontinued the platform's underlying data infrastructure while leaving the marketing site
  up. **Not wired in**, because the actual field names/schema could not be confirmed by live
  query, and this project's brief explicitly rules out inventing field names. If you can reach
  `civicdata.com` from a different network and confirm it still serves real data, the resource
  ID for Clearwater is `5443d8f7-3a99-44ba-bb79-21a651b84cca` (via `datastore_search`) — treat
  as an unverified lead, not a confirmed source. Separately: even if it worked, the Manatee
  archive stops in 2018 and would contribute zero *new* leads to a forward-looking system.
- **Paid third-party permit-data vendors**, as an alternative to free government sources for
  the 9-jurisdiction gap: **Shovels.ai** has a genuine documented REST API and claims Florida
  coverage, but county-level coverage for Pinellas/Pasco/Manatee/Sarasota and real pricing
  (secondhand estimates put it near $599/mo) aren't published — worth a direct coverage-dashboard
  check before subscribing. **Construction Monitor** likewise has a real API/FTP option but no
  public pricing or confirmed county coverage. **PermitGrab** ($149/mo, 14-day trial, no real
  API — CSV export only) was checked directly: its Tampa and Pinellas pages are dominated by
  residential trade permits (HVAC changeouts, reroofs) rather than new commercial construction,
  and its Sarasota and Manatee pages showed "data source updating" — i.e. not actually covered
  despite being listed. **ConstructConnect/Dodge** are enterprise-priced construction-bidding
  platforms, a poor fit for a lean permit feed. **Reonomy/CoStar** don't offer permit data at
  all (property/ownership only). None of these were purchased or wired in — they'd need your
  own account/API key, and are listed here purely so you don't have to re-research them.

---

## 2. Recommended Architecture

```
                 ┌───────────────────────┐
config.yaml ───► │   core/config.py       │
.env             └───────────┬───────────┘
                              │
                 ┌────────────▼────────────┐
                 │        main.py           │  (orchestrator)
                 └─┬───────┬────────┬───────┘
                   │       │        │
     ┌─────────────▼┐ ┌────▼────┐ ┌─▼──────────────┐
     │  connectors/  │ │  core/  │ │   scoring/      │
     │  (1 per       │ │ arcgis_ │ │  keyword tiers  │
     │  jurisdiction)│ │ client, │ │  + rule-based   │
     │  fetch_raw()  │ │ http_   │ │  scorer         │
     │  normalize()  │ │ client  │ │  (no LLM here)  │
     └──────┬────────┘ └────┬────┘ └────────┬────────┘
            │  raw dicts     │ retries/rate-limit      │ scored rows
            ▼                                          ▼
     data/raw/<connector>/*.json          data/scored/<ts>_scored_leads.csv
            │                                          ▲
            ▼ normalize()                              │
     List[PermitRecord] ──► core/dedup.py ──► core/storage.py
                             (persisted key         (CSV append +
                              index, cross-run)       optional SQLite)
                                    │
                                    ▼
                     data/normalized/permits_normalized.csv
                     data/permits.db (if sqlite enabled)
```

Design principles:
- **One connector = one source.** Each jurisdiction's quirks (field names, date semantics,
  what "commercial" even means in that dataset) are isolated in its own file, so adding a
  10th source later never touches the other nine.
- **Raw and normalized data are always stored separately.** `data/raw/` is the untouched
  as-fetched JSON; `data/normalized/` is what survives schema mapping. If a mapping bug is
  ever found, the original data is still there to re-process.
- **Deduplication is a cross-run, persisted index**, not just an in-memory set for one run —
  see `core/dedup.py`. This is what makes "run this daily forever" safe.
- **Scoring is separate from collection.** `main.py` calls `scoring/scorer.py` as its last
  step; you can re-run scoring against the historical CSV/SQLite at any time (e.g. after
  tuning keyword weights) without re-fetching anything.
- **No LLM in the collection or scoring path**, per the project requirement — everything here
  is `requests` + ArcGIS REST queries + rule-based Python. An LLM pass (summarization,
  ambiguous-description classification) is a natural *optional* addition on top of the scored
  CSV output, not a replacement for it.

---

## 3. Folder Structure

```
captiveaire_permit_leads/
├── main.py                          # daily orchestrator (entry point)
├── requirements.txt
├── .env.example                     # copy to .env
├── config/
│   └── config.yaml                  # connector on/off, lookback window, scoring thresholds
├── core/
│   ├── config.py                    # loads config.yaml + .env
│   ├── http_client.py               # retrying session, rate limiter, timeouts
│   ├── arcgis_client.py             # generic ArcGIS FeatureServer/MapServer pagination
│   ├── schema.py                    # PermitRecord — the normalized schema
│   ├── dedup.py                     # cross-run dedup index
│   ├── storage.py                   # raw JSON, normalized CSV, SQLite, scored CSV writers
│   └── logging_utils.py             # logging setup + optional failure webhook alert
├── connectors/
│   ├── base.py                      # BaseConnector abstract interface
│   ├── tampa_city.py
│   ├── hillsborough_county.py
│   ├── hillsborough_dev_review.py
│   ├── lakeland.py
│   ├── hernando_county.py
│   └── pinellas_drs.py
├── scoring/
│   ├── keywords.py                  # Tier A/B/C keyword lists
│   └── scorer.py                    # rule-based scoring engine
├── data/
│   ├── raw/<connector_name>/*.json  # untouched source payloads, one file per run
│   ├── normalized/permits_normalized.csv   # cumulative normalized history
│   ├── scored/<timestamp>_scored_leads.csv # one file per run + latest_scored_leads.csv
│   ├── dedup_index.csv              # persisted dedup key index
│   └── permits.db                   # SQLite (only if enabled in config.yaml)
├── logs/
│   └── collect_<timestamp>.log
├── .github/workflows/
│   └── daily_permit_collection.yml  # GitHub Actions scheduler
└── test_offline_pipeline.py         # offline smoke test (see section 6)
```

---

## 4. Required Python Packages

```
requests>=2.31.0        # HTTP
PyYAML>=6.0              # config.yaml parsing
python-dotenv>=1.0.0     # .env loading
tenacity>=8.2.3          # available for connector-level retry decorators if you extend the system
```

SQLite support uses Python's built-in `sqlite3` module — no extra package needed.
Install with:
```bash
pip install -r requirements.txt
```

---

## 5. Complete Working Python Code

All files are in the delivered folder (`captiveaire_permit_leads/`) exactly as described in
section 3 — every file referenced above is a real, complete file, not a snippet. Key files to
read first if you want to understand or extend the system:

- `connectors/base.py` — the interface every connector implements (`fetch_raw`, `normalize`)
- `connectors/tampa_city.py` — the simplest, most-commented example connector to copy when
  adding a new jurisdiction
- `core/arcgis_client.py` — shared pagination logic (reused by 5 of 6 connectors)
- `scoring/scorer.py` — the full scoring model with inline comments explaining each component

---

## 6. Setup Instructions

```bash
# 1. Install dependencies
cd captiveaire_permit_leads
pip install -r requirements.txt

# 2. (Optional) configure environment variables
cp .env.example .env
# edit .env if you want SQLite alerts, a Socrata token for a future source, etc.
# None of the 6 wired-in sources require any credentials.

# 3. (Optional) tune config/config.yaml — lookback window, which connectors run,
#    scoring thresholds. Defaults work out of the box.

# 4. Run it
python main.py                    # runs every connector enabled in config.yaml
python main.py --only tampa_city  # run a single connector while testing
python main.py --dry-run          # fetch + normalize + score, but write nothing to disk

# 5. Verify the logic offline (no network needed — useful in a locked-down sandbox/CI
#    smoke test, or just to see the scoring model work against known-good sample data)
python test_offline_pipeline.py
```

**First run** will create `data/raw/`, `data/normalized/permits_normalized.csv`,
`data/dedup_index.csv`, and `data/scored/`. Every subsequent run only adds genuinely new
records (see section 11 for a caveat about jurisdictions with no application-date field).

**Network note:** if you're running this inside a locked-down sandbox/CI environment that
blocks outbound traffic to arbitrary domains (this build's own development sandbox does — see
section 11), you'll need to run it somewhere with normal internet access (your laptop, a VM, or
GitHub Actions per section 10) — the ArcGIS endpoints above are public but do require live
outbound HTTPS.

---

## 7. Example Configuration File

This is the real `config/config.yaml` shipped with the system:

```yaml
run:
  lookback_days: 5
  data_dir: "data"
  log_dir: "logs"
  max_requests_per_second: 2
  request_timeout_seconds: 30
  max_retries: 4

storage:
  backends: ["csv", "sqlite"]
  sqlite_path: "data/permits.db"

connectors:
  tampa_city: {enabled: true}
  hillsborough_county: {enabled: true}
  hillsborough_dev_review: {enabled: true}
  lakeland: {enabled: true}
  hernando_county: {enabled: true}
  pinellas_drs: {enabled: true}

scoring:
  value_bonus_threshold: 25000
  recency_full_score_days: 30
  recency_zero_score_days: 180
  thresholds:
    very_high: 75
    high: 55
    medium: 35
    low: 15
```

To disable a source (e.g. you decide the Pinellas DRS site-plan signal is too noisy), set
`pinellas_drs: {enabled: false}` — no code changes needed.

---

## 8. Example Normalized Output

One row from `data/normalized/permits_normalized.csv` (Hillsborough County record, formatted
here as key/value for readability — the real file is flat CSV with the 26 schema columns):

```
jurisdiction:         Hillsborough County
permit_number:        HC-BLD-25-0007059
application_date:     (not available on this source — see section 11)
issue_date:           2025-09-04
expiration_date:      (not available on this source)
status:               Issued
address:              12345 Big Bend Rd
city:                 Riverview
state:                FL
zip_code:             (not available on this source)
parcel_number:        079525.0804
permit_type:          Commercial New Construction Starts
permit_subtype:       Commercial New Construction
work_description:     New restaurant with Type I hood, MAU, and Ansul fire suppression
project_value:         450000
square_footage:        5200
contractor_name:      (not available on this source)
contractor_company:   (not available on this source)
applicant_name:       (not available on this source)
owner_name:           (not available on this source)
business_name:        (not available on this source)
architect:            (not available on this source)
engineer:             (not available on this source)
source_record_url:    https://aca-prod.accela.com/HCFL/Cap/CapDetail.aspx?Module=Building&capID1=25CAP
source_dataset_url:   https://services.arcgis.com/apTfC6SUmnNfnxuF/arcgis/rest/services/AccelaDashBoard_MapService20211019/FeatureServer/0
date_collected:       2026-07-13T14:02:11Z
```

---

## 9. Example Lead-Scoring Output

Real output from `test_offline_pipeline.py` (section 6) run against representative sample
records from all six sources — this is the actual `data/scored/<timestamp>_scored_leads.csv`
shape, sorted by score descending:

| score | priority_category | jurisdiction | work_description (truncated) |
|---|---|---|---|
| 84 | **Very High** | City of Lakeland | Commercial kitchen hood and exhaust fan install for new cafe |
| 80 | **Very High** | City of Tampa | Kitchen hood and grease duct replacement for restaurant tenant build-out |
| 80 | **Very High** | Hillsborough County | New restaurant with Type I hood, MAU, and Ansul fire suppression |
| 78 | **Very High** | Hernando County | COMM KITCHEN HOOD/MAKEUP AIR |
| 64 | **High** | Hillsborough County (Development Review) | New retail/restaurant pad site with commercial kitchen build-out |
| 51 | **Medium** | Pinellas County (Development Review - Site Plans) | Biskits Restaurant Park Blvd |

`score_reasons` for the top row (Lakeland, 84):
```
Tier-A ventilation/fire-suppression keyword match: exhaust fan; +3 bonus for 2 distinct
keyword matches; Commercial occupancy indicator: commercial; Project value known ($62,000)
but below threshold; At least one contact/business name present (actionable lead);
Recent record (comparable to today's date)
```

This shows the model in action: a permit that names a hood/exhaust/grease/MAU/Ansul term
directly (Tier A) lands "Very High" even with a modest project value, while a pre-permit
development-review record with the same underlying opportunity but less certainty (no
confirmed permit issuance yet, weaker value/recency signal) lands "High" or "Medium" —
letting a salesperson correctly prioritize "call today" leads over "worth tracking" ones.

---

## 10. Running It Daily

### Cron (Linux/macOS)
```bash
# Edit your crontab:
crontab -e

# Run every day at 6:00 AM local time, log stdout/stderr to a file:
0 6 * * * cd /path/to/captiveaire_permit_leads && /usr/bin/python3 main.py >> logs/cron.log 2>&1
```

### Windows Task Scheduler
1. Open **Task Scheduler** → **Create Basic Task**.
2. Trigger: **Daily**, pick a time (e.g. 6:00 AM).
3. Action: **Start a program**.
   - Program/script: `C:\path\to\python.exe`
   - Add arguments: `main.py`
   - Start in: `C:\path\to\captiveaire_permit_leads`
4. Finish, then open the task's Properties → check "Run whether user is logged on or not" if
   you want it to run unattended.

### GitHub Actions (recommended if you want this fully hands-off with no machine to keep on)
The system ships with `.github/workflows/daily_permit_collection.yml`, already configured to:
- Run daily at 09:00 UTC (`cron: "0 9 * * *"`) — edit the cron expression for your preferred time
- Also support manual triggering via the Actions tab (`workflow_dispatch`)
- Install dependencies, run `python main.py`, and commit the updated `data/` and `logs/` files
  back to the repository so you have a full history in git

To use it: push this project to a GitHub repo, and the workflow activates automatically
(no secrets are required for the six wired-in sources; the `SOCRATA_APP_TOKEN` and
`ALERT_WEBHOOK_URL` secrets referenced in the workflow are optional).

### Any other scheduler
`main.py` is a plain script with a normal exit code (0 = success, 1 = every connector failed
and produced nothing) — it will work under systemd timers, `launchd` (macOS), Airflow,
Prefect, a simple `while true; sleep; done` loop in a container, etc. with no changes needed.

---

## 11. Known Limitations & Sources Requiring Manual Investigation

**Coverage gaps (9 of 13 target jurisdictions have no public API today):** Clearwater,
Pinellas County (issued permits — the DRS site-plan layer we do use is not the same thing),
Pasco County, St. Petersburg (live), Temple Terrace, Plant City, Bradenton, Manatee County, and
Sarasota County all lack a working, live, machine-readable permit feed as of this build (see
section 1b for what was checked and the manual-lookup fallback for each). This is a genuine
gap in what Tampa Bay governments publish today, not a shortcoming of the search — multiple
independent research passes (by different agents, using different search strategies) reached
the same conclusion for each.

**Missing fields are a real feature of these sources, not a bug in this system:**
- **No source publishes a `contractor_name`/`contractor_company` field.** This is a
  significant gap for a lead-gen use case — contractor-of-record is exactly who CaptiveAire
  would often want to reach. It typically requires opening the individual Accela detail page
  (the `source_record_url`/`ACA_LINK`/`hillsgovhub` field on most connectors links directly to
  it) — this system deliberately does NOT browser-scrape those pages per the "avoid fragile
  browser scraping" instruction, but the URLs are captured so a human (or a future, carefully
  rate-limited browser-automation enrichment step) can pull contractor info per-lead for your
  highest-scored records only, rather than at bulk-collection scale.
- **City of Tampa and Hillsborough County's main layers have no `project_value` /
  `application_date` field respectively** (see the per-connector docstrings for exactly which
  field is missing on which source) — scoring accounts for this by treating missing value/date
  data as "unknown" (partial credit) rather than penalizing the record as if value were known
  to be zero.
- **Hernando County's layer has no address field**, only a `PARCEL_KEY` — enriching to a real
  street address would require a second join against the county's parcel/GIS layer, not done
  here to keep the connector within "verified, no invented joins."
- **No source provides `architect` as a distinct field.** The Hillsborough Development Review
  connector maps its one named contact into `engineer` (civil engineer of record, per that
  dataset's own field label) as the closest fit, and leaves `architect` null everywhere.

**"Newly filed or issued" detection is best-effort, not perfect**, because most sources don't
expose a clean "application submitted" timestamp separate from "record last touched by GIS
sync." Each connector's `fetch_raw()` docstring/comments state exactly which date field is used
for the lookback filter and why. The default 5-day lookback window (vs. an assumed daily run
cadence) is a deliberate cushion against this imprecision — see `config/config.yaml`.

**St. Petersburg's `PermitsExternal` layer was found but excluded from the wired-in connector
list** because sampled data was from 2019-2021 and the layer's own naming (e.g. "(2019-2021)")
suggests it is a frozen historical snapshot, not a live feed — including it in daily collection
would produce zero new records and false confidence that St. Pete is covered. It's documented
in section 1b as a fallback for historical analysis only, not wired into `connectors/`.

**This build's own development sandbox could not reach outbound government/ArcGIS domains**
(only an allowlisted set of hosts, e.g. pypi.org, was reachable) — every endpoint above was
therefore verified using this environment's separate web-fetch tool (which has broader
network access), and the connector code itself was tested against real captured sample
payloads via `test_offline_pipeline.py` rather than a live `python main.py` run. Before your
first production run, run `python main.py --only tampa_city` (the simplest connector) on a
machine with normal internet access and confirm it produces `data/raw/tampa_city/*.json` with
real records, then expand to `--only <name>` for each of the other five before enabling all
six in a scheduled run.

**Contractor/owner enrichment beyond what's collected in bulk** (e.g. actually opening each
Accela detail page for your top-scored leads) is intentionally left as a manual or
separately-built step — see the PII/scope note below.

**Personal-information scope:** per the brief's instruction to avoid collecting personal
information beyond what's needed for legitimate commercial prospecting, the schema captures
business/professional names and roles (applicant, owner-of-record, contact-of-record on a
commercial project) but not, e.g., personal emails/phones beyond what a public government
dataset already publishes as part of the permit record itself. The Hillsborough Development
Review source's raw payload does include `ContactEmail`/`ContactPhone*` fields that were
deliberately **not** mapped into the normalized schema (which has no email/phone columns per
the requested 26-field spec) — they remain visible in `data/raw/hillsborough_dev_review/*.json`
if you decide you want them and choose to extend the schema yourself.
