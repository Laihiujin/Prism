import asyncio
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platforms.base import BasePlatform
from platforms.publish_verification import attach_browser, publishing, verify_page
from platforms.verification import verification_manager
from platforms.verification import VerificationManager
from fastapi_app.cache.redis_client import get_redis
from utils.automation_provider import async_playwright


class PublishVerificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_shared_browser_code_delivery_and_isolation(self):
        redis = get_redis()
        redis.ping()
        prefix = "prism:verification:test:" + str(uuid4()) + ":"
        old_prefix = getattr(verification_manager, "prefix", "prism:verification:")
        old_index = getattr(verification_manager, "index_key", "prism:verification:pending")
        verification_manager.prefix = prefix
        verification_manager.index_key = prefix + "pending"
        self.addCleanup(setattr, verification_manager, "prefix", old_prefix)
        self.addCleanup(setattr, verification_manager, "index_key", old_index)
        receiver = VerificationManager(redis)
        receiver.prefix = prefix
        receiver.index_key = prefix + "pending"
        async with async_playwright() as p:
            browser = await p.chromium.launch(channel="chrome", headless=True)
            try:
                for platform in range(1, 9):
                    task_id = "otp-test-" + str(uuid4())
                    token = publishing.set({"platform": platform, "account": "fixture-account", "task_id": task_id})
                    try:
                        # The hook keeps the actual Browser object and its methods.
                        hooked = attach_browser(browser)
                        context = await hooked.new_context()
                    finally:
                        publishing.reset(token)
                    page = await context.new_page()
                    await page.set_content('<div role="dialog"><input placeholder="验证码" maxlength="6"><button onclick="this.parentNode.remove();document.body.dataset.verified=1">确定</button></div>')
                    event = None
                    for _ in range(50):
                        event = next((e for e in receiver.get_pending_events() if e.get("task_id") == task_id), None)
                        if event: break
                        await asyncio.sleep(.1)
                    self.assertIsNotNone(event, getattr(page, "_prism_verification_error", "watcher still pending"))
                    self.assertEqual(event["platform"], platform)
                    self.assertFalse(receiver.submit_code("unrelated-request", "123456"))
                    self.assertFalse(receiver.submit_code(event["id"], "1234"))
                    confirmation = asyncio.create_task(page.wait_for_selector("body[data-verified]", timeout=200))
                    await asyncio.sleep(.4)
                    self.assertFalse(confirmation.done(), "Human verification must pause the short publishing timeout")
                    self.assertTrue(receiver.submit_code(event["id"], "123456"))
                    await confirmation
                    await page.wait_for_function("document.body.dataset.verified === '1'", timeout=10000)
                    self.assertFalse(any(e.get("task_id") == task_id for e in receiver.get_pending_events()))
                    await context.close()
            finally:
                await browser.close()

    async def test_upload_scope_restored_on_failure(self):
        class Fixture(BasePlatform):
            async def login(self, account_id, **kwargs): pass
            async def upload(self, account_file, **kwargs):
                self.captured = publishing.get()
                raise ValueError("fixture")
        fixture = Fixture(4, "快手")
        with self.assertRaises(ValueError):
            await fixture.upload("fixture-cookie", platform_settings={"_execution_task_id": "task-fixture", "_execution_account_id": "account-fixture"})
        self.assertEqual(fixture.captured["task_id"], "task-fixture")
        self.assertEqual(fixture.captured["account"], "account-fixture")
        self.assertIsNone(publishing.get())


if __name__ == "__main__":
    unittest.main()
