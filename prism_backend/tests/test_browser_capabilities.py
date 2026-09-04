import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from myUtils.browser_context import connect_browser_over_cdp, launch_persistent_browser_context


def test_persistent_context_uses_resolved_engine():
    firefox = SimpleNamespace(launch_persistent_context=AsyncMock(return_value="context"))
    playwright = SimpleNamespace(firefox=firefox)
    with patch("myUtils.browser_context.resolve_browser_launch_opts", return_value=("firefox", {"headless": True})):
        result = asyncio.run(launch_persistent_browser_context(playwright, platform="channels", headless=True))
    assert result == "context"
    firefox.launch_persistent_context.assert_awaited_once_with(headless=True)


def test_cdp_rejects_non_chromium_engine():
    with patch("myUtils.browser_context.resolve_browser_launch_opts", return_value=("firefox", {})):
        try:
            asyncio.run(connect_browser_over_cdp(SimpleNamespace(), "ws://example", platform="douyin"))
        except RuntimeError as error:
            assert "CDP attach 仅支持 Chromium" in str(error)
        else:
            raise AssertionError("Firefox CDP attach should be rejected")


def test_cdp_connects_when_chromium_is_selected():
    chromium = SimpleNamespace(connect_over_cdp=AsyncMock(return_value="browser"))
    with patch("myUtils.browser_context.resolve_browser_launch_opts", return_value=("chromium", {})):
        result = asyncio.run(connect_browser_over_cdp(SimpleNamespace(chromium=chromium), "ws://example", platform="douyin"))
    assert result == "browser"
    chromium.connect_over_cdp.assert_awaited_once_with("ws://example")
