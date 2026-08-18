from __future__ import annotations

import os


def _load_patchright() -> tuple[str, object, object, object, object, object, object, object, object]:
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

    return (
        "patchright",
        Browser,
        BrowserContext,
        Locator,
        Page,
        Playwright,
        TimeoutError,
        async_playwright,
        sync_playwright,
    )


def _load_playwright() -> tuple[str, object, object, object, object, object, object, object, object]:
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

    return (
        "playwright",
        Browser,
        BrowserContext,
        Locator,
        Page,
        Playwright,
        TimeoutError,
        async_playwright,
        sync_playwright,
    )


_preferred_runtime = os.getenv("SYNAPSE_PLAYWRIGHT_RUNTIME", "").strip().lower()

try:
    if _preferred_runtime == "playwright":
        (
            PLAYWRIGHT_RUNTIME,
            Browser,
            BrowserContext,
            Locator,
            Page,
            Playwright,
            TimeoutError,
            async_playwright,
            sync_playwright,
        ) = _load_playwright()
    elif _preferred_runtime == "patchright":
        (
            PLAYWRIGHT_RUNTIME,
            Browser,
            BrowserContext,
            Locator,
            Page,
            Playwright,
            TimeoutError,
            async_playwright,
            sync_playwright,
        ) = _load_patchright()
    else:
        try:
            (
                PLAYWRIGHT_RUNTIME,
                Browser,
                BrowserContext,
                Locator,
                Page,
                Playwright,
                TimeoutError,
                async_playwright,
                sync_playwright,
            ) = _load_patchright()
        except Exception:
            (
                PLAYWRIGHT_RUNTIME,
                Browser,
                BrowserContext,
                Locator,
                Page,
                Playwright,
                TimeoutError,
                async_playwright,
                sync_playwright,
            ) = _load_playwright()
except Exception:
    (
        PLAYWRIGHT_RUNTIME,
        Browser,
        BrowserContext,
        Locator,
        Page,
        Playwright,
        TimeoutError,
        async_playwright,
        sync_playwright,
    ) = _load_playwright()


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
