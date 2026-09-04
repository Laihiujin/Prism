"""Live browser-provider resolution shared by API and long-running workers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

SUPPORTED_BROWSER_BACKENDS = frozenset({"patchright", "persona"})


def normalize_browser_backend(value: object, fallback: str = "patchright") -> str:
    candidate = str(value or "").strip().lower()
    aliases = {"persona-studio": "persona", "persona_studio": "persona", "camofox": "persona"}
    candidate = aliases.get(candidate, candidate)
    return candidate if candidate in SUPPORTED_BROWSER_BACKENDS else fallback


def _read_runtime_settings() -> Mapping[str, Any]:
    raw_path = os.getenv("PRISM_RUNTIME_SETTINGS_PATH", "").strip()
    if not raw_path:
        return {}
    try:
        value = json.loads(Path(raw_path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def get_browser_runtime_snapshot() -> dict[str, Any]:
    """Return the live default plus its persisted desktop configuration generation."""
    settings = _read_runtime_settings()
    runtime_value = settings.get("browserBackendDefault")
    raw_generation = settings.get("browserBackendGeneration", 1)
    try:
        generation = max(1, int(raw_generation))
    except (TypeError, ValueError):
        generation = 1
    return {
        "backend": normalize_browser_backend(
            runtime_value or os.getenv("PRISM_BROWSER_BACKEND_DEFAULT", "patchright")
        ),
        "generation": generation,
    }


def get_default_browser_backend() -> str:
    """Resolve on every session creation so a desktop setting change is live."""
    return str(get_browser_runtime_snapshot()["backend"])


def resolve_browser_backend(account_binding: Mapping[str, Any] | None = None) -> str:
    """Account sticky binding wins; otherwise use the live global default."""
    bound = (account_binding or {}).get("browser_backend")
    return normalize_browser_backend(bound, get_default_browser_backend()) if bound else get_default_browser_backend()
