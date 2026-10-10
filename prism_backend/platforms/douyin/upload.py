"""
抖音上传模块 - 提供视频上传和发布功能
"""
import os
import asyncio
import time
import logging
import random
import re
from difflib import SequenceMatcher
from pathlib import Path
from datetime import datetime
from utils.automation_provider import async_playwright, Page
from typing import Dict, Any, Optional
# from config.conf import LOCAL_CHROME_PATH
from utils.base_social_media import set_init_script, HEADLESS_FLAG
from myUtils.browser_context import build_context_options, build_browser_args
from myUtils.close_guide import try_close_guide
from myUtils.publish_page_controls import dismiss_publish_guides, set_radio_choice, set_named_switch, douyin_video_upload_input
from utils.video_probe import probe_video_metadata
from ..base import BasePlatform
from ..path_utils import resolve_cookie_file, resolve_video_file

logger = logging.getLogger(__name__)


def _levenshtein_distance(a: str, b: str) -> int:
    """Return the character edit distance without adding a network dependency."""
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (ca != cb),
            ))
        previous = current
    return previous[-1]

# Build tag for runtime identification (helps confirm which implementation is used).
DOUYIN_PLATFORM_UPLOAD_BUILD_TAG = "platforms/douyin/upload.py:js-evaluate-cover+version-prompt@2026-09-02"

# 引导弹窗选择器
DOUYIN_TOUR_CONTAINERS = [
    '[role="dialog"]',
    '.semi-modal',
    '.semi-dialog',
    '.guide-modal',
    '.semi-modal-content',
]

DOUYIN_TOUR_BTNS = [
    'button:has-text("下一步")',
    'button:has-text("知道了")',
    'button:has-text("跳过")',
    'button:has-text("关闭")',
]

# 自主声明值归一化：前端/旧预设的文案 -> 抖音发布页「对作品内容添加声明」弹窗的真实单选项。
# 与 docs/douyin-publish-features.md §5.12 的实测枚举一一对应。
# 必须归一化后再去匹配，否则文案不一致会匹配不到选项 -> 弹窗残留 -> 发布按钮超时。
DOUYIN_DECLARATION_MAP = {
    # 前端/历史配置里可能出现的旧文案
    "不涉及（无需声明）": "无需添加自主声明",
    "不涉及": "无需添加自主声明",
    "使用AI工具生成": "内容由AI生成",
    "二次创作/剪辑": "内容为个人观点或见解",
    "剧情演绎/表演": "虚构演绎，仅供娱乐",
    "含广告/推广": "内容含营销推广信息",
    "知识科普": "内容为个人观点或见解",
}

# New UI XPaths (as of 2025-12) - best-effort (dynamic ids may change).
DOUYIN_COVER_CLICK_XPATH = "/html/body/div[@id='root']/div[@class='container-box']/div[@class='content-qNoE6N']/div[@class='micro-wrapper-OGvOEm']/div[@id='micro']/div[@id='garfish_app_for_douyin_creator_content_6fue1nrv']/div/div[2]/div[@id='root']/div[@class='card-container-creator-layout micro-LlzqtC new-layout']/div[@id='DCPF']/div[@class='container-pSH0u4']/div[@class='content-left-F3wKrk']/div[@class='form-container-MDtobK new-laytout']/div[@class='container-EMGgQp'][1]/div[2]/div[@class='content-obt4oA new-layout-sLYOT6'][1]/div[@class='content-child-V0CB7w content-limit-width-zybqBW']/div/div[@class='content-upload-new']/div[@class='wrapper-NN3Jh1']/div[@class='coverControl-CjlzqC'][1]/div[@class='cover-Jg3T4p']/div[@class='filter-k_CjvJ']"
DOUYIN_TITLE_INPUT_XPATH = "/html/body/div[@id='root']/div[@class='container-box']/div[@class='content-qNoE6N']/div[@class='micro-wrapper-OGvOEm']/div[@id='micro']/div[@id='garfish_app_for_douyin_creator_content_6fue1nrv']/div/div[2]/div[@id='root']/div[@class='card-container-creator-layout micro-LlzqtC new-layout']/div[@id='DCPF']/div[@class='container-pSH0u4']/div[@class='content-left-F3wKrk']/div[@class='form-container-MDtobK new-laytout']/div[@class='container-EMGgQp'][1]/div[2]/div[@class='publish-mention-wrapper-LWv5ed']/div[@class='content-obt4oA new-layout-sLYOT6']/div[@class='content-child-V0CB7w content-limit-width-zybqBW']/div/div[@class='editor-container-zRPSAi']/div[@class='editor-comp-publish-container-d4oeQI']/div[@class='editor-kit-root-container']/div[1]/div[@class='container-sGoJ9f']/div[@class='semi-input-wrapper semiInput-EyEyPL semi-input-wrapper__with-suffix semi-input-wrapper-default']/input[@class='semi-input semi-input-default']"
DOUYIN_COVER_VERTICAL_STEP_XPATH = "/html/body/div[@class='dy-creator-content-portal']/div[@class='modal-ExKlcK']/div[@class='dy-creator-content-modal-wrap']/div[@id='dialog-1']/div[@class='dy-creator-content-modal-content  undefined dy-creator-content-modal-content-height-set']/div[@id='dy-creator-content-modal-body']/div[@class='container-IaxQlJ']/div[@class='container-dTKE_6']/div[@class='steps-cgzd9T']/div[@class='step-dXVbPX step-active-AWDV7U']"
DOUYIN_COVER_DONE_BTN_XPATH = "/html/body/div[@class='dy-creator-content-portal']/div[@class='modal-ExKlcK']/div[@class='dy-creator-content-modal-wrap']/div[@id='dialog-1']/div[@class='dy-creator-content-modal-content  undefined dy-creator-content-modal-content-height-set']/div[@id='dy-creator-content-modal-body']/div[@class='container-IaxQlJ']/div[@class='wrap-qrLdpF']/div[@class='main-DAkOod']/div[@class='buttons-BoCvr4']/button[@class='semi-button semi-button-primary semi-button-light primary-RstHX_']"

# New cover UI selectors (2025-12): "编辑封面" trigger and different "完成" button classes by orientation.
DOUYIN_COVER_EDIT_TITLE_CSS = ".title-wA45Xd:has-text('编辑封面')"
DOUYIN_COVER_DONE_PRIMARY_CSS = "button.semi-button.semi-button-primary.semi-button-light.primary-RstHX_:has-text('完成')"
DOUYIN_COVER_DONE_SECONDARY_CSS = "button.semi-button.semi-button-primary.semi-button-light.secondary-zU1YLr:has-text('完成')"

DOUYIN_TITLE_INPUT_FALLBACK_XPATHS = [
    "//div[contains(@class,'editor-kit-root-container')]//div[contains(@class,'container-sGoJ9f')]//input[contains(@class,'semi-input')]",
    "//div[contains(@class,'editor-kit-root-container')]//input[contains(@class,'semi-input')]",
]

