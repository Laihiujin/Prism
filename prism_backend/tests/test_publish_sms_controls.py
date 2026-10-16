"""Local browser fixtures; no platform network requests or real SMS messages."""
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patchright.async_api import async_playwright
from platforms.publish_verification import verify_page


class PublishSmsControlsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(channel='chrome', headless=True)
        self.page = await self.browser.new_page()
        self.manager = SimpleNamespace(
            ttl=1800, redis=Mock(), _key=lambda *args: 'fixture-key',
            request_verification=Mock(return_value={'id': 'fixture'}),
            wait_for_code=AsyncMock(return_value='123456'), cleanup_queue=Mock(),
        )
        self.manager_patch = patch('platforms.verification.verification_manager', self.manager)
        self.manager_patch.start()

    async def asyncTearDown(self):
        self.manager_patch.stop()
        await self.browser.close()
        await self.playwright.stop()

    async def test_douyin_verification_success_and_resend(self):
        await self.page.set_content('''<section role="dialog"><h2>接收短信验证码</h2>
<p>短信已发送至 176******30</p><input placeholder="请输入验证码" maxlength="6">
<button onclick="document.body.dataset.resent='yes'">重新发送</button>
<button onclick="this.parentNode.remove()">验证</button></section>''')

        async def reply(request_id, *, timeout, on_resend):
            self.assertEqual(timeout, 1800)
            await on_resend()
            return '123456'

        self.manager.wait_for_code.side_effect = reply
        self.assertTrue(await verify_page(self.page, {'platform': 3, 'account': 'fixture'}))
        self.assertTrue(self.page._prism_publish_verified)
        self.assertEqual(await self.page.locator('body').get_attribute('data-resent'), 'yes')
        self.manager.cleanup_queue.assert_called_once_with('fixture')

    async def test_platform_validation_error_does_not_mark_verified(self):
        await self.page.set_content('''<section role="dialog"><h2>接收短信验证码</h2>
<p>短信已发送至 176******30</p><input placeholder="请输入验证码">
<button onclick="document.querySelector('#error').textContent='验证码错误，请重试'">验证</button>
<p id="error"></p></section>''')
        with self.assertRaisesRegex(RuntimeError, '验证码错误'):
            await verify_page(self.page, {'platform': 3})
        self.assertFalse(getattr(self.page, '_prism_publish_verified', False))
        self.manager.cleanup_queue.assert_called_once()

    async def test_unlabelled_platform_confirm_control_is_clicked(self):
        await self.page.set_content('''<div role="dialog"><input placeholder="验证码">
<div class="uc-ui-verify_sms-verify_button" onclick="this.parentNode.remove()"><span>确认发布</span></div></div>''')
        self.assertTrue(await verify_page(self.page, {'platform': 2}))
        self.assertTrue(self.page._prism_publish_verified)

    async def test_missing_confirm_button_stops_instead_of_claiming_success(self):
        await self.page.set_content('<div role="dialog"><input placeholder="验证码"></div>')
        with self.assertRaisesRegex(RuntimeError, '未找到可用'):
            await verify_page(self.page, {'platform': 2})
        self.assertFalse(getattr(self.page, '_prism_publish_verified', False))

    async def test_no_user_reply_expires_and_cleans_up(self):
        await self.page.set_content('<div role="dialog"><input placeholder="验证码"></div>')
        self.manager.wait_for_code.return_value = None
        self.assertFalse(await verify_page(self.page, {'platform': 3}))
        self.manager.cleanup_queue.assert_called_once()
