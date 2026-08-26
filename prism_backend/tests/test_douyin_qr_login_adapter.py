from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum

from prism_backend.reverse_api.login.douyin_adapter import DouyinQrLoginAdapter
from prism_backend.reverse_api.login.models import QrLoginState


class FakeStatus(str, Enum):
    WAITING = "waiting"
    CONFIRMED = "confirmed"


@dataclass
class FakeQr:
    session_id: str = "challenge-1"
    qr_url: str = "https://creator.example.test/login"
    qr_image: str = "data:image/png;base64,example"
    expires_in: int = 300


@dataclass
class FakeUser:
    user_id: str = "local-only"


@dataclass
class FakeResult:
    status: FakeStatus
    message: str = ""
    cookies: dict | None = None
    full_state: dict | None = None
    user_info: FakeUser | None = None


class FakeLegacyAdapter:
    def __init__(self):
        self.polls = 0
        self.closed = []

    async def get_qrcode(self):
        return FakeQr()

    async def poll_status(self, session_id):
        self.polls += 1
        if self.polls == 1:
            return FakeResult(FakeStatus.WAITING, "scan required")
        return FakeResult(
            FakeStatus.CONFIRMED,
            "ok",
            cookies={"session": "runtime-only"},
            full_state={"cookies": []},
            user_info=FakeUser(),
        )

    async def cleanup_session(self, session_id):
        self.closed.append(session_id)


def test_douyin_adapter_normalizes_waiting_and_confirmed():
    legacy = FakeLegacyAdapter()
    adapter = DouyinQrLoginAdapter(lambda: legacy)

    async def scenario():
        challenge = await adapter.create_challenge()
        waiting = await adapter.poll(challenge)
        confirmed = await adapter.poll(challenge)
        return challenge, waiting, confirmed

    challenge, waiting, confirmed = asyncio.run(scenario())
    assert challenge.platform == "douyin"
    assert waiting.state is QrLoginState.WAITING
    assert waiting.session_established is False
    assert confirmed.state is QrLoginState.CONFIRMED
    assert confirmed.session_established is True
    assert confirmed.session_payload["storage_state"] == {"cookies": []}
    assert "runtime-only" not in repr(confirmed)


def test_close_cleans_active_legacy_session():
    legacy = FakeLegacyAdapter()
    adapter = DouyinQrLoginAdapter(lambda: legacy)

    async def scenario():
        challenge = await adapter.create_challenge()
        await adapter.close(challenge)

    asyncio.run(scenario())
    assert legacy.closed == ["challenge-1"]
