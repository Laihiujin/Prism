"""Creator and login pages share the same human-operated viewport."""
import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from automation_worker.remote_login import login_page, viewport_frame, pointer_input, PointerInput, refresh_qrcode


class CreatorViewportTests(unittest.IsolatedAsyncioTestCase):
    def session(self):
        page = Mock()
        page.is_closed.return_value = False
        page.frames = []
        page.evaluate = AsyncMock(return_value={"width": 100, "height": 80})
        page.screenshot = AsyncMock(return_value=b"jpeg")
        page.mouse.move = AsyncMock()
        page.mouse.down = AsyncMock()
        page.mouse.up = AsyncMock()
        return {"type": "creator_center", "page": page,
                "created_at": asyncio.get_running_loop().time(), "expires_in": 3600}

    async def test_creator_frame_and_pointer_without_login_adapter(self):
        session = self.session()
        frame = await viewport_frame(session, "creator_test")
        self.assertEqual(frame["width"], 100)
        self.assertTrue(frame["image"].startswith("data:image/jpeg;base64,"))
        await pointer_input(session, "creator_test", PointerInput(action="down", x=.5, y=.5))
        await pointer_input(session, "creator_test", PointerInput(action="up", x=.5, y=.5))
        session["page"].mouse.down.assert_awaited_once()
        session["page"].mouse.up.assert_awaited_once()

    async def test_expired_and_closed_creator_rejected(self):
        session = self.session()
        session["created_at"] -= 3601
        with self.assertRaises(HTTPException) as error:
            login_page(session, "creator_test")
        self.assertEqual(error.exception.status_code, 410)
        session = self.session()
        session["page"].is_closed.return_value = True
        with self.assertRaises(HTTPException) as error:
            login_page(session, "creator_test")
        self.assertEqual(error.exception.status_code, 409)

    async def test_login_adapter_still_supported(self):
        session = self.session()
        page = session.pop("page")
        session.update(type="login", adapter=Mock(page=page))
        self.assertIs(login_page(session, "login_test"), page)

    async def test_refresh_keeps_page_adapter_and_session(self):
        session = self.session()
        page = session.pop('page')
        page.url = 'https://example.test/login'
        page.reload = AsyncMock()
        qr = Mock(wait_for=AsyncMock(), screenshot=AsyncMock(return_value=b'qr'))
        page.locator.return_value.first = qr
        adapter = Mock(page=page)
        session.update(type='login', adapter=adapter)
        result = await refresh_qrcode(session, 'same-session')
        self.assertEqual(result['session_id'], 'same-session')
        self.assertIs(session['adapter'], adapter)
        self.assertIs(login_page(session, 'same-session'), page)
        page.reload.assert_awaited_once()
        self.assertEqual(session['expires_in'], 3600)

    async def test_completed_login_cannot_be_refreshed(self):
        from app_new.platforms.base import LoginResult, LoginStatus
        session = self.session()
        session['type'] = 'login'
        session['terminal_result'] = LoginResult(status=LoginStatus.CONFIRMED)
        with self.assertRaises(HTTPException) as error:
            await refresh_qrcode(session, 'completed')
        self.assertEqual(error.exception.status_code, 409)

    async def test_refresh_tool_discovery_and_query_execution(self):
        from fastapi_app.services.agent_workflow_tools import build_workflow_tool_specs
        spec = next(s for s in build_workflow_tool_specs() if s.name == 'start_login_qrcode')
        self.assertIn('session_id', spec.parameters['properties'])
        client = Mock()
        client.request = AsyncMock(return_value=Mock(is_success=True, json=Mock(return_value={'success': True, 'qr_id': 'same'})))
        context = Mock(__aenter__=AsyncMock(return_value=client), __aexit__=AsyncMock())
        with patch('fastapi_app.services.agent_workflow_tools.httpx.AsyncClient', return_value=context):
            result = await spec.handler(platform='douyin', account_id='test', session_id='same')
        self.assertTrue(result['ok'])
        self.assertEqual(client.request.call_args.kwargs['params']['session_id'], 'same')


if __name__ == "__main__":
    unittest.main()
