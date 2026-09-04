# -*- coding: utf-8 -*-
"""浏览器引擎「组件」管理 —— 跨平台下载 / 安装 / 校验 / 卸载。

设计目标（对应「chromium / firefox 放到 tools 下作为组件下载安装」）：
- 组件安装目录：prism_backend/tools/browsers/（本模块所在目录下的 browsers）。
- 独立于仓库根目录 browsers/（那是历史遗留安装位，仍兼容，但新装走这里）。
- 全平台（macOS / Windows / Linux）用一个 Python 实现，不再依赖
  Windows-only 的 .bat / .ps1（Hibbiki Chromium 等历史胶片）。
- 下载/安装统一用 patchright（cross-platform 下载浏览器 build）：
    python -m patchright install chromium|firefox   （PLAYWRIGHT_BROWSERS_PATH 指向本组件目录）
- 供 fastapi_app/system/router.py 的 /browser-runtime/* 端点与 settings 页面复用。
"""
from __future__ import annotations

import glob
import importlib.metadata
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_COMPONENT_PREFIXES = (
    "hibbiki-",
    "chromium-",
    "chromium_headless_shell-",
    "chrome-",
    "firefox-",
)

# patchright/playwright 下载到 PLAYWRIGHT_BROWSERS_PATH 下各平台的二进制相对路径
_CHROMIUM_BINARY_PATTERNS = [
    # patchright 下载布局
    "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    "chromium-*/chrome-mac/Chromium",
    "chromium-*/chrome-win64/chrome.exe",
    "chromium-*/chrome-win/chrome.exe",
    "chromium-*/chrome-linux/chrome",
    # 历史 Hibbiki / 内置布局（Win）
    "chromium/hibbiki-*/Chrome-bin/chrome.exe",
    "chromium/chromium-*/chrome-win64/chrome.exe",
    "chromium/chromium-*/chrome-win/chrome.exe",
    "chrome-for-testing/chrome-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    "chrome-for-testing/chrome-*/chrome-win64/chrome.exe",
    "chrome-for-testing/chrome-*/chrome-linux/chrome",
]

_FIREFOX_BINARY_PATTERNS = [
    "firefox-*/firefox/Nightly.app/Contents/MacOS/firefox",
    "firefox-*/firefox/Contents/MacOS/firefox",
    "firefox-*/firefox/firefox",
    "firefox-*/firefox/firefox.exe",
    "firefox/Contents/MacOS/firefox",
]


def _repo_root() -> Path:
    """`prism_backend/tools/browser_components.py` -> `prism_backend/`。"""
    return Path(__file__).resolve().parents[1]


def component_root() -> Path:
    """浏览器引擎组件安装目录：prism_backend/tools/browsers/。"""
    return Path(__file__).resolve().parent / "browsers"


def component_root_exists() -> bool:
    return component_root().exists()


def _resolve_binary(root: Path, patterns: List[str]) -> Optional[Path]:
    for pat in patterns:
        matches = sorted(glob.glob(str(root / pat)))
        for m in matches:
            if os.path.isfile(m):
                return Path(m).resolve()
    return None


def _extract_version(path: Optional[Path]) -> Optional[str]:
    """从可执行文件父目录名里带上版本（如 chromium-143.0.0.0 / firefox-1538）。"""
    if not path:
        return None
    for parent in path.parents:
        if any(parent.name.startswith(p) for p in _COMPONENT_PREFIXES):
            return parent.name
    return None


def resolve_chromium_path(browsers_root: Optional[Path] = None) -> Optional[Path]:
    return _resolve_binary(browsers_root or component_root(), _CHROMIUM_BINARY_PATTERNS)


def resolve_firefox_path(browsers_root: Optional[Path] = None) -> Optional[Path]:
    return _resolve_binary(browsers_root or component_root(), _FIREFOX_BINARY_PATTERNS)


def component_status(target: str) -> Dict[str, Any]:
    """单个浏览器组件的安装状态（installed/path/version/uninstallable）。"""
    target = (target or "").strip().lower()
    if target == "chromium":
        path = resolve_chromium_path()
    elif target == "firefox":
        path = resolve_firefox_path()
    else:
        raise ValueError(f"unsupported_browser_component:{target}")
    return {
        "installed": path is not None,
        "path": str(path) if path else None,
        "version": _extract_version(path),
        "uninstallable": True,
    }


def components_status() -> Dict[str, Any]:
    return {
        "chromium": component_status("chromium"),
        "firefox": component_status("firefox"),
    }


