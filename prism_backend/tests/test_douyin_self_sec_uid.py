import unittest
from unittest.mock import patch
from utils.automation_provider import async_playwright
from fastapi_app.api.v1.analytics.douyin_browser_collector import resolve_browser_self_sec_uid

class SelfProfileTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_accepts_matching_authenticated_self(self):
        async with async_playwright() as provider:
            async def context_factory(*args, **kwargs):
                browser = await provider.chromium.launch(channel="chrome", headless=True)
                context = await browser.new_context()
                async def route(request):
                    if "/user/profile/self/" in request.request.url:
                        await request.fulfill(json={"user": {"unique_id": "fixture-id", "sec_uid": "MS4fixture"}})
                    else:
                        await request.fulfill(content_type="text/html", body='<script>fetch("/aweme/v1/web/user/profile/self/")</script>')
                await context.route("https://www.douyin.com/**", route)
                return browser, context, None, None
            with patch("fastapi_app.api.v1.analytics.douyin_browser_collector.create_context_with_policy", side_effect=context_factory):
                self.assertEqual(await resolve_browser_self_sec_uid({}, "fixture-id"), "MS4fixture")
                self.assertIsNone(await resolve_browser_self_sec_uid({}, "another-account"))

if __name__ == "__main__":
    unittest.main()
