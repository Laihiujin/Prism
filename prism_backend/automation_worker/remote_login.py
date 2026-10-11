"""Human-operated browser viewport for an active login session."""
import asyncio
import base64
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import HTTPException

class PointerInput(BaseModel):
    action: Literal['down', 'move', 'up', 'cancel']
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)

def login_page(session, sid):
    if session.get('type') == 'creator_center' or session.get('terminal_result'):
        raise HTTPException(410, '登录会话已结束')
    if asyncio.get_running_loop().time() - session.get('created_at', 0) > session.get('expires_in', 600):
        raise HTTPException(410, '登录会话已过期')
    adapter = session['adapter']
    page = getattr(adapter, 'page', None)
    if page is None and session.get('platform') in ('douyin', 'kuaishou', 'xiaohongshu'):
        from app_new import session_manager
        manager = getattr(session_manager, session['platform'] + '_session_manager')
        page = (manager.get_session(sid) or {}).get('page')
    if page is None or page.is_closed():
        raise HTTPException(409, '当前登录会话没有可操作的浏览器')
    return page

async def viewport_frame(session, sid):
    page = login_page(session, sid)
    if session.get('pointer_down') and asyncio.get_running_loop().time() - session.get('pointer_at', 0) > 5:
        await page.mouse.up()
        session['pointer_down'] = False
    size = await page.evaluate('({width:innerWidth,height:innerHeight})')
    image = await page.screenshot(type='jpeg', quality=65, full_page=False)
    return {**size, 'image': 'data:image/jpeg;base64,' + base64.b64encode(image).decode()}

async def pointer_input(session, sid, event):
    page = login_page(session, sid)
    size = await page.evaluate('({width:innerWidth,height:innerHeight})')
    # Release a stale drag when the client disappears, even without a cancel.
    now = asyncio.get_running_loop().time()
    if session.get('pointer_down') and now - session.get('pointer_at', now) > 5:
        await page.mouse.up()
        session['pointer_down'] = False
    if event.action == 'down' and session.get('pointer_down'):
        raise HTTPException(409, '已有拖动操作进行中')
    await page.mouse.move(event.x * (size['width'] - 1), event.y * (size['height'] - 1))
    if event.action == 'down':
        await page.mouse.down()
        session['pointer_down'] = True
    elif event.action in ('up', 'cancel'):
        await page.mouse.up()
        session['pointer_down'] = False
    session['pointer_at'] = now
    return {'success': True}
