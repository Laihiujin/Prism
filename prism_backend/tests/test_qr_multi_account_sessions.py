from __future__ import annotations

import asyncio

from prism_backend.reverse_api.login.douyin_adapter import DouyinQrLoginAdapter
from prism_backend.reverse_api.login.models import QrLoginState


class Qr:
    def __init__(self, session_id):
        self.session_id = session_id
        self.qr_url = "https://creator.example.test/login"
        self.qr_image = "data:image/png;base64,test"
        self.expires_in = 300


class Status:
    value = "waiting"


class Result:
    status = Status()
    message = "waiting"
    cookies = None
    full_state = None
    user_info = None


class Legacy:
    def __init__(self, session_id):
        self.session_id = session_id
        self.closed = False

    async def get_qrcode(self):
        return Qr(self.session_id)

    async def poll_status(self, session_id):
        assert session_id == self.session_id
        return Result()

    async def cleanup_session(self, session_id):
        assert session_id == self.session_id
        self.closed = True


def test_multiple_accounts_keep_isolated_challenges():
    instances = iter((Legacy("account-a-attempt"), Legacy("account-b-attempt")))
    adapter = DouyinQrLoginAdapter(lambda: next(instances))

    async def scenario():
        first, second = await asyncio.gather(
            adapter.create_challenge(), adapter.create_challenge()
        )
        first_result, second_result = await asyncio.gather(
            adapter.poll(first), adapter.poll(second)
        )
        return first, second, first_result, second_result

    first, second, first_result, second_result = asyncio.run(scenario())
    assert first.challenge_id != second.challenge_id
    assert first_result.state is QrLoginState.WAITING
    assert second_result.state is QrLoginState.WAITING
