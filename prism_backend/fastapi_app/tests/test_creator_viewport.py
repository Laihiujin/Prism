"""Creator and login pages share the same human-operated viewport."""
import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from fastapi import HTTPException
from automation_worker.remote_login import login_page, viewport_frame, pointer_input, PointerInput


class CreatorViewportTests(unittest.IsolatedAsyncioTestCase):
    def session(self):
        page = Mock()
        page.is_closed.return_value = False
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


if __name__ == "__main__":
    unittest.main()
