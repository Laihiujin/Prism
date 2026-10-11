import os
import unittest
from utils.automation_provider import async_playwright


class EngineStorageRestoration(unittest.IsolatedAsyncioTestCase):
    async def test_storage_and_javascript_for_both_engines(self):
        paths = {engine: os.getenv("PRISM_TEST_" + engine.upper() + "_PATH") for engine in ("chromium", "firefox")}
        if not all(paths.values()):
            self.skipTest("Set PRISM_TEST_CHROMIUM_PATH and PRISM_TEST_FIREFOX_PATH")
        async with async_playwright() as runtime:
            for engine, path in paths.items():
                with self.subTest(engine=engine):
                    browser = await getattr(runtime, engine).launch(executable_path=path, headless=True)
                    try:
                        context = await browser.new_context(storage_state={"cookies": [], "origins": [{"origin": "https://example.org", "localStorage": [{"name": "account", "value": "preserved"}]}]})
                        page = await context.new_page()
                        await page.route("https://example.org/**", lambda route: route.fulfill(body="Storage regression", content_type="text/html"))
                        await page.goto("https://example.org")
                        self.assertEqual(await page.evaluate('localStorage.getItem("account")'), "preserved")
                    finally:
                        await browser.close()
