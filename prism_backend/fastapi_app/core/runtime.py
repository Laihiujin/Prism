"""Single source of truth for Prism's local backend endpoint."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_BACKEND_HOST = "127.0.0.1"
DEFAULT_BACKEND_PORT = 7000
REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_FILE = REPO_ROOT / "runtime-data" / "runtime.json"


def _validated_port(value: object) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise ValueError("backend port must be between 1 and 65535")
    return port


def _runtime_state() -> dict:
    try:
        value = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def get_backend_url() -> str:
    explicit = os.getenv("PRISM_BACKEND_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    state = _runtime_state()
    host = os.getenv("PRISM_BACKEND_HOST") or state.get("backend_host") or DEFAULT_BACKEND_HOST
    port = _validated_port(os.getenv("PRISM_BACKEND_PORT") or state.get("backend_port") or DEFAULT_BACKEND_PORT)
    return f"http://{host}:{port}"


def get_backend_host() -> str:
    explicit = os.getenv("PRISM_BACKEND_HOST", "").strip()
    if explicit:
        return explicit
    url_host = urlsplit(os.getenv("PRISM_BACKEND_URL", "")).hostname
    return url_host or str(_runtime_state().get("backend_host") or DEFAULT_BACKEND_HOST)


def get_backend_port() -> int:
    explicit = os.getenv("PRISM_BACKEND_PORT", "").strip()
    if explicit:
        return _validated_port(explicit)
    url_port = urlsplit(os.getenv("PRISM_BACKEND_URL", "")).port
    return _validated_port(url_port or _runtime_state().get("backend_port") or DEFAULT_BACKEND_PORT)


def get_api_base_url() -> str:
    return f"{get_backend_url()}/api/v1"
