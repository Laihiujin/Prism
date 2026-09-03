"""跨平台可复用的浏览器 DOM / 弹窗 / 上传处理工具。

从抖音上传器（uploader/douyin_uploader/main_refactored.py)提炼的通用逻辑，
目标是给其它平台（tiktok/youtube/kuaishou/xiaohongshu/channels…）复用，
避免每个平台各自重写一套「关引导遮罩 / 处理定位弹窗 / 选封面 / 上传重试」。

约定：
- 所有函数为 async、接收 playwright `Page`，**best-effort**，失败不抛异常（记录日志后返回）。
- 平台差异只体现在**选择器**上；把平台特有选择器抽成参数/常量传入，函数本身与平台解耦。
- 文档：见 docs/AGENTS-BROWSER-REUSABLE-DOM.md（给 agent 的实现指引）。
"""
from __future__ import annotations

import asyncio
import random
from typing import Optional

from loguru import logger

_browser_logger = logger


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


# ---- 遮罩 / 引导浮层常用容器选择器（多平台通用，命中即移除） ----
# 注意：保持**极度保守**，只针对确实会拦截点击的引导浮层（shepherd / coachmark）。
# 凡是带 guide/mention/version/popup 等宽泛词的都不要放进来——会误删标题输入框、
# 内容编辑区（div.zone-container）等业务 DOM，导致后续 fill 找不到元素而超时。
DEFAULT_OVERLAY_SELECTORS = (
    ".shepherd-element",
    ".shepherd-modal-overlay-container",
    "[class*='coachmark']",
    "[class*='new-user-guide']",
)

# ---- 版本/引导提示的“关闭”文案（点任一可见按钮） ----
DEFAULT_DISMISS_TEXTS = ("立即体验", "我知道了", "知道了", "开始体验", "查看新功能", "跳过", "暂不")

# ---- 浏览器定位权限弹窗按钮 ----
PERMISSION_ALLOW_TEXTS = ("仅本次", "仅此一次", "允许")
PERMISSION_DENY_TEXTS = ("不允许", "关闭")


async def remove_overlays(page, selectors: tuple[str, ...] = DEFAULT_OVERLAY_SELECTORS) -> None:
    """移除会拦截点击的引导/遮罩容器（不依赖可见性）。

    注意：page.evaluate 的回调接收参数用 `(arg) => {...}`，**不要用 `arguments[0]`**——
    patchright 的 evaluate 环境中 `arguments` 未定义，会导致 `ReferenceError: arguments is not defined`。
    """
    if not selectors:
        return
    try:
        await page.evaluate(
            "(sels) => { document.querySelectorAll(sels.join(',')).forEach(e => e.remove()); }",
            list(selectors),
        )
    except Exception as exc:
        _browser_logger.debug(_msg("🗑️", f"移除遮罩未命中/跳过：{exc}"))


async def dismiss_version_prompt(
    page,
    dismiss_texts: tuple[str, ...] = DEFAULT_DISMISS_TEXTS,
    overlay_selectors: tuple[str, ...] = DEFAULT_OVERLAY_SELECTORS,
) -> bool:
    """关闭「官方新版本 / 新增功能 / 视频预览提示」等弹窗（best-effort）。

    常见抖音弹窗：「视频预览功能 视频素材已按原始分辨率上传… 我知道了」——点「我知道了」即可关。

    重要：**只点关闭按钮，绝不删除任何 DOM**。曾用 remove_overlays 删遮罩容器，
    但宽泛选择器（[class*='guide']/[class*='mention-wrapper']）会误删标题输入框/内容编辑区
    （实测点「我知道了」后 title/zone-container 被清空），导致后续 fill 找不到元素。
    弹窗有按钮，点按钮关闭即可；纯引导浮层如需清理，单独用 remove_overlays 并传保守选择器。
    """
    for text in dismiss_texts:
        try:
            btn = page.get_by_text(text, exact=True).first
            if await btn.count() and await btn.is_visible():
                await btn.click(timeout=2000)
                await page.wait_for_timeout(300)
                _browser_logger.info(_msg("🗑️", f"已关闭版本提示遮挡: {text}"))
                return True
        except Exception:
            continue
    return False


