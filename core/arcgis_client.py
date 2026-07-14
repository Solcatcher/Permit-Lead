"""Generic ArcGIS REST (MapServer/FeatureServer layer) query helper.

Five of the six connectors in this system are ArcGIS Feature Layers, all
sharing the same query/pagination contract, so this one module implements
it once instead of duplicating pagination logic per connector.

Verified against (as of this build; see README section 1 for full detail):
  - https://arcgis.tampagov.net/arcgis/rest/services/Planning/ConstructionInspections/MapServer/0
  - https://services.arcgis.com/apTfC6SUmnNfnxuF/arcgis/rest/services/AccelaDashBoard_MapService20211019/FeatureServer/0
  - https://services.arcgis.com/apTfC6SUmnNfnxuF/arcgis/rest/services/Site-Subdivision_DevReview_View/FeatureServer/0
  - https://services1.arcgis.com/mcbQY5xNGGGM1vBX/arcgis/rest/services/IMS_Projects_Permits/FeatureServer/6
  - https://services2.arcgis.com/x5zvhhxfUuRDntRe/arcgis/rest/services/HernandoBuilders/FeatureServer/63
  - https://egis.pinellas.gov/gis/rest/services/DRS/SitePlans/MapServer/0
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from core.http_client import HttpClient

logger = logging.getLogger(__name__)


def epoch_ms_to_iso_sane(value: Optional[int], max_years_future: int = 1, min_year: int = 1980) -> Optional[str]:
    """Like epoch_ms_to_iso, but discards obviously-erroneous dates (some
    source systems have data-entry typos, e.g. a permit application date
    entered as 2029 instead of 2024 — confirmed live in Hernando County's
    feed). Returns None rather than a nonsense date so scoring/recency logic
    never sees it.
    """
    iso = epoch_ms_to_iso(value)
    if iso is None:
        return None
    try:
        year = int(iso[:4])
    except ValueError:
        return None
    current_year = datetime.now(timezone.utc).year
    if year < min_year or year > current_year + max_years_future:
        return None
    return iso


def epoch_ms_to_iso(value: Optional[int]) -> Optional[str]:
    """ArcGIS date fields are returned as Unix epoch milliseconds (UTC)."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%d"
        )
    except (ValueError, OSError, OverflowError):
        return None


def get_layer_metadata(client: HttpClient, layer_url: str) -> Dict[str, Any]:
    """Fetch a layer's ?f=json metadata (fields, maxRecordCount, etc)."""
    return client.get_json(layer_url, params={"f": "json"})


def query_layer(
    client: HttpClient,
    layer_url: str,
    where: str = "1=1",
    out_fields: str = "*",
    page_size: int = 1000,
    max_pages: int = 200,
    order_by: Optional[str] = None,
) -> Iterator[Dict[str, Any]]:
    """Yield every feature's `attributes` dict from an ArcGIS layer, handling
    resultOffset/resultRecordCount pagination automatically.

    Stops when a page returns fewer than page_size records, when the service
    stops setting exceededTransferLimit, or after max_pages as a safety cap
    against a misbehaving service causing an infinite loop.
    """
    query_url = layer_url.rstrip("/") + "/query"
    offset = 0
    pages_fetched = 0

    while pages_fetched < max_pages:
        params = {
            "where": where,
            "outFields": out_fields,
            "f": "json",
            "resultRecordCount": page_size,
            "resultOffset": offset,
            "returnGeometry": "false",
        }
        if order_by:
            params["orderByFields"] = order_by

        data = client.get_json(query_url, params=params)

        if "error" in data:
            logger.error(
                "ArcGIS error from %s: %s", query_url, data["error"]
            )
            raise RuntimeError(f"ArcGIS query error from {query_url}: {data['error']}")

        features = data.get("features", [])
        logger.debug(
            "Fetched %d features from %s (offset=%d)", len(features), query_url, offset
        )
        if not features:
            break

        for feature in features:
            attrs = feature.get("attributes", {})
            if attrs:
                yield attrs

        pages_fetched += 1
        exceeded = data.get("exceededTransferLimit", False)
        if len(features) < page_size and not exceeded:
            break
        offset += len(features)

    if pages_fetched >= max_pages:
        logger.warning(
            "Hit max_pages=%d safety cap querying %s — data may be truncated",
            max_pages,
            query_url,
        )


def build_date_where(field_name: str, since: datetime, extra: str = "1=1") -> str:
    """Build a WHERE clause filtering an ArcGIS date field to `since` or
    later. ArcGIS SQL wants timestamps as 'YYYY-MM-DD HH:MM:SS'.
    """
    since_str = since.strftime("%Y-%m-%d %H:%M:%S")
    clause = f"{field_name} >= TIMESTAMP '{since_str}'"
    if extra and extra != "1=1":
        return f"({extra}) AND ({clause})"
    return clause
