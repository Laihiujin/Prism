"""Stable automation-driver boundary for Prism browser providers.

Business modules import this module, never a third-party driver directly.
Patchright is currently provisioned; the registry makes availability and
capabilities explicit so another compatible driver can be supplied later.
"""

from __future__ import annotations

import importlib.util
from typing import Any, Dict

from patchright.async_api import (  # type: ignore
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    TimeoutError,
    async_playwright as _patchright_async,
)
from patchright.sync_api import sync_playwright  # type: ignore

AUTOMATION_RUNTIME = "patchright"

# Compatibility for adapters that still use the protocol's historical name.
PLAYWRIGHT_RUNTIME = AUTOMATION_RUNTIME

RUNTIME_MANIFESTS: Dict[str, Dict[str, Any]] = {
    "patchright": {
        "package": "patchright",
        "capabilities": ["chromium", "persistent_context", "cdp_attach"],
    },
    "playwright": {
        "package": "playwright",
        "capabilities": ["chromium", "firefox", "webkit", "persistent_context", "cdp_attach"],
    },
}


def get_automation_runtime_registry() -> Dict[str, Dict[str, Any]]:
    return {
        name: {**manifest, "installed": importlib.util.find_spec(manifest["package"]) is not None}
        for name, manifest in RUNTIME_MANIFESTS.items()
    }


def require_automation_capability(runtime: str, capability: str) -> None:
    registry = get_automation_runtime_registry()
    manifest = registry.get(runtime)
    if not manifest or not manifest["installed"]:
        raise RuntimeError(f"Automation runtime '{runtime}' is not provisioned")
    if capability not in manifest["capabilities"]:
        raise RuntimeError(f"Automation runtime '{runtime}' does not support '{capability}'")

__all__ = [
    "AUTOMATION_RUNTIME",
    "PLAYWRIGHT_RUNTIME",
    "Browser",
    "BrowserContext",
    "Locator",
    "Page",
    "Playwright",
    "TimeoutError",
    "async_playwright",
    "sync_playwright",
    "get_automation_runtime_registry",
    "require_automation_capability",
]


class _EngineRouter:
    """Keep Chromium on Patchright; Firefox uses its supported Playwright driver."""
    def __init__(self, chromium_runtime, firefox_runtime, owner):
        self._chromium_runtime = chromium_runtime
        self.firefox = firefox_runtime.firefox
        self.webkit = firefox_runtime.webkit
        self.stop = owner.stop

    def __getattr__(self, name):
        return getattr(self._chromium_runtime, name)


class _AsyncDrivers:
    def __init__(self):
        self._drivers = []

    async def start(self):
        from playwright.async_api import async_playwright as firefox_driver
        try:
            chromium = await _patchright_async().start()
            self._drivers.append(chromium)
            firefox = await firefox_driver().start()
            self._drivers.append(firefox)
            return _EngineRouter(chromium, firefox, self)
        except BaseException:
            await self.stop()
            raise

    async def stop(self):
        while self._drivers:
            await self._drivers.pop().stop()

    async def __aenter__(self):
        return await self.start()

    async def __aexit__(self, *args):
        await self.stop()


def async_playwright():
    return _AsyncDrivers()
