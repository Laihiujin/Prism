"""
Chrome/Chromium 可执行文件自动检测模块
支持 Mac / Windows / Linux / Docker 全平台自动适配
优先使用 Playwright 自带浏览器，确保版本兼容性
"""
import os
import glob
from pathlib import Path
from typing import Optional
from utils.runtime_env import load_runtime_env


def get_chrome_executable() -> str:
    """
    自动检测并返回 Chrome/Chromium 可执行文件路径
    
    优先级:
    1. Playwright 自带浏览器 (推荐，版本永远匹配)
    2. Mac 系统 Chrome
    3. Windows 系统 Chrome
    4. Linux 系统级 Chromium
    
    Returns:
        str: Chrome 可执行文件的绝对路径
        
    Raises:
        FileNotFoundError: 找不到任何可用的浏览器
    """
    env = load_runtime_env()
    
    # 1. 优先使用 Playwright 浏览器（最稳定，推荐方案）
    playwright_path = _find_playwright_chromium()
    if playwright_path:
        print(f"✓ 使用 Playwright Chromium: {playwright_path}")
        return playwright_path
    
    # 2. Mac 系统 Chrome
    if env["is_mac"]:
        mac_path = _find_mac_chrome()
        if mac_path:
            print(f"✓ 使用 Mac Chrome: {mac_path}")
            return mac_path
    
    # 3. Windows 系统 Chrome
    if env["is_windows"]:
        win_path = _find_windows_chrome()
        if win_path:
            print(f"✓ 使用 Windows Chrome: {win_path}")
            return win_path
    
    # 4. Linux 系统级 Chromium
    if env["is_linux"]:
        linux_path = _find_linux_chromium()
        if linux_path:
            print(f"✓ 使用 Linux Chromium: {linux_path}")
            return linux_path
    
    # 找不到任何浏览器
    raise FileNotFoundError(
        "找不到可用的 Chrome/Chromium 可执行文件！\n"
        "请执行以下命令安装 Playwright 浏览器:\n"
        "  playwright install chromium\n"
        "或者安装系统 Chrome 浏览器"
    )


def _find_playwright_chromium() -> Optional[str]:
    """
    查找 Playwright 自带的 Chromium
    
    路径模式: 
    - Linux/Mac: ~/.cache/ms-playwright/chromium-*/chrome-linux/chrome
    - Windows: %LOCALAPPDATA%/ms-playwright/chromium-*/chrome-win/chrome.exe
    """
    home = Path.home()
    
    # 0. Check PLAYWRIGHT_BROWSERS_PATH environment variable
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
        ]
        for pat in patterns:
            matches = glob.glob(pat)
            if matches:
                return sorted(matches)[-1]

    # Windows: 检查 LOCALAPPDATA
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
    linux_pattern = str(home / ".cache/ms-playwright/chromium-*/chrome-linux/chrome")
    linux_matches = glob.glob(linux_pattern)
    if linux_matches:
        # 返回最新版本（按字母排序，版本号越大越靠后）
        return sorted(linux_matches)[-1]
    
    # Mac
    mac_pattern = str(home / ".cache/ms-playwright/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium")
    mac_matches = glob.glob(mac_pattern)
    if mac_matches:
        return sorted(mac_matches)[-1]
    
    # Windows (fallback to home directory cache)
    patterns = [
        str(home / ".cache/ms-playwright/chromium-*/chrome-win/chrome.exe"),
        str(home / ".cache/ms-playwright/chromium-*/chrome-win64/chrome.exe"),
    ]
    for pat in patterns:
        matches = glob.glob(pat)
        if matches:
            return sorted(matches)[-1]
    
    return None


def _find_mac_chrome() -> Optional[str]:
    """查找 Mac 系统的 Chrome"""
    # 环境变量优先
    env_path = os.getenv("LOCAL_CHROME_PATH_MAC")
    if env_path and Path(env_path).exists():
        return env_path
    
    # 默认路径
    default_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    
    for path in default_paths:
        if Path(path).exists():
            return path
    
    return None


def _find_windows_chrome() -> Optional[str]:
    """查找 Windows 系统的 Chrome"""
    # 环境变量优先
    env_path = os.getenv("LOCAL_CHROME_PATH_WIN")
    if env_path and Path(env_path).exists():
        return env_path
    
    # 默认路径
    default_paths = [
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        os.path.expanduser("~/AppData/Local/Google/Chrome/Application/chrome.exe"),
    ]
    
    for path in default_paths:
        if Path(path).exists():
            return path
    
    return None


def _find_linux_chromium() -> Optional[str]:
    """查找 Linux 系统的 Chromium"""
    # 环境变量优先
    env_path = os.getenv("LOCAL_CHROME_PATH_LINUX")
    if env_path and Path(env_path).exists():
        return env_path
    
    # 系统级路径
    default_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/snap/bin/chromium",
    ]
    
    for path in default_paths:
        if Path(path).exists():
            return path
    
    return None


def check_browser_availability() -> dict:
    """
    检查浏览器可用性
    
    Returns:
        dict: 包含检查结果的字典
    """
    result = {
        "available": False,
        "path": None,
        "type": None,
        "error": None
    }
    
    try:
        path = get_chrome_executable()
        result["available"] = True
        result["path"] = path
        
        if "playwright" in path.lower():
            result["type"] = "Playwright Chromium"
        elif "chrome" in path.lower():
            result["type"] = "System Chrome"
        else:
            result["type"] = "Chromium"
            
    except FileNotFoundError as e:
        result["error"] = str(e)
    
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
