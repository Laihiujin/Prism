import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation_worker import worker
from app_new.platforms.base import LoginResult, LoginStatus, UserInfo
from app_new.platforms.douyin import DouyinAdapter
from fastapi_app.api.v1.auth import router as auth
from fastapi_app.api.v1.auth.schemas import LoginStatusResponse


class DeliveryTests(unittest.TestCase):
    def test_success_is_delivered_while_browser_cleanup_is_blocked(self):
        async def scenario():
            cleanup_finished = asyncio.Event()
            cleanup_started = asyncio.Event()
            class Adapter:
                polls = 0
                async def poll_status(self, sid):
                    self.polls += 1
                    return LoginResult(status=LoginStatus.CONFIRMED, cookies={"sessionid": "fixture"}, full_state={"cookies": []}, user_info=UserInfo(user_id="fixture-user"))
                async def cleanup_session(self, sid):
                    cleanup_started.set()
                    await cleanup_finished.wait()
            adapter = Adapter()
            session = {"adapter": adapter}
            worker.sessions["delivery-fixture"] = session
            try:
                first = await asyncio.wait_for(worker.poll_qrcode_status("delivery-fixture"), .5)
                await cleanup_started.wait()
                second = await worker.poll_qrcode_status("delivery-fixture")
                self.assertEqual(first["data"]["status"], "confirmed")
                self.assertEqual(second["data"]["full_state"], first["data"]["full_state"])
                self.assertEqual(adapter.polls, 1)
                self.assertFalse(session["terminal_cleanup_task"].done())
            finally:
                cleanup_finished.set()
                await session["terminal_cleanup_task"]
                worker.sessions.pop("delivery-fixture", None)
        asyncio.run(scenario())

    def test_adapter_does_not_remove_authenticated_browser_before_delivery(self):
        async def scenario():
            adapter = DouyinAdapter()
            page = AsyncMock()
            page.url = 'https://creator.douyin.com/creator-micro/home'
            page.get_by_text = Mock(return_value=Mock(count=AsyncMock(return_value=0)))
            context = AsyncMock()
            context.cookies.return_value = [{"name": "sessionid", "value": "fixture"}]
            context.storage_state.return_value = {"cookies": []}
            adapter._extract_user_info = AsyncMock(return_value=UserInfo(user_id="fixture-user"))
            adapter.cleanup_session = AsyncMock()
            with patch('app_new.platforms.douyin.douyin_session_manager.get_session', return_value={"page": page, "context": context}), patch('app_new.platforms.douyin_sms.inspect_sms', AsyncMock(return_value=(None, None))):
                progress = await adapter.poll_status("fixture")
                self.assertEqual(progress.status, LoginStatus.SCANNED)
                adapter._extract_user_info.assert_not_awaited()
                result = await adapter.poll_status("fixture")
            self.assertEqual(result.status, LoginStatus.CONFIRMED)
            adapter.cleanup_session.assert_not_awaited()
        asyncio.run(scenario())

    def test_overlapping_api_polls_persist_once(self):
        async def scenario():
            session = {}
            auth.login_sessions['delivery-public'] = session
            calls = []
            async def impl(sid):
                calls.append(sid)
                await asyncio.sleep(.02)
                auth.login_sessions.pop(sid, None)
                return LoginStatusResponse(success=True, status='confirmed')
            try:
                with patch.object(auth, '_poll_login_status_impl', impl):
                    responses = await asyncio.gather(auth.poll_login_status('delivery-public'), auth.poll_login_status('delivery-public'))
                self.assertEqual(calls, ['delivery-public'])
                self.assertTrue(all(r.status == 'confirmed' for r in responses))
            finally:
                auth.login_sessions.pop('delivery-public', None)
        asyncio.run(scenario())

    def test_confirmed_result_reaches_account_persistence(self):
        async def scenario():
            auth.login_sessions['save-fixture'] = {"platform": auth.PlatformType.DOUYIN, "account_id": "save-fixture"}
            client = Mock()
            client.poll_status = AsyncMock(return_value={
                "status": "confirmed", "cookies": {"sessionid": "fixture"},
                "full_state": {"cookies": []},
                "user_info": {"user_id": "fixture-user", "name": "Fixture", "avatar": "fixture-avatar"},
            })
            save = AsyncMock()
            try:
                with patch('automation_worker.client.get_worker_client', return_value=client), patch.object(auth, '_save_douyin_login', save):
                    result = await auth.poll_login_status('save-fixture')
                self.assertEqual(result.status, 'confirmed')
                save.assert_awaited_once()
                self.assertEqual(save.call_args.args[1]['cookies'], {"sessionid": "fixture"})
                self.assertNotIn('save-fixture', auth.login_sessions)
            finally:
                auth.login_sessions.pop('save-fixture', None)
        asyncio.run(scenario())


if __name__ == '__main__':
    unittest.main()
