"""Human-provided SMS codes for a live publishing browser, across platforms."""
import asyncio
import json
import logging
import re
from contextvars import ContextVar
from functools import wraps
from uuid import uuid4
from weakref import WeakKeyDictionary

publishing = ContextVar("publishing_verification", default=None)
locks = WeakKeyDictionary()


def publishing_upload(method):
    @wraps(method)
    async def wrapped(self, *args, **kwargs):
        settings = kwargs.get("platform_settings") or {}
        account = kwargs.get("account_file") or (args[0] if args else "")
        token = publishing.set({"platform": self.platform_code,
            "account": settings.get("_execution_account_id") or str(account),
            "task_id": settings.get("_execution_task_id")})
        try:
            return await method(self, *args, **kwargs)
        finally:
            publishing.reset(token)
    return wrapped


async def code_input(page):
    for frame in page.frames:
        candidates = frame.locator('input[autocomplete="one-time-code"], input[placeholder*="验证码"], input[placeholder*="verification code" i], input[placeholder*="security code" i]')
        for index in range(await candidates.count()):
            field = candidates.nth(index)
            if await field.is_visible() and await field.is_enabled():
                return field
    return None


async def verify_page(page, metadata, trigger_selector=None):
    from platforms.verification import verification_manager
    lock = locks.setdefault(page, asyncio.Lock())
    async with lock:
        field = await code_input(page)
        if field is None:
            return True
        scope = field.locator('xpath=ancestor::*[@role="dialog" or contains(@class,"modal")][1]')
        scope = scope if await scope.count() else field.locator('xpath=ancestor::body')
        trigger = scope.get_by_text(re.compile(r'^(获取验证码|发送验证码|获取短信验证码|Send code)$', re.I))
        if trigger_selector:
            trigger = page.locator(trigger_selector)
        for index in range(await trigger.count()):
            button = trigger.nth(index)
            if await button.is_visible() and await button.is_enabled():
                await button.click(timeout=5000)
                break
        length = await field.get_attribute("maxlength")
        length = int(length) if length and length.isdigit() and 4 <= int(length) <= 8 else 6
        request_id = str(uuid4())
        event = verification_manager.request_verification(request_id, metadata["platform"],
            "发布需要短信验证，请输入手机收到的验证码。", length,
            task_id=metadata.get("task_id"), account=metadata.get("account"))
        request_id = event["id"]
        event["can_resend"] = bool(await trigger.count())
        verification_manager.redis.set(verification_manager._key(request_id, "event"), json.dumps(event, ensure_ascii=False), ex=verification_manager.ttl)
        async def resend():
            for index in range(await trigger.count()):
                button = trigger.nth(index)
                if await button.is_visible() and await button.is_enabled():
                    await button.click(timeout=5000)
                    return
            logging.getLogger(__name__).info("SMS resend button is still unavailable")
        try:
            code = await verification_manager.wait_for_code(request_id, timeout=180, on_resend=resend)
            if not code or page.is_closed():
                return False
            await field.fill(code, timeout=5000)
            buttons = scope.locator('button, [role="button"], div.uc-ui-verify_sms-verify_button').filter(
                has_text=re.compile(r'^(验证|提交|确定|确认|继续|Verify|Confirm|Continue|Submit)$', re.I))
            for index in range(await buttons.count()):
                button = buttons.nth(index)
                if await button.is_visible() and await button.is_enabled():
                    await button.click(timeout=5000)
                    break
            await field.wait_for(state="hidden", timeout=15000)
            return True
        finally:
            verification_manager.cleanup_queue(request_id)


def attach_context(context, metadata=None):
    metadata = metadata or publishing.get()
    if not metadata:
        return context
    context.set_default_timeout(180000)
    tasks = set()
    watched = set()
    async def watch(page):
        try:
            while not page.is_closed():
                if await code_input(page) is not None:
                    if not await verify_page(page, metadata):
                        raise RuntimeError("发布验证码等待超时或验证未通过")
                    await asyncio.sleep(2)
                else:
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            page._prism_verification_error = type(error).__name__
            # No code, cookie, or platform DOM is logged.
            logging.getLogger(__name__).warning("Publishing verification watcher ended")
    def guard_waits(page):
        # Publishing confirmation waits must pause for the human reply instead
        # of letting a short URL/selector timeout close the verification browser.
        for name in ("wait_for_url", "wait_for_selector", "wait_for_timeout"):
            original = getattr(page, name)
            def guarded(method):
                async def wait(*args, **kwargs):
                    async def complete_verification():
                        if getattr(page, "_prism_verification_error", None):
                            raise RuntimeError("发布验证码等待超时或验证未通过")
                        lock = locks.get(page)
                        if (lock and lock.locked()) or await code_input(page) is not None:
                            if not await verify_page(page, metadata):
                                raise RuntimeError("发布验证码等待超时或验证未通过")
                            return True
                        return False
                    await complete_verification()
                    try:
                        return await method(*args, **kwargs)
                    except Exception as error:
                        if type(error).__name__ == "TimeoutError" and await complete_verification():
                            return await method(*args, **kwargs)
                        raise
                return wait
            setattr(page, name, guarded(original))

    def add(page):
        if page in watched:
            return
        watched.add(page)
        guard_waits(page)
        task = asyncio.create_task(watch(page))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        page.on("close", lambda *_: task.cancel())
    original_new_page = context.new_page
    async def new_page(*args, **kwargs):
        page = await original_new_page(*args, **kwargs)
        add(page)
        return page
    context.new_page = new_page
    context.on("page", add)
    context.on("close", lambda *_: [task.cancel() for task in list(tasks)])
    for page in context.pages:
        add(page)
    return context


def attach_browser(browser):
    metadata = publishing.get()
    if not metadata:
        return browser
    if getattr(browser, "_prism_verification_hook", False):
        return browser
    browser._prism_verification_hook = True
    original = browser.new_context
    async def new_context(*args, **kwargs):
        return attach_context(await original(*args, **kwargs), publishing.get() or metadata)
    browser.new_context = new_context
    return browser
