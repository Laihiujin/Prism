import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patchright.async_api import async_playwright
from app_new.platforms.phone_login import PhoneLoginAdapter


class IdentityVerificationTests(unittest.TestCase):
    def test_identity_overlay_takes_priority_and_expired_qr_refreshes(self):
        async def run():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(channel="chrome", headless=True)
                page = await browser.new_page()
                await page.set_content("""<p>所有关联账号，请选择登录</p>
                <div><img><p>甲</p><p>抖音号：12345</p></div>
                <section><h2>使用原设备扫码</h2><p>二维码已失效</p>
                <button onclick="document.body.dataset.refreshed=1">刷新二维码</button></section>""")
                adapter = PhoneLoginAdapter("douyin")
                adapter.page = page
                adapter.session_id = "fixture"
                self.assertEqual(await adapter._account_choices(), [])
                status = await adapter.poll_status("fixture")
                self.assertEqual(status.verification["stage"], "platform_verification")
                self.assertEqual(await page.locator("body").get_attribute("data-refreshed"), "1")
                await browser.close()
        asyncio.run(run())
