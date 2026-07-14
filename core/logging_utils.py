"""Logging setup shared by every connector and the main orchestrator."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from core.config import AppConfig


def setup_logging(cfg: AppConfig, run_name: str = "run") -> logging.Logger:
    """Configure root logging to write to both stdout and a per-run log file.

    Call once at the top of main.py. Every module should then just do
    `logger = logging.getLogger(__name__)` and log normally.
    """
    log_dir = cfg.log_path()
    log_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_file = log_dir / f"{run_name}_{timestamp}.log"

    root = logging.getLogger()
    root.setLevel(getattr(logging, cfg.log_level.upper(), logging.INFO))
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    root.addHandler(stream_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger("captiveaire_permits")
    logger.info("Logging to %s", log_file)
    return logger


def send_alert(cfg: AppConfig, subject: str, message: str) -> None:
    """Best-effort alert on failure. No-op unless ALERT_WEBHOOK_URL is set.

    Posts a simple JSON payload {"subject": ..., "message": ...} — compatible
    with generic webhook receivers (Slack incoming webhooks want {"text":...}
    so this also sends that key for convenience). Failures to send an alert
    are logged but never raised, so alerting can never crash a collection run.
    """
    logger = logging.getLogger(__name__)
    if not cfg.alert_webhook_url:
        return
    try:
        import requests

        requests.post(
            cfg.alert_webhook_url,
            json={"subject": subject, "message": message, "text": f"{subject}\n{message}"},
            timeout=10,
        )
    except Exception as exc:  # noqa: BLE001 - alerting must never break the run
        logger.warning("Failed to send alert webhook: %s", exc)
