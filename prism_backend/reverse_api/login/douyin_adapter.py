from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import QrLoginAdapter
from .models import QrLoginChallenge, QrLoginState, QrPollResult


_STATUS_MAP = {
    "waiting": QrLoginState.WAITING,
    "scanned": QrLoginState.SCANNED,
    "confirmed": QrLoginState.CONFIRMED,
    "expired": QrLoginState.EXPIRED,
    "failed": QrLoginState.FAILED,
}


def _default_adapter_factory() -> Any:
    # Import lazily so protocol metadata and unit tests remain usable without a
    # browser runtime. Prism starts with prism_backend on sys.path in production.
    try:
        from prism_backend.app_new.platforms.douyin import DouyinAdapter
    except ImportError:
        from app_new.platforms.douyin import DouyinAdapter
    return DouyinAdapter({"headless": True})


class DouyinQrLoginAdapter(QrLoginAdapter):
    """Normalize Prism's current browser login into the reverse-login contract.

    The official page runtime owns dynamic request signing. This class never
    serializes those parameters; it returns the established session payload to
    the caller only after the underlying adapter confirms creator access.
    """

    platform = "douyin"

    def __init__(self, adapter_factory: Callable[[], Any] | None = None):
        self._adapter_factory = adapter_factory or _default_adapter_factory
        self._adapters: dict[str, Any] = {}

    async def create_challenge(self) -> QrLoginChallenge:
        adapter = self._adapter_factory()
        qr = await adapter.get_qrcode()
        self._adapters[qr.session_id] = adapter
        return QrLoginChallenge(
            platform=self.platform,
            challenge_id=qr.session_id,
            qr_content=qr.qr_image,
            expires_in=qr.expires_in,
            runtime_context={"login_url": qr.qr_url},
        )

    async def poll(self, challenge: QrLoginChallenge) -> QrPollResult:
        if challenge.platform != self.platform:
            return QrPollResult(QrLoginState.FAILED, "Challenge platform mismatch")

        adapter = self._adapters.get(challenge.challenge_id)
        if adapter is None:
            return QrPollResult(QrLoginState.EXPIRED, "Challenge is not active")

        result = await adapter.poll_status(challenge.challenge_id)
        raw_status = getattr(result.status, "value", str(result.status)).lower()
        state = _STATUS_MAP.get(raw_status, QrLoginState.FAILED)
        established = state is QrLoginState.CONFIRMED

        session_payload: dict[str, Any] = {}
        if established:
            session_payload = {
                "cookies": result.cookies or {},
                "storage_state": result.full_state,
                "user_info": result.user_info,
            }
            self._adapters.pop(challenge.challenge_id, None)
        elif state in {QrLoginState.EXPIRED, QrLoginState.FAILED}:
            self._adapters.pop(challenge.challenge_id, None)

        return QrPollResult(
            state=state,
            message=result.message,
            retry_after=1.0,
            session_established=established,
            session_payload=session_payload,
        )

    async def close(self, challenge: QrLoginChallenge) -> None:
        adapter = self._adapters.pop(challenge.challenge_id, None)
        if adapter is not None:
            await adapter.cleanup_session(challenge.challenge_id)
