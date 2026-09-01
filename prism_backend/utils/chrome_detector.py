"""
浏览器可执行文件自动检测模块（主流浏览器全覆盖）
支持 Mac / Windows / Linux / Docker 全平台自动适配

优先适配用户电脑端已安装的浏览器（无需下载浏览器），
仅在找不到任何系统浏览器时才回退到 Playwright/Patchright 自带浏览器。

检测范围（按主流程度排序）：
  1. Google Chrome
  2. Microsoft Edge（Chromium 系）
  3. Mozilla Firefox（video engine 不同，用 firefox API 驱动）
  4. Brave
  5. Opera
  6. Vivaldi
  7. Arc（macOS）
  8. Chromium（开源版）
  9. Playwright/Patchright 自带浏览器（最后兜底）

使用 detect_browser() 获取结构化结果（name / kind / path）：
  kind = 'chromium' → 用 pw.chromium 驱动（Chrome/Edge/Brave/Opera/Vivaldi/Arc/Chromium）
  kind = 'firefox'  → 用 pw.firefox 驱动（Firefox）
"""
import os
import glob
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from utils.runtime_env import load_runtime_env

# 各浏览器可执行文件（相对于检测到的目录）
BROWSER_BINARIES = {
    "Google Chrome": {
        "kind": "chromium",
        "win": [
            r"C:/Program Files/Google/Chrome/Application/chrome.exe",
            r"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
            "~/AppData/Local/Google/Chrome/Application/chrome.exe",
        ],
        "mac": [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ],
        "linux": [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/opt/google/chrome/chrome",
        ],
    },
    "Microsoft Edge": {
        "kind": "chromium",
        "win": [
            r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
            r"C:/Program Files/Microsoft/Edge/Application/msedge.exe",
            "~/AppData/Local/Microsoft/Edge/Application/msedge.exe",
        ],
        "mac": [
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ],
        "linux": [
            "/usr/bin/microsoft-edge",
            "/usr/bin/microsoft-edge-stable",
        ],
    },
    "Mozilla Firefox": {
        "kind": "firefox",
        "win": [
            r"C:/Program Files/Mozilla Firefox/firefox.exe",
            r"C:/Program Files (x86)/Mozilla Firefox/firefox.exe",
            "~/AppData/Local/Mozilla Firefox/firefox.exe",
        ],
        "mac": [
            "/Applications/Firefox.app/Contents/MacOS/firefox",
        ],
        "linux": [
            "/usr/bin/firefox",
            "/usr/bin/firefox-esr",
            "/snap/bin/firefox",
        ],
    },
    "Brave": {
        "kind": "chromium",
        "win": [
            r"C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe",
            "~/AppData/Local/BraveSoftware/Brave-Browser/Application/brave.exe",
        ],
        "mac": [
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ],
        "linux": [
            "/usr/bin/brave-browser",
            "/opt/brave.com/brave/brave-browser",
        ],
    },
    "Opera": {
        "kind": "chromium",
        "win": [
            r"C:/Program Files/Opera/launcher.exe",
            "~/AppData/Local/Programs/Opera/launcher.exe",
            "~/AppData/Local/Opera/launcher.exe",
        ],
        "mac": [
            "/Applications/Opera.app/Contents/MacOS/Opera",
        ],
        "linux": [
            "/usr/bin/opera",
            "/usr/bin/opera-stable",
        ],
    },
    "Vivaldi": {
        "kind": "chromium",
        "win": [
            r"C:/Program Files/Vivaldi/Application/vivaldi.exe",
            "~/AppData/Local/Vivaldi/Application/vivaldi.exe",
        ],
        "mac": [
            "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
        ],
        "linux": [
            "/usr/bin/vivaldi",
            "/usr/bin/vivaldi-stable",
        ],
    },
    "Arc": {
        "kind": "chromium",
        "win": [],
        "mac": [
            "/Applications/Arc.app/Contents/MacOS/Arc",
        ],
        "linux": [],
    },
    "Chromium": {
        "kind": "chromium",
        "win": [],
        "mac": [
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ],
        "linux": [
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ],
    },
}

# 环境变量优先顺序（用户显式指定时最高优先）
_ENV_OVERRIDES = [
    ("LOCAL_CHROME_PATH", "Google Chrome"),
    ("LOCAL_FIREFOX_PATH", "Mozilla Firefox"),
    ("LOCAL_CHROME_PATH_MAC", "Google Chrome"),
    ("LOCAL_CHROME_PATH_WIN", "Google Chrome"),
    ("LOCAL_CHROME_PATH_LINUX", "Google Chrome"),
    ("LOCAL_EDGE_PATH", "Microsoft Edge"),
]


@dataclass(frozen=True)
class BrowserInfo:
    """检测结果。kind: 'chromium'（pw.chromium 驱动）或 'firefox'（pw.firefox 驱动）。"""
    name: str
    kind: str
    path: str


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(path))


def _env_override() -> Optional[BrowserInfo]:
    """用户通过环境变量显式指定的浏览器（最高优先）。"""
    for env_name, browser_name in _ENV_OVERRIDES:
        raw = os.getenv(env_name)
        if not raw:
            continue
        candidate = _expand(raw)
        if not candidate.is_absolute():
            # 相对路径按项目根目录解析
            candidate = Path(__file__).resolve().parents[1].parent / candidate
        if candidate.is_file():
            return BrowserInfo(name=browser_name, kind=BROWSER_BINARIES[browser_name]["kind"], path=str(candidate.resolve()))
    return None


def _find_browser_on_platform(browser_name: str, platform_key: str) -> Optional[str]:
    paths = BROWSER_BINARIES[browser_name].get(platform_key, [])
    for raw in paths:
        candidate = _expand(raw)
        if candidate.is_file():
            return str(candidate.resolve())
    return None


