"""Pure-HTTP Douyin creator QR login adapter."""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict
from urllib.parse import urlencode

import httpx
from loguru import logger

try:
    from prism_backend.reverse_api.signing import DouyinABogusSigner
except ModuleNotFoundError:  # worker.py adds prism_backend itself to sys.path
    from reverse_api.signing import DouyinABogusSigner

from .base import LoginResult, LoginStatus, PlatformAdapter, QRCodeData, UserInfo


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
ORIGIN = "https://creator.douyin.com"
CREATE_URL = f"{ORIGIN}/passport/web/get_qrcode/"
POLL_URL = f"{ORIGIN}/passport/web/check_qrconnect/"


class DouyinHttpAdapter(PlatformAdapter):
    """Create, poll and complete QR login without launching a browser."""

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.platform_name = "douyin"
        self.account_id = (config or {}).get("account_id")
        self._sessions: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _create_params() -> dict[str, str]:
        return {
            "passport_jssdk_version": "3.4.2",
            "passport_jssdk_type": "normal",
            "is_from_ttaccountsdk": "1",
            "aid": "2906",
            "language": "zh",
            "account_app_language": "zh-CN",
            "next": ORIGIN,
            "need_short_url": "true",
            "need_logo": "false",
            "is_new_login": "1",
            "is_from_iesaccountsaas": "1",
            "account_sdk_source": "web",
        }

    @staticmethod
    def _poll_params() -> dict[str, str]:
        return {
            "passport_jssdk_version": "3.4.2",
            "passport_jssdk_type": "normal",
            "is_from_ttaccountsdk": "1",
            "aid": "2906",
            "language": "zh",
            "account_app_language": "zh-CN",
            "is_from_iesaccountsaas": "1",
            "p_ui": "2.4.2",
            "p_ca": "4.0.26",
            "p_ca_real": "1.0.0.874",
            "account_sdk_source": "web",
            "p_js_v": "3.4.2",
            "p_js_t": "pro",
            "p_zt": "unknown",
            "p_ver": "1.1.3",
            "p_ver_real": "0",
            "request_host": "https%3A%2F%2Fcreator.douyin.com",
            "p_bd": "1.0.1.16",
            "is_new_login": "1",
        }

    async def get_qrcode(self) -> QRCodeData:
        session_id = str(uuid.uuid4())
        client = httpx.AsyncClient(
            headers={
                "user-agent": USER_AGENT,
                "accept": "application/json, text/plain, */*",
                "referer": f"{ORIGIN}/",
                "origin": ORIGIN,
            },
            follow_redirects=True,
            timeout=20,
        )
        signer = DouyinABogusSigner()
        try:
            response = await client.get(CREATE_URL, params=self._create_params())
            response.raise_for_status()
            envelope = response.json()
            data = envelope.get("data") or {}
            if envelope.get("message") != "success" or not data.get("token") or not data.get("qrcode"):
                raise RuntimeError("Douyin QR create response was not successful")

            expires_at = int(data.get("expire_time") or 0)
            expires_in = max(1, expires_at - int(time.time())) if expires_at else 300
            self._sessions[session_id] = {
                "client": client,
                "signer": signer,
                "token": data["token"],
                "frontier": bool(data.get("is_frontier", False)),
                "created_at": time.monotonic(),
                "expires_in": expires_in,
            }
            logger.info(f"[DouyinHTTP] QR created: session={session_id[:8]}")
            return QRCodeData(
                session_id=session_id,
                qr_url=str(data.get("qrcode_index_url") or ORIGIN),
                qr_image=f"data:image/png;base64,{data['qrcode']}",
                expires_in=expires_in,
            )
        except Exception:
            await signer.close()
            await client.aclose()
            raise

    async def poll_status(self, session_id: str) -> LoginResult:
        session = self._sessions.get(session_id)
        if not session:
            return LoginResult(LoginStatus.EXPIRED, "Session expired")
        if time.monotonic() - session["created_at"] >= session["expires_in"]:
            await self.cleanup_session(session_id)
            return LoginResult(LoginStatus.EXPIRED, "QR code expired")

        client: httpx.AsyncClient = session["client"]
        signer: DouyinABogusSigner = session["signer"]
        body = {
            "need_logo": "false",
            # Creator login's current web client always polls the frontier
            # confirmation path. The create response can report false for a
            # stripped HTTP request, but forwarding that value reaches scan
            # and then fails the mobile confirmation hand-off (2156).
            "is_frontier": "true",
            "token": session["token"],
            "is_new_login": "1",
            "next": ORIGIN,
            "need_short_url": "true",
        }
        encoded_body = urlencode(body)
        params = self._poll_params()
        params["a_bogus"] = await signer.sign(urlencode(params), encoded_body, USER_AGENT)
        csrf = client.cookies.get("passport_csrf_token", "")
        response = await client.post(
            POLL_URL,
            params=params,
            content=encoded_body,
            headers={
                "content-type": "application/x-www-form-urlencoded",
                "x-csrftoken": csrf,
                "x-tt-passport-csrf-token": csrf,
            },
        )
        response.raise_for_status()
        envelope = response.json()
        if envelope.get("message") != "success":
            # The passport endpoint can transiently reject a poll during the
            # mobile confirmation hand-off. Keep the challenge alive so the
            # next scheduled poll can receive the terminal state.
            code = envelope.get("error_code")
            data = envelope.get("data") or {}
            code = code if code is not None else data.get("error_code")
            logger.warning(
                f"[DouyinHTTP] transient poll rejection: session={session_id[:8]} "
                f"code={code!r}"
            )
            return LoginResult(LoginStatus.WAITING, f"Poll retry required (code={code})")
        data = envelope.get("data") or {}
        raw_status = str(data.get("status") or "").lower()

        if raw_status in {"new", "waiting", "0"}:
            return LoginResult(LoginStatus.WAITING, "Waiting for scan")
        if raw_status in {"scan", "scanned", "1"}:
            return LoginResult(LoginStatus.SCANNED, "Scanned; waiting for confirmation")
        if raw_status in {"expired", "timeout", "3", "4"}:
            await self.cleanup_session(session_id)
            return LoginResult(LoginStatus.EXPIRED, "QR code expired")
        if raw_status not in {"confirmed", "success", "2"}:
            return LoginResult(LoginStatus.WAITING, f"Waiting ({raw_status or 'unknown'})")

        redirect = data.get("redirect_url") or data.get("redirect_uri") or data.get("next")
        if isinstance(redirect, str) and redirect.startswith("http"):
            await client.get(redirect)
        cookies = {cookie.name: cookie.value for cookie in client.cookies.jar}
        full_state = {"cookies": self._storage_cookies(client), "origins": []}
        user_info = UserInfo(
            user_id=str(data.get("user_id") or data.get("uid") or "") or None,
            name=data.get("screen_name") or data.get("nickname"),
            avatar=data.get("avatar_url") or data.get("avatar"),
            extra={"http_qr_login": True},
        )
        await self.cleanup_session(session_id, close_client=False)
        await client.aclose()
        return LoginResult(
            LoginStatus.CONFIRMED,
            "Login successful",
            cookies=cookies,
            user_info=user_info,
            full_state=full_state,
        )

    @staticmethod
    def _storage_cookies(client: httpx.AsyncClient) -> list[dict[str, Any]]:
        result = []
        for cookie in client.cookies.jar:
            result.append(
                {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain or ".douyin.com",
                    "path": cookie.path or "/",
                    "expires": float(cookie.expires or -1),
                    "httpOnly": bool(cookie.has_nonstandard_attr("HttpOnly")),
                    "secure": bool(cookie.secure),
                    "sameSite": "Lax",
                }
            )
        return result

    async def cleanup_session(self, session_id: str, *, close_client: bool = True):
        session = self._sessions.pop(session_id, None)
        if not session:
            return
        await session["signer"].close()
        if close_client:
            await session["client"].aclose()

    async def supports_api_login(self) -> bool:
        return True
