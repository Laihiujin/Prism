# -*- coding: utf-8 -*-
from datetime import datetime

from playwright.async_api import Playwright, async_playwright
import os
import asyncio

from config.conf import LOCAL_CHROME_PATH
from utils.base_social_media import set_init_script, HEADLESS_FLAG
from myUtils.browser_context import build_context_options
from myUtils.close_guide import try_close_guide
from utils.files_times import get_absolute_path
from utils.log import kuaishou_logger

TOUR_CONTAINER_SELECTORS = [
    "div[class*='_tooltip']",
    "div[class*='tour']",
    "div[class*='guide']",
    "[role='dialog']",
]

NEXT_BUTTON_SELECTORS = [
    "text=下一步",
    "text=下一步 >",
    "text=下一步 >>",
    "button:has-text('下一步')",
]

CLOSE_BUTTON_SELECTORS = [
    "text=知道了",
    "text=跳过",
    "[aria-label='关闭']",
    "[aria-label='Skip']",
    "._close_d7f44_29[aria-label='Skip']",  # 新版快手引导层关闭按钮
    "button:has-text('关闭')",
    "[title='关闭']",
]


async def _close_joyride_guide(page):
    """关闭快手的 react-joyride 新手引导遮罩"""
    try:
        # 检查 page 是否已关闭
        if page.is_closed():
            kuaishou_logger.warning("Page已关闭，跳过Joyride引导关闭")
            return False

        kuaishou_logger.info("尝试关闭 Joyride 引导...")

        # 等待一下看是否有引导出现
        await asyncio.sleep(1.5)

        # 持续点击"下一步"按钮，直到找不到为止
        step_count = 0
        max_steps = 3  # ⚠️ 减少到3步，避免无限循环

        while step_count < max_steps:
            # 每次循环检查 page 是否仍然有效
            if page.is_closed():
                kuaishou_logger.warning("Page在Joyride引导关闭过程中被关闭")
                return False

            step_count += 1
            next_button_found = False

            # 快手特定的动态类名选择器（红色按钮 #fe3666）
            next_button_selectors = [
                # 最精确：快手的红色primary按钮（动态类名）
                'button[class*="_button_"][class*="_button-primary_"]',
                'button[class*="_button-primary_"]',
                'button[class*="button-primary"]',
                # 通过文本匹配红色按钮（包含新的"立刻体验"按钮）
                'button[class*="_button_"]:has-text("立刻体验")',
                'button[class*="_button_"]:has-text("下一步")',
                'button[class*="primary"]:has-text("立刻体验")',
                'button[class*="primary"]:has-text("下一步")',
                # tooltip 容器内的按钮
                'div[class*="_tooltip-btns"] button[class*="primary"]',
                'div[class*="tooltip-btns"] button',
                '[class*="_tooltip"] button[class*="_button"]',
                # 通用选择器（优先匹配"立刻体验"）
                'button:has-text("立刻体验")',
                'button:has-text("下一步")',
                'button:has-text("继续")',
            ]

            for selector in next_button_selectors:
                try:
                    locator = page.locator(selector)
                    count = await locator.count()

                    if count > 0:
                        button = locator.first
                        if await button.is_visible():
                            # 尝试获取引导内容
                            try:
                                tooltip = page.locator('.react-joyride__tooltip')
                                if await tooltip.count() > 0:
                                    tooltip_text = await tooltip.inner_text()
                                    kuaishou_logger.info(f"步骤 {step_count}: {tooltip_text[:100]}")
                            except:
                                pass

                            kuaishou_logger.info(f"点击'下一步' (步骤{step_count}): {selector}")
                            await button.click(timeout=5000)
                            await asyncio.sleep(1.0)  # 等待下一步加载
                            next_button_found = True
                            break
                except Exception as e:
                    kuaishou_logger.debug(f"选择器 {selector} 失败: {e}")
                    continue

            # 如果没找到"下一步"，引导结束
            if not next_button_found:
                kuaishou_logger.info(f"引导完成，共{step_count-1}步")
                break

        # 检查 page 是否仍然有效
        if page.is_closed():
            kuaishou_logger.warning("Page在Joyride引导完成后被关闭")
            return False

        # 兜底：有些版本"下一步"不会自动消失，直接最多点 4 次
        if await page.locator('.react-joyride__spotlight').count() > 0:
            for _ in range(4):
                try:
                    if page.is_closed():
                        kuaishou_logger.warning("Page在兜底处理中被关闭")
                        return False
                    if not await _click_first_visible(page, NEXT_BUTTON_SELECTORS):
                        break
                    await asyncio.sleep(0.8)
                except Exception:
                    break

        # 检查是否还有引导遮罩
        if await page.locator('.react-joyride__spotlight').count() == 0:
            kuaishou_logger.success("Joyride 引导已成功完成")
            return True

        # 如果还有引导，尝试跳过/关闭按钮
        close_methods = [
            ('button:has-text("跳过")', 'click'),
            ('button:has-text("知道了")', 'click'),
            ('button:has-text("我知道了")', 'click'),
            ('button:has-text("完成")', 'click'),
            ('button[aria-label="Skip"]', 'click'),
            ('button[aria-label="Close"]', 'click'),
            ('.react-joyride__close', 'click'),
            ('button.react-joyride__close', 'click'),
            # 按 ESC 键
            (None, 'escape'),
        ]

        for selector, action in close_methods:
            try:
                if page.is_closed():
                    kuaishou_logger.warning("Page在关闭方法尝试中被关闭")
                    return False

                if action == 'escape':
                    kuaishou_logger.debug("尝试按 ESC 键关闭引导")
                    await page.keyboard.press('Escape')
                    await asyncio.sleep(0.5)
                elif action == 'click' and selector:
                    if await page.locator(selector).count() > 0:
                        kuaishou_logger.debug(f"找到关闭按钮: {selector}")
                        await page.locator(selector).first.click()
                        await asyncio.sleep(0.5)

                # 检查引导是否已关闭
                if await page.locator('.react-joyride__spotlight').count() == 0:
                    kuaishou_logger.success("Joyride 引导已成功关闭")
                    return True
            except Exception as e:
                kuaishou_logger.debug(f"关闭方法失败 ({selector}/{action}): {e}")
                continue

        # 如果还有引导，尝试强制关闭
        if not page.is_closed() and await page.locator('.react-joyride__spotlight').count() > 0:
            kuaishou_logger.warning("引导仍然存在，尝试强制移除")
            # 通过 JavaScript 强制移除
            await page.evaluate("""
                () => {
                    const joyride = document.querySelector('#react-joyride-portal');
                    if (joyride) {
                        joyride.remove();
                    }
                }
            """)
            await asyncio.sleep(0.5)
            if await page.locator('.react-joyride__spotlight').count() == 0:
                kuaishou_logger.success("强制移除 Joyride 成功")
                return True

        kuaishou_logger.warning("未检测到 Joyride 引导或已关闭")
        return True
    except Exception as e:
        kuaishou_logger.error(f"关闭 Joyride 引导异常: {e}")
        return False


