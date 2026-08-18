# -*- coding: utf-8 -*-
"""
LEGACY IMPLEMENTATION:
该模块为历史 uploader 栈实现；当前业务发布已统一走 `syn_backend/platforms/*/upload.py`。
平台层可能仍会复用本实现，建议不要在业务层直接 import/调用。
"""
from datetime import datetime

from utils.playwright_provider import Playwright, async_playwright, Page
import os
import asyncio
from typing import Optional

from config.conf import LOCAL_CHROME_PATH
from utils.base_social_media import set_init_script, HEADLESS_FLAG
from myUtils.browser_context import build_context_options
from myUtils.close_guide import try_close_guide
from utils.log import douyin_logger
# otp_events and input_queues are imported inside handle_sms_verification to avoid circular import


DOUYIN_TOUR_CONTAINERS = [
    '[role="dialog"]',
    '.semi-modal',
    '.semi-dialog',
    '.guide-modal',
    '.semi-modal-content',
    '.semi-modal-body',
    '.shepherd-element',
    '.shepherd-modal',
    '.shepherd-modal-overlay-container',
    '#guide-cocenter-description',
]

DOUYIN_TOUR_BTNS = [
    'button:has-text("下一步")',
    'button:has-text("知道了")',
    'button:has-text("跳过")',
    'button:has-text("我知道了")',
    'button:has-text("关闭")',
    'button:has-text("我知道了!")',
    '.shepherd-footer button',
    '[aria-label="关闭"]',
    '[aria-label="close"]',
]

# New UI XPaths (as of 2025-12)
DOUYIN_COVER_CLICK_XPATH = "/html/body/div[@id='root']/div[@class='container-box']/div[@class='content-qNoE6N']/div[@class='micro-wrapper-OGvOEm']/div[@id='micro']/div[@id='garfish_app_for_douyin_creator_content_6fue1nrv']/div/div[2]/div[@id='root']/div[@class='card-container-creator-layout micro-LlzqtC new-layout']/div[@id='DCPF']/div[@class='container-pSH0u4']/div[@class='content-left-F3wKrk']/div[@class='form-container-MDtobK new-laytout']/div[@class='container-EMGgQp'][1]/div[2]/div[@class='content-obt4oA new-layout-sLYOT6'][1]/div[@class='content-child-V0CB7w content-limit-width-zybqBW']/div/div[@class='content-upload-new']/div[@class='wrapper-NN3Jh1']/div[@class='coverControl-CjlzqC'][1]/div[@class='cover-Jg3T4p']/div[@class='filter-k_CjvJ']"
DOUYIN_TITLE_INPUT_XPATH = "/html/body/div[@id='root']/div[@class='container-box']/div[@class='content-qNoE6N']/div[@class='micro-wrapper-OGvOEm']/div[@id='micro']/div[@id='garfish_app_for_douyin_creator_content_6fue1nrv']/div/div[2]/div[@id='root']/div[@class='card-container-creator-layout micro-LlzqtC new-layout']/div[@id='DCPF']/div[@class='container-pSH0u4']/div[@class='content-left-F3wKrk']/div[@class='form-container-MDtobK new-laytout']/div[@class='container-EMGgQp'][1]/div[2]/div[@class='publish-mention-wrapper-LWv5ed']/div[@class='content-obt4oA new-layout-sLYOT6']/div[@class='content-child-V0CB7w content-limit-width-zybqBW']/div/div[@class='editor-container-zRPSAi']/div[@class='editor-comp-publish-container-d4oeQI']/div[@class='editor-kit-root-container']/div[1]/div[@class='container-sGoJ9f']/div[@class='semi-input-wrapper semiInput-EyEyPL semi-input-wrapper__with-suffix semi-input-wrapper-default']/input[@class='semi-input semi-input-default']"
DOUYIN_COVER_VERTICAL_STEP_XPATH = "/html/body/div[@class='dy-creator-content-portal']/div[@class='modal-ExKlcK']/div[@class='dy-creator-content-modal-wrap']/div[@id='dialog-1']/div[@class='dy-creator-content-modal-content  undefined dy-creator-content-modal-content-height-set']/div[@id='dy-creator-content-modal-body']/div[@class='container-IaxQlJ']/div[@class='container-dTKE_6']/div[@class='steps-cgzd9T']/div[@class='step-dXVbPX step-active-AWDV7U']"
DOUYIN_COVER_DONE_BTN_XPATH = "/html/body/div[@class='dy-creator-content-portal']/div[@class='modal-ExKlcK']/div[@class='dy-creator-content-modal-wrap']/div[@id='dialog-1']/div[@class='dy-creator-content-modal-content  undefined dy-creator-content-modal-content-height-set']/div[@id='dy-creator-content-modal-body']/div[@class='container-IaxQlJ']/div[@class='wrap-qrLdpF']/div[@class='main-DAkOod']/div[@class='buttons-BoCvr4']/button[@class='semi-button semi-button-primary semi-button-light primary-RstHX_']"

