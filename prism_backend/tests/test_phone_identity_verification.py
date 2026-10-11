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

    def test_selected_profile_survives_empty_post_login_profile(self):
        from unittest.mock import AsyncMock, patch
        from app_new.platforms.base import UserInfo, LoginStatus
        async def run():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(channel="chrome", headless=True)
                context = await browser.new_context()
                await context.add_cookies([{"name": "sessionid", "value": "fixture-only", "domain": "creator.douyin.com", "path": "/"}])
                page = await context.new_page()
                await page.route("https://creator.douyin.com/**", lambda route: route.fulfill(body='<div class="name-loading">已登录</div>', content_type="text/html"))
                await page.goto("https://creator.douyin.com/creator-micro/home")
                adapter = PhoneLoginAdapter("douyin")
                adapter.page, adapter.context, adapter.session_id = page, context, "profile-fixture"
                adapter.selected_account = {"account_id": "12345", "name": "选中的账号", "avatar": "https://example.com/avatar.jpg"}
                with patch("app_new.platforms.douyin.DouyinAdapter._extract_user_info", new=AsyncMock(return_value=UserInfo())):
                    result = await adapter.poll_status("profile-fixture")
                self.assertEqual(result.status, LoginStatus.CONFIRMED)
                self.assertEqual(result.user_info.user_id, "12345")
                self.assertEqual(result.user_info.name, "选中的账号")
                self.assertEqual(result.user_info.avatar, "https://example.com/avatar.jpg")
                await browser.close()
        asyncio.run(run())
