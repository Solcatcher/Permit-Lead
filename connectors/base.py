"""Base connector interface. Every jurisdiction connector implements
fetch_raw() and normalize(); main.py drives them identically regardless of
what's underneath (ArcGIS today; nothing stops a future connector from
being CKAN or Socrata instead — it just needs to return raw dicts + a
normalize() that produces PermitRecord objects).
"""
from __future__ import annotations

import abc
import logging
from datetime import datetime, timedelta, timezone
from typing import List

from core.config import AppConfig
from core.http_client import HttpClient
from core.schema import PermitRecord

logger = logging.getLogger(__name__)


class BaseConnector(abc.ABC):
    #: Short machine name, must match the key used in config.yaml's
    #: `connectors:` section and in connectors/__init__.py's ALL_CONNECTORS.
    name: str = "base"
    #: Human-readable jurisdiction label stored in PermitRecord.jurisdiction
    jurisdiction: str = "Unknown"
    #: Human-facing URL for the source (documentation / citation purposes)
    source_dataset_url: str = ""
    #: True if this connector returns actual issued/filed permits; False if
    #: it's a secondary/pre-permit signal (e.g. development-review projects,
    #: site plans) that should be flagged as such in scoring/reporting.
    is_permit_of_record: bool = True

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.client = HttpClient(
            max_requests_per_second=cfg.run.max_requests_per_second,
            timeout_seconds=cfg.run.request_timeout_seconds,
            max_retries=cfg.run.max_retries,
        )

    def since_datetime(self) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=self.cfg.run.lookback_days)

    @abc.abstractmethod
    def fetch_raw(self) -> List[dict]:
        """Query the source and return a list of raw attribute dicts,
        limited to the configured lookback window. Must not raise on an
        individual bad record — log and skip it instead; the whole run
        should only fail on a genuine connectivity/API problem.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def normalize(self, raw_records: List[dict]) -> List[PermitRecord]:
        """Map raw attribute dicts to the shared PermitRecord schema."""
        raise NotImplementedError

    def run(self) -> tuple[List[dict], List[PermitRecord]]:
        logger.info("[%s] starting collection (lookback=%d days)", self.name, self.cfg.run.lookback_days)
        raw = self.fetch_raw()
        logger.info("[%s] fetched %d raw records", self.name, len(raw))
        normalized = self.normalize(raw)
        logger.info("[%s] normalized %d records", self.name, len(normalized))
        return raw, normalized


def clean_str(value) -> str | None:
    """Normalize ArcGIS string quirks: strip whitespace, treat empty/'None'
    strings as null so scoring/CSV output doesn't have to special-case them.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("none", "null", "n/a"):
        return None
    return s


def clean_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
