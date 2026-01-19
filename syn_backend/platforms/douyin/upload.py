"""
抖音上传模块 - 提供视频上传和发布功能
"""
import os
import asyncio
import time
import logging
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, Page
from typing import Dict, Any, Optional
# from config.conf import LOCAL_CHROME_PATH
from utils.base_social_media import set_init_script, HEADLESS_FLAG
from myUtils.browser_context import build_context_options, build_browser_args
from myUtils.close_guide import try_close_guide
from utils.video_probe import probe_video_metadata
from ..base import BasePlatform
from ..path_utils import resolve_cookie_file, resolve_video_file

logger = logging.getLogger(__name__)

# Build tag for runtime identification (helps confirm which implementation is used).
DOUYIN_PLATFORM_UPLOAD_BUILD_TAG = "platforms/douyin/upload.py:js-evaluate-cover@2025-12-19"

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
    """关闭抖音引导弹窗（优化版：快速检测，早期退出）"""
    for attempt in range(max_attempts):
        has_popup = False
        # 快速检测：只检查第一个可见的弹窗
        for sel in DOUYIN_TOUR_CONTAINERS:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=500):
                    has_popup = True
                    break
            except:
                continue

        if not has_popup:
            return  # 没有弹窗，立即退出

        # 尝试点击关闭按钮
        clicked = False
        for btn_sel in DOUYIN_TOUR_BTNS:
            try:
                btn = page.locator(btn_sel).first
                if await btn.is_visible(timeout=500):
                    await btn.click(timeout=1000)
                    clicked = True
                    await page.wait_for_timeout(200)  # 减少等待时间
                    break
            except:
                continue

        if not clicked:
            # 如果所有按钮都点不到，说明弹窗可能已经消失或无法关闭，退出
            return


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
                    enable_third_party: bool = True,
                    location: str = '',
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
                cover_aspect_ratio = video_meta.get("cover_aspect_ratio")
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

                browser = await playwright.chromium.launch(**browser_options)
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
                await page.locator("div[class^='container'] input").set_input_files(file_path)

                # 等待进入发布页面
                await self._wait_for_upload_page(page)
                await dismiss_douyin_tour(page, max_attempts=2)

                # 填充标题和标签
                await self._fill_title_and_tags(page, title, tags, enable_third_party=enable_third_party)
                
                # 等待视频上传完成
                await self._wait_for_video_upload(page)
                
                # 设置封面（尽量设置，避免"请设置封面后再发布"）
                await self._set_thumbnail_best_effort(page, thumbnail_path, cover_aspect_ratio=cover_aspect_ratio)

                # 设置地理位置（如果提供）
                if location:
                    await self._set_location(page, location)

                # 设置商品链接（如果提供）
                if product_link and product_title:
                    await self._set_product_link(page, product_link, product_title)
                
                # 设置定时发布（如果提供）
                if publish_dt:
                    await self._set_schedule_time(page, publish_dt)

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
        try:
            loc = self._cover_modal_locator(page).first
            return (await loc.count()) > 0 and await loc.is_visible()
        except Exception:
            return False

    async def _wait_cover_modal_closed(self, page: Page, timeout_ms: int = 20000) -> None:
        """
        Avoid clicking publish while the cover modal is still open (user may be choosing a cover).
        Best-effort: if a visible "完成/确定" button exists and is enabled, click once.
        """
        start = time.monotonic()
        while time.monotonic() - start < timeout_ms / 1000:
            if not await self._is_cover_modal_open(page):
                return

            try:
                for sel in [
                    "div#tooltip-container button:visible:has-text('完成')",
                    "button:visible:has-text('完成')",
                    "button:visible:has-text('确定')",
                    "button:visible:has-text('确认')",
                ]:
                    btn = page.locator(sel).first
                    if await btn.count() and await btn.is_visible() and await btn.is_enabled():
                        await btn.click(timeout=2000)
                        await page.wait_for_timeout(500)
                        break
            except Exception:
                pass

            await asyncio.sleep(0.3)

        raise TimeoutError("封面弹窗长时间未关闭（可能被引导/弹窗遮挡或网络过慢）")

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
    
    async def _fill_title_and_tags(self, page: Page, title: str, tags: list, enable_third_party: bool = True):
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
            await page.locator('div.semi-select span:has-text("输入地理位置")').click()
            await page.keyboard.press("Backspace")
            await page.wait_for_timeout(2000)
            await page.keyboard.type(location)
            await page.wait_for_selector('div[role="listbox"] [role="option"]', timeout=5000)
            await page.locator('div[role="listbox"] [role="option"]').first.click()
            logger.info(f"[DouyinUpload] 成功设置地理位置: {location}")
        except Exception as e:
            logger.warning(f"[DouyinUpload] 设置地理位置失败（忽略继续）: {e}")
    
    async def _set_schedule_time(self, page: Page, publish_date: datetime):
        """设置定时发布"""
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


# 全局实例
douyin_upload = DouyinUpload()
