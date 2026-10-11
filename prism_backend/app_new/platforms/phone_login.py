"""User-driven SMS login through official browser pages; no HTTP login emulation."""
import asyncio
import re
import uuid
from urllib.parse import urlsplit

from utils.automation_provider import async_playwright
from myUtils.automation_context_factory import create_context_with_policy
from .base import PlatformAdapter, QRCodeData, LoginResult, LoginStatus, UserInfo, risk_control_detected

PHONE_LOGIN_URLS = {
    "douyin": "https://creator.douyin.com/",
    "kuaishou": "https://cp.kuaishou.com/profile",
    "xiaohongshu": "https://creator.xiaohongshu.com/login",
    "bilibili": "https://passport.bilibili.com/login",
}
AUTH_COOKIES = {
    "douyin": {"sessionid", "sessionid_ss"},
    "kuaishou": {"kuaishou.server.web_st"},
    "xiaohongshu": {"web_session", "customer-sso-sid"},
    "bilibili": {"SESSDATA"},
}


async def visible_one(locator):
    found = []
    for index in range(await locator.count()):
        item = locator.nth(index)
        if await item.is_visible():
            found.append(item)
    if len(found) != 1:
        raise ValueError("未找到唯一的短信登录控件，请检查平台登录页")
    return found[0]


