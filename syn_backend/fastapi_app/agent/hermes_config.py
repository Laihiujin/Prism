"""Project-local config storage for the Hermes/OpenClaw agent stack."""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any, Dict

import toml


_CONFIG_LOCK = Lock()


def get_config_path() -> Path:
    config_dir = Path(__file__).resolve().parents[2] / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "hermes_agent.toml"


def read_agent_config() -> Dict[str, Any]:
    config_path = get_config_path()
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        return toml.load(handle)


def write_agent_config(config: Dict[str, Any]) -> Path:
    config_path = get_config_path()
    with _CONFIG_LOCK:
        with config_path.open("w", encoding="utf-8") as handle:
            toml.dump(config, handle)
    return config_path


def delete_agent_config() -> bool:
    config_path = get_config_path()
    if not config_path.exists():
        return False
    config_path.unlink()
    return True
