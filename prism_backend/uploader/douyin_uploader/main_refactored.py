# -*- coding: utf-8 -*-
from datetime import datetime

import asyncio
import inspect
import os
import random
import sys
from pathlib import Path

from utils.automation_provider import Page, Playwright, async_playwright

from config.conf import BASE_DIR, DEBUG_MODE, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.base_social_media import set_init_script
from utils.login_qrcode import build_login_qrcode_path
from utils.login_qrcode import decode_qrcode_from_path
from utils.login_qrcode import print_terminal_qrcode
from utils.login_qrcode import remove_qrcode_file
from utils.login_qrcode import save_data_url_image
from utils.log import douyin_logger
from myUtils.browser_context import launch_optional_browser

DOUYIN_PUBLISH_STRATEGY_IMMEDIATE = "immediate"
DOUYIN_PUBLISH_STRATEGY_SCHEDULED = "scheduled"


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


async def _emit_qrcode_callback(qrcode_callback, payload: dict):
    if not qrcode_callback:
        return

    callback_result = qrcode_callback(payload)
    if inspect.isawaitable(callback_result):
        await callback_result


def _build_login_result(success: bool, status: str, message: str, account_file: str, qrcode: dict | None = None, current_url: str = "") -> dict:
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "qrcode": qrcode,
        "current_url": current_url,
    }


async def _read_verify_code(code_file: str) -> str:
    if os.path.exists(code_file):
        with open(code_file, encoding="utf-8") as file_obj:
            return file_obj.read().strip()

    if not sys.stdin or not sys.stdin.isatty():
        return ""

    try:
        return (await asyncio.to_thread(input, "请输入抖音短信验证码（直接回车可稍后重试）: ")).strip()
    except (EOFError, OSError):
        return ""


