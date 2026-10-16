import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_new.platforms.phone_login import PhoneLoginAdapter
from app_new.platforms.base import LoginStatus
from patchright.async_api import async_playwright


class PhoneLoginTests(unittest.TestCase):
    def test_kuaishou_challenge_response_does_not_claim_sms_sent(self):
        async def run():
            adapter = PhoneLoginAdapter("kuaishou")
            # phone_login queries the page through get_by_text / get_by_placeholder,
            # so the stub must expose those too, not just locator().
            page_stub = SimpleNamespace(
                locator=lambda selector: SimpleNamespace(
                    count=AsyncMock(return_value=0),
                    inner_text=AsyncMock(return_value="获取验证码"),
                    first=SimpleNamespace(is_visible=AsyncMock(return_value=False)),
                )
            )
            page_stub.get_by_text = lambda *args, **kwargs: page_stub.locator(None)
            page_stub.get_by_placeholder = lambda *args, **kwargs: page_stub.locator(None)
            adapter.page = page_stub
            response = SimpleNamespace(url="https://passport.kuaishou.com/pass/kuaishou/sms/requestMobileCode", json=AsyncMock(return_value={"result": 400002, "error_msg": "需要进行滑块验证"}))
            await adapter._observe_sms_response(response)
            state = await adapter.verification_state()
            self.assertFalse(adapter.sent)
            self.assertEqual(state["stage"], "choose")
            self.assertEqual(state["resend_after"], 0)
            self.assertIn("短信尚未发出", state["error"])
            response.json = AsyncMock(return_value={"result": 1})
            await adapter._observe_sms_response(response)
            self.assertTrue(adapter.sent)
            self.assertEqual((await adapter.verification_state())["error"], "")
        asyncio.run(run())

    def test_sms_submit_and_visitor_cookie_are_not_login_success(self):
        async def run():
            async with async_playwright() as p:
                browser = await p.chromium.launch(channel="chrome", headless=True)
                try:
                    for platform in ("douyin", "kuaishou", "xiaohongshu", "bilibili"):
                        page = await browser.new_page()
                        await page.set_content('''<input placeholder="请输入手机号"><div><input placeholder="请输入验证码">
                            <button onclick="this.innerText='60秒后重新发送'">获取验证码</button></div>
                            <button onclick="document.body.dataset.received=document.querySelector('input[placeholder*=验证码]').value">登录</button>''')
                        adapter = PhoneLoginAdapter(platform)
                        adapter.page = page
                        adapter.session_id = "fixture"
                        adapter.context = SimpleNamespace(cookies=AsyncMock(return_value=[{"name": "a1", "value": "visitor"}]))
                        self.assertEqual((await adapter.verification_state())["stage"], "code")
                        await adapter.sms_action("fixture", "request")
                        self.assertEqual((await adapter.verification_state())["stage"], "code")
                        with self.assertRaises(ValueError):
                            await adapter.sms_action("fixture", "resend")
                        with self.assertRaises(ValueError):
                            await adapter.sms_action("other-session", "submit", "123456")
                        await adapter.sms_action("fixture", "submit", "123456")
                        self.assertEqual(await page.locator('body').get_attribute('data-received'), "123456")
                        self.assertNotEqual((await adapter.poll_status("fixture")).status, LoginStatus.CONFIRMED)
                        await page.close()
                finally:
                    await browser.close()
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
