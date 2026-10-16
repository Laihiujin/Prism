"""Human-operated browser viewport for an active login session."""
import asyncio
import base64
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field
from fastapi import HTTPException

class PointerInput(BaseModel):
    action: Literal['down', 'move', 'up', 'cancel']
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)

class TextInput(BaseModel):
    action: Literal['type']
    text: str = Field(min_length=1, max_length=4096)

class KeyInput(BaseModel):
    action: Literal['key']
    key: str = Field(max_length=100, pattern=r'^(?:(?:Control|Meta|Alt|Shift)\+)*(?:Backspace|Delete|Enter|Tab|Escape|ArrowLeft|ArrowRight|ArrowUp|ArrowDown|Home|End|PageUp|PageDown|[a-zA-Z0-9])$')

BrowserInput = Annotated[Union[PointerInput, TextInput, KeyInput], Field(discriminator='action')]

async def focused_input(page):
    """Scroll the focused editable into view; return geometry only, never values."""
    for frame in page.frames:
        box = await frame.evaluate('''() => {
            let e = document.activeElement;
            while (e?.shadowRoot?.activeElement) e = e.shadowRoot.activeElement;
            if (!e || !(e.matches('input,textarea') || e.isContentEditable)) return null;
            e.scrollIntoView({block:'nearest', inline:'nearest'});
            const r=e.getBoundingClientRect();
            return {x:r.x,y:r.y,width:r.width,height:r.height};
        }''')
        if box:
            if frame != page.main_frame:
                element = await frame.frame_element()
                await element.scroll_into_view_if_needed()
                outer = await element.bounding_box()
                if not outer:
                    continue
                box['x'] += outer['x']
                box['y'] += outer['y']
            return box
    return None

def login_page(session, sid):
    terminal = session.get('terminal_result')
    if terminal and getattr(terminal.status, 'value', terminal.status) != 'expired':
        raise HTTPException(410, '登录会话已结束')
    if asyncio.get_running_loop().time() - session.get('created_at', 0) > session.get('expires_in', 600):
        raise HTTPException(410, '登录会话已过期')
    adapter = session.get('adapter')
    page = session.get('page') if session.get('type') == 'creator_center' else getattr(adapter, 'page', None)
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
    focus = await focused_input(page)
    size = await page.evaluate('({width:innerWidth,height:innerHeight})')
    image = await page.screenshot(type='jpeg', quality=65, full_page=False)
    return {**size, 'focus': focus, 'image': 'data:image/jpeg;base64,' + base64.b64encode(image).decode()}

async def pointer_input(session, sid, event):
    page = login_page(session, sid)
    if event.action in ('type', 'key'):
        if session.get('pointer_down'):
            await page.mouse.up()
            session['pointer_down'] = False
        if event.action == 'type':
            await page.keyboard.insert_text(event.text)
        else:
            await page.keyboard.press(event.key)
        return {'success': True}
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


async def refresh_qrcode(session, sid):
    """Reload the existing login page, preserving browser/context/session identity."""
    from app_new.platforms.base import QRCodeData, LoginStatus
    if session.get('type') == 'creator_center':
        raise HTTPException(400, '创作者中心不是扫码登录会话')
    terminal = session.get('terminal_result')
    if terminal is not None and terminal.status != LoginStatus.EXPIRED:
        raise HTTPException(409, '登录已完成或失败，请重新开始登录')
    # An expired QR can be refreshed while its browser is still alive.
    previous = session.pop('terminal_result', None)
    session['created_at'] = asyncio.get_running_loop().time()
    try:
        page = login_page(session, sid)
        await page.reload(wait_until='domcontentloaded', timeout=20000)
        selector = 'img[aria-label="二维码"], img[alt*="二维码"], img[src*="qrcode"], .qrcode img, #animate_qrcode_container img, .qrcode canvas, canvas[id*="qrcode"], canvas[class*="qrcode"]'
        element = page.locator(selector).first
        await element.wait_for(state='visible', timeout=15000)
        image = 'data:image/png;base64,' + base64.b64encode(await element.screenshot(type='png')).decode()
        qr = QRCodeData(session_id=sid, qr_url=page.url, qr_image=image, expires_in=300)
        session['qr_data'] = qr
        session['expires_in'] = 3600
        return {'session_id': sid, 'qr_url': qr.qr_url, 'qr_image': image, 'expires_in': 300}
    except Exception:
        if previous is not None:
            session['terminal_result'] = previous
        raise
