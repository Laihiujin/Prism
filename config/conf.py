from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent / "syn_backend"

_root_env = BASE_DIR.parent / ".env"
_local_env = BASE_DIR / ".env"
if _root_env.exists():
    load_dotenv(_root_env, override=True)
if _local_env.exists():
    load_dotenv(_local_env, override=False)

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

XHS_SERVER = "http://127.0.0.1:11901"

# 从 .env 读取 Chrome 路径配置
_local_chrome_raw = (
    os.getenv("LOCAL_CHROME_PATH")
    or os.getenv("LOCAL_CHROME_PATH_WIN")
    or os.getenv("LOCAL_CHROME_PATH_MAC")
    or os.getenv("LOCAL_CHROME_PATH_LINUX")
)

if _local_chrome_raw:
    _chrome_path = Path(_local_chrome_raw)
    if not _chrome_path.is_absolute():
        LOCAL_CHROME_PATH = str((BASE_DIR.parent / _local_chrome_raw).resolve())
    else:
        LOCAL_CHROME_PATH = str(_chrome_path.resolve())
else:
    LOCAL_CHROME_PATH = ""

# Chrome Headless Shell 路径 (用于 Playwright 模式的 social_media_copilot)
_local_chrome_headless_shell_raw = os.getenv("LOCAL_CHROME_HEADLESS_SHELL_PATH")
if _local_chrome_headless_shell_raw:
    _chrome_headless_shell_path = Path(_local_chrome_headless_shell_raw)
    if not _chrome_headless_shell_path.is_absolute():
        LOCAL_CHROME_HEADLESS_SHELL_PATH = str((BASE_DIR.parent / _local_chrome_headless_shell_raw).resolve())
    else:
        LOCAL_CHROME_HEADLESS_SHELL_PATH = str(_chrome_headless_shell_path.resolve())
else:
    LOCAL_CHROME_HEADLESS_SHELL_PATH = None

# Playwright Headless Mode - Set to False to show browser for debugging
PLAYWRIGHT_HEADLESS = _env_bool("PLAYWRIGHT_HEADLESS", True)  # true=无头, false=显示窗口
