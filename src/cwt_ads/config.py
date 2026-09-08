"""Project paths, .env loading and YAML config access."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
FIXTURE_DIR = DATA_DIR / "fixtures"
UNIQUE_DIR = DATA_DIR / "unique"
OUTPUT_DIR = ROOT / "output"
HERMES_DIR = ROOT / "hermes"


def load_env() -> None:
    """Load .env once, without clobbering variables already in the environment."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # dotenv is convenience, not a hard requirement
        return
    load_dotenv(ROOT / ".env", override=False)


def env(name: str, default: str | None = None) -> str | None:
    load_env()
    value = os.environ.get(name, default)
    return value.strip() if isinstance(value, str) else value


def env_flag(name: str, default: bool = False) -> bool:
    raw = env(name)
    if raw is None or raw == "":
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=None)
def _yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def brand() -> dict[str, Any]:
    return _yaml(CONFIG_DIR / "brand.yaml")


def pipeline() -> dict[str, Any]:
    return _yaml(CONFIG_DIR / "pipeline.yaml")


def run_dir(run_id: str) -> Path:
    """Every pipeline run gets its own folder; `output/latest` points at it."""
    path = OUTPUT_DIR / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def verified_claim(claim_id: str) -> dict[str, Any] | None:
    for claim in brand()["product"]["verified_claims"]:
        if claim["id"] == claim_id:
            return claim
    return None
