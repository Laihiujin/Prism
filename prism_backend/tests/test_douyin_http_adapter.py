from __future__ import annotations

import asyncio

from prism_backend.app_new.platforms.base import LoginStatus
from prism_backend.app_new.platforms.douyin_http import DouyinHttpAdapter


def test_douyin_http_adapter_live_create_and_waiting_poll():
    async def scenario():
        adapter = DouyinHttpAdapter({"account_id": "http-smoke"})
        qr = await adapter.get_qrcode()
        try:
            result = await adapter.poll_status(qr.session_id)
            return qr, result, await adapter.supports_api_login()
        finally:
            await adapter.cleanup_session(qr.session_id)

    qr, result, supports_http = asyncio.run(scenario())
    assert qr.qr_image.startswith("data:image/png;base64,iVBOR")
    assert qr.expires_in > 0
    assert result.status is LoginStatus.WAITING
    assert supports_http is True
