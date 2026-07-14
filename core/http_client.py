"""Shared HTTP client: retries, timeouts, basic rate limiting, and a
respectful User-Agent identifying this collector (good practice for public
government APIs, and required by some agencies' acceptable-use policies).
"""
from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

USER_AGENT = (
    "CaptiveAirePermitLeadBot/1.0 "
    "(+commercial-kitchen-ventilation-lead-research; contact: set-your-contact-email)"
)


class RateLimiter:
    """Very small token-bucket-ish limiter: sleeps enough to keep the
    average request rate at or below max_per_second. Good enough for a
    single-process daily batch job; not meant for high concurrency.
    """

    def __init__(self, max_per_second: float):
        self.min_interval = 1.0 / max_per_second if max_per_second > 0 else 0.0
        self._lock = Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            sleep_for = self.min_interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last_call = time.monotonic()


def build_session(max_retries: int = 4) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=max_retries,
        backoff_factor=1.5,  # 1.5s, 3s, 4.5s, ... between retries
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return session


class HttpClient:
    """Thin wrapper combining a retrying requests.Session with rate limiting
    and consistent timeout/error handling/logging for every connector.
    """

    def __init__(
        self,
        max_requests_per_second: float = 2.0,
        timeout_seconds: int = 30,
        max_retries: int = 4,
    ):
        self.session = build_session(max_retries=max_retries)
        self.limiter = RateLimiter(max_requests_per_second)
        self.timeout = timeout_seconds

    def get_json(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self.limiter.wait()
        logger.debug("GET %s params=%s", url, params)
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error("Timeout requesting %s", url)
            raise
        except requests.exceptions.HTTPError as exc:
            logger.error("HTTP error %s requesting %s", exc, url)
            raise
        except requests.exceptions.RequestException as exc:
            logger.error("Request failed for %s: %s", url, exc)
            raise

        try:
            return resp.json()
        except ValueError as exc:
            logger.error("Non-JSON response from %s: %s", url, resp.text[:300])
            raise ValueError(f"Non-JSON response from {url}") from exc