# New cover UI selectors (2025-12): "编辑封面" trigger and different "完成" button classes.
DOUYIN_COVER_EDIT_TITLE_CSS = ".title-wA45Xd:has-text('编辑封面')"
DOUYIN_COVER_DONE_PRIMARY_CSS = "button.semi-button.semi-button-primary.semi-button-light.primary-RstHX_:has-text('完成')"
DOUYIN_COVER_DONE_SECONDARY_CSS = "button.semi-button.semi-button-primary.semi-button-light.secondary-zU1YLr:has-text('完成')"

DOUYIN_TITLE_INPUT_FALLBACK_XPATHS = [
    # Prefer stable structure over dynamic garfish ids
    "//div[contains(@class,'editor-kit-root-container')]//div[contains(@class,'container-sGoJ9f')]//input[contains(@class,'semi-input')]",
    "//div[contains(@class,'editor-kit-root-container')]//input[contains(@class,'semi-input')]",
]

DOUYIN_TITLE_INPUT_FALLBACK_CSS = [
    'input[placeholder*="填写作品标题"]',
    "div.editor-kit-root-container div.container-sGoJ9f input.semi-input",
    "div.editor-kit-root-container input.semi-input",
]

DOUYIN_COVER_REQUIRED_TOAST_TEXT = "请设置封面后再发布"

DOUYIN_UPLOADER_BUILD_TAG = "douyin_uploader/main.py:cover+xpath+autofix@2025-12-16"


async def dismiss_douyin_tour(page, max_attempts: int = 6):
    """尝试点击抖音发布页的新手引导弹窗按钮，若不存在则快速返回。"""
    for _ in range(max_attempts):
        has_popup = False
        for sel in DOUYIN_TOUR_CONTAINERS:
            loc = page.locator(sel)
            if await loc.count() > 0 and await loc.first.is_visible():
                has_popup = True
                break
        if not has_popup:
            return

        clicked = False
        for btn_sel in DOUYIN_TOUR_BTNS:
            btn = page.locator(btn_sel)
            if await btn.count() > 0 and await btn.first.is_visible():
                try:
                    await btn.first.click()
                    clicked = True
                    await page.wait_for_timeout(300)
                    break
                except Exception:
                    continue
        if not clicked:
            break