async def cookie_auth(account_file):
    # 抖音无头会撞反爬墙→content/upload 跳登录→误判 cookie 失效（间歇性）。校验必须有头。
    # 即便有头，页面慢/瞬时跳转仍会让 wait_for_url(精确URL,5s) 误判→重试3次+宽松判定(URL含 content/upload 且无登录文案)。
    # 允许 linux server 用户通过 env var 强制无头: DOUYIN_COOKIE_AUTH_HEADLESS=true
    use_headless = os.environ.get("DOUYIN_COOKIE_AUTH_HEADLESS", "").lower() in ("1", "true", "yes")
    launch_kwargs = {
        "headless": use_headless,
        "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    }
    if LOCAL_CHROME_PATH:
        launch_kwargs["executable_path"] = LOCAL_CHROME_PATH
    else:
        launch_kwargs["channel"] = "chrome"
    for _attempt in range(3):
        async with async_playwright() as playwright:
            browser = await launch_optional_browser(playwright, platform="douyin", **launch_kwargs)
            try:
                context = await browser.new_context(storage_state=account_file)
                context = await set_init_script(context)
                page = await context.new_page()
                await page.goto("https://creator.douyin.com/creator-micro/content/upload", wait_until="domcontentloaded", timeout=90000)
                await page.wait_for_timeout(2500)  # 等页面稳定，避免瞬时跳转误判
                has_login = await page.get_by_text("手机号登录").count() or await page.get_by_text("扫码登录").count()
                if "content/upload" in page.url and not has_login:
                    return True
            except Exception:
                pass
            finally:
                await browser.close()
    return False


async def douyin_setup(account_file, handle=False, return_detail=False, qrcode_callback=None, headless: bool = LOCAL_CHROME_HEADLESS, cdp_url: str | None = None):
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie文件不存在或已失效", account_file)
            return result if return_detail else False
        douyin_logger.info(_msg("🥹", "cookie 失效了，准备打开浏览器重新登录"))
        result = await douyin_cookie_gen(account_file, qrcode_callback=qrcode_callback, headless=headless, cdp_url=cdp_url)
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie有效", account_file)
    return result if return_detail else True


async def _extract_douyin_qrcode_src(page: Page) -> str:
    # 等 SPA 加载完成（不只等"扫码登录"文字，否则抖音慢加载时 30s 就超时）。
    # 给 domcontentloaded 后足够时间让客户端 JS 注入登录卡。
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    scan_login_tab = page.get_by_text("扫码登录", exact=True).first
    # attached 状态：DOM 里出现即可，不要求 visible/渲染完整，避免 race
    await scan_login_tab.wait_for(state="attached", timeout=60000)

    # 新版抖音创作者中心 (single_tab + animate_qrcode_container) 不再用 aria-label="二维码"。
    # 按优先级兜底多个 selector，至少一个能命中即可。
    qrcode_selectors = [
        'div#animate_qrcode_container img[src^="data:image"]',
        'div[class*="animate_qrcode_container"] img[src^="data:image"]',
        'div[class*="scan_qrcode_login_content"] img[src^="data:image"]',
        'img[aria-label="二维码"]',
    ]
    last_err: Exception | None = None
    for sel in qrcode_selectors:
        qrcode_img = page.locator(sel).first
        try:
            await qrcode_img.wait_for(state="attached", timeout=10000)
        except Exception as e:
            last_err = e
            continue
        src = await qrcode_img.get_attribute("src")
        if src:
            return src
        last_err = RuntimeError(f"selector {sel} 命中但 src 为空")

    raise RuntimeError(f"未获取到抖音登录二维码地址 (last_err={last_err})")


async def _save_douyin_qrcode(page: Page, account_file: str, previous_qrcode_path: Path | None = None, qrcode_callback=None) -> dict:
    # 提取二维码 src 仅为了保存/终端显示；定位不到时不致命——有头浏览器里二维码可见，直接扫码即可
    try:
        qrcode_src = await _extract_douyin_qrcode_src(page)
    except Exception as exc:
        douyin_logger.warning(_msg("😵", f"没定位到二维码元素（{str(exc)[:50]}）——请直接在弹出的浏览器里扫码，小人继续等登录跳转"))
        return {"image_path": "", "image_data_url": ""}
    qrcode_path = save_data_url_image(qrcode_src, build_login_qrcode_path(account_file))
    if previous_qrcode_path and previous_qrcode_path != qrcode_path:
        if remove_qrcode_file(previous_qrcode_path):
            douyin_logger.info(_msg("🧹", f"临时二维码文件已清理: {previous_qrcode_path}"))
    douyin_logger.info(_msg("🖼️", f"二维码已经准备好啦，已保存到: {qrcode_path}"))
    qrcode_content = decode_qrcode_from_path(qrcode_path)
    if qrcode_content:
        print_terminal_qrcode(qrcode_content, qrcode_path, "抖音APP")
    else:
        douyin_logger.warning(_msg("😵", f"终端没法完整显示二维码，请打开 {qrcode_path} 扫码"))
    qrcode_info = {
        "image_path": str(qrcode_path),
        "image_data_url": qrcode_src,
    }
    await _emit_qrcode_callback(qrcode_callback, qrcode_info)
    return qrcode_info


async def _is_douyin_login_completed(page: Page) -> bool:
    # 登录后会跳到 creator-micro 下任意页（home/content 等）；登录页是 creator.douyin.com/ 根路径
    if "creator.douyin.com/creator-micro" not in page.url:
        return False

    login_markers = [
        page.get_by_text("扫码登录", exact=True).first,
        page.get_by_text("手机号登录", exact=True).first,
        page.get_by_text("二维码失效", exact=True).first,
        page.get_by_role("img", name="二维码").first,
    ]

    for marker in login_markers:
        if not await marker.count():
            continue
        try:
            if await marker.is_visible():
                return False
        except Exception:
            continue

    return True


async def _wait_for_douyin_login(page: Page, account_file: str, qrcode_info: dict, qrcode_callback=None, poll_interval: int = 3, max_checks: int = 100) -> dict:
    qrcode_path = Path(qrcode_info["image_path"]) if qrcode_info.get("image_path") else None
    original_url = page.url
    saw_2fa = False
    for _ in range(max_checks):
        if await _is_douyin_login_completed(page):
            douyin_logger.info(_msg("🥳", f"扫码成功，已经跳转到登录后页面: {page.url}"))
            return _build_login_result(True, "success", "抖音扫码登录成功", account_file, qrcode_info, page.url)

        # URL 变化 + sessionid 未到位 → 二验流程，继续等
        if page.url != original_url and not await _is_douyin_login_completed(page):
            sms_input = page.locator('input[placeholder*="验证码"], input[type="tel"], input[placeholder*="短信"], input[placeholder*="手机号"]')
            if await sms_input.count() > 0:
                if not saw_2fa:
                    douyin_logger.warning(_msg("⚠️", f"检测到抖音短信/安全二次验证，请在弹出的浏览器中手动输入。等待 sessionid ({i}/{max_checks})"))
                    saw_2fa = True
            await asyncio.sleep(poll_interval)
            continue

        expired_box = page.get_by_text("二维码失效", exact=True).locator("..").first
        if await expired_box.count() and await expired_box.is_visible():
            douyin_logger.warning(_msg("😵", "二维码失效了，小人马上去刷新"))
            await expired_box.click()
            await asyncio.sleep(1)
            qrcode_info = await _save_douyin_qrcode(page, account_file, qrcode_path, qrcode_callback=qrcode_callback)
            qrcode_path = Path(qrcode_info["image_path"]) if qrcode_info.get("image_path") else None

        await asyncio.sleep(poll_interval)

    return _build_login_result(False, "timeout", "等待抖音扫码登录超时", account_file, qrcode_info, page.url)


async def douyin_cookie_gen(
    account_file,
    qrcode_callback=None,
    poll_interval: int = 2,
    max_checks: int = 60,
    headless: bool = LOCAL_CHROME_HEADLESS,
    cdp_url: str | None = None,
):
    async with async_playwright() as playwright:
        if cdp_url:
            from myUtils.browser_context import connect_browser_over_cdp
            browser = await connect_browser_over_cdp(playwright, cdp_url, platform="douyin")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            should_close_context = False
        else:
            launch_kwargs = {"headless": headless}
            if LOCAL_CHROME_PATH:
                launch_kwargs["executable_path"] = LOCAL_CHROME_PATH
            else:
                launch_kwargs["channel"] = "chromium"
            browser = await launch_optional_browser(playwright, platform="douyin", **launch_kwargs)
            context = await browser.new_context()
            should_close_context = True
        context = await set_init_script(context)
        qrcode_path = None
        result = _build_login_result(False, "failed", "抖音登录失败", account_file)
        try:
            page = await context.new_page()
            await page.goto("https://creator.douyin.com/")
            qrcode_info = await _save_douyin_qrcode(page, account_file, qrcode_callback=qrcode_callback)
            qrcode_path = Path(qrcode_info["image_path"]) if qrcode_info.get("image_path") else None
            douyin_logger.info(_msg("🧍", "请扫码，小人正在耐心等待登录完成"))
            result = await _wait_for_douyin_login(
                page,
                account_file,
                qrcode_info,
                qrcode_callback=qrcode_callback,
                poll_interval=poll_interval,
                max_checks=max_checks,
            )
            if result["success"]:
                await asyncio.sleep(2)
                await context.storage_state(path=account_file)
                if not await cookie_auth(account_file):
                    result = _build_login_result(
                        False,
                        "cookie_invalid",
                        "抖音扫码流程结束，但 cookie 校验失败",
                        account_file,
                        qrcode_info,
                        page.url,
                    )
        except Exception as exc:
            result = _build_login_result(False, "failed", str(exc), account_file, current_url=page.url if "page" in locals() else "")
        finally:
            if remove_qrcode_file(qrcode_path):
                douyin_logger.info(_msg("🧹", f"临时二维码文件已清理: {qrcode_path}"))
            if not result["success"]:
                douyin_logger.error(_msg("😢", f"登录失败: {result['message']}"))
            if should_close_context:
                await context.close()
            await browser.close()
        return result


class DouYinBaseUploader(BaseVideoUploader):
    def __init__(
        self,
        publish_date: datetime | int,
        account_file,
        publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
        preview_only: bool = False,
    ):
        self.publish_date = publish_date
        self.account_file = account_file
        self.publish_strategy = publish_strategy
        self.debug = debug
        # preview_only: 完整跑上传+表单填充，但在点击「发布」前停下，用于安全调试不真正发布。
        self.preview_only = preview_only
        self.date_format = "%Y年%m月%d日 %H:%M"
        self.local_executable_path = LOCAL_CHROME_PATH
        self.headless = headless

    async def validate_base_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"cookie文件不存在，请先完成抖音登录: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"cookie文件已失效，请先完成抖音登录: {self.account_file}")
        if self.publish_strategy not in {DOUYIN_PUBLISH_STRATEGY_IMMEDIATE, DOUYIN_PUBLISH_STRATEGY_SCHEDULED}:
            raise ValueError(f"不支持的发布策略: {self.publish_strategy}")

        if self.publish_strategy == DOUYIN_PUBLISH_STRATEGY_SCHEDULED:
            self.publish_date = self.validate_publish_date(self.publish_date)
        else:
            self.publish_date = 0

    async def set_schedule_time_douyin(self, page, publish_date):
        label_element = page.locator("[class^='radio']:has-text('定时发布')")
        await label_element.click()
        await asyncio.sleep(1)
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")

        await asyncio.sleep(1)
        await page.locator('.semi-input[placeholder="日期和时间"]').click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")
        await asyncio.sleep(1)

    async def fill_title_and_description(self, page: Page, title: str, description: str, tags: list[str] | None = None):
        # 2026-06 抖音发布页 DOM：标题=input[placeholder*=填写作品标题]，描述=div.zone-container[contenteditable]
        # version_2(post/video) 发布页要等视频上传完才渲染表单（实测约 40s），故等待超时给到 120s
        title_input = page.locator('input[placeholder*="填写作品标题"]').first
        await title_input.wait_for(state="visible", timeout=120000)
        await title_input.fill(title[:30])

        description_editor = page.locator('div.zone-container[contenteditable="true"]').first
        await description_editor.wait_for(state="visible", timeout=120000)
        await description_editor.click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.press("Delete")

        for tag in tags or []:
            # 严禁把多个话题拼成一串后 paste/type_text；每个话题独立逐字输入，
            # 再用一次 Space 确认，避免重复 ##、换行和候选浮层误选。
            expected_topic = "#" + str(tag).lstrip("#")
            await page.keyboard.type(expected_topic)
            # 中文输入法/富文本异常时，禁止紧接着按空格制造孤立「#」；
            # 必须先确认当前编辑器文本确实包含本次完整话题。
            current_text = await description_editor.inner_text()
            # 抖音富文本在话题节点后可能附加零宽空格(U+200B/200C/200D等)，先去不可见字符再校验，避免误判“未完整输入”
            _norm = "".join(
                ch for ch in current_text
                if not (0x200B <= ord(ch) <= 0x200D) and ch not in "\ufeff\u2060\xa0"
            ).rstrip()
            if not _norm.endswith(expected_topic):
                raise RuntimeError(f"话题未完整输入，停止确认空格: expected={expected_topic!r}, actual={current_text!r}")
            await page.keyboard.press("Space")
            await page.wait_for_timeout(200)
        await page.keyboard.press("Escape")  # 收起话题下拉，避免浮层拦截后续点击

    async def _select_topic_exact(self, page: Page, tag: str) -> bool:
        """在话题补全下拉中选中与 tag 文本一致、且字符数一致的项；必要时下滑重试。"""
        tag = tag.lstrip("#")
        desired_len = len(tag)
        for _ in range(4):
            picked = await page.evaluate(
                """(crit) => {
                    const [tag, desiredLen] = crit;
                    const sels = ['.topic-item', '.topic-list-item', '[class*="topic-item"]',
                                  '[class*="mention"]', '[role="option"]'];
                    for (const sel of sels) {
                        for (const el of document.querySelectorAll(sel)) {
                            const t = (el.innerText || el.getAttribute('aria-label') || '').replace(/^#/, '').trim();
                            if (t && t === tag && t.length === desiredLen) { el.click(); return true; }
                        }
                    }
                    return false;
                }""",
                [tag, desired_len],
            )
            if picked:
                await page.wait_for_timeout(200)
                return True
            await page.keyboard.press("ArrowDown")
            await page.wait_for_timeout(300)
        return False

    async def set_location(self, page: Page, location: str = ""):
        if not location:
            return
        await page.locator('div.semi-select span:has-text("输入地理位置")').click()
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(2000)
        await page.keyboard.type(location)
        await page.wait_for_selector('div[role="listbox"] [role="option"]', timeout=5000)
        await page.locator('div[role="listbox"] [role="option"]').first.click()

    async def handle_product_dialog(self, page: Page, product_title: str):
        await page.wait_for_timeout(2000)
        await page.wait_for_selector('input[placeholder="请输入商品短标题"]', timeout=10000)
        short_title_input = page.locator('input[placeholder="请输入商品短标题"]')
        if not await short_title_input.count():
            douyin_logger.error(_msg("😵", "没找到商品短标题输入框"))
            return False

        product_title = product_title[:10]
        await short_title_input.fill(product_title)
        await page.wait_for_timeout(1000)

        finish_button = page.locator('button:has-text("完成编辑")')
        if "disabled" not in await finish_button.get_attribute("class"):
            await finish_button.click()
            douyin_logger.debug(_msg("🥳", "已点击“完成编辑”按钮"))
            await page.wait_for_selector(".semi-modal-content", state="hidden", timeout=5000)
            return True

        douyin_logger.error(_msg("😵", "“完成编辑”按钮是灰的，小人先把弹窗关掉"))
        cancel_button = page.locator('button:has-text("取消")')
        if await cancel_button.count():
            await cancel_button.click()
        else:
            close_button = page.locator(".semi-modal-close")
            await close_button.click()
        await page.wait_for_selector(".semi-modal-content", state="hidden", timeout=5000)
        return False

    async def set_product_link(self, page: Page, product_link: str, product_title: str):
        await page.wait_for_timeout(2000)
        try:
            await page.wait_for_selector("text=添加标签", timeout=10000)
            dropdown = page.get_by_text("添加标签").locator("..").locator("..").locator("..").locator(".semi-select").first
            if not await dropdown.count():
                douyin_logger.error(_msg("😵", "没找到标签下拉框"))
                return False
            douyin_logger.debug(_msg("🧍", "找到标签下拉框，小人准备选择“购物车”"))
            await dropdown.click()
            await page.wait_for_selector('[role="listbox"]', timeout=5000)
            await page.locator('[role="option"]:has-text("购物车")').click()
            douyin_logger.debug(_msg("🥳", "已经选中“购物车”"))

            await page.wait_for_selector('input[placeholder="粘贴商品链接"]', timeout=5000)
            input_field = page.locator('input[placeholder="粘贴商品链接"]')
            await input_field.fill(product_link)
            douyin_logger.debug(_msg("🔗", f"商品链接已经填好了: {product_link}"))

            add_button = page.locator('span:has-text("添加链接")')
            button_class = await add_button.get_attribute("class")
            if "disable" in button_class:
                douyin_logger.error(_msg("😵", "“添加链接”按钮现在点不了"))
                return False
            await add_button.click()
            douyin_logger.debug(_msg("🥳", "已点击“添加链接”按钮"))

            await page.wait_for_timeout(2000)
            error_modal = page.locator("text=未搜索到对应商品")
            if await error_modal.count():
                confirm_button = page.locator('button:has-text("确定")')
                await confirm_button.click()
                douyin_logger.error(_msg("😢", "这个商品链接无效"))
                return False

            if not await self.handle_product_dialog(page, product_title):
                return False

            douyin_logger.debug(_msg("🥳", "商品链接设置好了"))
            return True
        except Exception as e:
            douyin_logger.error(_msg("😢", f"设置商品链接时出错: {str(e)}"))
            return False

    async def set_self_declaration(self, page: Page, declaration: str) -> bool:
        """按调用方给出的平台原文选择自主声明；失败返回 False。"""
        try:
            # 发布页底部「自主声明」行，未选时显示占位文案「请选择自主声明」
            entry = page.get_by_text("请选择自主声明").first
            await entry.wait_for(state="visible", timeout=6000)
            await entry.click()

            # 弹窗标题「对作品内容添加声明」
            dialog = page.locator(".semi-modal-content").filter(has_text="对作品内容添加声明").first
            await dialog.wait_for(state="visible", timeout=6000)

            # 单选项：Semi 的文字是 .semi-radio-addon（常带 pointer-events:none，直接点会卡 30s 超时），
            # 要点可交互的 .semi-radio 外层；找不到外层再退回 force 强制点文字。exact 避免误命中预览「作者声明：…」。
            option = dialog.locator(".semi-radio").filter(has_text=declaration).first
            if await option.count():
                await option.click(timeout=6000)
            else:
                await dialog.get_by_text(declaration, exact=True).first.click(timeout=6000, force=True)
            await dialog.get_by_role("button", name="确定").click(timeout=6000)
            await dialog.wait_for(state="hidden", timeout=6000)
            douyin_logger.info(_msg("🧾", f"自主声明已选择「{declaration}」"))
            return True
        except Exception as exc:
            douyin_logger.warning(_msg("🧾", f"自主声明设置失败：{exc}"))
            return False

    async def select_bgm(self, page: Page, bgm_name: str) -> bool:
        """为图文发布选择 BGM：可选增强功能，搜索无结果或异常均跳过不中断发布。"""
        try:
            # 点击「选择音乐」按钮
            music_entry = page.locator('text="选择音乐"').nth(1)
            if not await music_entry.count():
                music_entry = page.locator('text="选择音乐"').first
            await music_entry.wait_for(state="visible", timeout=10000)
            await music_entry.click()

            # 等待侧边栏出现并搜索
            sidesheet = page.locator(".semi-sidesheet-content").first
            await sidesheet.wait_for(state="visible", timeout=8000)
            search_input = sidesheet.locator('input.semi-input[placeholder="搜索音乐"]').first
            await search_input.wait_for(state="visible", timeout=5000)
            await search_input.fill(bgm_name)
            await search_input.press("Enter")

            # 等待搜索结果
            await asyncio.sleep(2)
            first_card = sidesheet.locator(".card-container-tmocjc").first
            try:
                await first_card.wait_for(state="visible", timeout=8000)
            except Exception:
                douyin_logger.warning(_msg("🎵", f"音乐「{bgm_name}」搜索结果为空，小人跳过"))
                await self._close_music_sidesheet(page)
                return False

            # 打印找到的音乐名称
            try:
                song_name_el = first_card.locator(".song-name-oRge4d").first
                if await song_name_el.count():
                    song_name = await song_name_el.inner_text()
                    douyin_logger.info(_msg("🎵", f"小人找到了: {song_name}"))
            except Exception:
                pass

            # JS 点击「使用」（按钮 visibility:hidden，普通 click 无效）
            apply_btn = first_card.locator(".apply-btn-LUPP0D").first
            await apply_btn.evaluate("el => el.click()")
            douyin_logger.info(_msg("🥳", f"BGM「{bgm_name}」已应用"))

            # 等待侧边栏关闭，超时则手动关闭
            try:
                await sidesheet.wait_for(state="hidden", timeout=5000)
            except Exception:
                await self._close_music_sidesheet(page)

            return True
        except Exception as exc:
            douyin_logger.warning(_msg("🎵", f"添加 BGM 时出错，跳过该步骤继续发布：{exc}"))
            try:
                await self._close_music_sidesheet(page)
            except Exception:
                pass
            return False

    async def _close_music_sidesheet(self, page: Page) -> None:
        try:
            close_btn = page.locator(".semi-sidesheet-close").first
            if await close_btn.count() and await close_btn.is_visible():
                await close_btn.click()
                await asyncio.sleep(1)
        except Exception:
            pass

    async def dismiss_version_prompt(self, page: Page) -> bool:
        """关闭抖音「官方新版本/新增功能/视频预览提示」弹窗（best-effort）。

        委托共享 utils.browser_dom：先点「我知道了/立即体验/跳过」等关闭按钮，再移除纯遮挡容器。
        用保守选择器（shepherd/mention/guide），避免 [class*='popup']/[class*='version'] 误删业务 DOM
        （否则标题输入框/编辑区会被清掉，导致后续 fill 超时）。
        """
        from utils.browser_dom import dismiss_version_prompt as _dismiss
        try:
            return await _dismiss(page)
        except Exception as exc:
            douyin_logger.debug(_msg("🗑️", f"版本提示移除未命中/跳过：{exc}"))
            return False

    async def _wait_for_video_uploaded(self, page: Page, max_polls: int = 120) -> bool:
        """等视频上传完成（出现「重新上传」即完成；出现「上传失败」返回 False）。"""
        from utils.browser_dom import wait_upload_complete
        try:
            return await wait_upload_complete(page, logger=douyin_logger, poll_interval=2.0, max_polls=max_polls)
        except Exception as exc:
            douyin_logger.debug(_msg("🧍", f"等待视频上传完成异常：{exc}"))
            return True

    async def _handle_browser_permission(self, page: Page, allow_location: bool, has_location: bool) -> None:
        """处理浏览器位置权限弹窗：有位置时点「本次允许」；没选位置时关闭/选择「不允许」。

        抖音发布页在需要定位时会弹浏览器 navigator.permissions 询问框（允许/仅本次/不允许）。
        有头模式会看到原生弹窗；无头 mode 一般直接授权。此处兜底：命中弹窗时按 has_location 决策。
        """
        try:
            # 已授权场景（context permissions 里给了 geolocation）不会有弹窗；这里只兜底检测。
            candidates = [
                page.get_by_text("允许", exact=True).first,
                page.get_by_text("仅本次", exact=True).first,
                page.get_by_text("仅此一次", exact=True).first,
                page.get_by_text("不允许", exact=True).first,
                page.get_by_text("关闭", exact=True).first,
            ]
            for c in candidates:
                if await c.count() and await c.is_visible():
                    douyin_logger.info(_msg("📍", f"检测到浏览器权限弹窗，has_location={has_location}"))
                    if has_location or allow_location:
                        # 点「仅本次」优先；没有则「允许」
                        pick = None
                        for t in ("仅本次", "仅此一次", "允许"):
                            try:
                                pick = page.get_by_text(t, exact=True).first
                                if await pick.count() and await pick.is_visible():
                                    await pick.click(timeout=2000)
                                    douyin_logger.info(_msg("📍", f"已点「{t}」"))
                                    return
                            except Exception:
                                continue
                        # 都没有则接受浏览器 dialog（交给 dialog handler 兜底）
                    else:
                        # 未选位置 → 关闭或不允许
                        for t in ("不允许", "关闭"):
                            try:
                                pick = page.get_by_text(t, exact=True).first
                                if await pick.count() and await pick.is_visible():
                                    await pick.click(timeout=2000)
                                    douyin_logger.info(_msg("📍", f"已点「{t}」以关闭位置询问"))
                                    return
                            except Exception:
                                continue
                    break
        except Exception as exc:
            douyin_logger.debug(_msg("📍", f"位置权限弹窗处理跳过：{exc}"))

    async def set_miniprogram_link(self, page: Page, miniprogram_link: str) -> bool:
        """添加标签 → 挂小程序（输入小程序链接）。best-effort，选择器需实测校准。"""
        if not miniprogram_link:
            return False
        try:
            await page.wait_for_timeout(2000)
            await page.wait_for_selector("text=添加标签", timeout=10000)
            dropdown = page.get_by_text("添加标签").locator("..").locator("..").locator("..").locator(".semi-select").first
            if not await dropdown.count():
                douyin_logger.error(_msg("😵", "没找到标签下拉框"))
                return False
            await dropdown.click()
            await page.wait_for_selector('[role="listbox"]', timeout=5000)
            # 小程序入口：兜底命中「小程序」选项
            opt = page.locator('[role="option"]:has-text("小程序")').first
            if not await opt.count():
                opt = page.get_by_text("小程序", exact=True).first
            if not await opt.count() or not await opt.is_visible():
                douyin_logger.warning(_msg("😵", "未找到「小程序」标签入口"))
                return False
            await opt.click()

            # 输入小程序链接
            link_input = page.locator('input[placeholder*="小程序链接"], input[placeholder*="粘贴小程序"], input[placeholder*="链接"]').first
            await link_input.wait_for(state="visible", timeout=5000)
            await link_input.fill(miniprogram_link)
            douyin_logger.debug(_msg("🔗", f"小程序链接已填: {miniprogram_link}"))

            add_btn = page.locator('span:has-text("添加"), button:has-text("添加")').first
            if await add_btn.count():
                await add_btn.click()
            await page.wait_for_timeout(1500)
            douyin_logger.info(_msg("🥳", "小程序标签已挂载"))
            return True
        except Exception as exc:
            douyin_logger.warning(_msg("😢", f"挂小程序标签失败: {exc}"))
            return False


class DouYinVideo(DouYinBaseUploader):
    def __init__(
        self,
        title,
        file_path,
        tags,
        publish_date: datetime | int,
        account_file,
        thumbnail_landscape_path=None,
        productLink="",
        productTitle="",
        thumbnail_portrait_path=None,
        desc: str | None = None,
        publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
        declaration: str | None = None,
        random_cover: bool = False,
        miniprogramLink: str = "",
        miniprogramTitle: str = "",
        location: str = "",
        who_can_see: str = "",
        save_permission: str = "",
        hotspot: str = "",
        collection: str = "",
        miniProgram: dict | None = None,
        cover_orientation: str = "landscape",
        cover_file: str = "",
        preview_only: bool = False,
    ):
        super().__init__(
            publish_date=publish_date,
            account_file=account_file,
            publish_strategy=publish_strategy,
            debug=debug,
            headless=headless,
            preview_only=preview_only,
        )
        self.title = title
        self.file_path = file_path
        self.tags = tags
        self.thumbnail_landscape_path = thumbnail_landscape_path
        self.thumbnail_portrait_path = thumbnail_portrait_path
        self.productLink = productLink
        self.productTitle = productTitle
        self.desc = desc or ""
        self.declaration = declaration.strip() if declaration and declaration.strip() else None
        self.random_cover = random_cover
        self.miniprogramLink = miniprogramLink
        self.miniprogramTitle = miniprogramTitle
        self.location = location
        self.who_can_see = who_can_see
        self.save_permission = save_permission
        self.hotspot = hotspot
        self.collection = collection
        self.miniProgram = miniProgram
        self.cover_orientation = cover_orientation
        self.cover_file = cover_file or ""

    async def apply_self_declaration(self, page: Page) -> None:
        if not self.declaration:
            return
        if not await self.set_self_declaration(page, self.declaration):
            raise RuntimeError(f"自主声明「{self.declaration}」设置失败，拒绝继续发布")

    async def _submit_sms_verify_code(self, page: Page, sms_input, code: str, code_file: str) -> bool:
        douyin_logger.info(_msg("✍️", f"已获取验证码，准备填入: {code}"))
        await sms_input.click()
        await sms_input.fill(code)
        douyin_logger.info(_msg("✅", "验证码已填入输入框"))
        await page.wait_for_timeout(500)

        verify_btn = page.locator('div.uc-ui-verify_sms-verify_button:has-text("验证")').first
        if await verify_btn.count() and await verify_btn.is_visible():
            try:
                await verify_btn.click(force=True)
                douyin_logger.success(_msg("✅", "已点击「验证」按钮 (force)"))
            except Exception:
                await page.eval_on_selector('div.uc-ui-verify_sms-verify_button', 'el => el.click()')
                douyin_logger.success(_msg("✅", "已点击「验证」按钮 (JS)"))
        else:
            verify_by_text = page.get_by_text("验证", exact=True).first
            if await verify_by_text.count():
                await verify_by_text.click(force=True)
                douyin_logger.success(_msg("✅", "已点击「验证」按钮 (text)"))
            else:
                douyin_logger.warning(_msg("⚠️", "未找到验证按钮，尝试按Enter"))
                await page.keyboard.press("Enter")

        if os.path.exists(code_file):
            os.remove(code_file)
            douyin_logger.info(_msg("🧹", "验证码文件已清理"))

        await page.wait_for_timeout(3000)
        douyin_logger.info(_msg("🔄", "验证码处理完成，继续发布流程"))
        return True

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.title or not str(self.title).strip():
            raise ValueError("视频模式下，title 是必须的")

        self.file_path = str(self.validate_video_file(self.file_path))
        if self.thumbnail_landscape_path:
            self.thumbnail_landscape_path = str(self.validate_image_file(self.thumbnail_landscape_path))
        if self.thumbnail_portrait_path:
            self.thumbnail_portrait_path = str(self.validate_image_file(self.thumbnail_portrait_path))

    async def handle_upload_error(self, page):
        douyin_logger.warning(_msg("😵", "视频上传摔了一跤，小人马上重新上传"))
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    async def handle_auto_video_cover(self, page, random_cover: bool = False):
        if await page.get_by_text("请设置封面后再发布").first.is_visible():
            douyin_logger.info(_msg("🧍", "发布前还得先把封面弄好"))
            covers = page.locator('[class^="recommendCover-"]')
            n = await covers.count()
            if n > 0:
                # 勾选随机封面：在可用推荐封面里随机选一帧，降低"只取第一张"的容错率
                idx = random.randrange(n) if random_cover and n > 1 else 0
                target = covers.nth(idx)
                douyin_logger.info(_msg("🏃", f"小人去选推荐封面 (random={random_cover}, 共{n}, 选第{idx + 1})"))
                try:
                    await target.click()
                    await asyncio.sleep(1)
                    confirm_text = "是否确认应用此封面？"
                    if await page.get_by_text(confirm_text).first.is_visible():
                        douyin_logger.info(_msg("🪟", f"弹出确认框了: {confirm_text}"))
                        await page.get_by_role("button", name="确定").click()
                        douyin_logger.info(_msg("🥳", "推荐封面已经应用"))
                        await asyncio.sleep(1)
                    douyin_logger.info(_msg("🥳", "封面选择流程完成"))
                    return True
                except Exception as e:
                    douyin_logger.warning(_msg("😵", f"推荐封面没选成功: {e}"))
        return False

    async def _handle_cover_recommend_modal(self, page: Page, want_portrait: bool) -> bool:
        """封面弹窗出现另一方向推荐时按意图处理。

        竖屏视频在横封面界面会推荐竖封面；反向场景可能推荐横封面。
        想设推荐方向就点对应按钮，否则点「完成/暂不设置」保留用户已传封面。
        """
        try:
            # 触发提示的文案（兜底多个）
            trigger = None
            for t in ("设置两张封面", "推荐竖封面", "推荐横封面", "获得更多曝光", "设置两张"):
                loc = page.get_by_text(t, exact=False).first
                if await loc.count() and await loc.is_visible():
                    trigger = t
                    break
            if not trigger:
                return False
            douyin_logger.info(_msg("��", f"检测到推荐封面弹窗: {trigger}"))
            if want_portrait:
                for t in ("设置竖封面", "设置竖版封面"):
                    b = page.get_by_text(t, exact=False).first
                    if await b.count() and await b.is_visible():
                        await b.click(timeout=3000)
                        await page.wait_for_timeout(1000)
                        douyin_logger.info(_msg("��", "已点「设置竖封面」"))
                        return True
            else:
                for t in ("设置横封面", "设置横版封面"):
                    b = page.get_by_text(t, exact=False).first
                    if await b.count() and await b.is_visible():
                        await b.click(timeout=3000)
                        await page.wait_for_timeout(1000)
                        douyin_logger.info(_msg("🖼️", "已点「设置横封面」"))
                        return True
            # 保持已传封面：点「完成」或「暂不设置」跳过推荐
            for t in ("暂不设置", "完成", "暂不", "跳过"):
                b = page.get_by_text(t, exact=True).first
                if await b.count() and await b.is_visible():
                    await b.click(timeout=3000)
                    await page.wait_for_timeout(500)
                    douyin_logger.info(_msg("🖼️", f"已点「{t}」保留当前封面方向"))
                    return True
        except Exception as exc:
            douyin_logger.debug(_msg("��", f"推荐封面处理跳过：{exc}"))
        return False

    async def set_thumbnail(self, page: Page):
        if not self.thumbnail_landscape_path and not self.thumbnail_portrait_path and not self.cover_file:
            return

        douyin_logger.info(_msg("🏃", "小人正在设置视频封面"))
        # 先清掉 shepherd 新手引导浮层，否则它会拦截“选择封面”点击导致弹窗打不开
        # 只删明确引导层（shepherd），不要用 [class*="mention-wrapper"] 等宽泛词——会误删业务 DOM。
        await page.evaluate(
            "() => { document.querySelectorAll('.shepherd-element, .shepherd-modal-overlay-container, [class*=\"coachmark\"]').forEach(e => e.remove()); }"
        )
        await page.get_by_text("选择封面", exact=True).first.click(force=True)
        cover_locator_str = 'div.dy-creator-content-modal'
        cover_locator = page.locator(cover_locator_str).first
        await page.wait_for_selector(cover_locator_str, timeout=20000)

        await page.wait_for_timeout(1500)
        # version_2 封面弹窗有 4 个隐藏 file input：
        #   [0]/[1] 左侧“AI生成参考图”上传/替换，[2]/[3] 才是“上传封面”/替换。
        # 旧代码用 .first 传到了 AI 参考图（不会成为封面）→ 这就是“传了却没封面”的根因。
        # 取 input.semi-upload-hidden-input 的第 2 个（nth(1)），即真正的封面上传输入。
        cover_upload = cover_locator.locator("input.semi-upload-hidden-input").nth(1)

        # cover_orientation：landscape=横封面，portrait=竖封面。按用户选择的朝向决定用哪个文件；
        # 该朝向无文件时回退到已有的另一个朝向文件（不改变既有 7 个功能的行为）。
        orientation = (self.cover_orientation or "landscape").strip().lower()
        use_portrait = orientation == "portrait"
        used_portrait = bool(self.thumbnail_portrait_path)
        if use_portrait and self.thumbnail_portrait_path:
            cover_path = self.thumbnail_portrait_path
            cover_labels = ("设置竖封面", "竖封面3:4", "竖封面", "竖版封面")
            orientation_name = "竖版封面"
            used_portrait = True
        elif (not use_portrait) and self.thumbnail_landscape_path:
            cover_path = self.thumbnail_landscape_path
            cover_labels = ("设置横封面", "横封面4:3", "横封面", "横版封面")
            orientation_name = "横版封面"
            used_portrait = False
        elif self.thumbnail_portrait_path:
            cover_path = self.thumbnail_portrait_path
            cover_labels = ("设置竖封面", "竖封面3:4", "竖封面", "竖版封面")
            orientation_name = "竖版封面"
            used_portrait = True
        elif self.thumbnail_landscape_path:
            cover_path = self.thumbnail_landscape_path
            cover_labels = ("设置横封面", "横封面4:3", "横封面", "横版封面")
            orientation_name = "横版封面"
            used_portrait = False
        else:
            cover_path = None
            cover_labels = ()
            orientation_name = ""
            used_portrait = False

        if not cover_path and self.cover_file:
            cover_path = self.cover_file
            orientation_name = "自定义封面"

        if cover_path:
            try:
                for lbl in cover_labels:
                    el = cover_locator.get_by_text(lbl, exact=False).first
                    if await el.count() and await el.is_visible():
                        await el.click(timeout=3000)
                        break
                await page.wait_for_timeout(800)
            except Exception:
                pass
            await cover_upload.set_input_files(cover_path)
            await page.wait_for_timeout(3000)
            douyin_logger.info(_msg("🖼️", f"{orientation_name}已上传到预览"))

        # 竖屏视频在「横封面界面」上传封面后，抖音会弹「推荐竖封面」（暂不设置/设置竖封面），
        # 按意图处理：要竖封面→设置竖封面；否则→暂不设置（保留已传封面）。
        await self._handle_cover_recommend_modal(page, want_portrait=used_portrait)

        # 点红色主按钮“完成”应用封面（exact 避免误中“完成编辑”）
        await cover_locator.get_by_role("button", name="完成", exact=True).first.click()
        douyin_logger.info(_msg("🥳", "视频封面设置完成"))
        # 关键：竖屏视频会触发「设置竖封面获更多流量」弹窗，点「完成」后弹窗**不自动关闭**，
        # 残留遮罩（dy-creator-content-modal-wrap）会拦截后续「自主声明」等点击导致超时。
        # 因此这里必须确保封面弹窗真正关闭：等待 hidden，若还在则主动关闭/移遮罩。
        try:
            await cover_locator.wait_for(state="hidden", timeout=6000)
        except Exception:
            await self._force_close_cover_modal(page, cover_locator)

    async def _force_close_cover_modal(self, page: Page, cover_locator) -> None:
        """确保封面弹窗真正关闭（弹窗残留会遮罩后续点击）。best-effort。

        竖屏视频在「横封面界面」上传封面后，抖音会弹「设置竖封面获更多流量」推荐弹窗，
        含「暂不设置 / 设置竖封面」两个按钮。这里优先点「暂不设置」跳过推荐，
        保留用户已传入的封面并关闭弹窗；无法命中则继续关闭/删遮罩。
        """
        # 0) 优先处理「推荐竖封面」弹窗：点「暂不设置」跳过（保留已传封面，避免改用户选择）
        for t in ("暂不设置", "暂不", "跳过", "暂不使用"):
            try:
                btn = page.get_by_text(t, exact=True).first
                if await btn.count() and await btn.is_visible():
                    await btn.click(timeout=3000)
                    await page.wait_for_timeout(800)
                    return
            except Exception:
                continue
        # 1) 尝试点弹窗右上角关闭按钮（Semi modal 通常是 X）
        try:
            close_btn = page.locator(".dy-creator-content-modal-close, .semi-modal-close, .semi-modal-close-icon").first
            if await close_btn.count() and await close_btn.is_visible():
                await close_btn.click(timeout=3000)
                await page.wait_for_timeout(600)
                return
        except Exception:
            pass
        # 2) 按 ESC
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(600)
        except Exception:
            pass
        # 3) 兜底：移除弹窗遮罩与容器（含 mask，只删该弹窗，不用宽泛选择器）
        try:
            await page.evaluate(
                "() => { document.querySelectorAll('.dy-creator-content-modal-wrap, .dy-creator-content-modal-content, .dy-creator-content-modal-mask').forEach(e => e.remove()); }"
            )
        except Exception:
            pass
        douyin_logger.debug(_msg("🖼️", "已强制清理封面弹窗遮罩"))

    async def set_who_can_see(self, page: Page, who_can_see: str) -> bool:
        """设置「谁可以看」：公开 / 好友可见 / 仅自己可见（发布设置区单选）。

        实测 DOM：`label.radio-d4zkru`，三个选项文本全局唯一；`公开` 为默认选中（value=0）。
        默认「公开」无需操作。best-effort，失败不阻断发布。
        """
        if not who_can_see or who_can_see in ("公开", "public"):
            return True
        try:
            row = page.locator("div.content-obt4oA").filter(has_text="谁可以看").first
            await row.wait_for(state="visible", timeout=8000)
            target = row.locator("label.radio-d4zkru").filter(has_text=who_can_see).first
            if not await target.count():
                target = page.locator("label.radio-d4zkru").filter(has_text=who_can_see).first
            if await target.count() and await target.is_visible():
                await target.click(timeout=5000)
                douyin_logger.info(_msg("👀", f"「谁可以看」已设置「{who_can_see}」"))
                return True
            douyin_logger.warning(_msg("👀", f"「谁可以看」选项「{who_can_see}」未命中"))
        except Exception as exc:
            douyin_logger.warning(_msg("👀", f"设置「谁可以看」失败：{exc}"))
        return False

    async def set_save_permission(self, page: Page, save_permission: str) -> bool:
        """设置「保存权限」：允许 / 不允许（发布设置区单选）。

        实测 DOM：`div.download-content-Lci5tL label.radio-d4zkru`，选项文本 `允许`/`不允许`；
        `允许` 为默认选中（value=1）。仅当需要「不允许」时操作。
        """
        if not save_permission or save_permission in ("允许", "allow"):
            return True
        try:
            box = page.locator("div.download-content-Lci5tL").first
            await box.wait_for(state="visible", timeout=8000)
            target = box.locator("label.radio-d4zkru").filter(has_text=save_permission).first
            if not await target.count():
                target = page.locator("label.radio-d4zkru").filter(has_text=save_permission).first
            if await target.count() and await target.is_visible():
                await target.click(timeout=5000)
                douyin_logger.info(_msg("🔒", f"「保存权限」已设置「{save_permission}」"))
                return True
            douyin_logger.warning(_msg("🔒", f"「保存权限」选项「{save_permission}」未命中"))
        except Exception as exc:
            douyin_logger.warning(_msg("🔒", f"设置「保存权限」失败：{exc}"))
        return False

    async def set_hotspot(self, page: Page, hotspot: str) -> bool:
        """关联热点：点「点击输入热点词」筛选下拉，输入关键词后选首条。best-effort。

        实测 DOM：select[4]（占位 `点击输入热点词`，class `semi-select-single semi-select-filterable`），
        点击后内部有 1 个 input（`sel.locator('input')`），打开即预载选项（~55 个，含隐藏项），
        因此用 Semi 原生交互：fill 关键词 → ArrowDown → Enter 选第一条。
        """
        if not hotspot:
            return True
        try:
            sel = page.locator("div.semi-select").filter(has_text="点击输入热点词").first
            await sel.wait_for(state="visible", timeout=8000)
            await sel.click(timeout=5000)
            await page.wait_for_timeout(500)
            inp = sel.locator("input").first
            if await inp.count():
                await inp.fill(hotspot)
            else:
                await page.keyboard.type(hotspot)
            await page.wait_for_timeout(1200)
            # Semi 筛选下拉：键盘选中第一条（兼容 55 个隐藏选项的 DOM 污染）
            await page.keyboard.press("ArrowDown")
            await page.wait_for_timeout(250)
            await page.keyboard.press("Enter")
            douyin_logger.info(_msg("🔥", f"关联热点已选「{hotspot}」"))
            return True
        except Exception as exc:
            douyin_logger.warning(_msg("🔥", f"设置「关联热点」失败：{exc}"))
            return False

    async def set_collection(self, page: Page, collection: str) -> bool:
        """添加到合集：点「请选择合集」下拉选择合集；空/找不到则选「不选择合集」。best-effort。

        实测 DOM：`div.semi-select.select-collection-nkL6sA`（占位 `请选择合集`），
        点开后 `[role="listbox"] [role="option"]`，含 `不选择合集`。
        """
        if not collection:
            return True
        try:
            box = page.locator("div.semi-select.select-collection-nkL6sA").first
            await box.wait_for(state="visible", timeout=8000)
            await box.click(timeout=5000)
            await page.wait_for_selector('[role="listbox"] [role="option"]', timeout=8000)
            target = (collection or "").strip()
            option = None
            if target and target not in ("不选择合集", "不加入合集"):
                option = page.locator('[role="listbox"] [role="option"]').filter(has_text=target).first
                if not await option.count():
                    option = page.get_by_text(target, exact=True).first
            if not option or not await option.count():
                option = page.locator('[role="listbox"] [role="option"]').filter(has_text="不选择合集").first
                if not await option.count():
                    option = page.get_by_text("不选择合集", exact=True).first
            if await option.count() and await option.is_visible():
                await option.click(timeout=5000)
                douyin_logger.info(_msg("📁", f"合集已设置「{target or '不选择合集'}」"))
                return True
            douyin_logger.warning(_msg("📁", "「不选择合集」也未命中，跳过合集"))
        except Exception as exc:
            douyin_logger.warning(_msg("📁", f"设置「合集」失败：{exc}"))
        return False

    async def set_mount_object(self, page: Page, mini_program) -> bool:
        """添加标签 → 挂载内容（小程序/游戏/应用）「对象」选择。best-effort。

        实测 DOM：`div.anchor-container-hgj7gj div.semi-select`（class `select-lJTtRL`，当前值 `位置`），
        点开后选项为 `位置 / 影视演艺 / 小程序 / 标记万物`（`[role="option"]`）。
        选「小程序」后进入对象搜索浮层——**该浮层内部选择器未完整展开确认**，用兜底搜索，命不中记日志跳过。
        """
        if not mini_program:
            return True
        name = mini_program.get("name") if isinstance(mini_program, dict) else str(mini_program)
        if not name:
            return True
        try:
            anchor = page.locator("div.anchor-container-hgj7gj div.semi-select").first
            if not await anchor.count():
                douyin_logger.warning(_msg("🧩", "未找到「添加标签」下拉，跳过挂载"))
                return False
            await anchor.click(timeout=5000)
            await page.wait_for_selector('[role="listbox"] [role="option"]', timeout=8000)
            opt = page.locator('[role="listbox"] [role="option"]').filter(has_text="小程序").first
            if not await opt.count():
                opt = page.get_by_text("小程序", exact=True).first
            if not await opt.count() or not await opt.is_visible():
                douyin_logger.warning(_msg("🧩", "「小程序」选项未出现，跳过挂载"))
                return False
            await opt.click(timeout=5000)

            # 对象搜索浮层（「未确认」兜底）：搜索框 + 列表项
            await page.wait_for_timeout(1500)
            search_input = page.locator(
                'input[placeholder*="搜索"], input[placeholder*="小程序"], input[placeholder*="名称"]'
            ).first
            if await search_input.count():
                await search_input.fill(name)
                await page.wait_for_timeout(1200)
                obj = page.locator(
                    '[role="option"], .semi-sidesheet-content [class*="option"], [class*="item"]'
                ).filter(has_text=name).first
                if await obj.count() and await obj.is_visible():
                    await obj.click(timeout=5000)
                    douyin_logger.info(_msg("🧩", f"挂载内容「{name}」已选择"))
                    return True
            douyin_logger.warning(_msg("🧩", f"挂载内容「{name}」对象浮层未确认到，请人工核对"))
            return False
        except Exception as exc:
            douyin_logger.warning(_msg("🧩", f"设置挂载内容失败：{exc}"))
            return False

    async def upload(self, playwright: Playwright) -> None:
        douyin_logger.info(_msg("🧍", "小人先检查 cookie、视频文件、封面和发布时间"))
        await self.validate_upload_args()
        douyin_logger.info(_msg("🥳", "上传前检查通过"))

        # 抖音为大陆平台：强制走本地直连，不设任何代理。这里**故意不传 proxy**（patchright 默认直连，
        # 不读系统/环境代理），确保不吃 mihomo 等梯子代理；若未来有系统 HTTP 代理启用，也因 launch
        # 未设 proxy 而绕开。macOS 当前无系统代理（scutil --proxy 仅 FTPPassive），大陆直连 0.13s 可达。
        launch_kwargs = {"headless": self.headless}
        if LOCAL_CHROME_PATH:
            launch_kwargs["executable_path"] = LOCAL_CHROME_PATH
        else:
            launch_kwargs["channel"] = "chromium"
        browser = await launch_optional_browser(playwright, platform="douyin", **launch_kwargs)
        context = await browser.new_context(
            storage_state=f"{self.account_file}",
            permissions=["geolocation"],
        )
        context = await set_init_script(context)

        page = await context.new_page()
        await page.goto("https://creator.douyin.com/creator-micro/content/upload", wait_until="domcontentloaded", timeout=90000)
        douyin_logger.info(_msg("🏃", f"小人开始搬运视频: {self.title}.mp4"))
        douyin_logger.info(_msg("🧭", "小人正在赶往上传主页"))
        await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload", timeout=90000)
        # wait_for_url 完成时上传页可能尚未渲染出文件 input（实测偶发），先等它挂载再 set_input_files
        await page.wait_for_selector("div[class^='container'] input", state="attached", timeout=60000)
        await page.locator("div[class^='container'] input").set_input_files(self.file_path)

        while True:
            try:
                await page.wait_for_url(
                    "https://creator.douyin.com/creator-micro/content/publish?enter_from=publish_page",
                    timeout=3000,
                )
                douyin_logger.info(_msg("🥳", "已经进入 version_1 发布页面"))
                break
            except Exception:
                try:
                    await page.wait_for_url(
                        "https://creator.douyin.com/creator-micro/content/post/video?enter_from=publish_page",
                        timeout=3000,
                    )
                    douyin_logger.info(_msg("🥳", "已经进入 version_2 发布页面"))
                    break
                except Exception:
                    douyin_logger.debug(_msg("🧍", "还没进到视频发布页面，小人继续等一会"))
                    await asyncio.sleep(0.5)

        await asyncio.sleep(1)
        await self.dismiss_version_prompt(page)

        # version_2 发布页要等视频上传完成后才渲染表单（标题/描述/话题）。因此：
        # 先等「重新上传」/上传完成，再填表，否则标题框未渲染导致 fill 超时。
        douyin_logger.info(_msg("🏃", "小人正在等视频上传完成，便于后续填表"))
        awaited_upload = await self._wait_for_video_uploaded(page)
        if not awaited_upload:
            douyin_logger.warning(_msg("😵", "检测到视频上传失败，先重新上传再继续填表"))
            await self.handle_upload_error(page)
            awaited_upload = await self._wait_for_video_uploaded(page)
            if not awaited_upload:
                raise RuntimeError("抖音视频重新上传后仍未完成，停止填写发布表单")

        douyin_logger.info(_msg("✍️", "小人开始填标题、描述和话题"))
        await self.fill_title_and_description(page, self.title, self.desc or self.title, self.tags)
        douyin_logger.info(_msg("🏷️", f"小人一共贴了 {len(self.tags)} 个话题"))

        while True:
            try:
                number = await page.locator('[class^="long-card"] div:has-text("重新上传")').count()
                if number > 0:
                    douyin_logger.success(_msg("🥳", "视频已经传完啦"))
                    break
                douyin_logger.info(_msg("🏃", "小人正在努力上传视频"))
                await asyncio.sleep(2)
                if await page.locator('div.progress-div > div:has-text("上传失败")').count():
                    douyin_logger.error(_msg("😵", "检测到上传失败，小人准备重试"))
                    await self.handle_upload_error(page)
            except Exception:
                douyin_logger.debug(_msg("🧍", "小人还在等视频上传完成"))
                await asyncio.sleep(2)

        if self.productLink and self.productTitle:
            douyin_logger.info(_msg("🛒", "小人正在设置商品链接"))
            await self.set_product_link(page, self.productLink, self.productTitle)
            douyin_logger.info(_msg("🥳", "商品链接设置完成"))

        if self.miniprogramLink and self.miniprogramTitle:
            douyin_logger.info(_msg("🧩", "小人正在挂小程序"))
            await self.set_miniprogram_link(page, self.miniprogramLink)
            douyin_logger.info(_msg("🥳", "小程序标签设置完成"))

        if getattr(self, "location", ""):
            douyin_logger.info(_msg("📍", "小人正在设置位置"))
            await self.set_location(page, self.location)
            await self._handle_browser_permission(page, allow_location=True, has_location=True)
        else:
            await self._handle_browser_permission(page, allow_location=False, has_location=False)

        await self.set_thumbnail(page)

        # 新补功能（best-effort，失败不阻断）：合集 → 挂载内容 → 关联热点 → 谁可以看 → 保存权限
        douyin_logger.info(_msg("🧩", "小人开始设置合集/挂载内容/热点/可见性/保存权限"))
        await self.set_collection(page, self.collection)
        await self.set_mount_object(page, self.miniProgram)
        await self.set_hotspot(page, self.hotspot)
        await self.set_who_can_see(page, self.who_can_see)
        await self.set_save_permission(page, self.save_permission)

        try:
            await self.apply_self_declaration(page)
        except Exception:
            try:
                await context.close()
            except Exception:
                pass
            try:
                await browser.close()
            except Exception:
                pass
            raise

        third_part_element = '[class^="info"] > [class^="first-part"] div div.semi-switch'
        if await page.locator(third_part_element).count():
            if "semi-switch-checked" not in await page.eval_on_selector(third_part_element, "div => div.className"):
                await page.locator(third_part_element).locator("input.semi-switch-native-control").click()

        if self.publish_strategy == DOUYIN_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
            await self.set_schedule_time_douyin(page, self.publish_date)

        sms_prompt_logged = False
        while True:
            try:
                # 移除会拦截发布按钮点击的新手引导浮层（只删明确引导层 shepherd/coachmark，
                # 避免 [class*="mention-wrapper"] 等宽泛词误删业务 DOM）
                await page.evaluate(
                    "() => { document.querySelectorAll('.shepherd-element, .shepherd-modal-overlay-container, [class*=\"coachmark\"]').forEach(e => e.remove()); }"
                )
                # 检测并处理短信验证码弹窗
                sms_input = page.locator('input[placeholder*="验证码"], input[type="tel"], input[placeholder*="短信"], input[placeholder*="手机号"]').first
                if await sms_input.count() and await sms_input.is_visible():
                    douyin_logger.warning(_msg("📱", "检测到短信验证码弹窗"))
                    # 点击「获取验证码」按钮（仅首次）
                    get_code_btn = page.get_by_text("获取验证码").first
                    if await get_code_btn.count() and await get_code_btn.is_visible():
                        await get_code_btn.click()
                        douyin_logger.info(_msg("📤", "已点击「获取验证码」，请查看手机短信"))
                    code_file = os.path.join(BASE_DIR, "verify_code.txt")
                    code = await _read_verify_code(code_file)
                    if code:
                        sms_prompt_logged = False
                        await self._submit_sms_verify_code(page, sms_input, code, code_file)
                    elif not sms_prompt_logged:
                        douyin_logger.warning(_msg("⏳", f"等待验证码输入；可在交互终端直接输入，或写入文件: {code_file}"))
                        sms_prompt_logged = True
                if self.preview_only:
                    # 预览/调试模式：所有前置步骤（上传、标题/话题/描述、封面、定位、商品/小程序、自查声明）都已跑完，
                    # 只差最后点「发布」。此处停下，绝不真正发布，便于安全调试观察每一步结果。
                    douyin_logger.warning(_msg("🛑", "preview_only 预览模式：已到发布按钮前，跳过最终「发布」点击"))
                    if self.debug:
                        shot = os.path.join(BASE_DIR, "logs", "douyin_preview_screenshot.png")
                        try:
                            await page.screenshot(full_page=True, path=shot)
                            douyin_logger.info(_msg("📸", f"预览页已截图: {shot}"))
                        except Exception:
                            pass
                    return
                publish_button = page.get_by_role("button", name="发布", exact=True)
                if await publish_button.count():
                    await publish_button.click(force=True)
                await page.wait_for_url(
                    "https://creator.douyin.com/creator-micro/content/manage**",
                    timeout=3000,
                )
                douyin_logger.success(_msg("🥳", "视频发布成功，小人开心收工"))
                break
            except Exception:
                await self.handle_auto_video_cover(page, random_cover=self.random_cover)
                douyin_logger.info(_msg("🏃", "小人正在冲刺发布视频"))
                if self.debug:
                    await page.screenshot(full_page=True)
                await asyncio.sleep(0.5)

        await context.storage_state(path=self.account_file)
        douyin_logger.success(_msg("🥳", "cookie 更新完毕"))
        await asyncio.sleep(2)
        await context.close()
        await browser.close()

    async def douyin_upload_video(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def main(self):
        await self.douyin_upload_video()


class DouYinNote(DouYinBaseUploader):
    def __init__(
        self,
        image_paths,
        note,
        tags,
        publish_date: datetime | int,
        account_file,
        title: str | None = None,
        publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
        bgm: str = "",
        declaration: str | None = None,
        location: str = "",
        collection: str | None = None,
        who_can_see: str | None = None,
        save_permission: str | None = None,
        hotspot: str | None = None,
        mini_program: dict | str | None = None,
        cover_file: str | None = None,
        cover_orientation: str = "landscape",
        product_link: str = "",
        product_title: str = "",
    ):
        super().__init__(
            publish_date=publish_date,
            account_file=account_file,
            publish_strategy=publish_strategy,
            debug=debug,
            headless=headless,
        )
        self.image_paths = image_paths
        self.note = note or ""
        self.title = title or (self.note[:30] if self.note else "")
        self.tags = tags or []
        self.bgm = bgm or ""
        self.declaration = declaration.strip() if declaration and declaration.strip() else None
        self.location = location
        self.collection = collection
        self.who_can_see = who_can_see
        self.save_permission = save_permission
        self.hotspot = hotspot
        self.miniProgram = mini_program
        self.cover_file = cover_file or ""
        self.cover_orientation = cover_orientation or "landscape"
        self.productLink = product_link or ""
        self.productTitle = product_title or ""

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.title or not str(self.title).strip():
            raise ValueError("图文模式下，title 是必须的")

        if len(self.title) > 20:
            raise ValueError(f"标题不能超过20字符，当前: {len(self.title)}字符")

        if not self.image_paths:
            raise ValueError("图文模式下，图片是必须的")

        if isinstance(self.image_paths, (str, Path)):
            self.image_paths = [self.image_paths]

        if len(self.image_paths) > 35:
            raise ValueError("图文模式下最多只支持上传 35 张图片")

        note_len = len(self.note) if self.note else 0
        if note_len > 1000:
            raise ValueError(f"正文不能超过1000字符，当前: {note_len}字符")

        normalized_image_paths = []
        for image_path in self.image_paths:
            normalized_image_paths.append(str(self.validate_image_file(image_path)))
        self.image_paths = normalized_image_paths

    async def upload_note_content(self, page: Page) -> None:
        douyin_logger.info(_msg("🏃", f"小人开始搬运图文，共 {len(self.image_paths)} 张图片"))
        douyin_logger.info(_msg("🔀", "小人正在切换到图文发布"))
        await page.get_by_text("发布图文", exact=True).click()
        await page.wait_for_timeout(1000)

        douyin_logger.info(_msg("📤", "小人正在上传图片"))
        await page.locator("div[class^='container'] input[accept*='image']").set_input_files(self.image_paths)

        while True:
            try:
                await page.wait_for_url(
                    "**/creator-micro/content/post/image?**",
                    timeout=3000,
                )
                douyin_logger.info(_msg("🥳", "已经进入图文发布页面"))
                break
            except Exception:
                douyin_logger.debug(_msg("🧍", "小人还在等图片上传完成"))
                await asyncio.sleep(0.5)

        await asyncio.sleep(1)
        await self.dismiss_version_prompt(page)
        douyin_logger.info(_msg("✍️", "小人开始填标题、描述和话题"))
        await self.fill_title_and_description(page, self.title, self.note, self.tags)
        title_len = len(self.title) if self.title else 0
        tags_text = " ".join(f"#{t}" for t in self.tags) if self.tags else ""
        desc_and_tags_len = len(self.note or "") + (len(tags_text) + 2 if self.tags else 0)
        douyin_logger.info(_msg("📝", f"标题总字数: {title_len}，描述+话题总字数: {desc_and_tags_len}"))
        douyin_logger.info(_msg("🏷️", f"小人一共贴了 {len(self.tags)} 个话题"))

        if self.bgm:
            await self.select_bgm(page, self.bgm)

        if self.location:
            douyin_logger.info(_msg("📍", "小人正在设置位置"))
            await self.set_location(page, self.location)
            await self._handle_browser_permission(page, allow_location=True, has_location=True)
        else:
            await self._handle_browser_permission(page, allow_location=False, has_location=False)

        if self.declaration:
            douyin_logger.info(_msg("🧾", "小人正在选择自主声明"))
            await self.set_self_declaration(page, self.declaration)

        # 图文页与视频页的扩展配置 DOM 版本可能不同；各项均为 best-effort，
        # 未命中只记录日志，不伪造成功，也不阻断基础图文发布。
        await self.set_collection(page, self.collection)
        await self.set_mount_object(page, self.miniProgram)
        await self.set_hotspot(page, self.hotspot)
        await self.set_who_can_see(page, self.who_can_see)
        await self.set_save_permission(page, self.save_permission)

        if self.productLink and self.productTitle:
            await self.set_product_link(page, self.productLink, self.productTitle)

        if self.publish_strategy == DOUYIN_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
            await self.set_schedule_time_douyin(page, self.publish_date)

        while True:
            try:
                publish_button = page.get_by_role("button", name="发布", exact=True)
                if await publish_button.count():
                    await publish_button.click()
                await page.wait_for_url(
                    "**/creator-micro/content/manage?enter_from=publish**",
                    timeout=3000,
                )
                douyin_logger.success(_msg("🥳", "图文发布成功，小人开心收工"))
                break
            except Exception:
                douyin_logger.info(_msg("🏃", "小人正在冲刺发布图文"))
                await asyncio.sleep(0.5)

    async def upload(self, playwright: Playwright) -> None:
        douyin_logger.info(_msg("🧍", "小人先检查 cookie、图片和发布时间"))
        await self.validate_upload_args()
        douyin_logger.info(_msg("🥳", "图文上传前检查通过"))

        launch_kwargs = {"headless": self.headless}
        if LOCAL_CHROME_PATH:
            launch_kwargs["executable_path"] = LOCAL_CHROME_PATH
        else:
            launch_kwargs["channel"] = "chromium"
        browser = await launch_optional_browser(playwright, platform="douyin", **launch_kwargs)
        context = await browser.new_context(
            storage_state=f"{self.account_file}",
            permissions=["geolocation"],
        )
        context = await set_init_script(context)

        upload_success = False
        try:
            page = await context.new_page()
            await page.goto("https://creator.douyin.com/creator-micro/content/upload", wait_until="domcontentloaded", timeout=90000)
            douyin_logger.info(_msg("🧭", "小人正在赶往图文发布页"))
            await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload", timeout=90000)

            await self.upload_note_content(page)
            upload_success = True
        finally:
            if upload_success:
                await context.storage_state(path=self.account_file)
                douyin_logger.success(_msg("🥳", "cookie 更新完毕"))
                await asyncio.sleep(2)
            await context.close()
            await browser.close()

    async def douyin_upload_note(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
