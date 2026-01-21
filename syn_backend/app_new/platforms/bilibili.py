"""
Bilibili Platform Adapter - B站平台适配器

纯HTTP API实现,无需Playwright
复制自: syn_backend/fastapi_app/api/v1/auth/services.py::BilibiliLoginService
"""
import asyncio
import base64
import io
from typing import Tuple, Dict, Any

import httpx
from loguru import logger

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

from .base import PlatformAdapter, QRCodeData, UserInfo, LoginResult, LoginStatus


class BilibiliAdapter(PlatformAdapter):
    """B站登录适配器 (纯HTTP API)"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.platform_name = "bilibili"

    async def get_qrcode(self) -> QRCodeData:
        """
        生成B站登录二维码

        API: https://passport.bilibili.com/x/passport-login/web/qrcode/generate
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://passport.bilibili.com/x/passport-login/web/qrcode/generate",
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                data = resp.json()

                if data.get("code") != 0:
                    raise Exception(f"Bilibili QR API failed: {data.get('message', 'Unknown error')}")

                qrcode_url = data["data"]["url"]
                qrcode_key = data["data"]["qrcode_key"]

                # 生成二维码图片
                qr_image = await self._generate_qr_image(qrcode_url)

                logger.info(f"[Bilibili] QR code generated: key={qrcode_key[:12]}...")

                return QRCodeData(
                    session_id=qrcode_key,
                    qr_url=qrcode_url,
                    qr_image=qr_image,
                    expires_in=180  # B站二维码有效期3分钟
                )

        except Exception as e:
            logger.error(f"[Bilibili] QR generation failed: {e}")
            raise

    async def poll_status(self, session_id: str) -> LoginResult:
        """
        轮询B站登录状态

        API: https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={key}

        状态码映射:
        - 86101: waiting (未扫码)
        - 86090: scanned (已扫码,未确认)
        - 0: confirmed (已确认)
        - 86038: expired (已过期)
        """
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(
                    "https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
                    params={"qrcode_key": session_id},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )

                if resp.status_code != 200:
                    return LoginResult(
                        status=LoginStatus.FAILED,
                        message=f"HTTP {resp.status_code}"
                    )

                data = resp.json().get("data", {}) or {}
                code = data.get("code")

                # 状态映射
                status_map = {
                    86101: LoginStatus.WAITING,
                    86090: LoginStatus.SCANNED,
                    0: LoginStatus.CONFIRMED,
                    86038: LoginStatus.EXPIRED
                }
                status = status_map.get(code, LoginStatus.FAILED)

                if status != LoginStatus.CONFIRMED:
                    return LoginResult(
                        status=status,
                        message=data.get("message", "")
                    )

                # 登录成功,获取Cookie和用户信息
                login_url = data.get("url")
                if not login_url:
                    return LoginResult(
                        status=LoginStatus.FAILED,
                        message="No login URL returned"
                    )

                # 访问登录URL获取Cookie
                await client.get(login_url, headers={"User-Agent": "Mozilla/5.0"})
                cookies = dict(client.cookies)

                # 获取用户信息
                user_info = await self._fetch_user_info(client, cookies)

                logger.info(f"[Bilibili] Login confirmed: uid={user_info.user_id}")

                return LoginResult(
                    status=LoginStatus.CONFIRMED,
                    message="Login successful",
                    cookies=cookies,
                    user_info=user_info
                )

        except Exception as e:
            logger.error(f"[Bilibili] Poll failed: {e}")
            return LoginResult(
                status=LoginStatus.FAILED,
                message=str(e)
            )

    async def cleanup_session(self, session_id: str):
        """B站无需清理会话 (纯HTTP API)"""
        pass

    async def supports_api_login(self) -> bool:
        return True

    # ========== Helper Methods ==========

    async def _generate_qr_image(self, qr_url: str) -> str:
        """生成二维码图片 (base64)"""
        if not HAS_QRCODE:
            # 如果qrcode库不可用,返回URL作为降级
            logger.warning("[Bilibili] qrcode library not available, returning URL")
            return qr_url

        try:
            buffer = io.BytesIO()
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(qr_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(buffer, format="PNG")
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/png;base64,{b64}"
        except Exception as e:
            logger.warning(f"[Bilibili] QR image generation failed: {e}, returning URL")
            return qr_url

    async def _fetch_user_info(self, client: httpx.AsyncClient, cookies: Dict[str, str]) -> UserInfo:
        """
        获取B站用户信息

        API: https://api.bilibili.com/x/web-interface/nav
        """
        try:
            nav_resp = await client.get(
                "https://api.bilibili.com/x/web-interface/nav",
                cookies=cookies,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            if nav_resp.status_code != 200:
                return UserInfo()

            nav_data = nav_resp.json().get("data", {}) or {}

            return UserInfo(
                user_id=str(nav_data.get("mid", "")),
                username=nav_data.get("uname", ""),
                name=nav_data.get("uname", ""),
                avatar=nav_data.get("face", "")
            )

        except Exception as e:
            logger.warning(f"[Bilibili] Fetch user info failed: {e}")
            return UserInfo()
