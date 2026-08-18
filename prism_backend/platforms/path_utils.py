"""
Path utils for platform layer.

Platform uploaders accept either:
- absolute paths (recommended)
- legacy filenames (e.g. "account_xxx.json") that live under syn_backend/cookiesFile
"""

from __future__ import annotations

from pathlib import Path
from pathlib import PureWindowsPath
from typing import Optional
import os
import re


_SYN_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _is_dev_repo(base_dir: Path) -> bool:
    env = (os.getenv("SYNAPSE_ENV") or os.getenv("NODE_ENV") or "").strip().lower()
    if env in ("dev", "development", "local"):
        return True
    try:
        return (base_dir.parent / ".git").exists()
    except Exception:
        return False


def _load_settings_dirs() -> tuple[Path, Path]:
    """
    Resolve cookie/video base dirs.
    Prefer configured settings; fall back to repo defaults for non-FastAPI contexts.
    """
    try:
        from fastapi_app.core.config import settings
        cookies_dir = Path(settings.COOKIE_FILES_DIR)
        videos_dir = Path(settings.VIDEO_FILES_DIR)
        return cookies_dir, videos_dir
    except Exception:
        env_dir = os.getenv("SYNAPSE_DATA_DIR")
        if env_dir:
            return Path(env_dir) / "cookiesFile", _SYN_BACKEND_DIR / "videoFile"
        if _is_dev_repo(_SYN_BACKEND_DIR):
            return _SYN_BACKEND_DIR / "cookiesFile", _SYN_BACKEND_DIR / "videoFile"
        appdata = os.getenv("APPDATA")
        localappdata = os.getenv("LOCALAPPDATA")
        candidates = []
        if appdata:
            candidates.append(Path(appdata) / "SynapseAutomation" / "data" / "cookiesFile")
        if localappdata and localappdata != appdata:
            candidates.append(Path(localappdata) / "SynapseAutomation" / "data" / "cookiesFile")
        for candidate in candidates:
            if candidate.exists():
                return candidate, _SYN_BACKEND_DIR / "videoFile"
        return _SYN_BACKEND_DIR / "cookiesFile", _SYN_BACKEND_DIR / "videoFile"


_COOKIES_DIR, _VIDEOS_DIR = _load_settings_dirs()

_WIN_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _is_windows_abs_path(value: str) -> bool:
    try:
        return bool(_WIN_ABS_RE.match(str(value)))
    except Exception:
        return False


def _maybe_map_windows_path_to_wsl(value: str) -> str:
    """
    Map "C:\\foo\\bar" -> "/mnt/c/foo/bar" when running on posix with /mnt/<drive>.
    Returns original value if mapping isn't applicable or target doesn't exist.
    """
    if not _is_windows_abs_path(value):
        return value
    if os.name != "posix":
        return value
    try:
        drive = value[0].lower()
        tail = str(value)[2:].replace("\\", "/").lstrip("/")
        candidate = Path("/mnt") / drive / tail
        if candidate.exists():
            return str(candidate)
    except Exception:
        return value
    return value


def _basename(value: str) -> str:
    """
    Cross-platform basename for both Posix and Windows-style paths.
    """
    try:
        if _is_windows_abs_path(value):
            return PureWindowsPath(str(value)).name
        return Path(str(value)).name
    except Exception:
        return str(value)


def _fallback_to_dir_by_name(value: str, base_dir: Path) -> str:
    """
    If `value` is an absolute path that no longer exists (e.g. repo moved from D:\\ to E:\\),
    fall back to `base_dir / basename`.
    """
    try:
        candidate = base_dir / _basename(value)
        if candidate.exists():
            return str(candidate)
    except Exception:
        pass
    return value


def _fallback_to_dir_by_segment(value: str, base_dir: Path, segment_name: str) -> str:
    """
    If `value` contains a known segment (e.g. "...\\syn_backend\\videoFile\\foo.mp4"),
    map everything after that segment into `base_dir`.
    """
    try:
        s = str(value).replace("\\", "/")
        marker = f"/{segment_name}/"
        if marker not in s:
            return value
        tail = s.split(marker, 1)[1].lstrip("/")
        candidate = (base_dir / Path(tail)).resolve()
        if candidate.exists() and str(candidate).startswith(str(base_dir.resolve())):
            return str(candidate)
    except Exception:
        return value
    return value


def resolve_cookie_file(value: str) -> str:
    if not value:
        return value
    value = _maybe_map_windows_path_to_wsl(str(value))
    p = Path(value)
    if p.is_absolute() or _is_windows_abs_path(value):
        if p.exists():
            return str(p)
        # Repo moved / path stale: fall back to current cookiesFile by basename or segment.
        value = _fallback_to_dir_by_segment(str(value), _COOKIES_DIR, "cookiesFile")
        value = _fallback_to_dir_by_name(value, _COOKIES_DIR)
        return str(value)
    # If already contains "cookiesFile/...", normalize to base dir.
    value = _fallback_to_dir_by_segment(str(value), _COOKIES_DIR, "cookiesFile")
    candidate = _COOKIES_DIR / value
    return str(candidate)


def resolve_video_file(value: str) -> str:
    if not value:
        return value
    value = _maybe_map_windows_path_to_wsl(str(value))
    p = Path(value)
    if p.is_absolute() or _is_windows_abs_path(value):
        if p.exists():
            return str(p)
        # Repo moved / path stale: fall back to current videoFile by segment then basename.
        value = _fallback_to_dir_by_segment(str(value), _VIDEOS_DIR, "videoFile")
        value = _fallback_to_dir_by_name(value, _VIDEOS_DIR)
        return str(value)
    # If already contains "videoFile/...", normalize to base dir.
    value = _fallback_to_dir_by_segment(str(value), _VIDEOS_DIR, "videoFile")
    candidate = _VIDEOS_DIR / value
    return str(candidate)


def is_existing_file(value: Optional[str]) -> bool:
    if not value:
        return False
    try:
        return Path(value).exists()
    except Exception:
        return False
