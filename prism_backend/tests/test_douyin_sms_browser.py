"""Browser fixtures for the identity verification UI; never sends a real SMS."""
import asyncio
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_new.platforms.douyin_sms import inspect_sms, perform_sms_action
from patchright.async_api import async_playwright


CHOICE = '''<h2>身份验证</h2><button onclick="document.body.setAttribute('data-requested','true')">接收短信验证码</button><button>发送短信验证</button>'''
CODE = '''<section><h2>接收短信验证码</h2><p>短信已发送至 176******30</p>
<input placeholder="请输入验证码"><button id="resend" onclick="document.body.setAttribute('data-resent','true')">47s后重新发送</button>
<button onclick="document.body.setAttribute('data-submitted',document.querySelector('section input').value)">验证</button>
<p role="alert">验证码错误，请重试</p></section>'''


class SmsBrowserTests(unittest.TestCase):
    def test_verification_flow_and_frame_isolation(self):
        async def scenario():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(channel="chrome", headless=True)
                try:
                    page = await browser.new_page()
                    await page.set_content('<input placeholder="请输入验证码" id="background">' + CHOICE)
                    _, state = await inspect_sms(page)
                    self.assertEqual(state["stage"], "choose")
                    with self.assertRaises(ValueError):
                        await perform_sms_action(page, "submit", "123456")
                    await perform_sms_action(page, "request")
                    self.assertTrue(await page.locator('body').get_attribute('data-requested'))
                    await page.set_content('<input placeholder="请输入验证码" id="background">' + CODE)
                    _, state = await inspect_sms(page)
                    self.assertEqual(state["phone"], "176******30")
                    self.assertEqual(state["resend_after"], 47)
                    self.assertIn("错误", state["error"])
                    with self.assertRaises(ValueError):
                        await perform_sms_action(page, "resend")
                    with self.assertRaises(ValueError):
                        await perform_sms_action(page, "submit", "abcd")
                    await perform_sms_action(page, "submit", "123456")
                    self.assertEqual(await page.locator('body').get_attribute('data-submitted'), "123456")
                    self.assertEqual(await page.locator('#background').input_value(), "")
                    await page.locator('#resend').evaluate("e => e.textContent = '重新发送'")
                    await perform_sms_action(page, "resend")
                    self.assertTrue(await page.locator('body').get_attribute('data-resent'))
                    # Hidden stale verification must not keep the login blocked.
                    await page.set_content('<div style="display:none">' + CODE + '</div>')
                    self.assertIsNone((await inspect_sms(page))[1])
                    await page.set_content('<iframe></iframe>')
                    frame = page.frames[1]
                    await frame.set_content(CODE)
                    await perform_sms_action(page, "submit", "654321")
                    self.assertEqual(await frame.locator('body').get_attribute('data-submitted'), "654321")
                finally:
                    await browser.close()
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
