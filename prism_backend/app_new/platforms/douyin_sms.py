"""Relay user-provided SMS verification through the active Douyin browser."""
import re


async def inspect_sms(page):
    for frame in page.frames:
        try:
            state = await frame.evaluate("""() => {
                const visible = e => !!(e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
                const nodes = [...document.querySelectorAll('body *')];
                const title = nodes.find(e => visible(e) && e.textContent.trim() === '接收短信验证码' && ![...e.children].some(c => c.textContent.trim() === '接收短信验证码'));
                if (!title) return null;
                let root = title.parentElement;
                while (root && ![...root.querySelectorAll('input')].some(visible)) root = root.parentElement;
                const text = root?.innerText || '';
                if (text.includes('短信已发送至')) {
                    const phone = text.match(/1[0-9*•]{5,15}/)?.[0] || '';
                    const seconds = text.match(/(\\d+)\\s*(?:s|秒)\\s*后.*发送/)?.[1];
                    const error = text.split('\\n').find(t => /验证码.*(?:错误|不正确|过期|失效)|验证失败|操作频繁/.test(t)) || '';
                    return {stage: 'code', phone, resend_after: seconds ? Number(seconds) : 0, error};
                }
                const body = document.body.innerText;
                if (body.includes('身份验证') && body.includes('发送短信验证')) return {stage: 'choose', phone: '', resend_after: 0, error: ''};
                return null;
            }""")
            if state:
                return frame, state
        except Exception:
            continue
    return None, None


async def _visible(locator):
    for index in range(await locator.count()):
        candidate = locator.nth(index)
        if await candidate.is_visible():
            return candidate
    raise ValueError("当前页面未找到短信验证控件，请在登录浏览器中完成验证")


async def perform_sms_action(page, action, code=None):
    if action not in {"request", "resend", "submit"}:
        raise ValueError("不支持的短信验证操作")
    if action == "submit" and not re.fullmatch(r"[0-9]{4,8}", code or ""):
        raise ValueError("请输入 4–8 位数字验证码")
    frame, state = await inspect_sms(page)
    if not state:
        raise ValueError("当前登录会话不需要短信验证，请等待登录状态更新")
    if action == "request":
        if state["stage"] != "choose":
            raise ValueError("验证码已发送，请输入收到的验证码")
        await (await _visible(frame.get_by_text("接收短信验证码", exact=True))).click(timeout=3000)
        return {"success": True, "message": "已选择接收短信验证码，请查看手机短信"}
    if state["stage"] != "code":
        raise ValueError("请先选择接收短信验证码")
    title = await _visible(frame.get_by_text("接收短信验证码", exact=True))
    scope = title.locator("xpath=ancestor::*[.//input][1]")
    if action == "resend":
        if state["resend_after"] > 0:
            raise ValueError(f"请等待 {state['resend_after']} 秒后重新发送")
        control = await _visible(scope.get_by_text(re.compile(r"^(重新发送|重新获取|获取验证码)$")))
        if not await control.is_enabled():
            raise ValueError("暂时无法重新发送，请稍后重试")
        await control.click(timeout=3000)
        return {"success": True, "message": "已请求重新发送验证码"}
    field = await _visible(scope.get_by_placeholder(re.compile("验证码")))
    await field.fill(code, timeout=3000)
    control = await _visible(scope.get_by_text("验证", exact=True))
    if not await control.is_enabled():
        raise ValueError("验证码尚不能提交，请检查输入或在登录浏览器中完成验证")
    await control.click(timeout=3000)
    # Only the normal login poll may declare success and persist credentials.
    return {"success": True, "message": "验证码已提交，正在等待抖音验证结果"}