async def handle_browser_permission(page, allow_location: bool = False, has_location: bool = False) -> None:
    """处理浏览器定位权限弹窗（允许/仅本次/不允许/关闭）。

    有位置时优先点「仅本次/允许」；没选位置时点「不允许/关闭」。
    已授权（context 已给 geolocation）时一般无弹窗，此函数只兜底检测。
    """
    try:
        candidates = [
            page.get_by_text(t, exact=True).first
            for t in PERMISSION_ALLOW_TEXTS + PERMISSION_DENY_TEXTS
        ]
        for c in candidates:
            if await c.count() and await c.is_visible():
                _browser_logger.info(_msg("📍", f"检测到浏览器权限弹窗，has_location={has_location}"))
                if has_location or allow_location:
                    for t in PERMISSION_ALLOW_TEXTS:
                        try:
                            pick = page.get_by_text(t, exact=True).first
                            if await pick.count() and await pick.is_visible():
                                await pick.click(timeout=2000)
                                _browser_logger.info(_msg("📍", f"已点「{t}」"))
                                return
                        except Exception:
                            continue
                else:
                    for t in PERMISSION_DENY_TEXTS:
                        try:
                            pick = page.get_by_text(t, exact=True).first
                            if await pick.count() and await pick.is_visible():
                                await pick.click(timeout=2000)
                                _browser_logger.info(_msg("📍", f"已点「{t}」以关闭位置询问"))
                                return
                        except Exception:
                            continue
                break
    except Exception as exc:
        _browser_logger.debug(_msg("📍", f"位置权限弹窗处理跳过：{exc}"))


async def wait_upload_complete(page, logger=None, poll_interval: float = 2.0, max_polls: int = 300) -> bool:
    """轮询等待视频上传完成。

    判定：出现「重新上传」字样（含在 long-card）即上传完；出现「上传失败」则触发重试回调。
    """
    log = logger or _browser_logger
    try:
        for _ in range(max_polls):
            if await page.locator('[class^="long-card"] div:has-text("重新上传")').count():
                log.success(_msg("🥳", "视频已经传完啦"))
                return True
            if await page.locator('div.progress-div > div:has-text("上传失败")').count():
                log.error(_msg("😵", "检测到上传失败，小人准备重试"))
                return False
            await asyncio.sleep(poll_interval)
        log.warning(_msg("⏳", f"等上传完成超时（{max_polls * poll_interval:.0f}s 未见「重新上传/上传失败」），按已完成继续"))
        return True
    except Exception as exc:
        log.debug(_msg("🧍", f"等待上传完成异常：{exc}"))
        return True


async def handle_auto_cover(
    page,
    random_cover: bool = False,
    cover_selector: str = '[class^="recommendCover-"]',
    prompt_text: str = "请设置封面后再发布",
    confirm_text: str = "是否确认应用此封面？",
) -> bool:
    """发布前自动选推荐封面（缺封面时命中「请设置封面后再发布」）。

    random_cover=True 且在多个推荐封面里随机选一帧，降低“只取第一张”的容错率。
    """
    try:
        if not await page.get_by_text(prompt_text).first.is_visible():
            return False
        covers = page.locator(cover_selector)
        n = await covers.count()
        if n > 0:
            idx = random.randrange(n) if random_cover and n > 1 else 0
            target = covers.nth(idx)
            log_msg = f"小人去选推荐封面 (random={random_cover}, 共{n}, 选第{idx + 1})"
            _browser_logger.info(_msg("🏃", log_msg))
            try:
                await target.click()
                await asyncio.sleep(1)
                if await page.get_by_text(confirm_text).first.is_visible():
                    await page.get_by_role("button", name="确定").click()
                    _browser_logger.info(_msg("🥳", "推荐封面已经应用"))
                    await asyncio.sleep(1)
                _browser_logger.info(_msg("🥳", "封面选择流程完成"))
                return True
            except Exception as e:
                _browser_logger.warning(_msg("😵", f"推荐封面没选成功: {e}"))
        return False
    except Exception as exc:
        _browser_logger.debug(_msg("🖼️", f"自动封面处理跳过：{exc}"))
        return False


