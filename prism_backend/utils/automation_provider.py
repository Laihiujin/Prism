"""Prism browser automation runtime.

Patchright is the single production runtime.  Keeping the import behind this
module gives platform adapters one stable interface without tying public APIs
to a specific browser driver package.
"""

from patchright.async_api import (  # type: ignore
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    TimeoutError,
    async_playwright,
)
from patchright.sync_api import sync_playwright  # type: ignore

AUTOMATION_RUNTIME = "patchright"

# Compatibility for adapters that still use the protocol's historical name.
PLAYWRIGHT_RUNTIME = AUTOMATION_RUNTIME

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
]