def _get_python_package_info(package_name: str) -> Dict[str, Any]:
    spec = importlib.util.find_spec(package_name)
    payload: Dict[str, Any] = {"installed": spec is not None, "version": None, "error": None}
    if spec is None:
        return payload
    try:
        payload["version"] = importlib.metadata.version(package_name)
    except Exception as exc:
        payload["error"] = str(exc)
    return payload


def browser_runtime_info() -> Dict[str, Any]:
    """设置页「浏览器管理」用到的运行时信息（含组件安装状态）。"""
    patchright_info = _get_python_package_info("patchright")
    try:
        from fastapi_app.services.browser_backend import BrowserBackendManager
        from fastapi_app.services.browser_runtime import get_browser_runtime_snapshot

        browser_backends = BrowserBackendManager.describe()
        browser_backend_default = get_browser_runtime_snapshot()
    except Exception as exc:
        browser_backends = {}
        browser_backend_default = {"backend": "patchright", "generation": 1, "error": str(exc)}
    return {
        "pythonPath": sys.executable,
        "browsersPath": str(component_root()),
        "preferredRuntime": "patchright",
        "activeRuntime": "patchright" if patchright_info["installed"] else None,
        "runtimes": {"patchright": patchright_info},
        "browserBackendDefault": browser_backend_default,
        "browserBackends": browser_backends,
        "browsers": components_status(),
    }


def _run_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(component_root())
    env["PRISM_AUTOMATION_RUNTIME"] = "patchright"
    return env


def _ensure_patchright() -> Dict[str, Any]:
    """确保 patchright 已安装；未装则用 pip 安装。返回 (ok, 输出)。"""
    if _get_python_package_info("patchright")["installed"]:
        return True, "patchright already installed"
    component_root().mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "--force-reinstall", "patchright==1.59.1"],
        cwd=str(_repo_root()),
        env=_run_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return res.returncode == 0, (res.stdout + res.stderr)


def install_component(target: str) -> Dict[str, Any]:
    """下载并安装浏览器组件（chromium/firefox）或自动化运行时（patchright）。

    统一用 patchright 下载浏览器 build 到 tools/browsers/，跨平台。
    """
    target = (target or "").strip().lower()
    if target not in {"chromium", "firefox", "patchright"}:
        return {
            "success": False,
            "output": "",
            "error": f"unsupported_install_target:{target}",
            "browserRuntimeInfo": browser_runtime_info(),
        }

    if target != "patchright":
        ok, note = _ensure_patchright()
        if not ok:
            return {
                "success": False,
                "output": note,
                "error": "patchright install failed",
                "browserRuntimeInfo": browser_runtime_info(),
            }

    component_root().mkdir(parents=True, exist_ok=True)
    if target == "patchright":
        cmd = [sys.executable, "-m", "pip", "install", "-U", "patchright"]
    else:
        cmd = [sys.executable, "-m", "patchright", "install", target]

    res = subprocess.run(
        cmd,
        cwd=str(_repo_root()),
        env=_run_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "success": res.returncode == 0,
        "output": res.stdout,
        "error": None if res.returncode == 0 else (res.stderr.strip() or res.stdout.strip()),
        "browserRuntimeInfo": browser_runtime_info(),
    }


def uninstall_component(target: str) -> Dict[str, Any]:
    """卸载浏览器组件（移除 tools/browsers/ 下对应目录）。"""
    target = (target or "").strip().lower()
    root = component_root()
    if target == "chromium":
        candidates: List[Path] = [
            root / "chromium",
            root / "chromium_headless_shell-*",
            root / "chromium-*",
            root / "chrome-for-testing",
        ]
    elif target == "firefox":
        candidates = [root / "firefox", root / "firefox-*"]
    else:
        raise ValueError(f"unsupported_uninstall_target:{target}")

    removed: List[str] = []
    for c in candidates:
        for m in sorted(glob.glob(str(c))):
            p = Path(m)
            if p.exists():
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=False)
                else:
                    p.unlink()
                removed.append(str(p))
    return {
        "success": True,
        "removedPaths": removed,
        "browserRuntimeInfo": browser_runtime_info(),
    }


def list_scan_roots() -> List[Path]:
    """运行时/检测端需要感知的浏览器安装根（先组件目录，再历史 browsers/）。"""
    roots = [component_root()]
    legacy = _repo_root().parent / "browsers"
    if legacy.exists():
        roots.append(legacy)
    return roots


if __name__ == "__main__":
    print("component_root:", component_root())
    print("status:", components_status())
