import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platforms.douyin.upload import DouyinUpload, _submission_response_summary


class PublishResumeTests(unittest.IsolatedAsyncioTestCase):
    def test_response_summary_excludes_credentials_and_personal_data(self):
        self.assertEqual(_submission_response_summary({
            'status_code': 0, 'token': 'secret', 'message': 'phone or code',
            'data': {'error_code': 12, 'cookie': 'secret'},
            'base_resp': {'code': 1, 'verify_ticket': 'secret'},
        }), {'status_code': 0, 'data': {'error_code': 12}, 'base_resp': {'code': 1}})

    async def test_each_watcher_confirmation_can_resume_submission(self):
        class Button:
            clicks = 0
            async def wait_for(self, **kwargs): pass
            async def is_visible(self): return True
            async def is_enabled(self): return True
            async def click(self, **kwargs):
                self.clicks += 1
                if self.clicks == 3:
                    page.url = 'https://creator.douyin.com/creator-micro/content/manage'

        class Page:
            url = 'https://creator.douyin.com/creator-micro/content/post/video'
            _prism_publish_verified = False
            def on(self, *args): pass
            def get_by_role(self, *args, **kwargs): return button
            async def wait_for_timeout(self, timeout):
                # The shared watcher may finish verification during this wait.
                self._prism_publish_verified = True

        page, button = Page(), Button()
        uploader = DouyinUpload()
        uploader._wait_cover_modal_closed = AsyncMock()
        uploader._force_close_declaration_modal = AsyncMock()
        with patch('platforms.douyin.upload.dismiss_publish_guides', new=AsyncMock()), \
             patch('platforms.douyin.upload.asyncio.sleep', new=AsyncMock()):
            await uploader._publish_video(page)
        self.assertEqual(button.clicks, 3)
        self.assertFalse(page._prism_publish_verified)

    async def test_repeated_sms_after_resume_stops_before_requesting_another_code(self):
        button = type('Button', (), {})()
        button.wait_for = AsyncMock()
        button.is_visible = AsyncMock(return_value=True)
        button.is_enabled = AsyncMock(return_value=True)
        button.click = AsyncMock()
        verification = type('Verification', (), {})()
        verification.count = AsyncMock(return_value=1)
        verification.first = type('Visible', (), {'is_visible': AsyncMock(return_value=True)})()
        page = type('Page', (), {
            'url': 'https://creator.douyin.com/creator-micro/content/post/video',
            '_prism_publish_verified': True,
            'on': lambda *args: None,
            'get_by_role': lambda *args, **kwargs: button,
            'get_by_text': lambda *args, **kwargs: verification,
        })()
        uploader = DouyinUpload()
        uploader._wait_cover_modal_closed = AsyncMock()
        uploader._force_close_declaration_modal = AsyncMock()
        uploader._debug_dump = AsyncMock()
        uploader._check_and_handle_verification = AsyncMock()
        with patch('platforms.douyin.upload.dismiss_publish_guides', new=AsyncMock()), \
             patch('platforms.douyin.upload.asyncio.sleep', new=AsyncMock()):
            with self.assertRaisesRegex(RuntimeError, '再次要求短信'):
                await uploader._publish_video(page, account_id='fixture')
        self.assertEqual(button.click.await_count, 2)
        uploader._check_and_handle_verification.assert_not_awaited()
        uploader._debug_dump.assert_awaited_once()