class PhoneLoginAdapter(PlatformAdapter):
    def __init__(self, platform, config=None):
        super().__init__(config)
        if platform not in PHONE_LOGIN_URLS:
            raise ValueError("当前平台没有可用的手机号短信登录入口")
        self.platform_name = platform
        self.session_id = None
        self.page = self.context = self.browser = self.playwright = None
        self.sent = False
        self.resend_at = 0
        self.masked_phone = ""
        self.last_sms_error = ""

    async def get_qrcode(self):
        raise NotImplementedError("此会话使用短信登录")

    async def start(self, phone):
        if not re.fullmatch(r"1[0-9]{10}", phone):
            raise ValueError("请输入有效的中国大陆手机号")
        self.session_id = str(uuid.uuid4())
        self.masked_phone = phone[:3] + "****" + phone[-4:]
        try:
            self.playwright = await async_playwright().start()
            self.browser, self.context, _, _ = await create_context_with_policy(
                self.playwright, platform=self.platform_name,
                account_id=self.config.get("account_id"), headless=self.config.get("headless", True),
                base_context_opts={"viewport": {"width": 1280, "height": 800}},
            )
            self.page = await self.context.new_page()
            self.page.on("response", self._observe_sms_response)
            await self.page.goto(PHONE_LOGIN_URLS[self.platform_name], wait_until="domcontentloaded", timeout=60000)
            if self.platform_name == "kuaishou":
                await self.page.get_by_text("立即登录", exact=True).wait_for(state="visible", timeout=20000)
                await (await visible_one(self.page.get_by_text("立即登录", exact=True))).click(timeout=10000)
            await self.page.locator('input[placeholder*="手机"]').first.wait_for(state="visible", timeout=20000)
            tabs = self.page.get_by_text(re.compile(r"^(短信登录|验证码登录|手机号登录)$"))
            for index in range(await tabs.count()):
                tab = tabs.nth(index)
                if await tab.is_visible():
                    await tab.click(timeout=3000)
                    break
            field = await visible_one(self.page.get_by_placeholder(re.compile(r"手机号|登录手机")))
            await field.fill(phone, timeout=5000)
            # Consent applies only to the single login agreement checkbox.
            agreements = self.page.locator('input[type="checkbox"]')
            if await agreements.count() == 1 and await agreements.is_visible() and not await agreements.is_checked():
                await agreements.check(timeout=3000)
            return QRCodeData(self.session_id, PHONE_LOGIN_URLS[self.platform_name], "", 600)
        except Exception:
            await self.cleanup_session(self.session_id)
            raise

    async def _send_control(self):
        return await visible_one(self.page.get_by_text(re.compile(r"^(获取验证码|发送验证码|重新发送|重新获取|重新发送验证码)$")))

    async def _observe_sms_response(self, response):
        if self.platform_name != "kuaishou" or urlsplit(response.url).path != "/pass/kuaishou/sms/requestMobileCode":
            return
        try:
            data = await response.json()
            if data.get("result") in (0, 1):
                self.sent = True
                self.resend_at = asyncio.get_running_loop().time() + 60
                self.last_sms_error = ""
            elif data.get("result") == 400002:
                self.sent = False
                self.resend_at = 0
                self.last_sms_error = "快手要求滑块验证，短信尚未发出。请在登录浏览器中手动完成安全验证。"
            elif data.get("result") is not None:
                self.sent = False
                self.resend_at = 0
                self.last_sms_error = "平台拒绝发送短信验证码，请检查手机号及平台提示。"
        except Exception:
            pass

    async def _refresh_send_state(self):
        text = await self.page.locator("body").inner_text()
        countdown = re.search(r"(\d+)\s*(?:秒|s)\s*后.*?(?:发送|获取|重发)", text, re.I)
        if countdown and not self.last_sms_error:
            self.sent = True
            self.resend_at = asyncio.get_running_loop().time() + int(countdown.group(1))
            self.last_sms_error = ""

    async def sms_action(self, session_id, action, code=None):
        if session_id != self.session_id or not self.page:
            raise ValueError("短信登录会话已过期")
        if action in ("request", "resend"):
            now = asyncio.get_running_loop().time()
            if self.sent and now < self.resend_at:
                raise ValueError("请等待倒计时结束后重新发送")
            control = await self._send_control()
            if not await control.is_enabled():
                raise ValueError("平台暂时不允许发送验证码，请检查手机号或验证提示")
            self.last_sms_error = ""
            if self.platform_name == "kuaishou" and urlsplit(self.page.url).hostname not in (None, ""):
                self.sent = False
                try:
                    async with self.page.expect_response(lambda response: urlsplit(response.url).path == "/pass/kuaishou/sms/requestMobileCode", timeout=15000) as pending:
                        await control.click(timeout=5000)
                    await self._observe_sms_response(await pending.value)
                except ValueError:
                    raise
                except Exception:
                    await self._refresh_send_state()
            else:
                await control.click(timeout=5000)
                await self.page.wait_for_timeout(500)
                await self._refresh_send_state()
            if self.last_sms_error:
                raise ValueError(self.last_sms_error)
            if not self.sent:
                raise ValueError("短信发送尚未得到平台确认，请检查登录浏览器中的验证提示。")
            return {"success": True, "message": "平台已确认发送短信验证码，请查看手机短信"}
        if action != "submit" or not re.fullmatch(r"[0-9]{4,8}", code or ""):
            raise ValueError("请输入 4–8 位数字验证码")
        if not self.sent:
            raise ValueError("请先获取验证码")
        field = await visible_one(self.page.get_by_placeholder(re.compile("验证码")))
        await field.fill(code, timeout=3000)
        button = await visible_one(self.page.get_by_text(re.compile(r"^登\s*录$")))
        if not await button.is_enabled():
            raise ValueError("登录按钮不可用，请检查验证码和用户协议")
        await button.click(timeout=5000)
        return {"success": True, "message": "验证码已提交，正在等待平台登录结果"}

    async def verification_state(self):
        await self._refresh_send_state()
        text = await self.page.locator("body").inner_text()
        error = self.last_sms_error or next((line.strip() for line in text.splitlines() if re.search(r"验证码.*(?:错误|不正确|过期|失效)|验证失败|操作频繁|手机号.*(?:错误|不正确)", line)), "")
        return {"stage": "code" if self.sent else "choose", "phone": self.masked_phone,
                "resend_after": max(0, int(self.resend_at - asyncio.get_running_loop().time())), "error": error}

    async def poll_status(self, session_id):
        if session_id != self.session_id or not self.page:
            return LoginResult(LoginStatus.EXPIRED, "短信登录会话已过期")
        cookies = await self.context.cookies()
        names = {c["name"] for c in cookies if c.get("value")}
        login_inputs = self.page.get_by_placeholder(re.compile(r"手机号|登录手机"))
        login_visible = any([await login_inputs.nth(i).is_visible() for i in range(await login_inputs.count())])
        if AUTH_COOKIES[self.platform_name] & names and not login_visible and "login" not in self.page.url.lower():
            state = await self.context.storage_state()
            if self.platform_name == "douyin":
                from .douyin import DouyinAdapter
                user = await DouyinAdapter()._extract_user_info(self.page, cookies)
            elif self.platform_name == "kuaishou":
                from .kuaishou import KuaishouAdapter
                user = await KuaishouAdapter()._extract_user_info(self.page, cookies, state)
            elif self.platform_name == "xiaohongshu":
                from .xiaohongshu import XiaohongshuAdapter
                user = await XiaohongshuAdapter()._extract_user_info(self.page, cookies)
            else:
                uid = next((c["value"] for c in cookies if c["name"] == "DedeUserID"), None)
                user = UserInfo(user_id=uid, name=uid)
            return LoginResult(LoginStatus.CONFIRMED, "短信登录成功", {c["name"]: c["value"] for c in cookies}, user, state)
        risk = await risk_control_detected(self.page, self.platform_name)
        return LoginResult(LoginStatus.RISK_CONTROL if risk else LoginStatus.WAITING,
                           risk or "等待短信验证码", verification=await self.verification_state())

    async def cleanup_session(self, session_id):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.page = self.context = self.browser = self.playwright = None