async def _click_first_visible(page, selectors):
    for sel in selectors:
        # 跳过空选择器
        if not sel or not sel.strip():
            continue

        try:
            # 检查 page 是否已关闭
            if page.is_closed():
                kuaishou_logger.debug(f"Page已关闭，跳过选择器: {sel}")
                return False

            locator = page.locator(sel)
            if await locator.count() > 0 and await locator.first.is_visible():
                await locator.first.click()
                return True
        except Exception as e:
            # 如果选择器无效，继续尝试下一个
            kuaishou_logger.debug(f"选择器 {sel} 失败: {e}")
            continue
    return False


async def dismiss_kuaishou_tour(page, max_attempts=6):
    """
    快手发布页常有引导弹窗，尝试点击"下一步/跳过/知道了"来关闭。
    """
    try:
        # 检查 page 是否已关闭
        if page.is_closed():
            kuaishou_logger.warning("Page已关闭，跳过引导关闭")
            return

        for _ in range(max_attempts):
            guide_found = False
            for sel in TOUR_CONTAINER_SELECTORS:
                # 每次循环都检查 page 是否仍然有效
                if page.is_closed():
                    kuaishou_logger.warning("Page在引导关闭过程中被关闭")
                    return

                if await page.locator(sel).count() > 0:
                    guide_found = True
                    break
            if not guide_found:
                return

            clicked = await _click_first_visible(page, NEXT_BUTTON_SELECTORS)
            if not clicked:
                clicked = await _click_first_visible(page, CLOSE_BUTTON_SELECTORS)
            if not clicked:
                break

            await page.wait_for_timeout(400)

        kuaishou_logger.info(f"引导完成")
    except Exception as e:
        kuaishou_logger.error(f"关闭引导异常: {e}")
        # 不抛出异常，允许继续执行