DOUYIN_TITLE_INPUT_FALLBACK_CSS = [
    'input[placeholder*="填写作品标题"]',
    "div.editor-kit-root-container div.container-sGoJ9f input.semi-input",
    "div.editor-kit-root-container input.semi-input",
]

DOUYIN_COVER_REQUIRED_TOAST_TEXT = "请设置封面后再发布"


async def dismiss_douyin_tour(page: Page, max_attempts: int = 6):
    return await dismiss_publish_guides(page, max_steps=max_attempts)


class DouyinUpload(BasePlatform):
    """抖音上传处理类"""
    
    def __init__(self):
        super().__init__(platform_code=3, platform_name="抖音")
        self.upload_url = "https://creator.douyin.com/creator-micro/content/upload"

    async def _debug_dump(self, page: Page, prefix: str) -> None:
        """保存截图与 HTML，便于排查页面改版导致的定位失败。"""
        try:
            log_dir = Path(__file__).resolve().parents[2] / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            png = log_dir / f"{prefix}_{ts}.png"
            html_path = log_dir / f"{prefix}_{ts}.html"
            ocr_path = log_dir / f"{prefix}_{ts}.ocr.txt"

            try:
                await page.screenshot(path=str(png), full_page=True)
            except Exception:
                pass

            try:
                html = await page.content()
                html_path.write_text(html, encoding="utf-8")
            except Exception:
                pass

            # Optional OCR on screenshot (helps when selectors are unstable but UI text is visible)
            try:
                import os
                from automation.ocr_client import ocr_image_bytes  # lazy import

                if os.getenv("SILICONFLOW_API_KEY") and png.exists():
                    text = ocr_image_bytes(
                        png.read_bytes(),
                        prompt="识别图中与发布/上传/弹窗相关的关键文字，按行输出。",
                    )
                    if text:
                        ocr_path.write_text(text, encoding="utf-8")
            except Exception:
                pass

            logger.info(f"[DouyinUpload] 已保存调试文件: {png.name}, {html_path.name}")
        except Exception as e:
            logger.warning(f"[DouyinUpload] 保存调试文件失败（忽略）: {e}")
    
    async def login(self, *args, **kwargs):
        """登录功能在 login.py 中实现"""
        raise NotImplementedError("请使用 DouyinLogin 类进行登录")
    
    async def upload(self,
                    account_file: str,
                    title: str,
                    file_path: str,
                    tags: list,
                    publish_date: Optional[Any] = None,
                    thumbnail_path: Optional[str] = None,
                    product_link: str = '',
                    product_title: str = '',
                    proxy: Optional[Dict[str, str]] = None,
                    enable_third_party: bool = False,
                    location: str = '',
                    declaration: Optional[str] = None,
                    random_cover: bool = False,
                    miniprogram_link: str = "",
                    miniprogram_title: str = "",
                    sync_platforms: Optional[list[str]] = None,
                    who_can_see: str = "",
                    save_permission: str = "",
                    hotspot: str = "",
                    collection: str = "",
                    cover_orientation: str = "",
                    cover_file: str = "",
                    miniprogram_object: Optional[Dict[str, Any]] = None,
                    **kwargs) -> Dict[str, Any]:
        """
        上传并发布抖音视频

        Args:
            account_file: Cookie文件路径
            title: 视频标题
            file_path: 视频文件路径
            tags: 标签列表
            publish_date: 定时发布时间（None表示立即发布）
            thumbnail_path: 封面图路径
            product_link: 商品链接
            product_title: 商品标题
            proxy: 代理配置，格式如 {"server": "http://proxy.example.com:8080"}
            enable_third_party: 是否启用第三方平台同步（头条/西瓜），默认True
            location: 地理位置（POI），如 "北京市朝阳区"
            declaration: 自主声明文本（用于"对作品内容添加声明"）
            random_cover: 是否随机选择推荐封面（页面要求"请设置封面后再发布"时生效）
            miniprogram_link: 小程序链接（用于挂载小程序标签）
            miniprogram_title: 小程序标题

        Returns:
            上传结果
        """
        try:
            async with async_playwright() as playwright:
                logger.info(f"[DouyinUpload] 实现版本: {DOUYIN_PLATFORM_UPLOAD_BUILD_TAG} (file={__file__})")

                # 🆕 标题清理逻辑（从旧版迁移）
                clean_title = str(title).splitlines()[0].strip()
                if "#" in clean_title:
                    clean_title = clean_title.split("#", 1)[0].strip()
                    logger.info(f"[DouyinUpload] 标题已清理: {title} -> {clean_title}")
                title = clean_title

                account_file = resolve_cookie_file(account_file)
                file_path = resolve_video_file(file_path)

                video_meta = probe_video_metadata(file_path)
                cover_aspect_ratio = {"portrait": "3:4", "landscape": "4:3"}.get(cover_orientation) or video_meta.get("cover_aspect_ratio")
                logger.info(
                    f"[DouyinUpload] 视频元数据: {video_meta.get('width')}x{video_meta.get('height')} "
                    f"({video_meta.get('aspect_ratio')}, {video_meta.get('orientation')}), cover={cover_aspect_ratio}"
                )
                
                publish_dt: Optional[datetime] = None
                if publish_date:
                    if isinstance(publish_date, datetime):
                        publish_dt = publish_date
                    elif isinstance(publish_date, (int, float)):
                        publish_dt = datetime.fromtimestamp(publish_date)
                    elif isinstance(publish_date, str):
                        s = publish_date.strip().replace("T", " ").replace("Z", "")
                        try:
                            publish_dt = datetime.fromisoformat(s)
                        except Exception:
                            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                                try:
                                    publish_dt = datetime.strptime(s, fmt)
                                    break
                                except Exception:
                                    continue

                    # 抖音定时发布规则验证：2小时后~14天内
                    if publish_dt:
                        now = datetime.now()
                        time_diff = (publish_dt - now).total_seconds()
                        min_delay = 2 * 3600  # 2小时
                        max_delay = 14 * 24 * 3600  # 14天

                        if time_diff < min_delay:
                            raise ValueError(
                                f"抖音定时发布时间必须在2小时后，当前距离: {int(time_diff / 60)}分钟"
                            )
                        if time_diff > max_delay:
                            raise ValueError(
                                f"抖音定时发布时间不能超过14天，当前距离: {int(time_diff / 86400)}天"
                            )
                # Use Chromium for Douyin publish.
                browser_options = build_browser_args()
                browser_options["headless"] = HEADLESS_FLAG
                # Do not pass empty executable_path, otherwise Playwright may try to spawn '.' (ENOENT)
                if not browser_options.get("executable_path"):
                    browser_options.pop("executable_path", None)
                    logger.info("[DouyinUpload] 使用 Playwright 内置 Chromium")
                else:
                    logger.info(f"[DouyinUpload] 使用本地 Chromium: {browser_options['executable_path']}")

                # 🆕 代理支持（从旧版迁移）
                if proxy:
                    browser_options['proxy'] = proxy
                    logger.info(f"[DouyinUpload] 使用代理: {proxy.get('server', 'unknown')}")

                from myUtils.browser_context import launch_optional_browser
                browser = await launch_optional_browser(playwright, platform="douyin", **browser_options)
                context = await browser.new_context(**build_context_options(storage_state=account_file))
                context = await set_init_script(context)
                page = await context.new_page()

                # ✅ 添加 dialog 事件监听器，自动关闭浏览器确认对话框（避免按钮失效）
                async def handle_dialog(dialog):
                    logger.warning(f"[DouyinUpload] 检测到浏览器弹窗: type={dialog.type}, message={dialog.message}")
                    try:
                        # 自动接受所有对话框（alert/confirm/prompt）
                        await dialog.accept()
                        logger.info(f"[DouyinUpload] 已自动关闭弹窗: {dialog.type}")
                    except Exception as e:
                        logger.error(f"[DouyinUpload] 关闭弹窗失败: {e}")

                page.on("dialog", handle_dialog)

                # 访问上传页面
                await page.goto(self.upload_url, wait_until="domcontentloaded", timeout=60000)

                # 处理可能的验证码
                await self._check_and_handle_verification(page, account_file)

                # 快速关闭引导（减少尝试次数）
                await dismiss_douyin_tour(page, max_attempts=3)

                logger.info(f"[DouyinUpload] 正在上传视频: {title}")

                # 上传视频文件（直接上传，不再等待页面URL）
                logger.info(f"[DouyinUpload] 准备上传视频文件: {file_path}")
                video_input = await douyin_video_upload_input(page)
                await video_input.set_input_files(file_path)

                # 等待进入发布页面
                await self._wait_for_upload_page(page)
                await dismiss_douyin_tour(page, max_attempts=2)

                # 关闭「官方新版本/新增功能」提示遮挡层（best-effort）
                await self.dismiss_version_prompt(page)

                # 填充标题和标签
                await self._fill_title_and_tags(page, title, tags, enable_third_party=enable_third_party)
                
                # 等待视频上传完成
                await self._wait_for_video_upload(page)
                
                # 设置封面（尽量设置，避免"请设置封面后再发布"）；cover_file 有值时回退当封面上传
                if not thumbnail_path and cover_file:
                    thumbnail_path = cover_file
                await self._set_thumbnail_best_effort(page, thumbnail_path, cover_aspect_ratio=cover_aspect_ratio)
                await self._wait_cover_modal_closed(page)

                # 设置地理位置（如果提供）
                if location:
                    await self._set_location(page, location)

                # 处理浏览器位置权限弹窗（有位置→允许；未选位置→不允许）
                await self._handle_browser_permission(page, allow_location=bool(location), has_location=bool(location))

                if sync_platforms is not None:
                    await self._set_sync_platforms(page, sync_platforms)

                # 专属配置必须设置成功后才能继续发布：合集 → 挂载内容 → 关联热点 → 谁可以看 → 保存权限
                if collection:
                    await self._set_collection(page, collection)
                if miniprogram_object:
                    await self._set_mount_object(page, miniprogram_object)
                if hotspot:
                    await self._set_hotspot(page, hotspot)
                if who_can_see:
                    await self._set_who_can_see(page, who_can_see)
                if save_permission:
                    await self._set_save_permission(page, save_permission)

                # 设置商品链接（如果提供）
                if product_link and product_title:
                    await self._set_product_link(page, product_link, product_title)

                # 设置自主声明（如果提供）
                if declaration and not await self.set_self_declaration(page, declaration):
                    raise ValueError(f"自主声明未成功设置：{declaration}")

                # 挂载小程序标签（如果提供）
                if miniprogram_link:
                    await self.set_miniprogram_link(page, miniprogram_link)
                
                # 设置定时发布（如果提供）
                if publish_dt:
                    await self._set_schedule_time(page, publish_dt)

                # 未指定自定义封面且启用随机封面时，选择推荐封面（页面要求"请设置封面后再发布"时生效）
                if random_cover and not thumbnail_path:
                    await self._pick_recommend_cover(page, random_cover=random_cover)

                await dismiss_publish_guides(page)
                # 点击发布
                await self._publish_video(page, thumbnail_path, cover_aspect_ratio=cover_aspect_ratio)

                # 保存Cookie
                await context.storage_state(path=account_file)
                logger.info("[DouyinUpload] Cookie已更新")
                
                await browser.close()
                
                return {
                    "success": True,
                    "message": "视频发布成功",
                    "data": {
                        "title": title,
                        "file_path": file_path
                    }
                }
                
        except Exception as e:
            logger.error(f"[DouyinUpload] 上传失败: {e}")
            # ⚠️ 确保异常时也关闭浏览器，避免资源泄露
            try:
                if 'browser' in locals():
                    await browser.close()
            except Exception:
                pass
            return {
                "success": False,
                "message": str(e)
            }

    async def _fill_title_best_effort(self, page: Page, title: str) -> bool:
        desired = (title or "").strip()[:30]
        if not desired:
            return False

        candidates = [
            f"xpath={DOUYIN_TITLE_INPUT_XPATH}",
            *[f"xpath={xp}" for xp in DOUYIN_TITLE_INPUT_FALLBACK_XPATHS],
            *DOUYIN_TITLE_INPUT_FALLBACK_CSS,
            "text=作品标题 >> xpath=../following-sibling::div[1]//input",
        ]

        for selector in candidates:
            try:
                loc = page.locator(selector).first
                if await loc.count() == 0 or not await loc.is_visible():
                    continue
                await loc.click()
                await loc.fill(desired)
                await page.wait_for_timeout(100)
                try:
                    val = await loc.input_value()
                    if (val or "") == desired or desired in (val or ""):
                        return True
                except Exception:
                    return True
            except Exception:
                continue

        # contenteditable fallback - 使用 JavaScript 直接设置，避免慢速逐字符输入
        try:
            titlecontainer = page.locator(".notranslate").first
            if await titlecontainer.count() and await titlecontainer.is_visible():
                await titlecontainer.click()
                # 使用 JavaScript 直接设置 textContent/innerText（快速）
                await titlecontainer.evaluate(f"el => {{ el.textContent = '{desired}'; el.innerText = '{desired}'; }}")
                # 触发 input 事件让前端感知变化
                await titlecontainer.evaluate("el => el.dispatchEvent(new Event('input', { bubbles: true }))")
                await page.wait_for_timeout(100)
                return True
        except Exception:
            pass
        return False

    async def _pick_any_cover_in_modal(self, page: Page) -> bool:
        selectors = [
            "div.dy-creator-content-portal img",
            "div.dy-creator-content-modal img",
            "[role='dialog'] img",
            "img",
        ]
        for sel in selectors:
            try:
                img = page.locator(sel).first
                if await img.count() and await img.is_visible():
                    await img.click()
                    await page.wait_for_timeout(200)
                    return True
            except Exception:
                continue
        return False

    def _cover_modal_locator(self, page: Page):
        # Douyin cover selector lives under these portal/modal containers.
        return page.locator("div.dy-creator-content-modal, div.dy-creator-content-portal")

    async def _is_cover_modal_open(self, page: Page) -> bool:
        containers = self._cover_modal_locator(page)
        for index in range(await containers.count()):
            if await containers.nth(index).is_visible():
                return True
        return False

    async def _wait_cover_modal_closed(self, page: Page, timeout_ms: int = 20000) -> None:
        """Finish the cover editor through its controls; never remove its DOM."""
        start = time.monotonic()
        while time.monotonic() - start < timeout_ms / 1000:
            if not await self._is_cover_modal_open(page):
                return
            await dismiss_publish_guides(page)
            containers = self._cover_modal_locator(page)
            for index in range(await containers.count()):
                container = containers.nth(index)
                if not await container.is_visible():
                    continue
                for label in ("完成", "确定", "确认"):
                    button = container.get_by_role("button", name=label, exact=True)
                    if await button.count() == 1 and await button.is_visible() and await button.is_enabled():
                        try:
                            await button.click(timeout=2000)
                        except Exception:
                            logger.debug("Cover completion control remains blocked", exc_info=True)
                        break
            await page.wait_for_timeout(300)
        raise TimeoutError("封面编辑弹层未关闭，已停止设置定时及提交发布，请完成封面编辑后重试")

    async def _set_thumbnail_best_effort(
        self,
        page: Page,
        thumbnail_path: Optional[str],
        *,
        cover_aspect_ratio: Optional[str] = None,
    ) -> None:
        """
        设置封面（使用旧版 uploader 的稳定逻辑）
        """
        try:
            logger.info(f"[DouyinUpload] 开始设置封面（视频比例={cover_aspect_ratio}）")

            # 步骤1: 点击编辑封面入口（多个 fallback）
            clicked = False
            for sel in [
                ".title-wA45Xd:has-text('编辑封面')",
                'text="编辑封面"',
                'text="选择封面"',
                'text="设置封面"',
                'text=/选择封面|设置封面/',
            ]:
                try:
                    await page.click(sel, timeout=2000)
                    clicked = True
                    logger.info(f"[DouyinUpload] ✅ 已点击封面入口: {sel}")
                    break
                except Exception:
                    continue

            if not clicked:
                logger.warning("[DouyinUpload] 未找到封面入口按钮")
                return

            # 步骤2: 等待封面弹窗出现（等待真正的 modal，不是 portal 容器）
            try:
                await page.wait_for_selector(
                    "div.dy-creator-content-modal:visible, div.dy-creator-content-modal-wrap:visible",
                    timeout=8000
                )
                logger.info("[DouyinUpload] ✅ 封面弹窗已出现")
            except Exception as e:
                # Fallback: 检查是否有 role=dialog
                try:
                    await page.wait_for_selector('[role="dialog"]:visible', timeout=3000)
                    logger.info("[DouyinUpload] ✅ 封面弹窗已出现（dialog）")
                except Exception:
                    logger.warning(f"[DouyinUpload] 等待封面弹窗超时: {e}")
                    return

            # 步骤3: 尝试点击"设置竖封面"（如果有）
            try:
                await page.click('text="设置竖封面"', timeout=3000)
                logger.info("[DouyinUpload] ✅ 已点击'设置竖封面'")
            except Exception:
                pass

            # 步骤4: 上传自定义封面（如果提供）
            if thumbnail_path:
                logger.info(f"[DouyinUpload] 正在上传自定义封面: {thumbnail_path}")
                await page.wait_for_timeout(500)
                await page.locator("div[class^='semi-upload upload'] >> input.semi-upload-hidden-input").set_input_files(thumbnail_path)
                await page.wait_for_timeout(800)
                logger.info("[DouyinUpload] ✅ 已上传自定义封面")

            # 步骤5: 等待并点击完成按钮（使用 JavaScript evaluate）
            try:
                logger.info("[DouyinUpload] 等待完成按钮可用...")

                # 等待完成按钮出现且可用
                await page.wait_for_function("""
                () => {
                    const btn1 = document.getElementsByClassName("semi-button semi-button-primary semi-button-light primary-RstHX_")[0];
                    const btn2 = document.getElementsByClassName("semi-button semi-button-primary semi-button-light secondary-zU1YLr")[0];

                    const checkBtn = (btn) => {
                        if (!btn) return false;
                        const text = btn.innerText?.trim();
                        const style = window.getComputedStyle(btn);
                        return text === '完成' &&
                               !btn.className.includes('disabled') &&
                               style.display !== 'none' &&
                               style.visibility !== 'hidden' &&
                               btn.offsetParent !== null;
                    };

                    return checkBtn(btn1) || checkBtn(btn2);
                }
                """, timeout=15000)

                logger.info("[DouyinUpload] ✅ 完成按钮已可用")

                # 点击完成按钮
                clicked = await page.evaluate("""
                () => {
                    // 优先尝试 primary (竖屏)
                    const btn1 = document.getElementsByClassName("semi-button semi-button-primary semi-button-light primary-RstHX_")[0];
                    if (btn1 && btn1.innerText?.trim() === '完成' &&
                        !btn1.className.includes('disabled') &&
                        btn1.offsetParent !== null) {
                        btn1.click();
                        return 'primary-RstHX_';
                    }

                    // 尝试 secondary (横屏)
                    const btn2 = document.getElementsByClassName("semi-button semi-button-primary semi-button-light secondary-zU1YLr")[0];
                    if (btn2 && btn2.innerText?.trim() === '完成' &&
                        !btn2.className.includes('disabled') &&
                        btn2.offsetParent !== null) {
                        btn2.click();
                        return 'secondary-zU1YLr';
                    }

                    return null;
                }
                """)

                if clicked:
                    logger.info(f"[DouyinUpload] ✅ 已点击完成按钮: {clicked}")
                else:
                    logger.warning("[DouyinUpload] 未找到可用的完成按钮")

            except Exception as e:
                logger.warning(f"[DouyinUpload] 完成按钮点击失败: {e}")
                # 兜底：CSS-Module 哈希 class 随版本变化，改用文本语义点「完成/确定/保存」
                try:
                    btn = page.locator(
                        "button:visible:has-text('完成'), button:visible:has-text('确定'), button:visible:has-text('保存')"
                    ).first
                    if await btn.count() and await btn.is_visible() and await btn.is_enabled():
                        await btn.click(timeout=3000)
                        await page.wait_for_timeout(500)
                        logger.info("[DouyinUpload] ✅ 已用文本语义点击完成按钮")
                except Exception as e2:
                    logger.warning(f"[DouyinUpload] 文本语义点完成失败: {e2}")

            # 步骤6: 等待弹窗关闭
            try:
                await page.wait_for_selector(
                    "div.extractFooter, div.dy-creator-content-modal, div.dy-creator-content-portal",
                    state="detached",
                    timeout=8000
                )
                logger.info("[DouyinUpload] ✅ 封面弹窗已关闭")
            except Exception:
                logger.warning("[DouyinUpload] 封面弹窗未在预期内关闭（忽略）")

            logger.info("[DouyinUpload] ✅ 封面设置完成")
            return

        except Exception as e:
            logger.warning(f"[DouyinUpload] 封面设置流程失败，跳过封面设置: {e}")
            return

    async def _check_and_handle_verification(self, page: Page, account_id: str):
        """检查并处理短信验证码"""
        try:
            modal = page.locator("text=接收短信验证码").first
            if await modal.count() == 0:
                return
            
            logger.info("[DouyinUpload] 检测到验证码弹窗")
            
            # 使用基类的验证码处理方法
            success = await self.handle_verification(
                page=page,
                account_id=account_id,
                trigger_selector="text=获取验证码"
            )
            
            if not success:
                raise Exception("验证码验证失败")
                
        except Exception as e:
            logger.error(f"[DouyinUpload] 验证码处理失败: {e}")
            raise
    
    async def _wait_for_upload_page(self, page: Page):
        """等待进入视频发布页面"""
        start = time.monotonic()
        while True:
            if time.monotonic() - start > 30:
                await self._debug_dump(page, "douyin_wait_publish_page_timeout")
                raise TimeoutError("进入抖音发布页面超时（30s），可能页面改版或被拦截")

            # 检查 URL 是否匹配
            current_url = page.url
            if "creator.douyin.com/creator-micro/content/publish" in current_url or \
               "creator.douyin.com/creator-micro/content/post/video" in current_url:
                logger.info(f"[DouyinUpload] 已进入发布页面: {current_url}")
                break

            # 或者检查页面上是否已有标题输入框（说明已经进入发布页面）
            try:
                title_input = page.locator('input[placeholder*="填写作品标题"]').first
                if await title_input.count() > 0 and await title_input.is_visible():
                    logger.info(f"[DouyinUpload] 检测到标题输入框，已进入发布页面: {current_url}")
                    break
            except:
                pass

            await asyncio.sleep(0.5)
    
    async def _fill_title_and_tags(self, page: Page, title: str, tags: list, enable_third_party: bool = False):
        """填充标题和标签"""
        logger.info("[DouyinUpload] 填充标题和标签...")
        await self._fill_title_best_effort(page, title)

        # 🆕 标签去重与数量限制（从旧版迁移）
        seen = set()
        normalized_tags = []
        max_tags = 0
        try:
            max_tags = int(os.getenv("DOUYIN_MAX_TAGS", "0"))
        except ValueError:
            max_tags = 0
        for t in tags or []:
            t = str(t).strip().lstrip("#")
            if not t or t in seen:
                continue
            seen.add(t)
            normalized_tags.append(t)
            if max_tags > 0 and len(normalized_tags) >= max_tags:
                break

        logger.info(f"[DouyinUpload] 标签已去重: {len(tags)} -> {len(normalized_tags)} 个")

        # 添加话题标签 (在描述框中)
        # 用户确认描述框位置为 zone-container
        css_selector = ".zone-container"
        try:
            zone = page.locator(css_selector).first
            if await zone.count() > 0 and await zone.is_visible():
                await zone.click()
                await page.wait_for_timeout(200)

                # ⚠️ 先清空旧内容
                await page.keyboard.press("Control+KeyA")
                await page.keyboard.press("Delete")
                await page.wait_for_timeout(100)

                # ⚠️ 逐个输入标签，触发抖音的补全下拉框
                for idx, tag in enumerate(normalized_tags):
                    # 输入 #标签名
                    await page.keyboard.type(f"#{tag}")
                    await page.wait_for_timeout(500)  # 等待补全下拉框出现

                    # 检查是否有补全下拉框
                    try:
                        # 抖音标签补全下拉框的选择器（通常是 .topic-item 或类似）
                        suggestion = page.locator('.topic-item, .topic-list-item').first
                        if await suggestion.count() > 0:
                            await page.keyboard.press("ArrowDown")  # 选中第一个补全项
                            await page.wait_for_timeout(100)
                            await page.keyboard.press("Enter")  # 确认选择
                            await page.wait_for_timeout(200)
                        else:
                            # 没有补全，直接按空格继续
                            await page.keyboard.press("Space")
                            await page.wait_for_timeout(100)
                    except:
                        # 补全失败，按空格继续
                        await page.keyboard.press("Space")
                        await page.wait_for_timeout(100)

                    logger.info(f"[DouyinUpload] 已添加标签 {idx+1}/{len(normalized_tags)}: #{tag}")

                logger.info(f"[DouyinUpload] 已添加 {len(normalized_tags)} 个标签")
        except Exception as e:
            logger.error(f"[DouyinUpload] 填充标签失败: {e}")

        # 🆕 第三方平台同步（头条/西瓜）（从旧版迁移）
        if enable_third_party:
            await self._enable_third_party_sync(page)
    
    async def _wait_for_video_upload(self, page: Page):
        """等待视频上传完成"""
        start = time.monotonic()
        while True:
            try:
                count = await page.locator('[class^="long-card"] div:has-text("重新上传")').count()
                if count > 0:
                    logger.info("[DouyinUpload] 视频上传完成")
                    break
                if time.monotonic() - start > 60 * 20:
                    await self._debug_dump(page, "douyin_upload_timeout")
                    raise TimeoutError("抖音视频上传超时（20min），请检查网络/页面状态")
                logger.info("[DouyinUpload] 正在上传视频...")
                await asyncio.sleep(2)
            except:
                await asyncio.sleep(2)
    
    async def _set_thumbnail(self, page: Page, thumbnail_path: str):
        """设置视频封面"""
        logger.info("[DouyinUpload] 设置视频封面...")
        await page.click('text="选择封面"')
        await page.wait_for_selector("div.dy-creator-content-modal")
        await page.click('text="设置竖封面"')
        await page.wait_for_timeout(2000)
        await page.locator("div[class^='semi-upload upload'] >> input.semi-upload-hidden-input").set_input_files(thumbnail_path)
        await page.wait_for_timeout(2000)
        await page.locator("div#tooltip-container button:visible:has-text('完成')").click()
        logger.info("[DouyinUpload] 封面设置完成")
    
    async def _set_product_link(self, page: Page, product_link: str, product_title: str):
        """
        设置商品链接（完整实现）
        从旧版 uploader/douyin_uploader/main.py 迁移
        """
        logger.info("[DouyinUpload] 正在设置商品链接...")
        await page.wait_for_timeout(2000)
        try:
            # 定位"添加标签"文本，然后向上导航到容器，再找到下拉框
            await page.wait_for_selector('text=添加标签', timeout=10000)
            dropdown = page.get_by_text('添加标签').locator("..").locator("..").locator("..").locator(".semi-select").first
            if not await dropdown.count():
                logger.error("[DouyinUpload] 未找到标签下拉框")
                return False

            logger.info("[DouyinUpload] 找到标签下拉框，准备选择'购物车'")
            await dropdown.click()

            # 等待下拉选项出现
            await page.wait_for_selector('[role="listbox"]', timeout=5000)

            # 选择"购物车"选项
            await page.locator('[role="option"]:has-text("购物车")').click()
            logger.info("[DouyinUpload] 成功选择'购物车'")

            # 输入商品链接
            await page.wait_for_selector('input[placeholder="粘贴商品链接"]', timeout=5000)
            input_field = page.locator('input[placeholder="粘贴商品链接"]')
            await input_field.fill(product_link)
            logger.info(f"[DouyinUpload] 已输入商品链接: {product_link}")

            # 点击"添加链接"按钮
            add_button = page.locator('span:has-text("添加链接")')
            button_class = await add_button.get_attribute('class')
            if 'disable' in button_class:
                logger.error("[DouyinUpload] '添加链接'按钮不可用")
                return False

            await add_button.click()
            logger.info("[DouyinUpload] 成功点击'添加链接'按钮")

            # 检查链接是否有效
            await page.wait_for_timeout(2000)
            error_modal = page.locator('text=未搜索到对应商品')
            if await error_modal.count():
                confirm_button = page.locator('button:has-text("确定")')
                await confirm_button.click()
                logger.error("[DouyinUpload] 商品链接无效")
                return False

            # 填写商品短标题
            if not await self._handle_product_dialog(page, product_title):
                return False

            logger.info("[DouyinUpload] 成功设置商品链接")
            return True
        except Exception as e:
            logger.error(f"[DouyinUpload] 设置商品链接时出错: {str(e)}")
            return False

    async def _handle_product_dialog(self, page: Page, product_title: str):
        """
        处理商品编辑弹窗
        从旧版 uploader/douyin_uploader/main.py 迁移
        """
        logger.info("[DouyinUpload] 处理商品编辑弹窗...")
        await page.wait_for_timeout(2000)

        try:
            await page.wait_for_selector('input[placeholder="请输入商品短标题"]', timeout=10000)
            short_title_input = page.locator('input[placeholder="请输入商品短标题"]')
            if not await short_title_input.count():
                logger.error("[DouyinUpload] 未找到商品短标题输入框")
                return False

            # 商品短标题最多10个字符
            product_title = product_title[:10]
            await short_title_input.fill(product_title)
            logger.info(f"[DouyinUpload] 已填写商品短标题: {product_title}")

            # 等待界面响应
            await page.wait_for_timeout(1000)

            # 检查"完成编辑"按钮状态
            finish_button = page.locator('button:has-text("完成编辑")')
            button_classes = await finish_button.get_attribute('class')

            if 'disabled' not in button_classes:
                await finish_button.click()
                logger.info("[DouyinUpload] 成功点击'完成编辑'按钮")

                # 等待对话框关闭
                await page.wait_for_selector('.semi-modal-content', state='hidden', timeout=5000)
                return True
            else:
                logger.error("[DouyinUpload] '完成编辑'按钮处于禁用状态，尝试关闭对话框")
                # 如果按钮禁用，尝试点击取消或关闭按钮
                cancel_button = page.locator('button:has-text("取消")')
                if await cancel_button.count():
                    await cancel_button.click()
                else:
                    # 点击右上角的关闭按钮
                    close_button = page.locator('.semi-modal-close')
                    await close_button.click()

                await page.wait_for_selector('.semi-modal-content', state='hidden', timeout=5000)
                return False
        except Exception as e:
            logger.error(f"[DouyinUpload] 处理商品编辑弹窗失败: {e}")
            return False

    async def _set_location(self, page: Page, location: str):
        """
        设置地理位置（POI）
        从旧版 uploader/douyin_uploader/main.py 迁移
        """
        if not location:
            return

        logger.info(f"[DouyinUpload] 正在设置地理位置: {location}")
        try:
            location_input = page.get_by_placeholder("输入地理位置", exact=True)
            await location_input.fill(location)
            await page.wait_for_selector('div[role="listbox"] [role="option"]', timeout=5000)
            candidate = page.get_by_role("option", name=location, exact=True)
            if await candidate.count() != 1 or not await candidate.is_visible():
                raise ValueError(f"未找到唯一地点候选：{location}")
            await candidate.click(timeout=5000)
            logger.info(f"[DouyinUpload] 成功设置地理位置: {location}")
        except Exception as e:
            raise ValueError("抖音专属配置未成功应用，请检查地点、热点或合集候选") from e
    
    async def _set_schedule_time(self, page: Page, publish_date: datetime):
        """设置定时发布"""
        await self._wait_cover_modal_closed(page)
        await dismiss_publish_guides(page)
        label_element = page.locator("[class^='radio']:has-text('定时发布')")
        await label_element.click()
        await asyncio.sleep(1)
        
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")
        await page.locator('.semi-input[placeholder="日期和时间"]').click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")
        await asyncio.sleep(1)

    async def _publish_video(
        self,
        page: Page,
        thumbnail_path: Optional[str] = None,
        *,
        cover_aspect_ratio: Optional[str] = None,
    ):
        """点击发布按钮"""
        logger.info("[DouyinUpload] 准备点击发布按钮...")

        # 等待发布按钮可用
        max_wait = 60
        start = time.monotonic()

        await self._wait_cover_modal_closed(page, timeout_ms=8000)

        # best-effort：同样关闭「对作品内容添加声明」自主声明弹窗。
        # 该弹窗若残留（.semi-modal 遮罩）同样会挡住发布按钮（实测 2026-09-03 16:20 即因此超时）。
        try:
            await self._force_close_declaration_modal(page, timeout_ms=5000)
        except Exception as e:
            logger.warning(f"[DouyinUpload] 自主声明弹窗未自动关闭({e})")

        while time.monotonic() - start < max_wait:
            try:
                publish_button = page.get_by_role("button", name="发布", exact=True).first

                if await publish_button.count() and await publish_button.is_visible():
                    try:
                        if await publish_button.is_enabled():
                            await publish_button.click(timeout=5000)
                            logger.info("[DouyinUpload] 已点击发布按钮，等待跳转...")

                            # 等待跳转到管理页面
                            try:
                                await page.wait_for_url("**/creator-micro/content/manage**", timeout=15000)
                                logger.info("[DouyinUpload] ✅ 视频发布成功")
                                return
                            except:
                                # 可能已经发布成功但URL不匹配，检查页面内容
                                await asyncio.sleep(2)
                                if "manage" in page.url or "content" in page.url:
                                    logger.info("[DouyinUpload] ✅ 视频发布成功（通过URL检测）")
                                    return
                                logger.warning("[DouyinUpload] 发布后未检测到跳转，继续等待...")
                    except Exception as e:
                        logger.debug(f"[DouyinUpload] 发布按钮不可用: {e}")

                await asyncio.sleep(1)
            except Exception as e:
                logger.debug(f"[DouyinUpload] 等待发布按钮: {e}")
                await asyncio.sleep(1)

        # 超时
        await self._debug_dump(page, "douyin_publish_timeout")
        raise TimeoutError("[DouyinUpload] 点击发布按钮超时（60s）")


    async def _enable_third_party_sync(self, page: Page):
        """
        启用第三方平台同步（头条/西瓜）
        从旧版 uploader/douyin_uploader/main.py 迁移
        """
        try:
            # 第三方平台开关选择器
            third_part_element = '[class^="info"] > [class^="first-part"] div div.semi-switch'

            # 检测是否有第三方平台选项
            if await page.locator(third_part_element).count() == 0:
                logger.info("[DouyinUpload] 未找到第三方平台同步开关（可能账号未开通）")
                return

            # 检测是否已选中状态
            switch_classes = await page.eval_on_selector(third_part_element, 'div => div.className')
            if 'semi-switch-checked' not in switch_classes:
                logger.info("[DouyinUpload] 启用第三方平台同步（头条/西瓜）")
                await page.locator(third_part_element).locator('input.semi-switch-native-control').click()
                await page.wait_for_timeout(500)
            else:
                logger.info("[DouyinUpload] 第三方平台同步已启用")
        except Exception as e:
            logger.warning(f"[DouyinUpload] 第三方平台同步设置失败（忽略继续）: {e}")

    async def dismiss_version_prompt(self, page: Page) -> bool:
        return bool(await dismiss_publish_guides(page))

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
                    logger.info(f"[DouyinUpload] 检测到浏览器权限弹窗，has_location={has_location}")
                    if has_location or allow_location:
                        # 点「仅本次」优先；没有则「允许」
                        pick = None
                        for t in ("仅本次", "仅此一次", "允许"):
                            try:
                                pick = page.get_by_text(t, exact=True).first
                                if await pick.count() and await pick.is_visible():
                                    await pick.click(timeout=2000)
                                    logger.info(f"[DouyinUpload] 已点「{t}」")
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
                                    logger.info(f"[DouyinUpload] 已点「{t}」以关闭位置询问")
                                    return
                            except Exception:
                                continue
                    break
        except Exception as exc:
            logger.debug(f"[DouyinUpload] 位置权限弹窗处理跳过：{exc}")

    async def set_miniprogram_link(self, page: Page, miniprogram_link: str) -> bool:
        """添加标签 → 挂小程序（输入小程序链接）。best-effort，选择器需实测校准。"""
        if not miniprogram_link:
            return False
        try:
            await page.wait_for_timeout(2000)
            await page.wait_for_selector("text=添加标签", timeout=10000)
            dropdown = page.get_by_text("添加标签").locator("..").locator("..").locator("..").locator(".semi-select").first
            if not await dropdown.count():
                logger.error("[DouyinUpload] 没找到标签下拉框")
                return False
            await dropdown.click()
            await page.wait_for_selector('[role="listbox"]', timeout=5000)
            # 小程序入口：兜底命中「小程序」选项
            opt = page.locator('[role="option"]:has-text("小程序")').first
            if not await opt.count():
                opt = page.get_by_text("小程序", exact=True).first
            if not await opt.count() or not await opt.is_visible():
                logger.warning("[DouyinUpload] 未找到「小程序」标签入口")
                return False
            await opt.click()

            # 输入小程序链接
            link_input = page.locator('input[placeholder*="小程序链接"], input[placeholder*="粘贴小程序"], input[placeholder*="链接"]').first
            await link_input.wait_for(state="visible", timeout=5000)
            await link_input.fill(miniprogram_link)
            logger.debug(f"[DouyinUpload] 小程序链接已填: {miniprogram_link}")

            add_btn = page.locator('span:has-text("添加"), button:has-text("添加")').first
            if await add_btn.count():
                await add_btn.click()
            await page.wait_for_timeout(1500)
            logger.info("[DouyinUpload] 小程序标签已挂载")
            return True
        except Exception as exc:
            logger.warning(f"[DouyinUpload] 挂小程序标签失败: {exc}")
            return False

    async def _force_close_declaration_modal(self, page: Page, timeout_ms: int = 5000) -> None:
        """尽力关闭「对作品内容添加声明」弹窗（.semi-modal-content）。

        与 _wait_cover_modal_closed 同理：该弹窗若残留，其遮罩（dy-creator-content-modal-mask）
        会拦截 `发布` 按钮的 pointer-events，导致 _publish_video 60s 超时。
        """
        start = time.monotonic()
        # 先点「取消」优先（不会误触发提交），再点右上角关闭
        for sel in [
            '.semi-modal-content button:has-text("取消")',
            '.semi-modal-content button:has-text("关闭")',
            '.semi-modal-content .semi-modal-close',
        ]:
            if time.monotonic() - start > timeout_ms / 1000:
                break
            try:
                btn = page.locator(sel).first
                if await btn.count() and await btn.is_visible():
                    await btn.click(timeout=2000)
                    await page.wait_for_timeout(300)
            except Exception:
                continue

        # 若仍可见（点关闭失败或超时），直接移除 DOM，避免遮罩残留
        if await page.locator(".semi-modal-content").filter(has_text="对作品内容添加声明").first.is_visible():
            try:
                await page.evaluate(
                    "() => document.querySelectorAll('.semi-modal-wrap, .semi-modal, "
                    ".semi-modal-content, .dy-creator-content-modal-wrap, "
                    ".dy-creator-content-modal-mask').forEach(e => e.remove())"
                )
                await page.wait_for_timeout(300)
            except Exception:
                pass

    async def set_self_declaration(self, page: Page, declaration: str) -> bool:
        """按调用方给出的平台原文选择自主声明；失败返回 False。

        关键：无论成功失败都必须关闭「对作品内容添加声明」弹窗。
        若该弹窗残留（.semi-modal-content 遮罩），会挡发布按钮导致 _publish_video 60s 超时。
        """
        # 归一化调用方/旧预设文案 -> 平台真实单选项（见 DOUYIN_DECLARATION_MAP）
        declaration = DOUYIN_DECLARATION_MAP.get((declaration or "").strip(), declaration or "")
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
            logger.info(f"[DouyinUpload] 自主声明已选择「{declaration}」")
            return True
        except Exception as exc:
            logger.warning(f"[DouyinUpload] 自主声明设置失败：{exc}")
            # 失败后仍要尽力关闭弹窗，避免其遮罩残留挡住后续「发布」按钮
            try:
                await self._force_close_declaration_modal(page)
            except Exception as close_exc:
                logger.warning(f"[DouyinUpload] 关闭自主声明弹窗失败：{close_exc}")
            return False

    async def _pick_recommend_cover(self, page: Page, random_cover: bool = False) -> bool:
        """页面要求"请设置封面后再发布"时，从推荐封面里选一帧（random_cover=True 随机，否则选第 1 张）。

        从旧版 uploader/douyin_uploader/main_refactored.py 的 handle_auto_video_cover 迁移。
        """
        if await page.get_by_text(DOUYIN_COVER_REQUIRED_TOAST_TEXT).first.is_visible():
            logger.info("[DouyinUpload] 发布前还得先把封面弄好")
            covers = page.locator('[class^="recommendCover-"]')
            n = await covers.count()
            if n > 0:
                # 勾选随机封面：在可用推荐封面里随机选一帧，降低"只取第一张"的容错率
                idx = random.randrange(n) if random_cover and n > 1 else 0
                target = covers.nth(idx)
                logger.info(f"[DouyinUpload] 小人去选推荐封面 (random={random_cover}, 共{n}, 选第{idx + 1})")
                try:
                    await target.click()
                    await asyncio.sleep(1)
                    confirm_text = "是否确认应用此封面？"
                    if await page.get_by_text(confirm_text).first.is_visible():
                        logger.info(f"[DouyinUpload] 弹出确认框了: {confirm_text}")
                        await page.get_by_role("button", name="确定").click()
                        logger.info("[DouyinUpload] 推荐封面已经应用")
                        await asyncio.sleep(1)
                    logger.info("[DouyinUpload] 封面选择流程完成")
                    return True
                except Exception as e:
                    logger.warning(f"[DouyinUpload] 推荐封面没选成功: {e}")
        return False

    async def _set_who_can_see(self, page: Page, who_can_see: str) -> None:
        await set_radio_choice(page, "谁可以看", who_can_see)

    async def _set_save_permission(self, page: Page, save_permission: str) -> None:
        await set_radio_choice(page, "保存权限", save_permission)

    async def _set_hotspot(self, page: Page, hotspot: str) -> None:
        """关联热点：点「点击输入热点词」筛选下拉 → 输入关键词 → ArrowDown+Enter 选第一条。

        实测：该筛选下拉内部有 1 个 input，打开即预载约 55 个（含隐藏项）选项，
        故用 Semi 原生键盘交互而非点击（避免点中隐藏选项）。
        """
        if not hotspot:
            return
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
            candidate = page.get_by_role("option", name=hotspot, exact=True)
            if await candidate.count() != 1 or not await candidate.is_visible():
                raise ValueError(f"未找到唯一热点候选：{hotspot}")
            await candidate.click(timeout=5000)
            logger.info(f"[DouyinUpload] 关联热点已选「{hotspot}」")
        except Exception as exc:
            raise ValueError("抖音专属配置未成功应用，请检查地点、热点或合集候选") from exc

    async def _set_collection(self, page: Page, collection: str) -> None:
        """添加到合集：点「请选择合集」下拉选择合集；空/找不到则选「不选择合集」。"""
        if not collection:
            return
        try:
            box = page.locator("div.semi-select.select-collection-nkL6sA").first
            await box.wait_for(state="visible", timeout=8000)
            await box.click(timeout=5000)
            await page.wait_for_selector('[role="listbox"] [role="option"]', timeout=8000)
            target = (collection or "").strip()
            option = None
            if target and target not in ("不选择合集", "不加入合集"):
                option = page.get_by_role("option", name=target, exact=True)
                if await option.count() != 1:
                    raise ValueError(f"未找到唯一合集候选：{target}")
            if not option or not await option.count():
                option = page.locator('[role="listbox"] [role="option"]').filter(has_text="不选择合集").first
                if not await option.count():
                    option = page.get_by_text("不选择合集", exact=True).first
            if await option.count() and await option.is_visible():
                await option.click(timeout=5000)
                logger.info(f"[DouyinUpload] 合集已设置「{target or '不选择合集'}」")
            else:
                raise ValueError(f"合集候选不可用：{target}")
        except Exception as exc:
            raise ValueError("抖音专属配置未成功应用，请检查地点、热点或合集候选") from exc

    async def _set_sync_platforms(self, page: Page, platforms: list[str]) -> None:
        unsupported = set(platforms) - {"番茄小说", "红果短剧"}
        if unsupported:
            raise ValueError(f"不支持的同时发布平台：{unsupported}")
        if not await page.get_by_text("同时发布", exact=True).count():
            if platforms:
                raise ValueError("当前账号发布页未提供同时发布功能")
            return
        await set_radio_choice(page, "同时发布", "同时发布到" if platforms else "不同时发布")
        if platforms:
            for name in ("番茄小说", "红果短剧"):
                await set_named_switch(page, name, name in platforms)
            await set_named_switch(page, "记住我的选择", False)

    async def _set_mount_object(self, page: Page, item) -> None:
        name = str(item.get("name") or "").strip()
        kind = item.get("type") or "小程序"
        placeholders = {"小程序": "粘贴抖音小程序链接", "影视演艺": '输入IP名称', "标记万物": "请输入或选择标记的物品"}
        if not name or kind not in placeholders:
            raise ValueError("请填写有效的抖音添加标签类型与名称")
        anchor = page.locator("div.anchor-container-hgj7gj div.semi-select").first
        await anchor.click(timeout=5000)
        option = page.get_by_role("option", name=kind, exact=True)
        await option.click(timeout=5000)
        query = str(item.get("url") or item.get("link") or "") if kind == "小程序" else name
        if not query:
            raise ValueError("小程序标签需要填写抖音小程序链接")
        field = page.get_by_placeholder(re.compile(re.escape(placeholders[kind])))
        await field.fill(query, timeout=5000)
        candidates = page.get_by_role("option").filter(has_text=re.compile(r"^" + re.escape(name) + r"(?:\s|$)"))
        await candidates.first.wait_for(state="visible", timeout=8000)
        if await candidates.count() != 1:
            raise ValueError(f"标签「{name}」存在多个候选，请使用更准确的名称")
        await candidates.click(timeout=5000)
        rejected = page.get_by_text(re.compile(r"不满足.*门槛|无法使用.*标签|无.*权限"))
        if await rejected.count() and await rejected.first.is_visible():
            raise ValueError(await rejected.first.inner_text())
        value = await field.input_value()
        if not value:
            raise ValueError(f"标签「{name}」未成功选择")

    @staticmethod
    def _mount_match_score(query: str, candidate: str) -> float:
        """按字符距离、长度、前缀和 n-gram 混合评分候选。

        抖音候选会随关键词长度变化，因此长度接近和编辑距离优先于热度；
        不依赖外部 embedding 服务，避免发布链路被网络模型调用阻断。
        """
        q = re.sub(r"\s+", "", query).lower()
        c = re.sub(r"\s+", "", candidate).lower()
        if not q or not c:
            return 0.0
        exact = 1.0 if q == c else 0.0
        prefix = 1.0 if c.startswith(q) else 0.0
        seq = SequenceMatcher(None, q, c).ratio()
        length = min(len(q), len(c)) / max(len(q), len(c))
        distance = _levenshtein_distance(q, c)
        edit = 1.0 - distance / max(len(q), len(c))
        qgrams = {q[i:i + 2] for i in range(max(0, len(q) - 1))} or {q}
        cgrams = {c[i:i + 2] for i in range(max(0, len(c) - 1))} or {c}
        ngram = len(qgrams & cgrams) / len(qgrams)
        return 0.40 * exact + 0.15 * prefix + 0.20 * edit + 0.10 * length + 0.10 * seq + 0.05 * ngram


# 全局实例
douyin_upload = DouyinUpload()
