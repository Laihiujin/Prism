# -*- coding: utf-8 -*-
"""浏览器引擎「组件」管理 —— 跨平台下载 / 安装 / 校验 / 卸载。

设计目标（对应「浏览器由 Tools 管理」）：
- 组件安装目录：runtime-data/components/browsers/<provider>/。
- 源码仓库不保存浏览器二进制，也不兼容历史 browsers/ 安装位。
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
import json
import hashlib
import platform
import tempfile
import urllib.request
import zipfile
import re
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .browser_provider_registry import (
    browsers_root,
    current_platform_asset_key,
    describe_registry,
    get_provider,
    provider_root,
)

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
    "chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "chromium-*/chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    "chromium-*/chrome-mac/Chromium",
    "chromium-*/chrome-win64/chrome.exe",
    "chromium-*/chrome-win/chrome.exe",
    "chromium-*/chrome-linux/chrome",
    "chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell",
    "chromium_headless_shell-*/chrome-headless-shell-mac-x64/chrome-headless-shell",
    "chromium_headless_shell-*/chrome-headless-shell-win64/chrome-headless-shell.exe",
    "chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
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
    """浏览器引擎组件安装目录（由 Tools 管理，位于 runtime-data）。"""
    return browsers_root()


def patchright_root() -> Path:
    return provider_root("patchright") / "versions" / "current"


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
    return _resolve_binary(browsers_root or patchright_root(), _CHROMIUM_BINARY_PATTERNS)


def resolve_firefox_path(browsers_root: Optional[Path] = None) -> Optional[Path]:
    return _resolve_binary(browsers_root or patchright_root(), _FIREFOX_BINARY_PATTERNS)


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
        from utils.chrome_detector import list_detected_browsers
        local_browsers = [browser for browser in list_detected_browsers() if browser.get("source") == "system"]
    except Exception:
        local_browsers = []
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
        "patchrightBrowsersPath": str(patchright_root()),
        "providerRegistry": describe_registry(),
        "preferredRuntime": "patchright",
        "activeRuntime": "patchright" if patchright_info["installed"] else None,
        "runtimes": {"patchright": patchright_info},
        "browserBackendDefault": browser_backend_default,
        "browserBackends": browser_backends,
        "localBrowsers": local_browsers,
        "browserAvailable": bool(local_browsers) or any(
            item.get("installed") for item in components_status().values()
        ),
        "browsers": components_status(),
    }


def _run_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(patchright_root())
    env["PRISM_AUTOMATION_RUNTIME"] = "patchright"
    return env


def _ensure_patchright() -> Dict[str, Any]:
    """确保 patchright 已安装；未装则用 pip 安装。返回 (ok, 输出)。"""
    if _get_python_package_info("patchright")["installed"]:
        return True, "patchright already installed"
    patchright_root().mkdir(parents=True, exist_ok=True)
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

    统一用 patchright 下载浏览器 build 到 runtime-data 的 provider 版本目录。
    """
    target = (target or "").strip().lower()
    if get_provider(target) and target not in {"local", "persona"}:
        return _install_github_provider(target)
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

    patchright_root().mkdir(parents=True, exist_ok=True)
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


