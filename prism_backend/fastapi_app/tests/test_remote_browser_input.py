"""Exercise the viewport against a real local browser and a synthetic page."""
import asyncio
import unittest
from pathlib import Path
from automation_worker.remote_login import PointerInput, pointer_input, viewport_frame


class RealBrowserInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_click_unicode_keyboard_wheel_and_frame(self):
        from utils.automation_provider import async_playwright
        executable = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        if not executable.exists():
            self.skipTest('Local Chrome is unavailable')
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=str(executable), headless=True)
            try:
                page = await browser.new_page(viewport={"width": 800, "height": 600})
                await page.set_content('<input id="field" style="position:absolute;left:40px;top:40px;width:250px;height:40px"><div style="height:3000px"></div>')
                session = {"type": "creator_center", "page": page, "created_at": asyncio.get_running_loop().time(), "expires_in": 600}
                for action in ('down', 'up'):
                    await pointer_input(session, 'fixture', PointerInput(action=action, x=.15, y=.1))
                await pointer_input(session, 'fixture', PointerInput(action='text', text='测试 abc'))
                self.assertEqual(await page.locator('#field').input_value(), '测试 abc')
                await pointer_input(session, 'fixture', PointerInput(action='key', key='Backspace'))
                self.assertEqual(await page.locator('#field').input_value(), '测试 ab')
                await pointer_input(session, 'fixture', PointerInput(action='wheel', delta_y=500))
                await page.wait_for_function('scrollY > 0')
                frame = await viewport_frame(session, 'fixture')
                self.assertEqual((frame['width'], frame['height']), (800, 600))
                self.assertTrue(frame['image'].startswith('data:image/jpeg;base64,'))
            finally:
                await browser.close()

    async def test_input_validation_rejects_unbounded_or_invalid_commands(self):
        from pydantic import ValidationError
        for payload in ({"action": "key", "key": "arbitrary"}, {"action": "text", "text": ""}, {"action": "wheel", "delta_y": float('inf')}):
            with self.assertRaises(ValidationError):
                PointerInput(**payload)


if __name__ == '__main__':
    unittest.main()
