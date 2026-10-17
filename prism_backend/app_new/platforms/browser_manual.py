"""Interactive browser login for platforms without a stable web QR endpoint."""
import asyncio
import base64
import re
import uuid
from urllib.parse import urlparse
from .base import PlatformAdapter, QRCodeData, LoginResult, LoginStatus, UserInfo


class BrowserManualAdapter(PlatformAdapter):
    platform = ""

    def __init__(self, config=None):
        super().__init__(config)
        self.platform_name = self.platform
        self.page = self.context = self.browser = self.playwright = None

    async def get_qrcode(self):
        from utils.automation_provider import async_playwright
        from myUtils.automation_context_factory import create_context_with_policy
        sid = str(uuid.uuid4())
        try:
            self.playwright = await async_playwright().start()
            self.browser, self.context, _, _ = await create_context_with_policy(
                self.playwright, platform=self.platform, account_id=self.config.get("account_id"),
                headless=self.config.get("headless", True), base_context_opts={"viewport": {"width": 1280, "height": 800}})
            self.page = await self.context.new_page()
            url = {"youtube": "https://studio.youtube.com", "tiktok": "https://www.tiktok.com/tiktokstudio", "bilibili": "https://passport.bilibili.com/login"}[self.platform]
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # This is explicitly a browser preview, never presented as an official QR.
            if self.platform == "bilibili":
                qr = self.page.locator('.login-scan-box img, .login-scan-box canvas, .qrcode img, .qrcode canvas, img[alt="Scan me!"], img[src*="qrcode"]').first
                await qr.wait_for(state="visible", timeout=20000)
                preview = base64.b64encode(await qr.screenshot(type="png")).decode()
            else:
                preview = base64.b64encode(await self.page.screenshot(type="png")).decode()
            return QRCodeData(sid, url, "data:image/png;base64," + preview, expires_in=300 if self.platform == "bilibili" else 3600)
        except BaseException:
            await self.cleanup_session(sid)
            raise

    async def poll_status(self, session_id):
        pages = [page for page in self.context.pages if not page.is_closed()]
        if pages:
            self.page = pages[-1]
        cookies = await self.context.cookies()
        values = {c["name"]: c["value"] for c in cookies if (c.get("domain", "").lstrip(".") == self.platform + ".com" or c.get("domain", "").endswith("." + self.platform + ".com"))}
        parsed = urlparse(self.page.url)
        uid = None
        if self.platform == "bilibili" and values.get("SESSDATA") and values.get("DedeUserID"):
            uid = values["DedeUserID"]
        elif self.platform == "tiktok" and parsed.hostname in ("www.tiktok.com", "tiktok.com"):
            if "tiktokstudio" in parsed.path and (values.get("sessionid") or values.get("sessionid_ss")):
                uid = values.get("uid_tt") or values.get("uid_tt_ss")
        elif self.platform == "youtube" and parsed.hostname == "studio.youtube.com":
            match = re.search(r"/channel/(UC[\w-]+)", parsed.path)
            if match and any(values.get(k) for k in ("SAPISID", "__Secure-3PAPISID", "__Secure-1PAPISID")):
                uid = match.group(1)
        if not uid:
            return LoginResult(LoginStatus.WAITING, message="请在远程浏览器完成登录及平台验证")
        state = await self.context.storage_state()
        return LoginResult(LoginStatus.CONFIRMED, cookies=cookies, full_state=state,
                           user_info=UserInfo(user_id=uid, name=uid))

    async def cleanup_session(self, session_id):
        import contextlib
        for resource in (self.context, self.browser):
            if resource:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(resource.close(), timeout=5)
        if self.playwright:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.playwright.stop(), timeout=5)


class TikTokBrowserAdapter(BrowserManualAdapter):
    platform = "tiktok"


class YouTubeBrowserAdapter(BrowserManualAdapter):
    platform = "youtube"


class BilibiliBrowserAdapter(BrowserManualAdapter):
    platform = "bilibili"