async def _debug_dump(page, prefix: str) -> None:
    """保存截图/HTML/OCR，便于排查页面改版导致的定位失败。"""
    try:
        from pathlib import Path
        from datetime import datetime
        import os

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

        try:
            from automation.ocr_client import ocr_image_bytes

            if os.getenv("SILICONFLOW_API_KEY") and png.exists():
                text = ocr_image_bytes(
                    png.read_bytes(),
                    prompt="识别图中与快手发布/引导弹窗/下一步/跳过/关闭相关的关键文字，按行输出。",
                )
                if text:
                    ocr_path.write_text(text, encoding="utf-8")
        except Exception:
            pass
    except Exception:
        pass


async def _fill_title_and_topics(page, title: str, topics: list) -> bool:
    """
    快手填充逻辑：只有一个描述输入框
    - 第一行：标题
    - 换行后：#标签1 #标签2 #标签3

    Returns:
        bool: True 表示填充成功，False 表示失败
    """
    title_value = (title or "").strip()
    if not title_value:
        kuaishou_logger.warning("标题为空，跳过填充")
        return False

    # 清理标签（去重、去#、限制3个）
    cleaned_topics = [str(t).strip().lstrip("#") for t in (topics or []) if str(t).strip()]
    cleaned_topics = list(dict.fromkeys(cleaned_topics))[:3]  # 去重 + 限制3个

    # 组合内容：标题 + 换行 + 标签
    combined_content = title_value
    if cleaned_topics:
        tags_line = " ".join([f"#{tag}" for tag in cleaned_topics])
        combined_content = f"{title_value}\n{tags_line}"

    kuaishou_logger.info(f"[快手] 准备填充内容:\n{combined_content}")

    # 快手描述框选择器（优先级从高到低）
    candidates = [
        page.locator("textarea[placeholder*='作品']"),
        page.locator("textarea[placeholder*='描述']"),
        page.locator("textarea[placeholder*='内容']"),
        page.locator("textarea[placeholder*='标题']"),
        page.locator("textarea[class*='_textarea']"),
        page.locator("textarea[class*='TextArea']"),
        page.locator("div[contenteditable='true']").first,
        page.locator("textarea:visible").first,
    ]

    for idx, loc in enumerate(candidates):
        try:
            if await loc.count() == 0:
                continue
            el = loc.first
            if not await el.is_visible():
                continue

            kuaishou_logger.debug(f"[快手] 尝试候选项 {idx+1}/{len(candidates)}")
            await el.click(timeout=3000)

            # 方法1: 使用 JavaScript 直接设置（快速）
            try:
                # 转义单引号
                safe_content = combined_content.replace("'", "\\'").replace("\n", "\\n")
                await el.evaluate(f"""
                    el => {{
                        el.value = '{safe_content}';
                        el.textContent = '{safe_content}';
                        el.innerText = '{safe_content}';
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                """)
                kuaishou_logger.success(f"✅ [快手] 内容填充成功（JavaScript 方式）")
                await asyncio.sleep(0.5)
                return True
            except Exception as e:
                kuaishou_logger.debug(f"[快手] JavaScript 填充失败: {e}")

            # 方法2: fill() 方法
            try:
                await el.fill(combined_content)
                kuaishou_logger.success(f"✅ [快手] 内容填充成功（fill 方式）")
                await asyncio.sleep(0.5)
                return True
            except Exception as e:
                kuaishou_logger.debug(f"[快手] fill() 失败: {e}")

            # 方法3: keyboard.type（慢但可靠）
            try:
                await page.keyboard.press("Control+KeyA")
                await page.keyboard.press("Delete")
                await page.keyboard.type(combined_content)
                kuaishou_logger.success(f"✅ [快手] 内容填充成功（keyboard 方式）")
                await asyncio.sleep(0.5)
                return True
            except Exception as e:
                kuaishou_logger.debug(f"[快手] keyboard.type() 失败: {e}")

        except Exception as e:
            kuaishou_logger.debug(f"[快手] 候选项 {idx+1} 失败: {e}")
            continue

    kuaishou_logger.error("❌ [快手] 所有输入方式均失败")
    return False


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=HEADLESS_FLAG)
        context = await browser.new_context(**build_context_options(storage_state=account_file))
        context = await set_init_script(context)
        page = await context.new_page()

        try:
            await page.goto("https://cp.kuaishou.com/article/publish/video", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)

            # 检查是否有登录指示器（有则说明cookie失效）
            login_indicators = [
                "text=扫码登录",
                "text=手机号登录",
                "text=密码登录",
                "[class*='qrcode']",
                "canvas"  # 二维码
            ]

            for indicator in login_indicators:
                if await page.locator(indicator).count() > 0:
                    kuaishou_logger.info(f"[+] 发现登录指示器 {indicator}，cookie已失效")
                    await browser.close()
                    return False

            # 检查是否有已登录的特征（发布相关元素）
            logged_in_indicators = [
                "text=发布作品",
                "text=发布视频",
                "button[class*='upload-btn']",
                "input[type='file']"
            ]

            for indicator in logged_in_indicators:
                if await page.locator(indicator).count() > 0:
                    kuaishou_logger.success("[+] cookie 有效")
                    await browser.close()
                    return True

            kuaishou_logger.warning("[+] 无法确定cookie状态，假定失效")
            await browser.close()
            return False

        except Exception as e:
            kuaishou_logger.error(f"[+] Cookie验证出错: {e}")
            await browser.close()
            return False


