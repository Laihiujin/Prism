"""Static browser-provider catalogue used by the Tools browser manager.

The catalogue describes install sources; it never downloads a browser while
being imported. Release metadata is resolved only after an explicit install or
update action from Tools.
"""
from __future__ import annotations

import os
import json
import platform
import sys
from pathlib import Path
from typing import Any


EXCLUDED_INSTALL_SOURCES = {
    "chromium/chromium": "source_mirror_without_release_binaries",
}


PROVIDERS: tuple[dict[str, Any], ...] = (
    {
        "id": "local",
        "name": "Local browsers",
        "category": "local",
        "installable": False,
        "platforms": ["darwin", "win32", "linux"],
    },
    {
        "id": "ungoogled-chromium-macos",
        "name": "Ungoogled Chromium",
        "category": "chromium",
        "repository": "ungoogled-software/ungoogled-chromium-macos",
        "installable": True,
        "recommendedFor": ["darwin"],
        "userSelectable": True,
        "defaultDownload": False,
        "labels": ["推荐", "第三方", "已公证"],
        "trust": "notarized-third-party",
        "assets": {
            "darwin-arm64": r"_arm64-macos\.dmg$",
            "darwin-x64": r"_x86_64-macos\.dmg$",
        },
    },
    {
        "id": "hibbiki-chromium-win64",
        "name": "Hibbiki Chromium",
        "category": "chromium",
        "repository": "Hibbiki/chromium-win64",
        "installable": True,
        "recommendedFor": ["win32"],
        "userSelectable": True,
        "defaultDownload": False,
        "labels": ["推荐", "第三方"],
        "trust": "third-party",
        "assets": {"win32-x64": r"^chrome\.7z$"},
    },
    {
        "id": "fingerprint-chromium",
        "name": "Fingerprint Chromium",
        "category": "fingerprint",
        "repository": "adryfish/fingerprint-chromium",
        "installable": True,
        "experimental": True,
        "userSelectable": True,
        "defaultDownload": False,
        "labels": ["指纹浏览器", "实验性", "第三方"],
        "trust": "third-party",
        "capabilities": ["native-fingerprint", "proxy", "timezone", "locale"],
        "assets": {
            # The upstream macOS filename does not declare architecture. The
            # installer must inspect the mounted app before activation.
            "darwin-unknown": r"_macos\.dmg$",
            "win32-x64": r"_windows_x64\.zip$",
            "linux-x64": r"_x86_64_linux\.tar\.xz$",
        },
    },
    {
        "id": "winchrome",
        "name": "Ungoogled Chromium (WinChrome)",
        "category": "chromium",
        "repository": "macchrome/winchrome",
        "installable": True,
        "userSelectable": True,
        "defaultDownload": False,
        "labels": ["备用", "第三方"],
        "trust": "third-party",
        "assets": {"win32-x64": r"_Win64\.7z$"},
    },
    {
        "id": "helium-macos",
        "name": "Helium",
        "category": "chromium-browser",
        "repository": "imputnet/helium-macos",
        "installable": True,
        "userSelectable": True,
        "defaultDownload": False,
        "labels": ["完整浏览器", "第三方"],
        "trust": "third-party-product",
        "assets": {
            "darwin-arm64": r"_arm64-macos\.dmg$",
            "darwin-x64": r"_x86_64-macos\.dmg$",
        },
    },
    {
        "id": "helium-windows",
        "name": "Helium",
        "category": "chromium-browser",
        "repository": "imputnet/helium-windows",
        "installable": True,
        "userSelectable": True,
        "defaultDownload": False,
        "labels": ["完整浏览器", "第三方"],
        "trust": "third-party-product",
        "assets": {
            "win32-arm64": r"_arm64-windows\.zip$",
            "win32-x64": r"_x64-windows\.zip$",
        },
    },
    {
        "id": "persona",
        "name": "Persona Engines",
        "category": "persona",
        "installable": True,
        "userSelectable": True,
        "defaultDownload": False,
        "managedBy": "persona",
        "engines": ["camoufox", "cloak", "persona-chromium"],
        "platforms": ["darwin", "win32", "linux"],
    },
)


def runtime_data_root() -> Path:
    configured = os.getenv("PRISM_RUNTIME_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    settings = os.getenv("PRISM_RUNTIME_SETTINGS_PATH", "").strip()
    if settings:
        return Path(settings).expanduser().resolve().parent
    return Path(__file__).resolve().parents[2] / "runtime-data"


def browsers_root() -> Path:
    return runtime_data_root() / "components" / "browsers"


def provider_root(provider_id: str) -> Path:
    return browsers_root() / provider_id


def active_provider_executable(kind: str | None = None) -> Path | None:
    try:
        state = json.loads((browsers_root() / "active.json").read_text(encoding="utf-8"))
        if kind and str(state.get("kind") or "chromium") != kind:
            return None
        executable = Path(str(state.get("executablePath", ""))).resolve()
        return executable if executable.is_file() else None
    except (OSError, ValueError, TypeError):
        return None


def current_platform_asset_key() -> tuple[str, str]:
    os_key = "win32" if sys.platform == "win32" else ("darwin" if sys.platform == "darwin" else "linux")
    raw_arch = platform.machine().lower()
    arch = "arm64" if raw_arch in {"arm64", "aarch64"} else "x64"
    return os_key, f"{os_key}-{arch}"


def get_provider(provider_id: str) -> dict[str, Any] | None:
    return next((dict(item) for item in PROVIDERS if item["id"] == provider_id), None)


def describe_registry() -> dict[str, Any]:
    active = None
    try:
        active = json.loads((browsers_root() / "active.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        pass
    providers = []
    os_key, asset_key = current_platform_asset_key()
    for provider in PROVIDERS:
        item = dict(provider)
        versions_dir = provider_root(str(provider["id"])) / "versions"
        item["installedVersions"] = sorted(
            [entry.name for entry in versions_dir.iterdir() if entry.is_dir() and not entry.name.endswith(".staging")],
            reverse=True,
        ) if versions_dir.exists() else []
        item["installed"] = bool(item["installedVersions"])
        assets = item.get("assets", {})
        item["platformAssetKey"] = asset_key if asset_key in assets else (f"{os_key}-unknown" if f"{os_key}-unknown" in assets else None)
        item["compatible"] = bool(item["platformAssetKey"] or os_key in item.get("platforms", []))
        item["recommended"] = os_key in item.get("recommendedFor", [])
        item["active"] = bool(active and active.get("provider") == item["id"])
        providers.append(item)
    return {
        "storageRoot": str(browsers_root()),
        "providers": providers,
        "excludedInstallSources": dict(EXCLUDED_INSTALL_SOURCES),
        "active": active,
    }
