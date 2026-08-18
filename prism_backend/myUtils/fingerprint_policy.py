import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional


_DEFAULT_POLICY: Dict[str, Any] = {
    "apply_fingerprint": True,
    "apply_stealth": True,
    "use_persistent_profile": True,
    "persistent_profile_dir": "browser_profiles",
    "proxy": None,
    "webrtc": {"mode": "mask"},
    "audio": {"mode": "noise", "noise": 0.0001},
    "fonts": {"mode": "allowlist"},
    "plugins": {"mode": "spoof"},
    "media_devices": {"mode": "spoof"},
    "client_hints": {"mode": "spoof"},
    "tls_ja3": {
        "enabled": False,
        "note": "Not supported by Playwright; requires a custom TLS stack.",
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _load_policy_file() -> Dict[str, Any]:
    try:
        from config.conf import BASE_DIR

        path = Path(BASE_DIR) / "config" / "fingerprint_policy.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _env_bool(name: str, default: Optional[bool]) -> Optional[bool]:
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = raw.strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _apply_env_overrides(policy: Dict[str, Any]) -> Dict[str, Any]:
    apply_fingerprint = _env_bool("PLAYWRIGHT_APPLY_FINGERPRINT", None)
    apply_stealth = _env_bool("PLAYWRIGHT_APPLY_STEALTH", None)
    use_persistent = _env_bool("PLAYWRIGHT_USE_PERSISTENT_PROFILE", None)
    proxy_server = os.getenv("PLAYWRIGHT_PROXY_SERVER")
    proxy_username = os.getenv("PLAYWRIGHT_PROXY_USERNAME")
    proxy_password = os.getenv("PLAYWRIGHT_PROXY_PASSWORD")

    if apply_fingerprint is not None:
        policy["apply_fingerprint"] = apply_fingerprint
    if apply_stealth is not None:
        policy["apply_stealth"] = apply_stealth
    if use_persistent is not None:
        policy["use_persistent_profile"] = use_persistent

    if proxy_server:
        policy["proxy"] = {
            "server": proxy_server,
            "username": proxy_username or "",
            "password": proxy_password or "",
        }
    return policy


def get_fingerprint_policy(account_id: Optional[str], platform: Optional[str]) -> Dict[str, Any]:
    raw = _load_policy_file()
    policy = _deep_merge(_DEFAULT_POLICY, raw.get("defaults") or {})

    platform_key = (platform or "").strip().lower()
    if platform_key:
        policy = _deep_merge(policy, (raw.get("platforms") or {}).get(platform_key) or {})

    if account_id:
        policy = _deep_merge(policy, (raw.get("accounts") or {}).get(account_id) or {})

    policy = _apply_env_overrides(policy)
    data_root = os.getenv("SYNAPSE_DATA_DIR")
    if not data_root:
        try:
            from fastapi_app.core.config import settings
            data_root = settings.DATA_DIR
        except Exception:
            data_root = None
    if data_root:
        policy["persistent_profile_dir"] = str(Path(data_root) / "browser_profiles")

    return policy


def resolve_proxy(policy: Dict[str, Any]) -> Optional[Dict[str, str]]:
    proxy = policy.get("proxy") if isinstance(policy, dict) else None
    if not proxy or not isinstance(proxy, dict):
        return None
    server = (proxy.get("server") or "").strip()
    if not server:
        return None
    return {
        "server": server,
        "username": proxy.get("username") or "",
        "password": proxy.get("password") or "",
    }

