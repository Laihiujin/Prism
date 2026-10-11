import unittest
from utils.automation_provider import async_playwright
from uploader.douyin_uploader.main import dismiss_horizontal_cover_prompt, deny_location_prompt

class CoverOverlayTests(unittest.IsolatedAsyncioTestCase):
    async def test_optional_prompt_closes_without_closing_cover_editor(self):
        async with async_playwright() as provider:
            browser = await provider.chromium.launch(channel="chrome", headless=True)
            try:
                context = await browser.new_context()
                page = await context.new_page()
                await deny_location_prompt(page)
                await page.set_content('<div role="dialog" id="editor"><button>Done</button></div><div role="dialog" id="hint"><h2>\u8bbe\u7f6e\u6a2a\u5c01\u9762\u83b7\u66f4\u591a\u6d41\u91cf</h2><button onclick="this.parentNode.remove()">\u6682\u4e0d\u8bbe\u7f6e</button></div>')
                await dismiss_horizontal_cover_prompt(page)
                self.assertEqual(await page.locator("#hint").count(), 0)
                self.assertEqual(await page.locator("#editor").count(), 1)
                await dismiss_horizontal_cover_prompt(page)
            finally:
                await browser.close()

if __name__ == "__main__":
    unittest.main()
