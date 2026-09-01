"""Unit tests for DouyinHttpAdapter session activation + auth-cookie verification.

These cover the CONFIRMED-branch fix: passport's ``confirmed`` alone is NOT a
usable login — the account session cookies (sessionid/sessionid_ss/sid_guard …)
must be seeded by following redirect + hitting creator/home pages, and missing
core cookies must surface as FAILED instead of a silent "Login successful".
No real network is used: ``client`` is a fake httpx-like object.
"""

from __future__ import annotations

import asyncio
import types

import httpx

from prism_backend.app_new.platforms.base import LoginStatus
from prism_backend.app_new.platforms.douyin_http import (
    AUTH_COOKIE_NAMES,
    DouyinHttpAdapter,
)


class FakeClient:
    """Minimal stand-in for httpx.AsyncClient: records GETs, holds a cookie jar."""

    def __init__(self) -> None:
        self.cookies = httpx.Cookies()
        self.get_calls: list[str] = []

    def seed(self, name: str, value: str = "v") -> None:
        # httpx.Cookies.set accepts a domain; ".douyin.com" covers both hosts.
        self.cookies.set(name, value, domain=".douyin.com")

    async def get(self, url: str, **kwargs) -> types.SimpleNamespace:
        self.get_calls.append(url)
        return types.SimpleNamespace(raise_for_status=lambda: None)


def _run(coro):
    return asyncio.run(coro)


def test_activation_follows_redirect_then_creator_and_home():
    client = FakeClient()
    client.seed("sessionid", "abc123")  # simulate account session seeded by activation requests

    async def scenario():
        adapter = DouyinHttpAdapter({})
        return await adapter._activate_session_and_verify(client, {}, "https://creator.douyin.com/?from=qr")

    ok, message, cookies = _run(scenario())
    assert ok is True
    assert message == ""
    # redirect → creator home → douyin home
    assert client.get_calls == [
        "https://creator.douyin.com/?from=qr",
        "https://creator.douyin.com/",
        "https://www.douyin.com/",
    ]
    assert cookies.get("sessionid") == "abc123"


def test_activation_success_when_sessionid_seeded():
    client = FakeClient()
    client.seed("sessionid", "abc123")

    ok, message, cookies = _run(DouyinHttpAdapter({})._activate_session_and_verify(client, {}, None))
    assert ok is True
    assert cookies.get("sessionid") == "abc123"


def test_activation_success_with_sid_guard_when_no_sessionid():
    client = FakeClient()
    client.seed("sid_guard", "guard-token")
    client.seed("passport_csrf_token", "csrf")  # passport-only cookie should not count

    ok, message, cookies = _run(DouyinHttpAdapter({})._activate_session_and_verify(client, {}, None))
    assert ok is True
    assert cookies.get("sid_guard") == "guard-token"


def test_activation_fails_without_core_cookie_and_lists_missing():
    client = FakeClient()
    # passport-only cookies: confirmed by passport but no account session
    client.seed("passport_csrf_token", "csrf")
    client.seed("sid_tt", "sid-tt")

    ok, message, cookies = _run(DouyinHttpAdapter({})._activate_session_and_verify(client, {}, None))
    assert ok is False
    assert "sessionid" in message and "sessionid_ss" in message and "sid_guard" in message
    assert message.startswith("账号会话未激活")


def test_activation_activation_requests_failures_do_not_crash():
    class FailingGetClient(FakeClient):
        async def get(self, url: str, **kwargs):
            raise RuntimeError("network down")

    client = FailingGetClient()
    client.seed("sessionid_ss", "ss-token")

    ok, message, _ = _run(DouyinHttpAdapter({})._activate_session_and_verify(client, {}, None))
    assert ok is True  # request failures tolerated; cookie verdict decides


def test_auth_cookie_names_align_with_auth_service():
    # auth/services.py:505 checks exactly these names for login-state
    expected = {"sessionid", "sessionid_ss", "sid_guard", "sid_tt", "passport_auth_id", "odin_tt"}
    assert set(AUTH_COOKIE_NAMES) == expected
