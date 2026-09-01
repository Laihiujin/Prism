"""Pure-HTTP Douyin creator QR login adapter."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import datetime, timezone
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
    "AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/147.0.0.0 Safari/537.36"
)
ORIGIN = "https://creator.douyin.com"
CREATE_URL = f"{ORIGIN}/passport/web/get_qrcode/"
POLL_URL = f"{ORIGIN}/passport/web/check_qrconnect/"
PASSPORT_APP_KEY = "6ddd3ec693f3a124adb29b91b244ece5"

# 账号登录态判定所需的 cookie（与 fastapi_app/api/v1/auth/services.py 保持一致）。
# 抖音 passport QR 确认只代表“扫码通过”，账号会话（sessionid 等）需要在
# 跟随 redirect / 访问创作者中心与主站后由服务端种下；缺了这些 cookie，
# 账号系统会判定为未登录（“获取不到账号 cookie”）。
AUTH_COOKIE_NAMES = (
    "sessionid", "sessionid_ss", "sid_guard", "sid_tt", "passport_auth_id", "odin_tt",
)
# 必须至少存在其中一个，才认为账号会话已激活
CORE_AUTH_COOKIES = ("sessionid", "sessionid_ss", "sid_guard")


def _xor5_hex(value: str) -> str:
    return bytes(byte ^ 5 for byte in value.encode()).hex()


def _base36(value: int) -> str:
    alphabet, result = "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while value:
        value, remainder = divmod(value, 36)
        result = alphabet[remainder] + result
    return result or "0"


def _passport_aid_signature(ts: str, path: str = "/passport/web/check_qrconnect/") -> str:
    # Mirrors @byted/douyin-login-new's HKDF/HMAC middleware. Its HMAC helper
    # takes (key, message), including the SDK's intentionally nonstandard
    # extract order: HMAC(timestamp, appKey).
    prk = hmac.new(ts.encode(), PASSPORT_APP_KEY.encode(), hashlib.sha256).digest()
    key = hmac.new(prk, b"\x01", hashlib.sha256).digest()
    content = f"aid=2906&path={path}&ts={ts}"
    return hmac.new(key, content.encode(), hashlib.sha256).hexdigest()


def _passport_sign(params: dict[str, str], body: dict[str, str]) -> tuple[str, str]:
    keys = sorted(params)[:10]
    query = "&".join(f"{key}={params[key]}" for key in keys)
    form = "&".join(f"{key}={body[key]}" for key in sorted(body))
    raw = f"{query}&{form}&app_key={PASSPORT_APP_KEY}"
    return hashlib.sha256(raw.encode()).hexdigest(), _xor5_hex(",".join(keys))


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
            trace_id = secrets.token_hex(4)
            portrait = f"{uuid.uuid4()}.login"
            csrf_probe = await client.head(
                CREATE_URL,
                headers={"x-secsdk-csrf-request": "1", "x-secsdk-csrf-version": "1.2.22"},
            )
            csrf_parts = csrf_probe.headers.get("x-ware-csrf-token", "").split(",")
            if len(csrf_parts) < 2 or csrf_parts[0] != "0" or not csrf_parts[1]:
                raise RuntimeError("Douyin SecSDK CSRF bootstrap was not successful")
            now_ms = int(time.time() * 1000)
            utc = datetime.now(timezone.utc)
            aid_ts = str(int(datetime(utc.year, utc.month, utc.day, 12, tzinfo=timezone.utc).timestamp()))
            browser_info = {
                "hardwareConcurrency": 8, "webdriver": False, "plugins": 5,
                "innerHeight": 720, "innerWidth": 1280, "outerHeight": 720, "outerWidth": 1280,
                "browser": {"t": str(now_ms), "bit_protocol": "false", "bit_helper": "false"},
            }
            params = self._create_params()
            params.update({
                "ts": aid_ts, "p_ui": "2.4.2", "account_sdk_source": "web",
                "account_sdk_source_info": _xor5_hex(json.dumps(browser_info, separators=(",", ":"))),
                "p_js_v": "3.4.2", "p_js_t": "pro", "p_zt": "unknown", "p_ver": "1.1.3",
                "p_ver_real": "0", "request_host": "https%3A%2F%2Fcreator.douyin.com",
                "p_bd": "1.0.1.16", "p_ts": str(now_ms), "biz_trace_id": trace_id,
            })
            p_no_values = {key: params[key] for key in (
                "passport_jssdk_version", "p_bd", "p_ts", "p_ver", "p_zt"
            )}
            p_no_values["p_ca"] = "0"
            params["p_no"] = hashlib.sha256("&".join(
                f"{key}={value}" for key, value in sorted(p_no_values.items())
            ).encode()).hexdigest()
            params["sign"], params["qs"] = _passport_sign(params, {})
            signed = await signer.sign_request(urlencode(params), "", USER_AGENT, url=CREATE_URL, method="GET")
            fp = signed.get("verify_fp")
            if not fp:
                raise RuntimeError("Douyin VerifyCenter did not produce fp")
            params["fp"] = fp
            params["verifyFp"] = fp
            ms_token = signed.get("msToken", "")
            params["account_sdk_source_info"] = signed.get(
                "account_sdk_source_info", params["account_sdk_source_info"]
            )
            if ms_token:
                params["msToken"] = ms_token
                params["sign"], params["qs"] = _passport_sign(params, {})
                signed = await signer.sign_request(
                    urlencode({k: v for k, v in params.items() if k != "a_bogus"}),
                    "", USER_AGENT, url=CREATE_URL, method="GET",
                )
            params["a_bogus"] = signed["a_bogus"]
            csrf = client.cookies.get("passport_csrf_token", "")
            response = await client.get(CREATE_URL, params=params, headers={
                "x-tt-session-dtrait": signed["x-tt-session-dtrait"],
                "x-tt-passport-aid-sign": _passport_aid_signature(aid_ts, "/passport/web/get_qrcode/"),
                "x-tt-passport-trace-id": trace_id,
                "x-tt-passport-verify-portrait": portrait,
                "x-secsdk-csrf-token": csrf_parts[1],
                "x-tt-passport-csrf-token": csrf,
            })
            response.raise_for_status()
            # Passport rotates the anti-abuse token in its response headers.
            # Browser fetch keeps this value in the SDK state before the first
            # confirmation poll; carry the same rotation into the HTTP session.
            response_ms_token = response.headers.get("x-ms-token", "")
            if response_ms_token:
                ms_token = response_ms_token
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
                "fp": fp,
                "trace_id": trace_id,
                "portrait": portrait,
                "secsdk_csrf": csrf_parts[1],
                "msToken": ms_token,
                "account_sdk_source_info": params["account_sdk_source_info"],
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
            # The official Creator browser creates a non-frontier token but
            # still uses the frontier confirmation route for every poll.
            "is_frontier": "true",
            "token": session["token"],
            "is_new_login": "1",
            "next": ORIGIN,
            "need_short_url": "true",
        }
        encoded_body = urlencode(body)
        params = self._poll_params()
        now_ms = int(time.time() * 1000)
        utc = datetime.now(timezone.utc)
        midday = datetime(utc.year, utc.month, utc.day, 12, tzinfo=timezone.utc)
        aid_ts = str(int(midday.timestamp()))
        browser_info = {
            "hardwareConcurrency": 8,
            "webdriver": False,
            "plugins": 5,
            "innerHeight": 720,
            "innerWidth": 1280,
            "outerHeight": 720,
            "outerWidth": 1280,
            "browser": {"t": str(now_ms), "bit_protocol": "false", "bit_helper": "false"},
        }
        params.update(
            {
                "ts": aid_ts,
                "fp": session["fp"],
                "verifyFp": session["fp"],
                "account_sdk_source_info": session.get("account_sdk_source_info") or _xor5_hex(
                    json.dumps(browser_info, separators=(",", ":"))
                ),
                "biz_trace_id": session["trace_id"],
                "p_ts": str(now_ms),
            }
        )
        p_no_raw = "&".join(
            f"{key}={value}"
            for key, value in sorted(
                {
                    "passport_jssdk_version": params["passport_jssdk_version"],
                    "p_bd": params["p_bd"],
                    "p_ca": params["p_ca"],
                    "p_ts": params["p_ts"],
                    "p_ver": params["p_ver"],
                    "p_zt": params["p_zt"],
                }.items()
            )
        )
        params["p_no"] = hashlib.sha256(p_no_raw.encode()).hexdigest()
        ms_token = session.get("msToken") or client.cookies.get("msToken", "")
        if ms_token:
            params["msToken"] = ms_token
        params["sign"], params["qs"] = _passport_sign(params, body)
        csrf = client.cookies.get("passport_csrf_token", "")
        signed = await signer.sign_request(
            urlencode(params),
            encoded_body,
            USER_AGENT,
            {"content-type": "application/x-www-form-urlencoded"},
        )
        params["a_bogus"] = signed["a_bogus"]
        response = await client.post(
            POLL_URL,
            params=params,
            content=encoded_body,
            headers={
                "content-type": "application/x-www-form-urlencoded",
                "web-sdk-version": "1",
                "x-csrftoken": csrf,
                "x-tt-passport-csrf-token": csrf,
                "x-tt-session-dtrait": signed["x-tt-session-dtrait"],
                "x-tt-passport-aid-sign": _passport_aid_signature(aid_ts),
                "x-tt-passport-trace-id": session["trace_id"],
                "x-tt-passport-verify-portrait": session["portrait"],
                "x-secsdk-csrf-token": session["secsdk_csrf"],
            },
        )
        response.raise_for_status()
        response_ms_token = response.headers.get("x-ms-token", "")
        if response_ms_token:
            session["msToken"] = response_ms_token
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
                f"code={code!r} envelope={json.dumps(envelope, ensure_ascii=False)[:600]}"
            )
            # code=2156（"系统繁忙"）：扫码确认交接被 passport 风控。根因：
            # HTTP 会话缺少 verifycenter 会话信任——浏览器版在 get_qrcode 前会调
            # /passport/web/challenge/（rmc-nocaptcha），该接口要求 JS 采集指纹后
            # 种下的 s_v_web_id 等 cookie，HTTP 客户端无法执行（详见
            # prism_backend/reverse_api/DOUYIN_HTTP_2156_FINDINGS.md）。
            # 保持 WAITING 让二维码自然过期，避免假成功。
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
        activated, message, cookies = await self._activate_session_and_verify(client, session, redirect)
        if not activated:
            # 明确失败而不是假成功：账号会话未激活时直接报错，
            # 避免下游拿到残缺 cookie 后判定“未登录”。
            await self.cleanup_session(session_id, close_client=False)
            await client.aclose()
            logger.warning(f"[DouyinHTTP] {message} session={session_id[:8]}")
            return LoginResult(LoginStatus.FAILED, message)

        full_state = {"cookies": self._storage_cookies(client), "origins": []}
        user_info = UserInfo(
            user_id=str(data.get("user_id") or data.get("uid") or "") or None,
            name=data.get("screen_name") or data.get("nickname"),
            avatar=data.get("avatar_url") or data.get("avatar"),
            extra={"http_qr_login": True, "activated_cookies": sorted(c for c in AUTH_COOKIE_NAMES if cookies.get(c))},
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

    async def _activate_session_and_verify(
        self,
        client: httpx.AsyncClient,
        session: dict[str, Any],
        redirect: Any,
    ) -> tuple[bool, str, dict[str, str]]:
        """
        账号会话激活 + 登录 cookie 校验。

        passport 的 check_qrconnect 返回 confirmed 只是“扫码确认通过”，
        账号 cookie（sessionid/sessionid_ss/sid_guard 等）需要服务端在后续
        请求中种下。这里依次请求：passport 给的 redirect → 创作者中心首页
        → 主站首页，让服务端种下账号 cookie，然后校验齐全性。

        Returns:
            (ok, message, cookies)：ok=False 时 message 说明缺失的核心 cookie。
        """
        urls: list[str] = []
        if isinstance(redirect, str) and redirect.startswith("http"):
            urls.append(redirect)
        urls.append(f"{ORIGIN}/")
        urls.append("https://www.douyin.com/")

        for url in urls:
            try:
                response = await client.get(url, timeout=20)
                response.raise_for_status()
            except Exception as exc:
                logger.warning(f"[DouyinHTTP] session activation request failed: {url} -> {exc}")

        cookies = {cookie.name: cookie.value for cookie in client.cookies.jar}
        auth = {name: value for name, value in cookies.items() if name in AUTH_COOKIE_NAMES and value}
        core = [name for name in CORE_AUTH_COOKIES if auth.get(name)]
        missing = [name for name in AUTH_COOKIE_NAMES if name not in auth]
        if not core:
            return False, (
                f"账号会话未激活：缺少核心登录 cookie（{', '.join(missing) or 'unknown'}）。"
                "请重新扫码登录。"
            ), cookies
        return True, "", cookies

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
