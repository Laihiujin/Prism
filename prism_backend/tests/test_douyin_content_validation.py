"""Publishing must stop when the editor does not retain the requested content."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platforms.douyin.upload import DouyinUpload


class ContentValidationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.uploader = DouyinUpload()
        self.uploader._fill_title_best_effort = AsyncMock(return_value=True)
        self.uploader._enable_third_party_sync = AsyncMock()
        self.zone = SimpleNamespace(
            count=AsyncMock(return_value=1),
            is_visible=AsyncMock(return_value=True),
            click=AsyncMock(),
            inner_text=AsyncMock(return_value="A description\n#topic"),
        )
        suggestion = SimpleNamespace(count=AsyncMock(return_value=0))
        self.page = SimpleNamespace(
            locator=Mock(side_effect=lambda selector: SimpleNamespace(
                first=self.zone if selector == '.zone-container' else suggestion)),
            keyboard=SimpleNamespace(press=AsyncMock(), insert_text=AsyncMock(), type=AsyncMock()),
            wait_for_timeout=AsyncMock(),
        )

    async def test_title_editor_can_mount_after_initial_attempts(self):
        self.uploader._fill_title_best_effort.side_effect = [False, False, True]
        with patch('platforms.douyin.upload.asyncio.sleep', new=AsyncMock()):
            await self.uploader._fill_title_and_tags(
                self.page, 'title', ['topic', '#topic'], False, 'A description')
        self.assertEqual(self.uploader._fill_title_best_effort.await_count, 3)
        self.page.keyboard.insert_text.assert_awaited_once_with('A description\n')
        self.page.keyboard.type.assert_awaited_once_with('#topic')

    async def test_missing_title_stops_before_description_or_sync(self):
        self.uploader._fill_title_best_effort.return_value = False
        with patch('platforms.douyin.upload.asyncio.sleep', new=AsyncMock()):
            with self.assertRaisesRegex(RuntimeError, '标题'):
                await self.uploader._fill_title_and_tags(self.page, 'title', [])
        self.page.locator.assert_not_called()
        self.uploader._enable_third_party_sync.assert_not_awaited()

    async def test_lost_description_or_topic_stops_publication(self):
        for rendered in ('#topic', 'A description'):
            with self.subTest(rendered=rendered):
                self.zone.inner_text.return_value = rendered
                with self.assertRaises(RuntimeError):
                    await self.uploader._fill_title_and_tags(
                        self.page, 'title', ['topic'], True, 'A description')
        self.uploader._enable_third_party_sync.assert_not_awaited()

    async def test_unavailable_description_editor_stops_publication(self):
        self.zone.count.return_value = 0
        with self.assertRaisesRegex(RuntimeError, '输入框不可用'):
            await self.uploader._fill_title_and_tags(self.page, 'title', [], False, 'A description')
        self.page.keyboard.insert_text.assert_not_awaited()
