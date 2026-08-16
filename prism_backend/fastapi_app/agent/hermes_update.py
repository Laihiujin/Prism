"""Hermes Agent upstream update management.

Update preferences and state live under HERMES_HOME.  That directory is deliberately
outside ``tools/hermes-agent`` and is never passed to git, so model, gateway, MCP and
WebUI state survive source refreshes.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .hermes_config import get_hermes_home_path, get_hermes_source_path, get_repo_root


logger = logging.getLogger(__name__)


DEFAULT_SETTINGS: Dict[str, Any] = {
    "enabled": True,
    "interval_hours": 24,
    "branch": "main",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _settings_path() -> Path:
    return get_hermes_home_path() / "update-settings.json"


def _state_path() -> Path:
    return get_hermes_home_path() / "update-state.json"


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def get_update_settings() -> Dict[str, Any]:
    stored = _read_json(_settings_path())
    settings = {**DEFAULT_SETTINGS, **stored}
    settings["enabled"] = bool(settings["enabled"])
    settings["interval_hours"] = max(1, min(168, int(settings["interval_hours"])))
    settings["branch"] = str(settings["branch"] or "main").strip() or "main"
    return settings


def save_update_settings(*, enabled: bool, interval_hours: int, branch: str) -> Dict[str, Any]:
    normalized_branch = str(branch or "main").strip() or "main"
    if normalized_branch.startswith("-") or ".." in normalized_branch:
        raise ValueError("Invalid Hermes upstream branch")
    settings = {
        "enabled": bool(enabled),
        "interval_hours": max(1, min(168, int(interval_hours))),
        "branch": normalized_branch,
    }
    _write_json(_settings_path(), settings)
    return settings


def _git(*args: str, check: bool = True) -> str:
    source = get_hermes_source_path()
    result = subprocess.run(
        ["git", "-C", str(source), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "git failed").strip())
    return (result.stdout or "").strip()


def _revision(ref: str) -> Optional[str]:
    value = _git("rev-parse", ref, check=False).strip()
    return value if len(value) == 40 else None


def check_for_updates() -> Dict[str, Any]:
    settings = get_update_settings()
    state = _read_json(_state_path())
    source = get_hermes_source_path()
    if not (source / ".git").exists():
        result = {"installed": False, "update_available": False, "error": "Hermes Agent 尚未安装。"}
    else:
        try:
            branch = settings["branch"]
            _git("fetch", "--depth", "1", "origin", branch)
            local_revision = _revision("HEAD")
            remote_revision = _revision("FETCH_HEAD")
            result = {
                "installed": True,
                "update_available": bool(local_revision and remote_revision and local_revision != remote_revision),
                "local_revision": local_revision,
                "remote_revision": remote_revision,
                "error": None,
            }
        except Exception as exc:
            result = {"installed": True, "update_available": False, "error": str(exc)}
    state.update(result)
    state["last_checked_at"] = _now()
    _write_json(_state_path(), state)
    return get_update_status()


def _powershell() -> Optional[str]:
    return shutil.which("pwsh") or shutil.which("powershell") or shutil.which("powershell.exe")


def apply_update() -> Dict[str, Any]:
    """Run the existing full installer so dependencies and both Web UIs stay aligned."""
    settings = get_update_settings()
    state = _read_json(_state_path())
    shell = _powershell()
    script = get_repo_root() / "scripts" / "hermes" / "setup-local-hermes.ps1"
    if not shell or not script.exists():
        raise RuntimeError("找不到 PowerShell 或 Hermes 安装脚本，无法执行完整更新。")

    state.update({"updating": True, "last_error": None})
    _write_json(_state_path(), state)
    try:
        result = subprocess.run(
            [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
             "-Branch", settings["branch"], "-Force"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "Hermes 更新失败").strip()[-4000:])
        state.update({
            "updating": False,
            "update_available": False,
            "local_revision": _revision("HEAD"),
            "remote_revision": _revision("HEAD"),
            "last_updated_at": _now(),
            "last_error": None,
        })
    except Exception as exc:
        state.update({"updating": False, "last_error": str(exc)})
        _write_json(_state_path(), state)
        raise
    _write_json(_state_path(), state)
    return get_update_status()


def get_update_status() -> Dict[str, Any]:
    settings = get_update_settings()
    state = _read_json(_state_path())
    source = get_hermes_source_path()
    return {
        "settings": settings,
        "installed": (source / ".git").exists(),
        "local_revision": state.get("local_revision") or (_revision("HEAD") if (source / ".git").exists() else None),
        "remote_revision": state.get("remote_revision"),
        "update_available": bool(state.get("update_available")),
        "updating": bool(state.get("updating")),
        "last_checked_at": state.get("last_checked_at"),
        "last_updated_at": state.get("last_updated_at"),
        "last_error": state.get("last_error") or state.get("error"),
        "preserved_home_path": str(get_hermes_home_path()),
    }


class HermesUpdateScheduler:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        while True:
            settings = get_update_settings()
            if settings["enabled"]:
                status = get_update_status()
                last = status.get("last_checked_at")
                due = True
                if last:
                    try:
                        due = datetime.now(timezone.utc) >= datetime.fromisoformat(last) + timedelta(hours=settings["interval_hours"])
                    except ValueError:
                        pass
                if due:
                    try:
                        checked = await asyncio.to_thread(check_for_updates)
                        if checked["update_available"]:
                            # Updating in-use Python/UI files is unsafe on Windows.
                            from .hermes_agent import reset_hermes_agent, stop_hermes_dashboard

                            await stop_hermes_dashboard()
                            await reset_hermes_agent()
                            await asyncio.to_thread(apply_update)
                    except Exception as exc:
                        logger.warning("Scheduled Hermes update failed: %s", exc)
            await asyncio.sleep(900)


_scheduler = HermesUpdateScheduler()


async def start_hermes_update_scheduler() -> None:
    await _scheduler.start()


async def stop_hermes_update_scheduler() -> None:
    await _scheduler.stop()
