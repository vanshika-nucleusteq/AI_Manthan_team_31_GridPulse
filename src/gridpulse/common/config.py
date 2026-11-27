"""Load YAML settings from the repo config/ directory (override with GRIDPULSE_CONFIG_DIR)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def config_dir() -> Path:
    env = os.environ.get("GRIDPULSE_CONFIG_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "config"


def load_yaml(name: str) -> dict[str, Any]:
    path = config_dir() / f"{name}.yaml"
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data