def _install_github_provider(provider_id: str) -> Dict[str, Any]:
    """Install a GitHub provider after an explicit Tools action only."""
    provider = get_provider(provider_id)
    if not provider or not provider.get("repository") or not provider.get("userSelectable"):
        return {"success": False, "error": "provider_not_downloadable", "browserRuntimeInfo": browser_runtime_info()}
    system = platform.system().lower()
    machine = platform.machine().lower()
    _, exact_asset_key = current_platform_asset_key()
    os_key = "darwin" if system == "darwin" else ("win32" if system == "windows" else "linux")
    assets = provider.get("assets", {})
    asset_key = exact_asset_key if exact_asset_key in assets else f"{os_key}-unknown"
    asset_pattern = assets.get(asset_key)
    if not asset_pattern:
        return {"success": False, "error": f"unsupported_platform:{system}-{machine}", "browserRuntimeInfo": browser_runtime_info()}
    req = urllib.request.Request(
        f"https://api.github.com/repos/{provider['repository']}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Prism-browser-manager"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        release = json.load(response)
    asset = next((a for a in release.get("assets", []) if re.search(asset_pattern, a.get("name", ""))), None)
    if not asset:
        raise RuntimeError(f"release_asset_missing:{asset_key}")
    version = str(release["tag_name"])
    destination = provider_root(provider_id) / "versions" / version
    if destination.exists():
        return {"success": True, "output": "already installed", "browserRuntimeInfo": browser_runtime_info()}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="prism-browser-") as temp:
        archive = Path(temp) / asset["name"]
        download = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "Prism-browser-manager"})
        digest_builder = hashlib.sha256()
        with urllib.request.urlopen(download, timeout=120) as source, archive.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                output.write(chunk)
                digest_builder.update(chunk)
        digest = digest_builder.hexdigest()
        staged = destination.with_name(destination.name + ".staging")
        if staged.exists():
            shutil.rmtree(staged)
        staged.mkdir(parents=True)
        lower_name = archive.name.lower()
        if lower_name.endswith(".zip"):
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.infolist():
                    target = (staged / member.filename).resolve()
                    if staged.resolve() not in target.parents and target != staged.resolve():
                        raise RuntimeError("unsafe_browser_archive")
                    unix_mode = member.external_attr >> 16
                    if (unix_mode & 0o170000) == 0o120000:
                        raise RuntimeError("unsafe_browser_archive_symlink")
                bundle.extractall(staged)
        elif lower_name.endswith((".tar.xz", ".tar.gz", ".tgz")):
            with tarfile.open(archive) as bundle:
                for member in bundle.getmembers():
                    target = (staged / member.name).resolve()
                    if staged.resolve() not in target.parents and target != staged.resolve():
                        raise RuntimeError("unsafe_browser_archive")
                    if member.issym() or member.islnk():
                        raise RuntimeError("unsafe_browser_archive_symlink")
                bundle.extractall(staged)
        elif lower_name.endswith(".7z"):
            seven_zip_candidates = [
                _repo_root().parent / "desktop-electron" / "node_modules" / "7zip-bin" / "win" / "x64" / "7za.exe",
                _repo_root().parent / "desktop-electron" / "node_modules" / "7zip-bin" / "win" / "arm64" / "7za.exe",
            ]
            seven_zip = next((str(path) for path in seven_zip_candidates if path.is_file()), None)
            seven_zip = seven_zip or shutil.which("7z") or shutil.which("7za") or shutil.which("7zr")
            if not seven_zip:
                raise RuntimeError("7zip_runtime_missing")
            subprocess.run([seven_zip, "x", str(archive), f"-o{staged}", "-y"], check=True, capture_output=True)
        elif lower_name.endswith(".dmg") and system == "darwin":
            mount = Path(temp) / "mount"
            mount.mkdir()
            subprocess.run(["hdiutil", "attach", str(archive), "-mountpoint", str(mount), "-nobrowse"], check=True, capture_output=True)
            try:
                apps = list(mount.glob("*.app"))
                if not apps:
                    raise RuntimeError("fingerprint_chromium_app_missing")
                shutil.copytree(apps[0], staged / apps[0].name)
            finally:
                subprocess.run(["hdiutil", "detach", str(mount)], check=False, capture_output=True)
        else:
            raise RuntimeError(f"unsupported_browser_archive:{archive.suffix}")
        executable_names = {"chromium", "chrome", "chrome.exe", "ungoogled-chromium", "helium", "helium.exe"}
        executable = next((p for p in staged.rglob("*") if p.is_file() and p.name.lower() in executable_names), None)
        if not executable:
            shutil.rmtree(staged)
            raise RuntimeError("fingerprint_chromium_executable_missing")
        if system == "darwin":
            architectures = subprocess.run(["lipo", "-archs", str(executable)], capture_output=True, text=True, check=True).stdout.split()
            required = "arm64" if machine in {"arm64", "aarch64"} else "x86_64"
            if required not in architectures:
                shutil.rmtree(staged)
                raise RuntimeError(f"browser_architecture_mismatch:{required}:{','.join(architectures)}")
        upstream_digest = str(asset.get("digest") or "")
        if upstream_digest.startswith("sha256:") and upstream_digest.removeprefix("sha256:") != digest:
            shutil.rmtree(staged)
            raise RuntimeError("browser_checksum_mismatch")
        manifest = {"provider": provider_id, "repository": provider["repository"], "version": version, "asset": asset["name"], "sha256": digest, "installedAt": datetime.now(timezone.utc).isoformat(), "executableRelativePath": str(executable.relative_to(staged))}
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        staged.rename(destination)
        current = provider_root(provider_id) / "current.json"
        current_tmp = current.with_suffix(".json.tmp")
        current_tmp.write_text(json.dumps({"version": version}, indent=2), encoding="utf-8")
        current_tmp.replace(current)
    return {"success": True, "output": f"installed {version}", "browserRuntimeInfo": browser_runtime_info()}