async def _best_effort_close_overlays(page: Page):
    try:
        await try_close_guide(page, "douyin")
    except Exception:
        pass
    try:
        await dismiss_douyin_tour(page, max_attempts=10)
    except Exception:
        pass


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=HEADLESS_FLAG)
        context = await browser.new_context(**build_context_options(storage_state=account_file))
        context = await set_init_script(context)
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        try:
            await page.goto("https://creator.douyin.com/creator-micro/content/upload", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as e:
            douyin_logger.error(f"[+] 访问页面失败: {e}")
            await context.close()
            await browser.close()
            return False

        # 2024.06.17 抖音创作者中心改版
        # 检查是否有登录相关的元素
        login_indicators = [
            page.get_by_text('手机号登录'),
            page.get_by_text('扫码登录'),
            page.locator('text=请登录'),
        ]

        for indicator in login_indicators:
            if await indicator.count() > 0:
                douyin_logger.error("[+] 检测到登录页面，cookie已失效")
                await context.close()
                await browser.close()
                return False

        # 检查是否有上传页面的关键元素
        try:
            upload_input = page.locator('input[type="file"]').first
            if await upload_input.count() > 0:
                douyin_logger.success("[+] cookie 有效")
                await context.close()
                await browser.close()
                return True
        except Exception:
            pass

        douyin_logger.warning("[+] 未找到上传元素，可能cookie已失效")
        await context.close()
        await browser.close()
        return False


async def douyin_setup(account_file, handle=False):
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            # Todo alert message
            return False
        douyin_logger.info('[+] cookie文件不存在或已失效，即将自动打开浏览器，请扫码登录，登陆后会自动生成cookie文件')
        await douyin_cookie_gen(account_file)
    return True


async def douyin_cookie_gen(account_file):
    async with async_playwright() as playwright:
        options = {
            'headless': HEADLESS_FLAG
        }
        # Make sure to run headed.
        browser = await playwright.chromium.launch(**options)
        # Setup context however you like.
        context = await browser.new_context(**build_context_options())
        context = await set_init_script(context)
        # Pause the page, and start recording manually.
        page = await context.new_page()
        await page.goto("https://creator.douyin.com/")
        await page.pause()
        # 点击调试器的继续，保存cookie
        await context.storage_state(path=account_file)


class DouYinVideo(object):
    def __init__(self, title, file_path, tags, publish_date: datetime, account_file, thumbnail_path=None, productLink='', productTitle='', proxy=None):
        # Defensive: upstream may mistakenly concatenate hashtags/description into title.
        clean_title = str(title).splitlines()[0].strip()
        if "#" in clean_title:
            clean_title = clean_title.split("#", 1)[0].strip()
        self.title = clean_title  # 视频标题
        self.file_path = file_path
        self.tags = tags
        self.publish_date = publish_date
        self.account_file = account_file
        self.date_format = '%Y年%m月%d日 %H:%M'
        self.local_executable_path = LOCAL_CHROME_PATH
        self.thumbnail_path = thumbnail_path
        self.productLink = productLink
        self.productTitle = productTitle
        self.proxy = proxy

    async def set_schedule_time_douyin(self, page, publish_date):
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")

        # Step 1: enable scheduled publish
        schedule_selectors = [
            "[class^='radio']:has-text('定时发布')",
            "label:has-text('定时发布')",
            "text=定时发布",
            "text=定时",
        ]
        scheduled_enabled = False
        for sel in schedule_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() and await loc.first.is_visible():
                    await loc.first.click()
                    scheduled_enabled = True
                    break
            except Exception:
                continue

        if not scheduled_enabled:
            douyin_logger.warning("  [!] 未找到“定时发布”入口，跳过定时设置")
            return

        await page.wait_for_timeout(500)

        # Step 2: fill datetime
        datetime_inputs = [
            '.semi-input[placeholder="日期和时间"]',
            'input[placeholder*="日期"]',
            'input[placeholder*="时间"]',
        ]
        filled = False
        for sel in datetime_inputs:
            try:
                inp = page.locator(sel)
                if await inp.count() and await inp.first.is_visible():
                    await inp.first.click()
                    await page.keyboard.press("Control+KeyA")
                    await page.keyboard.type(str(publish_date_hour))
                    await page.keyboard.press("Enter")
                    filled = True
                    break
            except Exception:
                continue

        if not filled:
            douyin_logger.warning("  [!] 未找到定时输入框，跳过定时设置")
            return

        await page.wait_for_timeout(800)

    async def handle_upload_error(self, page):
        douyin_logger.info('视频出错了，重新上传中')
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    async def handle_sms_verification(self, page: Page):
        """检测短信验证码弹窗，如果存在则请求用户输入验证码"""
        try:
            # 检测是否存在短信验证码弹窗
            modal = page.locator("text=接收短信验证码").first
            if await modal.count() == 0:
                return

            douyin_logger.warning("⚠️ 检测到短信验证码弹窗，等待用户输入...")

            # 导入验证码管理器
            from platforms.verification import verification_manager

            # 发起验证码请求（通知前端）
            verification_manager.request_verification(
                account_id=self.account_file,  # 使用cookie文件名作为标识
                platform=3,  # 抖音
                message="抖音发布需要短信验证码",
                code_length=6
            )

            # 等待用户输入验证码（最多2分钟）
            code = await verification_manager.wait_for_code(
                account_id=self.account_file,
                timeout=120
            )

            if not code:
                douyin_logger.error("❌ 验证码输入超时")
                raise Exception("SMS_VERIFICATION_TIMEOUT")

            # 填入验证码
            douyin_logger.info(f"✅ 收到验证码: {code}")

            # 查找验证码输入框并填入
            input_selector = 'input[placeholder*="验证码"]'
            await page.locator(input_selector).fill(code)
            await page.wait_for_timeout(500)

            # 点击确认按钮
            confirm_btn = page.locator('button:has-text("确定"), button:has-text("确认"), button:has-text("提交")')
            if await confirm_btn.count() > 0:
                await confirm_btn.first.click()
                await page.wait_for_timeout(2000)

            douyin_logger.info("✅ 验证码已提交")

            # 清理队列
            verification_manager.cleanup_queue(self.account_file)

        except Exception as e:
            if "SMS_VERIFICATION" in str(e):
                raise  # 重新抛出验证码相关异常
            douyin_logger.error(f"处理短信验证码时出错: {e}")

    async def upload(self, playwright: Playwright) -> None:
        try:
            douyin_logger.info(
                f"[抖音] Uploader实现: {DOUYIN_UPLOADER_BUILD_TAG} (file={__file__})"
            )
        except Exception:
            pass
        # 使用 Chromium 浏览器启动一个浏览器实例
        launch_kwargs = {"headless": HEADLESS_FLAG}
        # 🔧 不再使用 LOCAL_CHROME_PATH，让 Playwright 自动使用内置 Chromium
        # if self.local_executable_path:
        #     launch_kwargs["executable_path"] = self.local_executable_path

        if self.proxy:
            launch_kwargs["proxy"] = self.proxy
            douyin_logger.info(f"Using Proxy: {self.proxy.get('server')}")

        browser = await playwright.chromium.launch(**launch_kwargs)
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(**build_context_options(storage_state=f"{self.account_file}"))
        context = await set_init_script(context)

        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://creator.douyin.com/creator-micro/content/upload")
        await self.handle_sms_verification(page)
        await _best_effort_close_overlays(page)
        douyin_logger.info(f'[+]正在上传-------{self.title}.mp4')
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        douyin_logger.info(f'[-] 正在打开主页...')
        await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload")
        await _best_effort_close_overlays(page)
        # 点击 "上传视频" 按钮
        await page.locator("div[class^='container'] input").set_input_files(self.file_path)

        # 等待页面跳转到指定的 URL 2025.01.08修改在原有基础上兼容两种页面
        while True:
            try:
                # 尝试等待第一个 URL
                await page.wait_for_url(
                    "https://creator.douyin.com/creator-micro/content/publish?enter_from=publish_page", timeout=2000)
                douyin_logger.info("[+] 成功进入version_1发布页面!")
                break  # 成功进入页面后跳出循环
            except Exception:
                try:
                    # 如果第一个 URL 超时，再尝试等待第二个 URL
                    await page.wait_for_url(
                        "https://creator.douyin.com/creator-micro/content/post/video?enter_from=publish_page",
                        timeout=3000)
                    douyin_logger.info("[+] 成功进入version_2发布页面!")

                    break  # 成功进入页面后跳出循环
                except:
                    print("  [-] 超时未进入视频发布页面，重新尝试...")
                    await asyncio.sleep(0.5)  # 等待 0.5 秒后重新尝试
        # 进入发布页后再尝试关闭新版“共创”类引导
        await _best_effort_close_overlays(page)
        # 填充标题和话题
        # 检查是否存在包含输入框的元素
        # 这里为了避免页面变化，故使用相对位置定位：作品标题父级右侧第一个元素的input子元素
        await asyncio.sleep(1)
        douyin_logger.info(f'  [-] 正在填充标题和话题...')
        await self._fill_title_best_effort(page, self.title)
        css_selector = ".zone-container"
        # Douyin tags: cap to 3 to reduce duplication risk
        seen = set()
        normalized_tags = []
        for t in self.tags or []:
            t = str(t).strip().lstrip("#")
            if not t or t in seen:
                continue
            seen.add(t)
            normalized_tags.append(t)
            if len(normalized_tags) >= 3:
                break

        # Clear existing hashtags/text in the topic container to avoid duplicates on retry
        try:
            zone = page.locator(css_selector).first
            if await zone.count() > 0 and await zone.is_visible():
                await zone.click()
                await page.keyboard.press("Control+KeyA")
                await page.keyboard.press("Delete")
                await page.wait_for_timeout(200)
        except Exception:
            pass

        for index, tag in enumerate(normalized_tags, start=1):
            await page.type(css_selector, "#" + tag)
            await page.press(css_selector, "Space")
        douyin_logger.info(f'总共添加{len(normalized_tags)}个话题')
        while True:
            # 判断重新上传按钮是否存在，如果不存在，代表视频正在上传，则等待
            try:
                #  新版：定位重新上传
                number = await page.locator('[class^="long-card"] div:has-text("重新上传")').count()
                if number > 0:
                    douyin_logger.success("  [-]视频上传完毕")
                    break
                else:
                    douyin_logger.info("  [-] 正在上传视频中...")
                    await asyncio.sleep(2)

                    if await page.locator('div.progress-div > div:has-text("上传失败")').count():
                        douyin_logger.error("  [-] 发现上传出错了... 准备重试")
                        await self.handle_upload_error(page)
            except:
                douyin_logger.info("  [-] 正在上传视频中...")
                await asyncio.sleep(2)

        if self.productLink and self.productTitle:
            douyin_logger.info(f'  [-] 正在设置商品链接...')
            await self.set_product_link(page, self.productLink, self.productTitle)
            douyin_logger.info(f'  [+] 完成设置商品链接...')
        
        #上传视频封面
        await self.set_thumbnail(page, self.thumbnail_path)

        # 更换可见元素
        await self.set_location(page, "")


        # 頭條/西瓜
        third_part_element = '[class^="info"] > [class^="first-part"] div div.semi-switch'
        # 定位是否有第三方平台
        if await page.locator(third_part_element).count():
            # 检测是否是已选中状态
            if 'semi-switch-checked' not in await page.eval_on_selector(third_part_element, 'div => div.className'):
                await page.locator(third_part_element).locator('input.semi-switch-native-control').click()

        if self.publish_date != 0:
            await self.set_schedule_time_douyin(page, self.publish_date)

        # 判断视频是否发布成功
        while True:
            # 判断视频是否发布成功
            try:
                await _best_effort_close_overlays(page)
                # If cover is required, attempt to set it and retry publish.
                if await page.get_by_text(DOUYIN_COVER_REQUIRED_TOAST_TEXT).count():
                    douyin_logger.warning(f"  [!] 检测到提示“{DOUYIN_COVER_REQUIRED_TOAST_TEXT}”，尝试自动设置封面后重试发布")
                    await self.set_thumbnail(page, self.thumbnail_path)
                    await asyncio.sleep(0.8)
                publish_button = page.get_by_role('button', name="发布", exact=True)
                if await publish_button.count():
                    await publish_button.click()
                await page.wait_for_url("https://creator.douyin.com/creator-micro/content/manage**",
                                        timeout=3000)  # 如果自动跳转到作品页面，则代表发布成功
                douyin_logger.success("  [-]视频发布成功")
                break
            except:
                douyin_logger.info("  [-] 视频正在发布中...")
                await page.screenshot(full_page=True)
                await asyncio.sleep(0.5)

        await context.storage_state(path=self.account_file)  # 保存cookie
        douyin_logger.success('  [-]cookie更新完毕！')
        await asyncio.sleep(2)  # 这里延迟是为了方便眼睛直观的观看
        # 关闭浏览器上下文和浏览器实例
        await context.close()
        await browser.close()
    
    async def _fill_title_best_effort(self, page: Page, title: str) -> bool:
        """优先按 XPath 定位标题输入框，避免页面结构变化导致填充失败。"""
        desired = (title or "").strip()[:30]
        if not desired:
            return False

        candidates = [
            f"xpath={DOUYIN_TITLE_INPUT_XPATH}",
            *[f"xpath={xp}" for xp in DOUYIN_TITLE_INPUT_FALLBACK_XPATHS],
            *DOUYIN_TITLE_INPUT_FALLBACK_CSS,
            # Old relative locator as last resort
            "text=作品标题 >> xpath=../following-sibling::div[1]//input",
        ]

        for selector in candidates:
            try:
                loc = page.locator(selector).first
                if await loc.count() == 0:
                    continue
                if not await loc.is_visible():
                    continue
                await loc.click()
                await loc.fill(desired)
                await page.wait_for_timeout(100)

                # Validate for input-like elements.
                try:
                    val = await loc.input_value()
                    if desired in (val or "") or (val or "") == desired:
                        return True
                except Exception:
                    return True
            except Exception:
                continue

        # Final fallback: contenteditable container
        try:
            titlecontainer = page.locator(".notranslate").first
            if await titlecontainer.count() and await titlecontainer.is_visible():
                await titlecontainer.click()
                await page.keyboard.press("Control+KeyA")
                await page.keyboard.press("Delete")
                await page.keyboard.type(desired)
                await page.keyboard.press("Enter")
                return True
        except Exception:
            pass
        return False

    async def _pick_any_cover_in_modal(self, page: Page) -> bool:
        """在封面选择弹窗中，尽量点击一个可用的封面帧/推荐封面。"""
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

    async def set_thumbnail(self, page: Page, thumbnail_path: Optional[str]):
        """
        设置视频封面。
        - 如果提供 thumbnail_path：上传自定义封面。
        - 如果未提供：仍会尝试打开封面弹窗并选择任意一张封面，避免“请设置封面后再发布”。
        """
        douyin_logger.info('  [-] 正在设置视频封面...')

        # Prefer old flow, fallback to new layout click area (XPath)
        try:
            clicked = False
            for sel in [
                DOUYIN_COVER_EDIT_TITLE_CSS,
                'text="编辑封面"',
                'text="选择封面"',
                'text="设置封面"',
                'text=/选择封面|设置封面/',
            ]:
                try:
                    await page.click(sel, timeout=2000)
                    clicked = True
                    break
                except Exception:
                    continue
            if not clicked:
                raise RuntimeError("未找到封面入口按钮")
            await page.wait_for_selector("div.dy-creator-content-modal, div.dy-creator-content-portal, [role='dialog']", timeout=8000)

            # Prefer vertical cover if available
            try:
                await page.click('text="设置竖封面"', timeout=3000)
            except Exception:
                pass

            if thumbnail_path:
                await page.wait_for_timeout(500)
                await page.locator("div[class^='semi-upload upload'] >> input.semi-upload-hidden-input").set_input_files(thumbnail_path)
                await page.wait_for_timeout(800)
            # No custom thumbnail: prefer "直接完成" so Douyin uses the first frame as cover.

            # Click confirm
            root = page.locator("div.dy-creator-content-modal, div.dy-creator-content-portal, [role='dialog']")
            clicked_done = False
            for sel in [DOUYIN_COVER_DONE_PRIMARY_CSS, DOUYIN_COVER_DONE_SECONDARY_CSS]:
                btn = root.locator(sel).first
                if await btn.count() and await btn.is_visible():
                    await btn.click(timeout=5000)
                    clicked_done = True
                    break

            if not clicked_done:
                for sel in [
                    "div#tooltip-container button:visible:has-text('完成')",
                    "button:visible:has-text('完成')",
                    "button:visible:has-text('确定')",
                    "button:visible:has-text('确认')",
                ]:
                    btn = root.locator(sel).first
                    if await btn.count() and await btn.is_visible():
                        await btn.click(timeout=5000)
                        clicked_done = True
                        break

            if not clicked_done and not thumbnail_path:
                # Last resort: select any frame then click "完成" (avoid publish being blocked).
                await self._pick_any_cover_in_modal(page)
                for sel in ["button:visible:has-text('完成')", "button:visible:has-text('确定')", "button:visible:has-text('确认')"]:
                    btn = root.locator(sel).first
                    if await btn.count() and await btn.is_visible():
                        await btn.click(timeout=5000)
                        break

            # Wait modal disappears best-effort
            try:
                await page.wait_for_selector("div.extractFooter, div.dy-creator-content-modal, div.dy-creator-content-portal", state="detached", timeout=8000)
            except Exception:
                pass
            douyin_logger.info('  [+] 视频封面设置完成！')
            return
        except Exception as e:
            douyin_logger.warning(f'  [!] 封面按钮流程失败，尝试点击封面区域: {e}')

        try:
            cover_click = page.locator(f"xpath={DOUYIN_COVER_CLICK_XPATH}")
            if await cover_click.count():
                await cover_click.first.click()
                await page.wait_for_timeout(500)

            await page.wait_for_selector("div.dy-creator-content-portal, div.dy-creator-content-modal, [role='dialog']", timeout=8000)

            step = page.locator(f"xpath={DOUYIN_COVER_VERTICAL_STEP_XPATH}")
            if await step.count():
                await step.first.click()
                await page.wait_for_timeout(500)

            if thumbnail_path:
                cover_inputs = [
                    'input[type="file"][accept*="image"]',
                    'input[type="file"][accept*=".png"]',
                    'input[type="file"][accept*=".jpg"]',
                    'input[type="file"]',
                ]
                for sel in cover_inputs:
                    loc = page.locator(sel).first
                    if await loc.count():
                        try:
                            await loc.set_input_files(thumbnail_path)
                            await page.wait_for_timeout(800)
                            break
                        except Exception:
                            continue
            else:
                # No custom thumbnail: prefer "直接完成" so Douyin uses the first frame as cover.
                pass

            root = page.locator("div.dy-creator-content-modal, div.dy-creator-content-portal, [role='dialog']")
            clicked_done = False
            for sel in [DOUYIN_COVER_DONE_PRIMARY_CSS, DOUYIN_COVER_DONE_SECONDARY_CSS]:
                btn = root.locator(sel).first
                if await btn.count() and await btn.is_visible():
                    await btn.click(timeout=5000)
                    clicked_done = True
                    break

            if not clicked_done:
                done_btn = page.locator(f"xpath={DOUYIN_COVER_DONE_BTN_XPATH}")
                if await done_btn.count() and await done_btn.first.is_visible():
                    await done_btn.first.click()
                    clicked_done = True

            if not clicked_done and not thumbnail_path:
                await self._pick_any_cover_in_modal(page)
                for sel in ["button:visible:has-text('完成')", "button:visible:has-text('确定')", "button:visible:has-text('确认')"]:
                    btn = root.locator(sel).first
                    if await btn.count() and await btn.is_visible():
                        await btn.click(timeout=5000)
                        break

            await page.wait_for_timeout(1200)
            douyin_logger.info('  [+] 视频封面设置完成（点击封面区域流程）！')
        except Exception as e:
            douyin_logger.error(f'  [-] 视频封面设置失败: {e}')
            

    async def set_location(self, page: Page, location: str = ""):
        if not location:
            return
        # todo supoort location later
        # await page.get_by_text('添加标签').locator("..").locator("..").locator("xpath=following-sibling::div").locator(
        #     "div.semi-select-single").nth(0).click()
        await page.locator('div.semi-select span:has-text("输入地理位置")').click()
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(2000)
        await page.keyboard.type(location)
        await page.wait_for_selector('div[role="listbox"] [role="option"]', timeout=5000)
        await page.locator('div[role="listbox"] [role="option"]').first.click()

    async def handle_product_dialog(self, page: Page, product_title: str):
        """处理商品编辑弹窗"""

        await page.wait_for_timeout(2000)
        await page.wait_for_selector('input[placeholder="请输入商品短标题"]', timeout=10000)
        short_title_input = page.locator('input[placeholder="请输入商品短标题"]')
        if not await short_title_input.count():
            douyin_logger.error("[-] 未找到商品短标题输入框")
            return False
        product_title = product_title[:10]
        await short_title_input.fill(product_title)
        # 等待一下让界面响应
        await page.wait_for_timeout(1000)

        finish_button = page.locator('button:has-text("完成编辑")')
        if 'disabled' not in await finish_button.get_attribute('class'):
            await finish_button.click()
            douyin_logger.debug("[+] 成功点击'完成编辑'按钮")
            
            # 等待对话框关闭
            await page.wait_for_selector('.semi-modal-content', state='hidden', timeout=5000)
            return True
        else:
            douyin_logger.error("[-] '完成编辑'按钮处于禁用状态，尝试直接关闭对话框")
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
        
    async def set_product_link(self, page: Page, product_link: str, product_title: str):
        """设置商品链接功能"""
        await page.wait_for_timeout(2000)  # 等待2秒
        try:
            # 定位"添加标签"文本，然后向上导航到容器，再找到下拉框
            await page.wait_for_selector('text=添加标签', timeout=10000)
            dropdown = page.get_by_text('添加标签').locator("..").locator("..").locator("..").locator(".semi-select").first
            if not await dropdown.count():
                douyin_logger.error("[-] 未找到标签下拉框")
                return False
            douyin_logger.debug("[-] 找到标签下拉框，准备选择'购物车'")
            await dropdown.click()
            ## 等待下拉选项出现
            await page.wait_for_selector('[role="listbox"]', timeout=5000)
            ## 选择"购物车"选项
            await page.locator('[role="option"]:has-text("购物车")').click()
            douyin_logger.debug("[+] 成功选择'购物车'")
            
            # 输入商品链接
            ## 等待商品链接输入框出现
            await page.wait_for_selector('input[placeholder="粘贴商品链接"]', timeout=5000)
            # 输入
            input_field = page.locator('input[placeholder="粘贴商品链接"]')
            await input_field.fill(product_link)
            douyin_logger.debug(f"[+] 已输入商品链接: {product_link}")
            
            # 点击"添加链接"按钮
            add_button = page.locator('span:has-text("添加链接")')
            ## 检查按钮是否可用（没有disable类）
            button_class = await add_button.get_attribute('class')
            if 'disable' in button_class:
                douyin_logger.error("[-] '添加链接'按钮不可用")
                return False
            await add_button.click()
            douyin_logger.debug("[+] 成功点击'添加链接'按钮")
            ## 如果链接不可用
            await page.wait_for_timeout(2000)
            error_modal = page.locator('text=未搜索到对应商品')
            if await error_modal.count():
                confirm_button = page.locator('button:has-text("确定")')
                await confirm_button.click()
                # await page.wait_for_selector('.semi-modal-content', state='hidden', timeout=5000)
                douyin_logger.error("[-] 商品链接无效")
                return False

            # 填写商品短标题
            if not await self.handle_product_dialog(page, product_title):
                return False
            
            # 等待链接添加完成
            douyin_logger.debug("[+] 成功设置商品链接")
            return True
        except Exception as e:
            douyin_logger.error(f"[-] 设置商品链接时出错: {str(e)}")
            return False

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
