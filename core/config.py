"""Configuration loading: config.yaml + .env, with sane defaults.

Usage:
    from core.config import load_config
    cfg = load_config()
    cfg.run.lookback_days
    cfg.connectors["tampa_city"].enabled
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is in requirements.txt
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


@dataclass
class RunConfig:
    lookback_days: int = 5
    data_dir: str = "data"
    log_dir: str = "logs"
    max_requests_per_second: float = 2.0
    request_timeout_seconds: int = 30
    max_retries: int = 4


@dataclass
class StorageConfig:
    backends: List[str] = field(default_factory=lambda: ["csv"])
    sqlite_path: str = "data/permits.db"


@dataclass
class ConnectorConfig:
    enabled: bool = True


@dataclass
class ScoringConfig:
    value_bonus_threshold: float = 25000
    recency_full_score_days: int = 30
    recency_zero_score_days: int = 180
    thresholds: Dict[str, int] = field(
        default_factory=lambda: {
            "very_high": 75,
            "high": 55,
            "medium": 35,
            "low": 15,
        }
    )


@dataclass
class AppConfig:
    run: RunConfig
    storage: StorageConfig
    connectors: Dict[str, ConnectorConfig]
    scoring: ScoringConfig
    socrata_app_token: str = ""
    alert_webhook_url: str = ""
    log_level: str = "INFO"

    def data_path(self, *parts: str) -> Path:
        base = Path(os.environ.get("DATA_DIR") or self.run.data_dir)
        if not base.is_absolute():
            base = PROJECT_ROOT / base
        return base.joinpath(*parts)

    def log_path(self, *parts: str) -> Path:
        base = PROJECT_ROOT / self.run.log_dir
        return base.joinpath(*parts)


def load_config(path: str | Path | None = None) -> AppConfig:
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")

    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    raw: dict = {}
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    run_raw = raw.get("run", {})
    run = RunConfig(
        lookback_days=int(run_raw.get("lookback_days", 5)),
        data_dir=run_raw.get("data_dir", "data"),
        log_dir=run_raw.get("log_dir", "logs"),
        max_requests_per_second=float(run_raw.get("max_requests_per_second", 2.0)),
        request_timeout_seconds=int(run_raw.get("request_timeout_seconds", 30)),
        max_retries=int(run_raw.get("max_retries", 4)),
    )

    storage_raw = raw.get("storage", {})
    storage = StorageConfig(
        backends=storage_raw.get("backends", ["csv"]),
        sqlite_path=storage_raw.get("sqlite_path", "data/permits.db"),
    )

    connectors_raw = raw.get("connectors", {})
    connectors = {
        name: ConnectorConfig(enabled=bool(val.get("enabled", True)))
        for name, val in connectors_raw.items()
    }

    scoring_raw = raw.get("scoring", {})
    scoring = ScoringConfig(
        value_bonus_threshold=float(scoring_raw.get("value_bonus_threshold", 25000)),
        recency_full_score_days=int(scoring_raw.get("recency_full_score_days", 30)),
        recency_zero_score_days=int(scoring_raw.get("recency_zero_score_days", 180)),
        thresholds=scoring_raw.get(
            "thresholds",
            {"very_high": 75, "high": 55, "medium": 35, "low": 15},
        ),
    )

    return AppConfig(
        run=run,
        storage=storage,
        connectors=connectors,
        scoring=scoring,
        socrata_app_token=os.environ.get("SOCRATA_APP_TOKEN", ""),
        alert_webhook_url=os.environ.get("ALERT_WEBHOOK_URL", ""),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