def detect_browser() -> Optional[BrowserInfo]:
    """
    按主流程度检测用户本机浏览器，返回 BrowserInfo（name/kind/path）。
    找不到任何系统浏览器时回退到 Playwright/Patchright 自带浏览器；
    仍然没有则返回 None（不抛异常）。
    """
    env_info = load_runtime_env()

    override = _env_override()
    if override is not None:
        return override

    if env_info["is_mac"]:
        platform_key = "mac"
    elif env_info["is_windows"]:
        platform_key = "win"
    else:
        platform_key = "linux"

    # 按 BROWSER_BINARIES 定义顺序（主流程度）逐个检测
    for browser_name in BROWSER_BINARIES:
        if not BROWSER_BINARIES[browser_name].get(platform_key):
            continue
        path = _find_browser_on_platform(browser_name, platform_key)
        if path:
            return BrowserInfo(name=browser_name, kind=BROWSER_BINARIES[browser_name]["kind"], path=path)

    # 最后兜底：Playwright/Patchright 自带浏览器（已存在于本机缓存时）
    playwright_path = _find_playwright_chromium()
    if playwright_path:
        return BrowserInfo(name="Playwright Chromium", kind="chromium", path=playwright_path)

    return None


def get_chrome_executable() -> str:
    """
    （兼容入口）自动检测并返回可用的浏览器可执行文件路径。
    保持历史行为：找不到时抛 FileNotFoundError。
    """
    info = detect_browser()
    if info is None:
        raise FileNotFoundError(
            "找不到可用的浏览器可执行文件！\n"
            "请安装 Google Chrome / Microsoft Edge / Firefox / Brave / Opera / Vivaldi 等主流浏览器，\n"
            "或设置 LOCAL_CHROME_PATH 指向已安装的浏览器。"
        )
    return info.path


def _find_playwright_chromium() -> Optional[str]:
    """
    查找 Playwright/Patchright 自带的 Chromium（仅作为最后兜底）。
    """
    home = Path.home()

    custom_path = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    if custom_path:
        repo_root = Path(__file__).resolve().parents[1].parent
        candidate = Path(custom_path)
        if not candidate.is_absolute():
            candidate = (repo_root / candidate).resolve()
        else:
            candidate = candidate.resolve()
        patterns = [
            str(candidate / "chromium-*/chrome-win/chrome.exe"),
            str(candidate / "chromium-*/chrome-win64/chrome.exe"),
            str(candidate / "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
            str(candidate / "chromium-*/chrome-linux/chrome"),
        ]
        for pat in patterns:
            matches = glob.glob(pat)
            if matches:
                return sorted(matches)[-1]

    # Windows: LOCALAPPDATA
    localappdata = os.getenv("LOCALAPPDATA")
    if localappdata:
        patterns = [
            str(Path(localappdata) / "ms-playwright/chromium-*/chrome-win/chrome.exe"),
            str(Path(localappdata) / "ms-playwright/chromium-*/chrome-win64/chrome.exe"),
        ]
        for pat in patterns:
            matches = glob.glob(pat)
            if matches:
                return sorted(matches)[-1]

    # Linux / Docker
    linux_matches = glob.glob(str(home / ".cache/ms-playwright/chromium-*/chrome-linux/chrome"))
    if linux_matches:
        return sorted(linux_matches)[-1]

    # Mac
    mac_matches = glob.glob(str(home / ".cache/ms-playwright/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"))
    if mac_matches:
        return sorted(mac_matches)[-1]

    # Windows (home cache fallback)
    for pat in [
        str(home / ".cache/ms-playwright/chromium-*/chrome-win/chrome.exe"),
        str(home / ".cache/ms-playwright/chromium-*/chrome-win64/chrome.exe"),
    ]:
        matches = glob.glob(pat)
        if matches:
            return sorted(matches)[-1]

    return None


# ---- 兼容旧函数（历史调用方仍可用）----

def _find_mac_chrome() -> Optional[str]:
    return _find_browser_on_platform("Google Chrome", "mac")


def _find_windows_chrome() -> Optional[str]:
    return _find_browser_on_platform("Google Chrome", "win")


def _find_linux_chromium() -> Optional[str]:
    return _find_browser_on_platform("Chromium", "linux")


def check_browser_availability() -> dict:
    """
    检查浏览器可用性（兼容入口）。
    """
    result = {
        "available": False,
        "path": None,
        "type": None,
        "error": None,
    }

    info = detect_browser()
    if info is not None:
        result["available"] = True
        result["path"] = info.path
        if info.kind == "firefox":
            result["type"] = f"{info.name} (Firefox)"
        elif "chromium" in info.path.lower():
            result["type"] = "Playwright Chromium"
        elif "chrome" in info.path.lower():
            result["type"] = "System Chrome"
        else:
            result["type"] = info.name
    else:
        result["error"] = (
            "未检测到本机浏览器（Chrome/Edge/Firefox/Brave/Opera/Vivaldi）。\n"
            "请安装任一主流浏览器，或设置 LOCAL_CHROME_PATH 指向已安装的浏览器。"
        )

    return result


if __name__ == "__main__":
    from utils.runtime_env import get_env_info

    print("=" * 60)
    print("浏览器可执行文件检测")
    print("=" * 60)
    print(f"运行环境: {get_env_info()}")
    print("-" * 60)

    result = check_browser_availability()

    if result["available"]:
        print(f"✓ 浏览器可用")
        print(f"  类型: {result['type']}")
        print(f"  路径: {result['path']}")
    else:
        print(f"✗ 浏览器不可用")
        print(f"  错误: {result['error']}")

    print("=" * 60)
