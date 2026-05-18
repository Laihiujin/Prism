"""Project-local config storage for the Hermes agent runtime."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, Optional

import toml
import yaml


_CONFIG_LOCK = Lock()
_RUNTIME_DISPLAY_DEFAULTS = {
    "skin": "mono",
    "language": "zh",
}
_RUNTIME_DASHBOARD_DEFAULTS = {
    "theme": "mono",
}


def _resolve_env_path(*keys: str) -> Optional[Path]:
    for key in keys:
        raw = (os.getenv(key) or "").strip()
        if raw:
            return Path(raw).expanduser().resolve()
    return None


def get_source_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def get_repo_root() -> Path:
    return _resolve_env_path("SYNAPSE_RESOURCES_PATH", "SYNAPSE_APP_ROOT") or get_source_repo_root()


def get_backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_synenv_root() -> Path:
    override = _resolve_env_path("SYNAPSE_HERMES_PYTHON")
    if override is not None and override.exists():
        parent = override.parent
        if parent.name.lower() in {"scripts", "bin"}:
            return parent.parent
        return parent

    candidates = [
        get_repo_root() / "synenv",
        get_source_repo_root() / "synenv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def get_workspace_root() -> Path:
    workspace_root = _resolve_env_path("SYNAPSE_HERMES_WORKSPACE")
    if workspace_root is not None:
        workspace_root.mkdir(parents=True, exist_ok=True)
        return workspace_root
    return get_source_repo_root()


def get_config_path() -> Path:
    config_root = _resolve_env_path("SYNAPSE_HERMES_CONFIG_ROOT")
    config_dir = config_root if config_root is not None else (get_backend_root() / "config")
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "hermes_agent.toml"


def get_hermes_source_path() -> Path:
    return get_repo_root() / "tools" / "hermes-agent"


def _normalize_path_key(raw: object) -> Optional[str]:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        resolved = str(Path(text).expanduser().resolve())
    except Exception:
        resolved = os.path.abspath(os.path.expanduser(text))
    return os.path.normcase(os.path.normpath(resolved))


def _is_same_or_child_path(candidate: str, root: str) -> bool:
    return candidate == root or candidate.startswith(root + os.sep)


def build_hermes_pythonpath(
    *preferred: object,
    base: Optional[str] = None,
    exclude: Optional[Iterable[object]] = None,
) -> str:
    entries: list[str] = []
    seen: set[str] = set()
    excluded: list[str] = []

    for raw in exclude or ():
        normalized = _normalize_path_key(raw)
        if normalized:
            excluded.append(normalized)

    def add(raw: object) -> None:
        normalized = _normalize_path_key(raw)
        if not normalized:
            return
        if any(_is_same_or_child_path(normalized, root) for root in excluded):
            return
        if normalized in seen:
            return
        seen.add(normalized)
        entries.append(normalized)

    for item in preferred:
        add(item)

    for raw_entry in str(base or "").split(os.pathsep):
        add(raw_entry)

    return os.pathsep.join(entries)


def get_hermes_webui_path() -> Path:
    return get_repo_root() / "tools" / "hermes-webui"


def get_hermes_dashboard_dist_path() -> Path:
    return get_hermes_source_path() / "hermes_cli" / "web_dist"


def get_hermes_home_path() -> Path:
    return _resolve_env_path("SYNAPSE_HERMES_HOME") or (get_source_repo_root() / "tools" / "hermes-home")


def get_hermes_runtime_config_path() -> Path:
    return get_hermes_home_path() / "config.yaml"


def get_hermes_runtime_env_path() -> Path:
    return get_hermes_home_path() / ".env"


def get_hermes_webui_state_path() -> Path:
    return _resolve_env_path("SYNAPSE_HERMES_WEBUI_STATE_DIR") or (get_hermes_home_path() / "webui")


def get_hermes_python_path() -> Path:
    synenv_root = get_synenv_root()
    candidates = [
        synenv_root / "Scripts" / "python.exe",
        synenv_root / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def get_hermes_runtime_stamp_path() -> Path:
    return get_synenv_root() / ".hermes-runtime-ready"


def get_hermes_wrapper_path() -> Path:
    packaged_path = get_repo_root() / "scripts" / "hermes" / "hermes.ps1"
    if packaged_path.exists():
        return packaged_path
    return get_source_repo_root() / "scripts" / "hermes" / "hermes.ps1"


def detect_git_bash_path() -> Optional[Path]:
    override = os.getenv("HERMES_GIT_BASH_PATH")
    if override:
        candidate = Path(override)
        if candidate.exists():
            return candidate

    candidates = [
        get_repo_root() / "tools" / "git" / "bin" / "bash.exe",
        get_repo_root() / "tools" / "git" / "usr" / "bin" / "bash.exe",
        get_source_repo_root() / "tools" / "git" / "bin" / "bash.exe",
        get_source_repo_root() / "tools" / "git" / "usr" / "bin" / "bash.exe",
        Path(os.getenv("ProgramFiles", "")) / "Git" / "bin" / "bash.exe",
        Path(os.getenv("ProgramFiles", "")) / "Git" / "usr" / "bin" / "bash.exe",
        Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Git" / "bin" / "bash.exe",
    ]

    for candidate in candidates:
        if str(candidate) and candidate.exists():
            return candidate
    return None


def get_gateway_platform_status() -> Dict[str, Any]:
    hermes_source_path = get_hermes_source_path()
    if not hermes_source_path.exists():
        return {
            "configured": False,
            "platforms": [],
            "reason": "Hermes runtime is not installed.",
        }

    hermes_source_str = str(hermes_source_path)
    python_path = get_hermes_python_path()

    if python_path.exists():
        env = os.environ.copy()
        env["PYTHONPATH"] = build_hermes_pythonpath(
            hermes_source_path,
            base=env.get("PYTHONPATH"),
            exclude=(get_backend_root(),),
        )
        try:
            result = subprocess.run(
                [
                    str(python_path),
                    "-c",
                    (
                        "import json, sys; "
                        "sys.path.insert(0, sys.argv[1]); "
                        "from gateway.config import Platform, load_gateway_config; "
                        "config = load_gateway_config(); "
                        "platforms = sorted("
                        "platform.value "
                        "for platform, platform_config in (config.platforms or {}).items() "
                        "if getattr(platform_config, 'enabled', False) and platform != Platform.LOCAL"
                        "); "
                        "print(json.dumps({'platforms': platforms}, ensure_ascii=False))"
                    ),
                    hermes_source_str,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=hermes_source_str,
                check=True,
            )
            payload = json.loads((result.stdout or "").strip() or "{}")
            platforms = payload.get("platforms", [])
            if not isinstance(platforms, list):
                raise ValueError("Invalid Hermes gateway platform payload")
        except Exception as exc:
            return {
                "configured": False,
                "platforms": [],
                "reason": f"Failed to inspect Hermes gateway configuration: {exc}",
            }

        if platforms:
            return {
                "configured": True,
                "platforms": platforms,
                "reason": "",
            }

        return {
            "configured": False,
            "platforms": [],
            "reason": "No messaging platforms are configured for Hermes gateway.",
        }

    original_sys_path = list(sys.path)
    try:
        backend_root = _normalize_path_key(get_backend_root())
        filtered_sys_path = [
            entry
            for entry in original_sys_path
            if not (
                (normalized := _normalize_path_key(entry))
                and backend_root
                and _is_same_or_child_path(normalized, backend_root)
            )
        ]
        sys.path[:] = [hermes_source_str, *filtered_sys_path]
        from gateway.config import Platform, load_gateway_config

        config = load_gateway_config()
        platforms = sorted(
            platform.value
            for platform, platform_config in (config.platforms or {}).items()
            if getattr(platform_config, "enabled", False) and platform != Platform.LOCAL
        )
    except Exception as exc:
        return {
            "configured": False,
            "platforms": [],
            "reason": f"Failed to inspect Hermes gateway configuration: {exc}",
        }
    finally:
        sys.path[:] = original_sys_path

    if platforms:
        return {
            "configured": True,
            "platforms": platforms,
            "reason": "",
        }

    return {
        "configured": False,
        "platforms": [],
        "reason": "No messaging platforms are configured for Hermes gateway.",
    }


def get_runtime_summary() -> Dict[str, Any]:
    source_path = get_hermes_source_path()
    webui_path = get_hermes_webui_path()
    dashboard_dist_path = get_hermes_dashboard_dist_path()
    home_path = get_hermes_home_path()
    webui_state_path = get_hermes_webui_state_path()
    python_path = get_hermes_python_path()
    runtime_stamp_path = get_hermes_runtime_stamp_path()
    wrapper_path = get_hermes_wrapper_path()
    git_bash_path = detect_git_bash_path()
    gateway_platform_status = get_gateway_platform_status()

    agent_installed = source_path.exists() and python_path.exists() and runtime_stamp_path.exists()
    webui_installed = (
        webui_path.exists()
        and (webui_path / "server.py").exists()
        and (webui_path / "static" / "index.html").exists()
    )
    official_dashboard_installed = (
        source_path.exists()
        and python_path.exists()
        and dashboard_dist_path.exists()
        and (dashboard_dist_path / "index.html").exists()
    )

    preferred_dashboard_backend: Optional[str]
    if official_dashboard_installed:
        preferred_dashboard_backend = "official"
    elif webui_installed:
        preferred_dashboard_backend = "webui"
    else:
        preferred_dashboard_backend = None

    return {
        "repo_root": str(get_repo_root()),
        "workspace_root": str(get_workspace_root()),
        "config_path": str(get_config_path()),
        "source_path": str(source_path),
        "webui_path": str(webui_path),
        "dashboard_dist_path": str(dashboard_dist_path),
        "home_path": str(home_path),
        "webui_state_path": str(webui_state_path),
        "python_path": str(python_path),
        "runtime_stamp_path": str(runtime_stamp_path),
        "wrapper_path": str(wrapper_path) if wrapper_path.exists() else None,
        "git_bash_path": str(git_bash_path) if git_bash_path else None,
        "agent_installed": agent_installed,
        "official_dashboard_installed": official_dashboard_installed,
        "webui_installed": webui_installed,
        "preferred_dashboard_backend": preferred_dashboard_backend,
        "gateway_platform_configured": bool(gateway_platform_status["configured"]),
        "gateway_platforms": gateway_platform_status["platforms"],
        "gateway_config_reason": gateway_platform_status["reason"],
        "is_installed": agent_installed,
        "gui_installed": agent_installed and bool(preferred_dashboard_backend),
    }


def _read_hermes_runtime_config() -> Dict[str, Any]:
    config_path = get_hermes_runtime_config_path()
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def _write_hermes_runtime_config(data: Dict[str, Any]) -> Path:
    config_path = get_hermes_runtime_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)
    return config_path


def _apply_runtime_ui_defaults(data: Dict[str, Any]) -> Dict[str, Any]:
    display = data.get("display")
    if not isinstance(display, dict):
        display = {}
    if str(display.get("skin") or "").strip().lower() in {"", "default"}:
        display["skin"] = _RUNTIME_DISPLAY_DEFAULTS["skin"]
    if str(display.get("language") or "").strip().lower() in {"", "en"}:
        display["language"] = _RUNTIME_DISPLAY_DEFAULTS["language"]
    data["display"] = display

    dashboard = data.get("dashboard")
    if not isinstance(dashboard, dict):
        dashboard = {}
    if str(dashboard.get("theme") or "").strip().lower() in {"", "default"}:
        dashboard["theme"] = _RUNTIME_DASHBOARD_DEFAULTS["theme"]
    data["dashboard"] = dashboard
    return data


def ensure_runtime_ui_defaults() -> Path:
    data = _read_hermes_runtime_config()
    return _write_hermes_runtime_config(_apply_runtime_ui_defaults(data))


def _snapshot_from_hermes_runtime_config() -> Dict[str, Any]:
    data = _read_hermes_runtime_config()
    model_cfg = data.get("model") or {}
    agent_cfg = data.get("agent") or {}

    if isinstance(model_cfg, str):
        model_name = model_cfg.strip()
        provider = ""
        base_url = ""
        api_key = ""
    elif isinstance(model_cfg, dict):
        model_name = str(model_cfg.get("default") or model_cfg.get("model") or "").strip()
        provider = str(model_cfg.get("provider") or "").strip()
        base_url = str(model_cfg.get("base_url") or "").strip()
        api_key = str(model_cfg.get("api_key") or "").strip()
    else:
        model_name = ""
        provider = ""
        base_url = ""
        api_key = ""

    max_turns = agent_cfg.get("max_turns") if isinstance(agent_cfg, dict) else None
    if max_turns in (None, ""):
        max_turns = 12

    if not any([model_name, provider, base_url, api_key]):
        return {}

    return {
        "llm": {
            "provider": provider or "custom",
            "model": model_name,
            "api_key": api_key,
            "base_url": base_url,
        },
        "runtime": {
            "max_turns": int(max_turns),
        },
    }


def sync_agent_config_to_runtime(config: Dict[str, Any]) -> Path:
    llm = config.get("llm") or {}
    runtime = config.get("runtime") or {}

    existing = _read_hermes_runtime_config()
    model_cfg = existing.get("model")
    if not isinstance(model_cfg, dict):
        model_cfg = {}
    agent_cfg = existing.get("agent")
    if not isinstance(agent_cfg, dict):
        agent_cfg = {}
    approvals_cfg = existing.get("approvals")
    if not isinstance(approvals_cfg, dict):
        approvals_cfg = {}

    provider = str(llm.get("provider") or "").strip().lower()
    base_url = str(llm.get("base_url") or "").strip()

    model_cfg["default"] = str(llm.get("model") or "").strip()
    if provider == "lmstudio":
        model_cfg["provider"] = "lmstudio"
    else:
        model_cfg["provider"] = "custom" if base_url else (provider or "custom")

    if base_url:
        model_cfg["base_url"] = base_url
    elif "base_url" in model_cfg:
        model_cfg.pop("base_url", None)

    api_key = str(llm.get("api_key") or "").strip()
    if api_key:
        model_cfg["api_key"] = api_key
    elif "api_key" in model_cfg:
        model_cfg.pop("api_key", None)

    agent_cfg["max_turns"] = int(runtime.get("max_turns") or 12)
    approvals_cfg["mode"] = "off"
    approvals_cfg["destructive_slash_confirm"] = False
    approvals_cfg["mcp_reload_confirm"] = False

    existing["model"] = model_cfg
    existing["agent"] = agent_cfg
    existing["approvals"] = approvals_cfg
    return _write_hermes_runtime_config(_apply_runtime_ui_defaults(existing))


def read_agent_config() -> Dict[str, Any]:
    runtime_snapshot = _snapshot_from_hermes_runtime_config()
    if runtime_snapshot.get("llm"):
        return runtime_snapshot

    config_path = get_config_path()
    if not config_path.exists():
        try:
            from ..api.v1.ai.router import get_ai_config

            legacy = get_ai_config("function_calling")
            if legacy:
                return {
                    "llm": {
                        "provider": legacy.get("provider") or "custom",
                        "model": legacy.get("model_name") or "",
                        "api_key": legacy.get("api_key") or "",
                        "base_url": legacy.get("base_url") or "",
                    },
                    "runtime": {
                        "max_turns": 12,
                    },
                }
        except Exception:
            pass
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        return toml.load(handle)


def write_agent_config(config: Dict[str, Any]) -> Path:
    config_path = get_config_path()
    with _CONFIG_LOCK:
        with config_path.open("w", encoding="utf-8") as handle:
            toml.dump(config, handle)
        sync_agent_config_to_runtime(config)
    return config_path


def delete_agent_config() -> bool:
    config_path = get_config_path()
    if not config_path.exists():
        return False
    config_path.unlink()
    return True
