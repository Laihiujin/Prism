from pathlib import Path
import glob
import os
import sys
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

def _is_drive_root(path: Path) -> bool:
    try:
        return len(path.parts) <= 1
    except Exception:
        return False


def _looks_like_app_root(path: Path) -> bool:
    if (path / "syn_backend").exists() or (path / "backend").exists():
        return True
    if (path / "synenv").exists() and (path / "browsers").exists():
        return True
    return False


def _search_app_root(start: Path) -> Path | None:
    for candidate in [start, *start.parents]:
        if _is_drive_root(candidate):
            continue
        name = candidate.name.lower()
        if name in {"syn_backend", "backend"}:
            return candidate.parent
        if _looks_like_app_root(candidate):
            return candidate
    return None


# Prefer explicit app root from Electron or packagers, fall back to repo root.
def _resolve_app_root() -> Path:
    env_root = os.getenv("SYNAPSE_APP_ROOT") or os.getenv("SYNAPSE_RESOURCES_PATH")
    if env_root:
        return Path(env_root).resolve()
    if getattr(sys, "frozen", False):
        frozen_root = _search_app_root(Path(sys.executable).resolve().parent)
        if frozen_root:
            return frozen_root
    repo_root = _search_app_root(BASE_DIR)
    if repo_root:
        return repo_root
    return BASE_DIR.parent

APP_ROOT = _resolve_app_root()

# 兼容两种启动方式：
# - 在 `syn_backend/` 目录启动：读取 `syn_backend/.env`
# - 在项目根目录启动：读取 `./.env`
_root_env = APP_ROOT / ".env"
if _root_env.exists():
    load_dotenv(_root_env, override=True)

XHS_SERVER = "http://127.0.0.1:11901"

def _normalize_env_path(name: str) -> None:
    raw = os.getenv(name)
    if not raw:
        return
    try:
        candidate = Path(raw)
        if not candidate.is_absolute():
            os.environ[name] = str((APP_ROOT / candidate).resolve())
    except Exception:
        return

_normalize_env_path("PLAYWRIGHT_BROWSERS_PATH")
_normalize_env_path("LOCAL_CHROME_PATH")
_normalize_env_path("LOCAL_CHROME_HEADLESS_SHELL_PATH")
_normalize_env_path("LOCAL_FIREFOX_PATH")

def _find_preferred_local_chrome() -> str | None:
    for pattern in (
        APP_ROOT / "browsers" / "chromium" / "hibbiki-*" / "Chrome-bin" / "chrome.exe",
        APP_ROOT / "browsers" / "chromium" / "chromium-*" / "chrome-win64" / "chrome.exe",
        APP_ROOT / "browsers" / "chromium" / "chromium-*" / "chrome-win" / "chrome.exe",
        APP_ROOT / "browsers" / "chrome-for-testing" / "chrome-*" / "chrome-win64" / "chrome.exe",
    ):
        matches = sorted(glob.glob(str(pattern)))
        if matches:
            return str(Path(matches[-1]).resolve())
    return None


def _is_legacy_bundled_chrome(path: str | Path) -> bool:
    normalized = str(path).replace("/", "\\").lower()
    return (
        "\\browsers\\chromium\\chromium-" in normalized
        or "\\browsers\\chrome-for-testing\\" in normalized
    )

# 从 .env 获取配置，如果不存在则使用默认值
_local_chrome_raw = (
    os.getenv("LOCAL_CHROME_PATH")
    or os.getenv("LOCAL_CHROME_PATH_WIN")
    or os.getenv("LOCAL_CHROME_PATH_MAC")
    or os.getenv("LOCAL_CHROME_PATH_LINUX")
)

# 将相对路径转换为绝对路径（相对于项目根目录）
if _local_chrome_raw:
    _chrome_path = Path(_local_chrome_raw)
    if not _chrome_path.is_absolute():
        # 相对路径：相对于应用根目录（APP_ROOT）

        LOCAL_CHROME_PATH = str((APP_ROOT / _local_chrome_raw).resolve())
    else:
        LOCAL_CHROME_PATH = str(_chrome_path.resolve())
    _preferred_chrome = _find_preferred_local_chrome()
    if _preferred_chrome and _is_legacy_bundled_chrome(LOCAL_CHROME_PATH):
        LOCAL_CHROME_PATH = _preferred_chrome
else:
    LOCAL_CHROME_PATH = _find_preferred_local_chrome()

# Chrome Headless Shell 路径 (用于 Playwright 模式)
_local_chrome_headless_shell_raw = os.getenv("LOCAL_CHROME_HEADLESS_SHELL_PATH")
if _local_chrome_headless_shell_raw:
    _chrome_headless_shell_path = Path(_local_chrome_headless_shell_raw)
    if not _chrome_headless_shell_path.is_absolute():
        LOCAL_CHROME_HEADLESS_SHELL_PATH = str((APP_ROOT / _local_chrome_headless_shell_raw).resolve())
    else:
        LOCAL_CHROME_HEADLESS_SHELL_PATH = str(_chrome_headless_shell_path.resolve())
else:
    LOCAL_CHROME_HEADLESS_SHELL_PATH = None
    for pattern in (
        APP_ROOT / "browsers" / "chromium_headless_shell-*" / "chrome-headless-shell-win64" / "chrome-headless-shell.exe",
    ):
        matches = sorted(glob.glob(str(pattern)))
        if matches:
            LOCAL_CHROME_HEADLESS_SHELL_PATH = str(Path(matches[-1]).resolve())
            break

def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = raw.strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default


# Playwright Headless Mode
# `PLAYWRIGHT_HEADLESS=true` => 无头；`false` => 显示浏览器窗口
PLAYWRIGHT_HEADLESS = _env_bool("PLAYWRIGHT_HEADLESS", True)