def apply_provider(provider_id: str) -> Dict[str, Any]:
    root = provider_root(provider_id)
    selected = None
    try:
        current = json.loads((root / "current.json").read_text(encoding="utf-8"))
        candidate = root / "versions" / str(current["version"])
        if candidate.is_dir() and (candidate / "manifest.json").exists():
            selected = candidate
    except (OSError, ValueError, TypeError, KeyError):
        pass
    if selected is None:
        versions = sorted((root / "versions").glob("*"), reverse=True) if (root / "versions").exists() else []
        selected = next((v for v in versions if v.is_dir() and (v / "manifest.json").exists()), None)
    if not selected:
        return {"success": False, "error": "provider_not_installed", "browserRuntimeInfo": browser_runtime_info()}
    manifest = json.loads((selected / "manifest.json").read_text(encoding="utf-8"))
    executable = selected / manifest["executableRelativePath"]
    state = {"provider": provider_id, "name": get_provider(provider_id).get("name", provider_id), "kind": "chromium", "version": manifest["version"], "executablePath": str(executable)}
    component_root().mkdir(parents=True, exist_ok=True)
    temp = component_root() / "active.json.tmp"
    temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temp.replace(component_root() / "active.json")
    return {"success": True, "active": state, "browserRuntimeInfo": browser_runtime_info()}


def apply_local_browser(executable_path: str) -> Dict[str, Any]:
    from utils.chrome_detector import list_detected_browsers

    requested = Path(executable_path).expanduser().resolve()
    detected = [item for item in list_detected_browsers() if item.get("source") == "system"]
    selected = next(
        (item for item in detected if Path(str(item.get("path", ""))).resolve() == requested),
        None,
    )
    if not selected or not requested.is_file():
        return {"success": False, "error": "local_browser_not_detected", "browserRuntimeInfo": browser_runtime_info()}
    state = {
        "provider": "local",
        "name": selected["name"],
        "kind": selected["kind"],
        "version": None,
        "executablePath": str(requested),
    }
    component_root().mkdir(parents=True, exist_ok=True)
    temp = component_root() / "active.json.tmp"
    temp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(component_root() / "active.json")
    return {"success": True, "active": state, "browserRuntimeInfo": browser_runtime_info()}


def uninstall_provider(provider_id: str) -> Dict[str, Any]:
    provider = get_provider(provider_id)
    if not provider or provider_id in {"local", "persona", "patchright"}:
        return {"success": False, "error": "provider_not_uninstallable", "browserRuntimeInfo": browser_runtime_info()}
    active_file = component_root() / "active.json"
    try:
        active = json.loads(active_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        active = {}
    was_active = active.get("provider") == provider_id
    if was_active and active_file.exists():
        # Existing browser processes keep their executable mapped; only new
        # sessions fall back to another detected browser after this point.
        active_file.unlink()
    root = provider_root(provider_id)
    removed = []
    if root.exists():
        shutil.rmtree(root)
        removed.append(str(root))
    return {"success": True, "removedPaths": removed, "deactivated": was_active, "browserRuntimeInfo": browser_runtime_info()}


def uninstall_component(target: str) -> Dict[str, Any]:
    """卸载 Patchright provider 当前版本目录中的浏览器组件。"""
    target = (target or "").strip().lower()
    root = patchright_root()
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
    """运行时/检测端需要感知的唯一浏览器组件根。"""
    return [component_root()]


if __name__ == "__main__":
    print("component_root:", component_root())
    print("status:", components_status())
