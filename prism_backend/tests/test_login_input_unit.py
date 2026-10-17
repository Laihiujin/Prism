"""No browser/network/account data required for login input contracts."""
import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pydantic import TypeAdapter, ValidationError
from fastapi import HTTPException
from app_new.platforms.phone_login import PhoneLoginAdapter
from automation_worker.remote_login import PointerInput, pointer_input, viewport_frame


class Fields:
    def __init__(self, items=()):
        self.items = items
    async def count(self):
        return len(self.items)
    def nth(self, index):
        return self.items[index]


class LoginInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_platform_stage_and_submit_share_visible_frame_field(self):
        for platform in ('douyin', 'kuaishou', 'xiaohongshu', 'bilibili'):
            with self.subTest(platform=platform):
                button = SimpleNamespace(is_enabled=AsyncMock(return_value=True), click=AsyncMock(), is_visible=AsyncMock(return_value=True))
                scope = SimpleNamespace(get_by_text=lambda *a: Fields([button]))
                field = SimpleNamespace(is_visible=AsyncMock(return_value=True), is_enabled=AsyncMock(return_value=True), fill=AsyncMock(), locator=lambda *a: scope)
                hidden = SimpleNamespace(is_visible=AsyncMock(return_value=False))
                frame = SimpleNamespace(locator=lambda selector: SimpleNamespace(inner_text=AsyncMock(return_value='')) if selector == 'body' else Fields([hidden, field]), get_by_text=lambda *a, **k: Fields())
                page = SimpleNamespace(frames=[frame], locator=lambda *a: SimpleNamespace(inner_text=AsyncMock(return_value='')), get_by_text=lambda *a, **k: Fields())
                adapter = PhoneLoginAdapter(platform)
                adapter.page, adapter.session_id = page, 'fixture'
                self.assertFalse(adapter.sent)
                self.assertEqual((await adapter.verification_state())['stage'], 'code')
                await adapter.sms_action('fixture', 'submit', '123456')
                field.fill.assert_awaited_once_with('123456', timeout=3000)
                button.click.assert_awaited_once()
                adapter.last_sms_error = 'SMS rejected'
                self.assertEqual((await adapter.verification_state())['stage'], 'choose')
                with self.assertRaises(ValueError):
                    await adapter.sms_action('fixture', 'submit', '123456')

    async def test_ambiguous_missing_and_secondary_fields(self):
        adapter = PhoneLoginAdapter('kuaishou')
        field = SimpleNamespace(is_visible=AsyncMock(return_value=True), is_enabled=AsyncMock(return_value=True))
        frame = SimpleNamespace(locator=lambda selector: SimpleNamespace(inner_text=AsyncMock(return_value='')) if selector == 'body' else Fields([field, field]), get_by_text=lambda *a, **k: Fields())
        adapter.page = SimpleNamespace(frames=[frame], locator=lambda *a: SimpleNamespace(inner_text=AsyncMock(return_value='')), get_by_text=lambda *a, **k: Fields())
        self.assertIsNone(await adapter._code_target())
        adapter.sent = True
        self.assertEqual((await adapter.verification_state())['stage'], 'choose')
        frame.locator = lambda selector: SimpleNamespace(inner_text=AsyncMock(return_value='')) if selector == 'body' else Fields([])
        self.assertIsNone(await adapter._code_target())
        secondary = SimpleNamespace(locator=lambda *a: Fields([field]))
        adapter._secondary_verification = AsyncMock(return_value=secondary)
        self.assertEqual((await adapter.verification_state())['stage'], 'secondary')
        self.assertEqual((await adapter._code_target())[1], field)

    async def test_type_key_and_session_validation(self):
        schema = TypeAdapter(PointerInput)
        page = SimpleNamespace(is_closed=lambda: False, keyboard=SimpleNamespace(insert_text=AsyncMock(), press=AsyncMock()), mouse=SimpleNamespace(up=AsyncMock()))
        session = {'adapter': SimpleNamespace(page=page), 'created_at': asyncio.get_running_loop().time(), 'pointer_down': True}
        await pointer_input(session, 'fixture', schema.validate_python({'action': 'text', 'text': '123456'}))
        await pointer_input(session, 'fixture', schema.validate_python({'action': 'key', 'key': 'Shift+Tab'}))
        page.keyboard.insert_text.assert_awaited_once_with('123456')
        page.keyboard.press.assert_awaited_once_with('Shift+Tab')
        self.assertFalse(session['pointer_down'])
        for payload in ({'action': 'text', 'text': ''}, {'action': 'text', 'text': 'x'*4001}, {'action': 'key', 'key': 'BadKey'}, {'action': 'down', 'x': 2, 'y': 0}):
            with self.assertRaises(ValidationError):
                schema.validate_python(payload)
        session['created_at'] -= 601
        with self.assertRaises(HTTPException) as error:
            await pointer_input(session, 'fixture', schema.validate_python({'action': 'text', 'text': 'x'}))
        self.assertEqual(error.exception.status_code, 410)

    async def test_bare_seconds_countdown(self):
        adapter = PhoneLoginAdapter('xiaohongshu')
        adapter.page = SimpleNamespace(locator=lambda *a: SimpleNamespace(inner_text=AsyncMock(return_value='59s')))
        await adapter._refresh_send_state()
        self.assertTrue(adapter.sent)
        self.assertGreater(adapter.resend_at, asyncio.get_running_loop().time() + 57)

    async def test_frame_contains_focus_geometry_without_values(self):
        box = {'x': 10, 'y': 20, 'width': 100, 'height': 30}
        frame = SimpleNamespace(evaluate=AsyncMock(return_value=box))
        page = SimpleNamespace(frames=[frame], main_frame=frame, is_closed=lambda: False,
                               evaluate=AsyncMock(return_value={'width':800,'height':600}), screenshot=AsyncMock(return_value=b'fixture'))
        session = {'adapter': SimpleNamespace(page=page), 'created_at': asyncio.get_running_loop().time()}
        result = await viewport_frame(session, 'fixture')
        self.assertEqual(result['focus'], box)
        self.assertNotIn('value', result['focus'])

    async def test_iframe_focus_geometry(self):
        from automation_worker.remote_login import focused_input
        outer = SimpleNamespace(scroll_into_view_if_needed=AsyncMock(), bounding_box=AsyncMock(return_value={'x': 50, 'y': 70}))
        main = SimpleNamespace(evaluate=AsyncMock(return_value=None))
        child = SimpleNamespace(evaluate=AsyncMock(return_value={'x': 4,'y': 8,'width': 100,'height': 30}), frame_element=AsyncMock(return_value=outer))
        box = await focused_input(SimpleNamespace(frames=[main,child], main_frame=main))
        self.assertEqual((box['x'], box['y']), (54,78))
        outer.scroll_into_view_if_needed.assert_awaited_once()

    async def test_input_through_public_api_and_worker(self):
        import httpx
        from fastapi import FastAPI
        from automation_worker import worker
        from automation_worker.client import AutomationWorkerClient
        from fastapi_app.api.v1.auth import router as auth
        page = SimpleNamespace(is_closed=lambda: False, keyboard=SimpleNamespace(insert_text=AsyncMock(), press=AsyncMock()))
        sid, public = 'unit-input-worker', 'unit-input-api'
        worker.sessions[sid] = {'adapter': SimpleNamespace(page=page), 'created_at': asyncio.get_running_loop().time()}
        auth.login_sessions[public] = {'worker_session_id': sid}
        client = AutomationWorkerClient()
        await client.client.aclose()
        client.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=worker.app), base_url='http://worker')
        app = FastAPI()
        app.include_router(auth.router, prefix='/api/v1')
        try:
            with patch('automation_worker.client.get_worker_client', return_value=client):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://api') as api:
                    url = f'/api/v1/auth/qrcode/pointer/{public}'
                    for payload in ({'action':'text','text':'123456'}, {'action':'key','key':'Enter'}):
                        self.assertEqual((await api.post(url, json=payload)).status_code, 200)
                    self.assertEqual((await api.post(url, json={'action':'key','key':'BadKey'})).status_code, 422)
                    worker.sessions[sid]['created_at'] -= 601
                    self.assertEqual((await api.post(url, json={'action':'text','text':'x'})).status_code, 410)
            page.keyboard.insert_text.assert_awaited_once_with('123456')
            page.keyboard.press.assert_awaited_once_with('Enter')
        finally:
            worker.sessions.pop(sid, None)
            auth.login_sessions.pop(public, None)
            await client.client.aclose()


if __name__ == '__main__':
    unittest.main()
