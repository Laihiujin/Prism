import unittest
from unittest.mock import AsyncMock, Mock
from app_new.platforms.browser_manual import TikTokBrowserAdapter, YouTubeBrowserAdapter, BilibiliBrowserAdapter
from app_new.platforms.base import LoginStatus


class BrowserManualLoginTests(unittest.IsolatedAsyncioTestCase):
    def adapter(self, cls, url, cookies):
        adapter = cls()
        page = Mock(url=url)
        page.is_closed.return_value = False
        adapter.page = page
        adapter.context = Mock(pages=[page], cookies=AsyncMock(return_value=cookies), storage_state=AsyncMock(return_value={"cookies": cookies, "origins": []}))
        return adapter

    async def test_tiktok_requires_creator_page_and_authenticated_identity(self):
        cookies = [{"name": "sessionid", "value": "fixture", "domain": ".tiktok.com"}, {"name": "uid_tt", "value": "fixture-user", "domain": ".tiktok.com"}]
        adapter = self.adapter(TikTokBrowserAdapter, 'https://www.tiktok.com/', cookies)
        self.assertEqual((await adapter.poll_status('fixture')).status, LoginStatus.WAITING)
        adapter.page.url = 'https://www.tiktok.com/tiktokstudio'
        result = await adapter.poll_status('fixture')
        self.assertEqual(result.status, LoginStatus.CONFIRMED)
        self.assertEqual(result.user_info.user_id, 'fixture-user')

    async def test_youtube_requires_channel_identity_in_studio(self):
        cookies = [{"name": "SAPISID", "value": "fixture", "domain": ".youtube.com"}]
        adapter = self.adapter(YouTubeBrowserAdapter, 'https://accounts.google.com/signin', cookies)
        self.assertEqual((await adapter.poll_status('fixture')).status, LoginStatus.WAITING)
        adapter.page.url = 'https://studio.youtube.com/channel/UCfixture'
        self.assertEqual((await adapter.poll_status('fixture')).user_info.user_id, 'UCfixture')

    async def test_cookie_domain_must_match_platform(self):
        cookies = [{"name": "SESSDATA", "value": "fixture", "domain": ".notbilibili.com"}, {"name": "DedeUserID", "value": "fixture-user", "domain": ".notbilibili.com"}]
        adapter = self.adapter(BilibiliBrowserAdapter, 'https://passport.bilibili.com/login', cookies)
        self.assertEqual((await adapter.poll_status('fixture')).status, LoginStatus.WAITING)

    async def test_bilibili_preserves_real_browser_state_for_persistence(self):
        cookies = [{"name": "SESSDATA", "value": "fixture", "domain": ".bilibili.com"}, {"name": "DedeUserID", "value": "fixture-user", "domain": ".bilibili.com"}]
        adapter = self.adapter(BilibiliBrowserAdapter, 'https://passport.bilibili.com/login', cookies)
        result = await adapter.poll_status('fixture')
        self.assertEqual(result.status, LoginStatus.CONFIRMED)
        self.assertEqual(result.full_state['cookies'], cookies)