async def select_topics_exact(page, tags, logger=None) -> int:
    """在内容编辑区输入话题，并在补全下拉中选“文本一致且字符数一致”的项。

    返回成功选中的话题数。选中失败的用空格补齐，保证话题被分割。
    平台差异（编辑器选择器）抽成参数，见 select_topics_exact_with_editor。
    """
    # 实现依赖编辑器选择器，故聚合在下方 *_with_editor
    raise NotImplementedError("use select_topics_exact_with_editor")


async def select_topics_exact_with_editor(
    page,
    tags,
    editor_selector: str = 'div.zone-container[contenteditable="true"]',
    topic_item_selectors: tuple[str, ...] = (
        ".topic-item", ".topic-list-item", '[class*="topic-item"]',
        '[class*="mention"]', '[role="option"]',
    ),
    tag_prefix: str = "#",
    logger=None,
    clear_on_fail: bool = False,
    topic_wait_selector: str = "",
) -> int:
    """在内容编辑区输入话题并在补全下拉精确选择（见 select_topics_exact 说明）。

    best-effort：先点一下编辑区（若存在）聚焦，再逐条输入并精确选中；任何异常记录日志并返回已选数量，
    不抛异常（符合共享模块「失败记录日志返回」的约定）。

    clear_on_fail=True：某个话题未精确命中时，回退删除已键入的「#tag」文本（如小红书需要清掉未成词的
    话题，避免残留进正文）；默认 False 则按空格占位。topic_wait_selector：若提供，在每次输入话题后、
    精确选择前先等该候选容器出现（如平台话题联想较慢时避免过早放弃）。
    """
    log = logger or _browser_logger
    picked = 0
    try:
        if editor_selector:
            editor = page.locator(editor_selector).first
            if await editor.count():
                await editor.click()
                await page.wait_for_timeout(200)
        for tag in tags or []:
            await page.keyboard.type(tag_prefix + tag)
            await page.wait_for_timeout(400)
            if topic_wait_selector:
                try:
                    await page.locator(topic_wait_selector).first.wait_for(
                        state="visible", timeout=6000
                    )
                except Exception:
                    pass
            if await _pick_topic_item_exact(page, tag, topic_item_selectors):
                picked += 1
                # 话题选中后补一个空格分隔（对齐抖音发布 skill：一次性输入完整 #关键词 后按空格确认，
                # 避免多个话题/正文粘连成「#话题1#话题2」）。候选点击已把 #tag 变成话题节点/链接，
                # 这里再补一个 space 把话题与下一个话题或后续正文隔开。
                await page.keyboard.press("Space")
                await page.wait_for_timeout(150)
            elif clear_on_fail:
                for _ in range(len(tag_prefix + tag)):
                    await page.keyboard.press("Backspace")
            else:
                await page.keyboard.press("Space")
            await page.wait_for_timeout(200)
        await page.keyboard.press("Escape")
    except Exception as exc:
        log.debug(_msg("🏷️", f"话题选择跳过（已选 {picked} 个）: {exc}"))
    return picked


async def _pick_topic_item_exact(page, tag: str, selectors: tuple[str, ...]) -> bool:
    tag = tag.lstrip("#")
    desired_len = len(tag)
    for _ in range(4):
        picked = await page.evaluate(
            """(crit) => {
                const [tag, desiredLen, sels] = crit;
                for (const sel of sels) {
                    for (const el of document.querySelectorAll(sel)) {
                        const t = (el.innerText || el.getAttribute('aria-label') || '').replace(/^#/, '').trim();
                        if (t && t === tag && t.length === desiredLen) { el.click(); return true; }
                    }
                }
                return false;
            }""",
            (tag, desired_len, list(selectors)),
        )
        if picked:
            return True
        await asyncio.sleep(0.5)
    return False


async def handle_upload_error(page, file_path: str, upload_input_selector: str = 'div.progress-div [class^="upload-btn-input"]') -> bool:
    """上传失败后触发重新上传（best-effort，选择器需实测校准）。"""
    try:
        await page.locator(upload_input_selector).set_input_files(file_path)
        _browser_logger.warning(_msg("😵", "视频上传摔了一跤，小人马上重新上传"))
        return True
    except Exception as exc:
        _browser_logger.debug(_msg("😵", f"重新上传失败：{exc}"))
        return False
