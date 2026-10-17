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
        self.identity_refresh_at = 0
        self.selected_account = None

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
            if self.platform_name == "douyin" and self.config.get("login_role") == "mcn":
                await (await visible_one(self.page.get_by_text("我是MCN机构", exact=True))).click(timeout=10000)
            if self.platform_name == "kuaishou":
                await self.page.get_by_text("立即登录", exact=True).wait_for(state="visible", timeout=20000)
                await (await visible_one(self.page.get_by_text("立即登录", exact=True))).click(timeout=10000)
            tabs = self.page.get_by_text(re.compile(r"^(短信登录|验证码登录|手机号登录)$"))
            for index in range(await tabs.count()):
                tab = tabs.nth(index)
                if await tab.is_visible():
                    await tab.click(timeout=3000)
                    break
            await self.page.locator('input[placeholder*="手机"]').first.wait_for(state="visible", timeout=20000)
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

    async def _identity_verification(self):
        if self.platform_name != "douyin":
            return False
        headings = self.page.get_by_text(re.compile(r"^(身份验证|使用原设备扫码|手机刷脸验证)$"))
        return any([await headings.nth(i).is_visible() for i in range(await headings.count())])

    async def _refresh_identity_qr(self):
        if not await self._identity_verification():
            raise ValueError("当前没有待完成的身份验证")
        heading = self.page.get_by_text("身份验证", exact=True)
        if await heading.count() and await heading.first.is_visible():
            entry = await visible_one(self.page.get_by_text("使用原设备扫码", exact=True))
            await entry.click(timeout=5000)
            return
        refreshers = self.page.get_by_text(re.compile(r"^(刷新二维码|点击刷新|点击刷新二维码|刷新|重新获取二维码)$"))
        for i in range(await refreshers.count()):
            button = refreshers.nth(i)
            if await button.is_visible():
                await button.click(timeout=5000)
                return
        # A valid QR does not need a new login session.

    async def _account_choices(self):
        if self.platform_name != "douyin" or await self._identity_verification():
            return []
        prompt = self.page.get_by_text(re.compile("所有关联账号.*请选择登录"))
        if not await prompt.count() or not await prompt.first.is_visible():
            return []
        choices = []
        labels = self.page.get_by_text(re.compile(r"^抖音号[：:]\s*[0-9]+$"))
        for i in range(await labels.count()):
            label = labels.nth(i)
            if not await label.is_visible():
                continue
            account_id = re.search(r"[0-9]+", await label.inner_text()).group()
            row = label.locator("xpath=ancestor::*[.//img][1]")
            lines = (await row.inner_text()).splitlines()
            name = next((line.strip() for line in lines if line.strip() and not re.match(r"抖音号[：:]", line.strip())), account_id)
            avatar = await row.locator("img").first.get_attribute("src")
            choices.append({"account_id": account_id, "name": name, "avatar": avatar or ""})
        return choices

    async def _secondary_verification(self):
        if self.platform_name != "kuaishou":
            return None
        for frame in getattr(self.page, "frames", [self.page]):
            headings = frame.get_by_text("手机号码验证", exact=True)
            for i in range(await headings.count()):
                heading = headings.nth(i)
                if await heading.is_visible():
                    return heading.locator("xpath=ancestor::*[.//input][1]")
        return None

    async def _send_control(self):
        controls = []
        for frame in getattr(self.page, "frames", [self.page]):
            matches = frame.get_by_text(re.compile(r"^(获取验证码|发送验证码|重新发送|重新获取|重新发送验证码)$"))
            for i in range(await matches.count()):
                control = matches.nth(i)
                if await control.is_visible():
                    controls.append(control)
        if len(controls) != 1:
            raise ValueError("未找到唯一的短信发送控件，请检查平台登录页")
        return controls[0]

    async def _code_target(self):
        """Use the same visible field for stage detection and submission.

        Placeholder matching follows douyin_sms and test_phone_login_flow;
        one-time-code follows platforms/publish_verification.py. Never choose
        an arbitrary input (phone/password/captcha) or a hidden background form.
        """
        secondary = await self._secondary_verification()
        scopes = [secondary] if secondary is not None else getattr(self.page, "frames", [self.page])
        targets = []
        for scope in scopes:
            fields = scope.locator('input[placeholder*="验证码"], input[autocomplete="one-time-code"]')
            for i in range(await fields.count()):
                field = fields.nth(i)
                if await field.is_visible() and await field.is_enabled():
                    targets.append((scope, field, secondary is not None))
        if len(targets) != 1:
            return None
        return targets[0]

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
                self.last_sms_error = "快手要求滑块验证，短信尚未发出。请在下方验证画面中完成验证。"
            elif data.get("result") is not None:
                self.sent = False
                self.resend_at = 0
                self.last_sms_error = "平台拒绝发送短信验证码，请检查手机号及平台提示。"
        except Exception:
            pass

    async def _refresh_send_state(self):
        text = "\n".join([await frame.locator("body").inner_text() for frame in getattr(self.page, "frames", [self.page])])
        countdown = re.search(r"(\d+)\s*(?:秒|s)\s*(?:后.*?(?:发送|获取|重发)|[)）]?$)", text, re.I | re.M)
        if countdown and not self.last_sms_error:
            self.sent = True
            self.resend_at = asyncio.get_running_loop().time() + int(countdown.group(1))
            self.last_sms_error = ""

    async def sms_action(self, session_id, action, code=None, account_choice=None):
        if session_id != self.session_id or not self.page:
            raise ValueError("短信登录会话已过期")
        if action == "identity_qr":
            await self._refresh_identity_qr()
            return {"success": True, "message": "已更新原设备扫码验证"}
        if action == "select_account":
            choices = await self._account_choices()
            if not account_choice or account_choice not in {item["account_id"] for item in choices}:
                raise ValueError("账号选择已失效，请重新获取当前账号列表")
            label = await visible_one(self.page.get_by_text(re.compile(r"^抖音号[：:]\s*" + re.escape(account_choice) + r"$")))
            await label.locator("xpath=ancestor::*[.//img][1]").click(timeout=5000)
            self.selected_account = next(item for item in choices if item["account_id"] == account_choice)
            return {"success": True, "message": "已选择账号，正在确认登录结果"}
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
                raise ValueError("短信尚未确认发送，请查看下方验证画面。")
            return {"success": True, "message": "平台已确认发送短信验证码，请查看手机短信"}
        if action != "submit" or not re.fullmatch(r"[0-9]{4,8}", code or ""):
            raise ValueError("请输入 4–8 位数字验证码")
        target = await self._code_target()
        if self.last_sms_error or (not self.sent and target is None):
            raise ValueError("请先获取验证码")
        if target is None:
            raise ValueError("未找到唯一的短信验证码输入框，请检查平台登录页")
        scope, field, secondary = target
        # The code's own wrapper can contain the SEND button. Ascend to the
        # submit label, rather than stopping at that smaller wrapper.
        labels = ("确定",) if secondary else ("登录",)
        predicate = " or ".join(f"translate(normalize-space(.), ' ', '')='{label}'" for label in labels)
        scope = field.locator(f"xpath=ancestor::*[.//*[{predicate}]][1]")
        await field.fill(code, timeout=3000)
        # Labels are often padded (Xiaohongshu renders " 登 录 "); anchor around the whitespace.
        button = await visible_one(scope.get_by_text(re.compile(r"^\s*确定\s*$" if secondary else r"^\s*登\s*录\s*$")))
        if not await button.is_enabled():
            raise ValueError("登录按钮不可用，请检查验证码和用户协议")
        await button.click(timeout=5000)
        return {"success": True, "message": "验证码已提交，正在等待平台登录结果"}

    async def verification_state(self):
        if await self._identity_verification():
            return {"stage": "platform_verification", "phone": self.masked_phone, "resend_after": 0, "error": "", "message": "请使用原设备扫码或手机刷脸完成身份验证"}
        choices = await self._account_choices()
        if choices:
            return {"stage": "account_selection", "phone": self.masked_phone, "resend_after": 0, "error": "", "accounts": choices}
        await self._refresh_send_state()
        text = await self.page.locator("body").inner_text()
        error = self.last_sms_error or next((line.strip() for line in text.splitlines() if re.search(r"验证码.*(?:错误|不正确|过期|失效)|验证失败|操作频繁|手机号.*(?:错误|不正确)", line)), "")
        secondary = await self._secondary_verification()
        target = await self._code_target()
        return {"stage": "secondary" if secondary is not None else "code" if target is not None and not self.last_sms_error else "choose", "phone": self.masked_phone,
                "resend_after": max(0, int(self.resend_at - asyncio.get_running_loop().time())), "error": error}

    async def poll_status(self, session_id):
        if session_id != self.session_id or not self.page:
            return LoginResult(LoginStatus.EXPIRED, "短信登录会话已过期")
        if await self._identity_verification():
            text = await self.page.locator("body").inner_text()
            expired = bool(re.search(r"二维码.*(?:失效|过期)|(?:失效|过期).*二维码", text))
            now = asyncio.get_running_loop().time()
            if expired and now - self.identity_refresh_at >= 5:
                self.identity_refresh_at = now
                try:
                    await self._refresh_identity_qr()
                except Exception:
                    return LoginResult(LoginStatus.RISK_CONTROL, "二维码刷新失败，请手动刷新", verification=await self.verification_state())
            return LoginResult(LoginStatus.RISK_CONTROL, "请使用原设备扫码完成身份验证", verification=await self.verification_state())
        choices = await self._account_choices()
        if choices:
            return LoginResult(LoginStatus.RISK_CONTROL, "请选择要登录的抖音账号", verification=await self.verification_state())
        cookies = await self.context.cookies()
        names = {c["name"] for c in cookies if c.get("value")}
        login_inputs = self.page.get_by_placeholder(re.compile(r"手机号|登录手机"))
        login_visible = any([await login_inputs.nth(i).is_visible() for i in range(await login_inputs.count())])
        if AUTH_COOKIES[self.platform_name] & names and not login_visible and "login" not in self.page.url.lower():
            state = await self.context.storage_state()
            if self.platform_name == "douyin":
                from .douyin import DouyinAdapter
                role = self.config.get("login_role", "creator")
                if role == "creator" and any(c["name"] == "oc_login_type" and c["value"] == "LOGIN_ORG" for c in cookies):
                    await self.context.clear_cookies(name="oc_login_type")
                    await self.page.goto("https://creator.douyin.com/creator-micro/home", wait_until="domcontentloaded", timeout=30000)
                    cookies = await self.context.cookies()
                # Passport completion can precede creator profile hydration.
                if "creator.douyin.com" not in self.page.url:
                    await self.page.goto("https://creator.douyin.com/creator-micro/home", wait_until="domcontentloaded", timeout=30000)
                try:
                    await self.page.locator("div[class*='unique_id-'], div[class*='nickname'], div[class*='name-']").first.wait_for(state="visible", timeout=8000)
                except Exception:
                    pass
                user = await DouyinAdapter()._extract_user_info(self.page, cookies)
                if self.selected_account:
                    user.user_id = user.user_id or self.selected_account["account_id"]
                    user.name = user.name or self.selected_account["name"]
                    user.avatar = user.avatar or self.selected_account["avatar"]
                if role == "mcn":
                    user.extra = {**(user.extra or {}), "account_type": "mcn", "profile_pending": not bool(user.name)}
                    user.name = user.name or "抖音MCN账号（资料待补全）"
                else:
                    user.extra = {**(user.extra or {}), "account_type": "creator"}
                state = await self.context.storage_state()
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
        if await self._secondary_verification() is not None:
            return LoginResult(LoginStatus.RISK_CONTROL,
                               "快手要求二次手机号验证，请在下方画面获取验证码，再在这里输入。",
                               verification=await self.verification_state())
        risk = await risk_control_detected(self.page, self.platform_name)
        return LoginResult(LoginStatus.RISK_CONTROL if risk else LoginStatus.WAITING,
                           risk or "等待短信验证码", verification=await self.verification_state())

    async def cleanup_session(self, session_id):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.page = self.context = self.browser = self.playwright = None
