from __future__ import annotations

try:
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

    PLAYWRIGHT_RUNTIME = "patchright"
except Exception:  # pragma: no cover - fallback for dev envs without patchright
    from playwright.async_api import (
        Browser,
        BrowserContext,
        Locator,
        Page,
        Playwright,
        TimeoutError,
        async_playwright,
    )
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_RUNTIME = "playwright"

__all__ = [
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