async def ks_setup(account_file, handle=False):
    account_file = get_absolute_path(account_file, "ks_uploader")
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            return False
        kuaishou_logger.info('[+] cookie文件不存在或已失效，即将自动打开浏览器，请扫码登录，登陆后会自动生成cookie文件')
        await get_ks_cookie(account_file)
    return True


async def get_ks_cookie(account_file):
    async with async_playwright() as playwright:
        options = {
            'args': [
                '--lang en-GB'
            ],
            'headless': HEADLESS_FLAG,  # Set headless option here
        }
        # Make sure to run headed.
        browser = await playwright.chromium.launch(**options)
        # Setup context however you like.
        context = await browser.new_context(**build_context_options())  # Pass any options
        context = await set_init_script(context)
        # Pause the page, and start recording manually.
        page = await context.new_page()
        await page.goto("https://cp.kuaishou.com")
        await page.pause()
        # 点击调试器的继续，保存cookie
        await context.storage_state(path=account_file)


class KSVideo(object):
    def __init__(self, title, file_path, tags, publish_date: datetime, account_file, proxy=None):
        self.title = title  # 视频标题
        self.file_path = file_path
        self.tags = tags
        self.publish_date = publish_date
        self.account_file = account_file
        self.date_format = '%Y-%m-%d %H:%M'
        self.local_executable_path = LOCAL_CHROME_PATH
        self.proxy = proxy

    async def handle_upload_error(self, page):
        kuaishou_logger.error("视频出错了，重新上传中")
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    async def upload(self, playwright: Playwright) -> None:
        # 使用 Chromium 浏览器启动一个浏览器实例
        launch_kwargs = {
            "headless": HEADLESS_FLAG
        }
        if self.local_executable_path:
            launch_kwargs["executable_path"] = self.local_executable_path
        
        if self.proxy:
            launch_kwargs["proxy"] = self.proxy
            kuaishou_logger.info(f"Using Proxy: {self.proxy.get('server')}")

        browser = await playwright.chromium.launch(**launch_kwargs)
        context = await browser.new_context(**build_context_options(storage_state=f"{self.account_file}"))
        context = await set_init_script(context)

        # 创建一个新的页面
        page = await context.new_page()

        # 设置页面事件监听 - 处理新弹出的窗口/标签页
        async def handle_popup(popup):
            kuaishou_logger.info(f"检测到弹出窗口: {popup.url}")
            # 如果是创作者中心相关的弹窗，关闭它
            if "cp.kuaishou.com" not in popup.url:
                kuaishou_logger.info("关闭非相关弹出窗口")
                await popup.close()

        context.on("page", handle_popup)

        # 访问指定的 URL
        kuaishou_logger.info('正在访问快手创作者中心...')
        try:
            await page.goto("https://cp.kuaishou.com/article/publish/video", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=10000)
            # ⚠️ 统一在这里关闭引导，不要多处调用
            try:
                await try_close_guide(page, "kuaishou")
            except Exception:
                pass
        except Exception as e:
            kuaishou_logger.warning(f'页面加载超时，继续尝试: {e}')

        # ⚠️ 移除：避免重复调用引导关闭
        # await dismiss_kuaishou_tour(page, max_attempts=10)
        await asyncio.sleep(1)

        kuaishou_logger.info('正在上传-------{}.mp4'.format(self.title))
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        kuaishou_logger.info('正在确认页面加载完成...')

        # 检查是否真的进入了发布页面
        max_retries = 3
        for retry in range(max_retries):
            try:
                current_url = page.url
                kuaishou_logger.info(f'当前页面URL: {current_url}')

                # 如果不在发布页面，尝试再次跳转
                if "publish/video" not in current_url:
                    kuaishou_logger.warning(f'未进入发布页面，尝试重新跳转 ({retry + 1}/{max_retries})')
                    await page.goto("https://cp.kuaishou.com/article/publish/video", timeout=30000)
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    # ⚠️ 移除：避免在重试中重复关闭引导
                    # await dismiss_kuaishou_tour(page, max_attempts=5)
                else:
                    kuaishou_logger.success('成功进入发布页面')
                    break
            except Exception as e:
                kuaishou_logger.error(f'检查页面状态出错: {e}')
                if retry == max_retries - 1:
                    raise Exception(f"无法进入快手发布页面，已重试{max_retries}次")
                await asyncio.sleep(2)

        # 点击 "上传视频" 按钮 - 尝试多种选择器
        upload_button_selectors = [
            "button[class^='_upload-btn']",
            "button:has-text('上传视频')",
            "button:has-text('上传作品')",
            ".upload-btn",
            "[class*='upload-btn']",
        ]

        upload_button = None
        for selector in upload_button_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0:
                    await btn.wait_for(state='visible', timeout=5000)
                    upload_button = btn
                    kuaishou_logger.info(f'找到上传按钮，选择器: {selector}')
                    break
            except Exception as e:
                kuaishou_logger.debug(f'选择器 {selector} 失败: {e}')
                continue

        if not upload_button:
            kuaishou_logger.error('未找到上传按钮，尝试截图')
            await page.screenshot(path='logs/ks_upload_button_not_found.png', full_page=True)
            raise Exception("未找到上传视频按钮")

        async with page.expect_file_chooser() as fc_info:
            await upload_button.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(self.file_path)

        await asyncio.sleep(2)

        # if not await page.get_by_text("封面编辑").count():
        #     raise Exception("似乎没有跳转到到编辑页面")

        await asyncio.sleep(1)

        # 关闭 react-joyride 引导遮罩（如果存在）
        await _close_joyride_guide(page)
        await dismiss_kuaishou_tour(page, max_attempts=8)

        # 等待按钮可交互
        new_feature_button = page.locator('button[type="button"] span:text("我知道了")')
        if await new_feature_button.count() > 0:
            await new_feature_button.click()
            await asyncio.sleep(0.5)

        # ⚠️ 关键修复：必须在填充前关闭 Joyride 引导，避免遮挡输入框
        kuaishou_logger.info("确保 Joyride 引导已关闭...")
        await _close_joyride_guide(page)
        await asyncio.sleep(1)

        kuaishou_logger.info("正在填充标题和话题...")
        try:
            fill_success = await _fill_title_and_topics(page, self.title, self.tags)
            if not fill_success:
                kuaishou_logger.error("❌ 标题/话题填充失败，终止发布")
                await _debug_dump(page, "kuaishou_fill_failed")
                raise Exception("标题/话题填充失败，无法继续发布")
            kuaishou_logger.success("✅ 标题和话题填充成功")
        except Exception as e:
            kuaishou_logger.error(f"填充标题/话题失败: {e}")
            await _debug_dump(page, "kuaishou_fill_failed")
            raise  # ⚠️ 抛出异常，阻止空标题发布

        max_retries = 60  # 设置最大重试次数,最大等待时间为 2 分钟
        retry_count = 0

        while retry_count < max_retries:
            try:
                # 获取包含 '上传中' 文本的元素数量
                number = await page.locator("text=上传中").count()

                if number == 0:
                    kuaishou_logger.success("视频上传完毕")
                    break
                else:
                    if retry_count % 5 == 0:
                        kuaishou_logger.info("正在上传视频中...")
                    await asyncio.sleep(2)
            except Exception as e:
                kuaishou_logger.error(f"检查上传状态时发生错误: {e}")
                await asyncio.sleep(2)  # 等待 2 秒后重试
            retry_count += 1

        if retry_count == max_retries:
            kuaishou_logger.warning("超过最大重试次数，视频上传可能未完成。")

        # 🔧 2025-12-29: 快手发布流程更新
        # 前3步: 引导提示（点击"下一步"或"立刻体验"）
        kuaishou_logger.info("[发布] 关闭引导提示...")
        try:
            await _close_joyride_guide(page)
            await dismiss_kuaishou_tour(page, max_attempts=6)
            kuaishou_logger.success("[发布] 引导提示已关闭")
        except Exception as e:
            kuaishou_logger.warning(f"[发布] 关闭引导失败（继续）: {e}")

        await asyncio.sleep(1)

        # 定时任务（在点击发布按钮前设置）
        if self.publish_date != 0:
            kuaishou_logger.info("[发布] 设置定时发布...")
            await self.set_schedule_time(page, self.publish_date)

        # 步骤1: 点击"发布"按钮打开"发布设置"对话框
        kuaishou_logger.info("[发布] 步骤1: 点击发布按钮...")
        publish_button = page.get_by_text("发布", exact=True)
        if await publish_button.count() > 0:
            await publish_button.click()
            kuaishou_logger.success("[发布] 已点击发布按钮，等待发布设置对话框...")
            await asyncio.sleep(2)

        # 步骤2: 在"发布设置"对话框中配置
        kuaishou_logger.info("[发布] 步骤2: 等待发布设置对话框...")

        # 等待对话框出现（通过标题"发布设置"或"互动设置"确认）
        try:
            # 尝试多种可能的对话框选择器
            dialog_indicators = [
                "text=发布设置",
                "text=互动设置",
                "text=查看权限",
                "div.ant-modal-content",  # Ant Design 模态框
                "div[role='dialog']",
            ]

            dialog_found = False
            for indicator in dialog_indicators:
                if await page.locator(indicator).count() > 0:
                    kuaishou_logger.success(f"[发布] 检测到发布设置对话框: {indicator}")
                    dialog_found = True
                    break

            if dialog_found:
                kuaishou_logger.info("[发布] 使用对话框中的默认设置")
                await asyncio.sleep(1)

                # 步骤3: 点击对话框内的"发布"按钮
                kuaishou_logger.info("[发布] 步骤3: 点击对话框内的发布按钮...")

                # 尝试多种可能的发布按钮选择器
                dialog_publish_selectors = [
                    "div.ant-modal-footer button:has-text('发布')",  # 对话框底部的发布按钮
                    "div[role='dialog'] button:has-text('发布')",
                    "button.ant-btn-primary:has-text('发布')",
                    "button:has-text('发布')",
                ]

                clicked = False
                for selector in dialog_publish_selectors:
                    try:
                        btn = page.locator(selector)
                        if await btn.count() > 0:
                            await btn.first.click()
                            kuaishou_logger.success(f"[发布] 已点击对话框发布按钮: {selector}")
                            clicked = True
                            break
                    except Exception:
                        continue

                if not clicked:
                    kuaishou_logger.warning("[发布] 未找到对话框发布按钮，尝试查找确认发布按钮...")
                    confirm_button = page.get_by_text("确认发布")
                    if await confirm_button.count() > 0:
                        await confirm_button.click()
                        kuaishou_logger.success("[发布] 已点击确认发布按钮")
            else:
                # 如果没有对话框，可能是旧版本流程
                kuaishou_logger.warning("[发布] 未检测到发布设置对话框，尝试直接确认发布...")
                confirm_button = page.get_by_text("确认发布")
                if await confirm_button.count() > 0:
                    await confirm_button.click()
                    kuaishou_logger.success("[发布] 已点击确认发布按钮（旧流程）")

        except Exception as e:
            kuaishou_logger.error(f"[发布] 发布设置对话框处理失败: {e}")
            await _debug_dump(page, "kuaishou_publish_dialog_error")

        # 步骤4: 等待页面跳转，确认发布成功
        kuaishou_logger.info("[发布] 步骤4: 等待发布完成...")
        try:
            await page.wait_for_url(
                "https://cp.kuaishou.com/article/manage/video?status=2&from=publish",
                timeout=15000,  # 增加超时时间到15秒
            )
            kuaishou_logger.success("✅ 视频发布成功！")
        except Exception as e:
            kuaishou_logger.warning(f"[发布] 等待跳转超时: {e}")
            # 检查是否真的发布成功（有些情况下虽然超时但实际已发布）
            current_url = page.url
            if "manage/video" in current_url or "status=2" in current_url:
                kuaishou_logger.success("✅ 视频发布成功（URL确认）")
            else:
                kuaishou_logger.error(f"❌ 视频可能发布失败，当前URL: {current_url}")
                await _debug_dump(page, "kuaishou_publish_failed")
                raise Exception(f"发布失败，当前URL: {current_url}")

        await context.storage_state(path=self.account_file)  # 保存cookie
        kuaishou_logger.info('cookie更新完毕！')
        await asyncio.sleep(2)  # 这里延迟是为了方便眼睛直观的观看
        # 关闭浏览器上下文和浏览器实例
        await context.close()
        await browser.close()

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def set_schedule_time(self, page, publish_date):
        kuaishou_logger.info("click schedule")
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M:%S")
        await page.locator("label:text('发布时间')").locator('xpath=following-sibling::div').locator(
            '.ant-radio-input').nth(1).click()
        await asyncio.sleep(1)

        await page.locator('div.ant-picker-input input[placeholder="选择日期时间"]').click()
        await asyncio.sleep(1)

        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")
        await asyncio.sleep(1)
