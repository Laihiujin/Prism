import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi import FastAPI
from automation_worker import worker
from automation_worker.client import AutomationWorkerClient
from fastapi_app.api.v1.auth import router as auth
from fastapi_app.api.v1.auth.schemas import PlatformType, SmsVerificationRequest


class SmsApiTests(unittest.TestCase):
    def test_phone_start_and_code_travel_through_api_and_worker(self):
        from app_new.platforms.base import QRCodeData
        calls = []
        class PhoneAdapter:
            def __init__(self, platform, config=None):
                self.platform = platform
            async def start(self, phone):
                calls.append((self.platform, "start", phone))
                return QRCodeData("phone-flow-fixture", "", "", 600)
            async def verification_state(self):
                return {"stage": "choose", "phone": "180****0000", "resend_after": 0, "error": ""}
            async def sms_action(self, sid, action, code=None):
                calls.append((self.platform, action, code))
                return {"success": True}
            async def cleanup_session(self, sid):
                pass
        async def run():
            app = FastAPI()
            app.include_router(auth.router, prefix="/api/v1")
            client = AutomationWorkerClient()
            await client.client.aclose()
            client.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=worker.app), base_url="http://worker")
            try:
                with patch("automation_worker.client.get_worker_client", return_value=client), patch("app_new.platforms.phone_login.PhoneLoginAdapter", PhoneAdapter):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as api:
                        for platform in ("kuaishou", "xiaohongshu"):
                            start = await api.post("/api/v1/auth/sms/start", json={"platform": platform, "account_id": "fixture-account", "phone": "18000000000"})
                            self.assertEqual(start.status_code, 200)
                            sid = start.json()["qr_id"]
                            self.assertEqual(start.json()["verification"]["stage"], "choose")
                            submit = await api.post("/api/v1/auth/qrcode/sms", json={"session_id": sid, "action": "submit", "code": "654321"})
                            self.assertEqual(submit.status_code, 200)
                            self.assertEqual(calls[-1], (platform, "submit", "654321"))
                        invalid = await api.post("/api/v1/auth/sms/start", json={"platform": "kuaishou", "account_id": "fixture", "phone": "invalid"})
                        self.assertEqual(invalid.status_code, 422)
            finally:
                await client.client.aclose()
                worker.sessions.pop("phone-flow-fixture", None)
                auth.login_sessions.pop("phone-flow-fixture", None)
        asyncio.run(run())

    def test_proxy_validation_and_session_isolation(self):
        class Adapter:
            def __init__(self):
                self.calls = []

            async def sms_action(self, session_id, action, code):
                self.calls.append((session_id, action, code))
                return {"success": True, "message": "submitted"}

        async def scenario():
            app = FastAPI()
            app.include_router(auth.router, prefix="/api/v1")
            adapter_a, adapter_b = Adapter(), Adapter()
            worker.sessions["sms-test-a"] = {"platform": "douyin", "adapter": adapter_a}
            worker.sessions["sms-test-b"] = {"platform": "douyin", "adapter": adapter_b}
            auth.login_sessions["sms-public-a"] = {"platform": PlatformType.DOUYIN, "worker_session_id": "sms-test-a"}
            client = AutomationWorkerClient()
            await client.client.aclose()
            client.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=worker.app), base_url="http://worker")
            try:
                with patch("automation_worker.client.get_worker_client", return_value=client):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as api:
                        result = await api.post('/api/v1/auth/qrcode/sms', json={"session_id": "sms-public-a", "action": "submit", "code": "123456"})
                        self.assertEqual(result.status_code, 200)
                        self.assertEqual(adapter_a.calls, [("sms-test-a", "submit", "123456")])
                        self.assertEqual(adapter_b.calls, [])
                        for payload in (
                            {"session_id": "sms-public-a", "action": "submit", "code": "abc"},
                            {"session_id": "sms-public-a", "action": "submit"},
                            {"session_id": "sms-public-a", "action": "unknown"},
                        ):
                            self.assertEqual((await api.post('/api/v1/auth/qrcode/sms', json=payload)).status_code, 422)
                        self.assertEqual((await api.post('/api/v1/auth/qrcode/sms', json={"session_id": "expired", "action": "request"})).status_code, 404)
                        auth.login_sessions["sms-public-a"]["platform"] = PlatformType.KUAISHOU
                        self.assertEqual((await api.post('/api/v1/auth/qrcode/sms', json={"session_id": "sms-public-a", "action": "request"})).status_code, 200)
            finally:
                await client.client.aclose()
                auth.login_sessions.pop("sms-public-a", None)
                worker.sessions.pop("sms-test-a", None)
                worker.sessions.pop("sms-test-b", None)
        asyncio.run(scenario())
        self.assertNotIn("123456", repr(SmsVerificationRequest(session_id="test", action="submit", code="123456")))


if __name__ == "__main__":
    unittest.main()
