# -*- coding: utf-8 -*-
"""
LEGACY IMPLEMENTATION:
该模块为历史 uploader 栈实现；当前业务发布已统一走 `syn_backend/platforms/*/upload.py`。
平台层可能仍会复用本实现，建议不要在业务层直接 import/调用。
"""
from datetime import datetime

from playwright.async_api import Playwright, async_playwright
import os
import asyncio
from pathlib import Path

from config.conf import LOCAL_CHROME_PATH
from utils.base_social_media import set_init_script, HEADLESS_FLAG
from myUtils.browser_context import build_context_options, build_browser_args, build_firefox_args
from myUtils.close_guide import try_close_guide
from utils.files_times import get_absolute_path
from utils.log import tencent_logger


def format_str_for_short_title(origin_title: str) -> str:
    # 定义允许的特殊字符
    allowed_special_chars = "《》“”:+?%°"

    # 移除不允许的特殊字符
    filtered_chars = [char if char.isalnum() or char in allowed_special_chars else ' ' if char == ',' else '' for
                      char in origin_title]
    formatted_string = ''.join(filtered_chars)

    # 调整字符串长度
    if len(formatted_string) > 16:
        # 截断字符串
        formatted_string = formatted_string[:16]
    elif len(formatted_string) < 6:
        # 使用空格来填充字符串
        formatted_string += ' ' * (6 - len(formatted_string))

    return formatted_string


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        # 🦊 使用 Firefox 替代 Chromium（更快、更稳定）
        firefox_args = build_firefox_args()
        firefox_args['headless'] = HEADLESS_FLAG
        # Do not pass empty executable_path, otherwise Playwright may try to spawn '.' (ENOENT)
        if not firefox_args.get("executable_path"):
            firefox_args.pop("executable_path", None)
        browser = await playwright.firefox.launch(**firefox_args)
        context = await browser.new_context(**build_context_options(storage_state=account_file))
        context = await set_init_script(context)
        # 创建一个新的页面
        page = await context.new_page()

        try:
            # 访问指定的 URL
            page.set_default_timeout(20000)
            page.set_default_navigation_timeout(30000)
            await page.goto("https://channels.weixin.qq.com/platform/post/create", timeout=30000, wait_until="domcontentloaded")
            
            # 2025 Fix: 使用与 upload() 中一致的逻辑
            # 优先看是否有上传入口（attached 即可）
            try:
                # 给一点点时间等待 DOM 渲染
                await page.wait_for_selector("input[type='file'], span.ant-upload", state="attached", timeout=5000)
            except:
                pass

            # 检查是否有发布页面的关键元素（只要有上传入口，就说明登录成功）
            # input[type="file"] 即使隐藏也算有效
            if await page.locator('input[type="file"]').count() > 0 or await page.locator('.input-editor').count() > 0:
                tencent_logger.success("[+] 检测到上传入口/编辑框，Cookie有效")
                await context.close()
                await browser.close()
                return True

            # 检查是否有登录相关的特有元素（说明确实在登录页）
            login_indicators = [
                'div.login-container',
                '.login-qrcode',
                'div:has-text("请扫码登录")',
                'canvas',  # 登录二维码通常是 canvas
            ]

            for indicator in login_indicators:
                if await page.locator(indicator).count() > 0:
                    tencent_logger.error("[+] 检测到登录页面特有元素，cookie已失效")
                    await context.close()
                    await browser.close()
                    return False

            # 如果检测到 "登录" 文本，但也可能在首页顶部，所以我们要更谨慎
            # 只有在没有发现任何发布页元素的情况下，看到这类文本才认为失效
            if await page.locator('button:has-text("登录"), text=请先登录').count() > 0:
                 tencent_logger.warning("[+] 检测到登录引导文本且无发布元素，cookie可能失效")
                 await context.close()
                 await browser.close()
                 return False

            # 兜底：如果啥都没看到
            tencent_logger.warning("[+] 未检测到预期页面元素，保守判断为失效")
            await context.close()
            await browser.close()
            return False

        except Exception as e:
            tencent_logger.error(f"[+] Cookie验证出错: {e}")
            await context.close()
            await browser.close()
            return False


async def get_tencent_cookie(account_file):
    async with async_playwright() as playwright:
        browser_args = build_firefox_args()  # 使用 Firefox 配置
        browser_args['headless'] = HEADLESS_FLAG
        # Make sure to run headed.
        if not browser_args.get("executable_path"):
            browser_args.pop("executable_path", None)
        # 🦊 使用 Firefox 替代 Chromium（更快、更稳定）
        browser = await playwright.firefox.launch(**browser_args)
        # Setup context however you like.
        context = await browser.new_context(**build_context_options())  # Pass any options
        # Pause the page, and start recording manually.
        context = await set_init_script(context)
        page = await context.new_page()
        await page.goto("https://channels.weixin.qq.com")
        await page.pause()
        # 点击调试器的继续，保存cookie
        await context.storage_state(path=account_file)


async def weixin_setup(account_file, handle=False):
    account_file = get_absolute_path(account_file, "tencent_uploader")
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            # Todo alert message
            return False
        tencent_logger.info('[+] cookie文件不存在或已失效，即将自动打开浏览器，请扫码登录，登陆后会自动生成cookie文件')
        await get_tencent_cookie(account_file)
    return True


class TencentVideo(object):
    def __init__(self, title, file_path, tags, publish_date: datetime, account_file, category=None, thumbnail_path=None, proxy=None):
        self.title = title  # 视频标题
        self.file_path = file_path
        self.tags = tags
        self.publish_date = publish_date
        self.account_file = account_file
        self.category = category
        self.thumbnail_path = thumbnail_path
        self.local_executable_path = LOCAL_CHROME_PATH
        self.proxy = proxy

    async def set_schedule_time_tencent(self, page, publish_date):
        label_element = page.locator("label").filter(has_text="定时").nth(1)
        await label_element.click()

        await page.click('input[placeholder="请选择发表时间"]')

        str_month = str(publish_date.month) if publish_date.month > 9 else "0" + str(publish_date.month)
        current_month = str_month + "月"
        # 获取当前的月份
        page_month = await page.inner_text('span.weui-desktop-picker__panel__label:has-text("月")')

        # 检查当前月份是否与目标月份相同
        if page_month != current_month:
            await page.click('button.weui-desktop-btn__icon__right')

        # 获取页面元素
        elements = await page.query_selector_all('table.weui-desktop-picker__table a')

        # 遍历元素并点击匹配的元素
        for element in elements:
            if 'weui-desktop-picker__disabled' in await element.evaluate('el => el.className'):
                continue
            text = await element.inner_text()
            if text.strip() == str(publish_date.day):
                await element.click()
                break

        # 输入小时部分（假设选择11小时）
        await page.click('input[placeholder="请选择时间"]')
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date.hour))

        # 选择标题栏（令定时时间生效）
        await page.locator("div.input-editor").click()

    async def handle_upload_error(self, page):
        tencent_logger.info("视频出错了，重新上传中")
        await page.locator('div.media-status-content div.tag-inner:has-text("删除")').click()
        await page.get_by_role('button', name="删除", exact=True).click()
        file_input = page.locator('input[type="file"]')
        await file_input.set_input_files(self.file_path)

    async def upload(self, playwright: Playwright) -> None:
        try:
            tencent_logger.info(f"[视频号] Uploader实现: tencent_uploader/main.py (file={__file__})")
        except Exception:
            pass
        # 视频号必须使用 Chrome for Testing（支持 H.265）
        # Playwright Chromium 不支持 H.265 会导致"浏览器不支持此视频格式"错误
        browser_args = build_browser_args()
        browser_args['headless'] = HEADLESS_FLAG

        # Inject Proxy if available
        if self.proxy:
             browser_args['proxy'] = self.proxy
             tencent_logger.info(f"Using Proxy: {self.proxy.get('server')}")

        # 视频号专用：强制使用 Chrome for Testing
        # 策略：使用相对路径定位（项目可移动）
        # 注意：视频号必须使用 Chrome for Testing，不使用全局 LOCAL_CHROME_PATH
        chrome_for_testing_path = None

        # 优先级1: 实例化时传入的路径（可以是相对或绝对）
        if self.local_executable_path:
            candidate = Path(str(self.local_executable_path))
            if not candidate.is_absolute():
                # 如果是相对路径，从项目根目录开始解析
                project_root = Path(__file__).parent.parent.parent.parent
                candidate = project_root / candidate

            if candidate.is_file():
                chrome_for_testing_path = candidate
                tencent_logger.info(f"[+] 使用传入的浏览器（相对项目）")

        # 优先级2: 从配置读取 Chrome for Testing 路径（支持相对路径）
        if not chrome_for_testing_path:
            try:
                from config.conf import LOCAL_CHROME_PATH
                if LOCAL_CHROME_PATH:
                    candidate = Path(str(LOCAL_CHROME_PATH))

                    # 如果配置的是相对路径，从项目根目录解析
                    if not candidate.is_absolute():
                        project_root = Path(__file__).parent.parent.parent.parent
                        candidate = project_root / candidate

                    if candidate.is_file():
                        chrome_for_testing_path = candidate
                        tencent_logger.info(f"[+] 从配置读取 Chrome for Testing")
                    else:
                        tencent_logger.warning(f"[+] 配置的路径无效: {LOCAL_CHROME_PATH}")
            except Exception as e:
                tencent_logger.warning(f"[+] 读取配置失败: {e}")

        # 优先级3: 自动查找项目内的 Chrome for Testing（使用相对路径）
        if not chrome_for_testing_path:
            project_root = Path(__file__).parent.parent.parent.parent
            auto_chrome_path = project_root / '.chrome-for-testing'

            # 查找最新版本
            if auto_chrome_path.exists():
                chrome_dirs = sorted(auto_chrome_path.glob('chrome-*'), reverse=True)
                for chrome_dir in chrome_dirs:
                    chrome_exe = chrome_dir / 'chrome-win64' / 'chrome.exe'
                    if chrome_exe.exists():
                        chrome_for_testing_path = chrome_exe
                        # 计算相对路径用于日志显示
                        try:
                            rel_path = chrome_exe.relative_to(project_root)
                            tencent_logger.info(f"[+] 自动找到 Chrome for Testing: {rel_path}")
                        except:
                            tencent_logger.info(f"[+] 自动找到 Chrome for Testing")
                        break

        # 🦊 视频号改用 Firefox（比 Chrome for Testing 更快）
        # Firefox 也支持 H.265 视频编解码
        tencent_logger.info(f"[+] ✅ 使用 Firefox 浏览器（更快、更稳定）")

        # 使用 Firefox 专用配置（会自动读取 LOCAL_FIREFOX_PATH）
        firefox_args = build_firefox_args()
        firefox_args['headless'] = browser_args.get('headless', False)
        # 如果没有配置 executable_path，移除该字段让 Playwright 使用默认 Firefox
        if not firefox_args.get('executable_path'):
            firefox_args.pop('executable_path', None)

        browser = await playwright.firefox.launch(**firefox_args)
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(**build_context_options(storage_state=f"{self.account_file}"))
        context = await set_init_script(context)

        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        tencent_logger.info(f'[+]正在访问发布页面...')
        page.set_default_timeout(10000)
        page.set_default_navigation_timeout(10000)
        
        # 优化1: 只要 commit 了就开始检查元素，不一定要等 domcontentloaded
        await page.goto("https://channels.weixin.qq.com/platform/post/create", wait_until="commit")

        # 等待页面加载
        try:
            tencent_logger.info('[+]快速探测核心元素...')
            # 优化2: 使用 race 方式等待多个可能的元素，谁先到用谁
            await page.wait_for_selector("input[type='file'], span.ant-upload, div.upload-content", timeout=15000)
            tencent_logger.success('[+]页面核心元素已就绪')
        except Exception as e:
            tencent_logger.warning(f'[-]快速探测超时，尝试兜底检查: {e}')
            
        # 调试：打印当前页面标题和URL
        title = await page.title()
        tencent_logger.info(f'[+]页面标题: {title}, URL: {page.url}')
        try:
            # 优化3: 移除指南弹窗的等待，改为非阻塞异步
            asyncio.create_task(try_close_guide(page, "channels"))
        except Exception:
            pass

        # 检查是否需要登录（cookie可能已过期）
        # 2025 Fix: "登录" text might appear in header even when logged in.
        should_check_login = True
        
        # Determine if we strongly believe we are logged in (upload input found)
        upload_input_found = await page.locator("input[type='file']").count() > 0
        
        if upload_input_found:
             tencent_logger.success("[+] 检测到上传入口，Cookie有效 (Skipping strict login check)")
             should_check_login = False
        
        if should_check_login:
             is_login_url = "login" in page.url.lower()
             login_text_exists = await page.locator('.login-container, .login-qrcode, div:has-text("请扫码登录")').count() > 0
             
             if is_login_url or login_text_exists:
                 tencent_logger.error("[+] 检测到需要登录，cookie可能已过期")
                 await page.screenshot(path='logs/channels_need_login.png', full_page=True)
                 raise Exception("Cookie已过期，需要重新登录")

        tencent_logger.info(f'[+]正在上传-------{self.title}.mp4')

        # 尝试多个文件上传选择器（更新为2025年最新选择器）
        file_input_selectors = [
            'input[type="file"]',  # universal file input (most reliable)
            'div.ant-upload input[type="file"]',
            'span.ant-upload input[type="file"]',
            'input[accept*="video"]',
            'input[name="file"]',
        ]

        scopes = [("page", page)]
        try:
            for idx, frame in enumerate(page.frames):
                if frame == page.main_frame:
                    continue
                scopes.append((f"frame[{idx}]", frame))
        except Exception:
            pass

        async def _find_file_input():
            for selector in file_input_selectors:
                for scope_name, scope in scopes:
                    try:
                        locator = scope.locator(selector)
                        count = await locator.count()
                        if count > 0:
                            return locator.first, scope_name, selector, count
                    except Exception as e:
                        tencent_logger.debug(f'选择器 {selector} @ {scope_name} 失败: {e}')
                        continue
            return None, None, None, 0

        file_input, scope_name, matched_selector, count = await _find_file_input()
        if file_input:
            tencent_logger.info(f'[+]找到文件上传元素({scope_name}): {matched_selector} (共{count}个)')

        if not file_input:
            tencent_logger.warning('[+]未找到隐藏的文件上传input，尝试点击上传按钮触发')

            # 尝试点击上传按钮/区域来触发文件选择器
            upload_button_selectors = [
                'div.upload-content',  # 2024年最新：视频号上传区域
                'span.weui-icon-outlined-add',  # 2024年最新：上传图标
                'div.upload-content div.center',  # 上传中心区域
                'button:has-text("上传")',
                'button:has-text("选择文件")',
                'button:has-text("添加视频")',
                'div.upload-btn',
                'div.upload-area',
                'div[role="button"]:has-text("上传")',
                '.upload-trigger',
                'text=上传视频',
                'text=选择视频',
            ]

            button_clicked = False
            for btn_selector in upload_button_selectors:
                clicked = False
                for click_scope_name, click_scope in scopes:
                    try:
                        btn = click_scope.locator(btn_selector)
                        if await btn.count() > 0:
                            tencent_logger.info(f'[+]尝试点击上传按钮({click_scope_name}): {btn_selector}')
                            await btn.first.click()
                            clicked = True
                            break
                    except Exception as e:
                        tencent_logger.debug(f'点击按钮 {btn_selector} @ {click_scope_name} 失败: {e}')
                        continue

                if not clicked:
                    continue

                await page.wait_for_timeout(1000)  # 等待1秒
                file_input, scope_name, matched_selector, _count = await _find_file_input()
                if file_input:
                    tencent_logger.success(f'[+]点击按钮后找到文件上传元素({scope_name}): {matched_selector}')
                    button_clicked = True
                    break

            if not file_input:
                tencent_logger.error('[+]未找到文件上传元素，进行截图和HTML调试')
                await page.screenshot(path='logs/channels_no_file_input.png', full_page=True)

                # 额外调试：打印页面中所有input元素
                try:
                    all_inputs = await page.locator('input').all()
                    tencent_logger.info(f'[+]页面共有 {len(all_inputs)} 个input元素')
                    for idx, inp in enumerate(all_inputs[:10]):  # 只打印前10个
                        inp_type = await inp.get_attribute('type')
                        inp_id = await inp.get_attribute('id')
                        inp_class = await inp.get_attribute('class')
                        inp_accept = await inp.get_attribute('accept')
                        tencent_logger.info(f'  Input {idx}: type={inp_type}, id={inp_id}, class={inp_class}, accept={inp_accept}')
                except Exception as debug_error:
                    tencent_logger.error(f'调试信息获取失败: {debug_error}')

                raise Exception("未找到文件上传元素，请检查视频号页面是否改版")

        await file_input.set_input_files(self.file_path)
        tencent_logger.success('[+]文件已选择，等待上传确认...')

        # 2025 Fix: 文件选择后，需要点击"确认上传"或类似按钮来真正触发上传
        # 等待一小段时间让 DOM 更新
        await page.wait_for_timeout(800)

        # 查找并点击上传确认按钮
        upload_confirm_selectors = [
            'button:has-text("开始上传")',
            'button:has-text("确认上传")',
            'button:has-text("上传")',
            'div.upload-btn button',
            'button.upload-confirm',
            'button.start-upload',
            'div.ant-modal-footer button.ant-btn-primary',  # 如果有弹窗
        ]

        upload_confirmed = False
        for confirm_selector in upload_confirm_selectors:
            try:
                confirm_btn = page.locator(confirm_selector)
                if await confirm_btn.count() > 0 and await confirm_btn.first.is_visible():
                    tencent_logger.info(f'[+]找到上传确认按钮: {confirm_selector}')
                    await confirm_btn.first.click()
                    upload_confirmed = True
                    tencent_logger.success('[+]已点击上传确认按钮，开始上传')
                    break
            except Exception as e:
                tencent_logger.debug(f'尝试点击 {confirm_selector} 失败: {e}')
                continue

        if not upload_confirmed:
            tencent_logger.warning('[+]未找到明确的上传确认按钮，文件可能会自动上传（取决于页面逻辑）')

        # 再等待一小段时间让上传开始
        await page.wait_for_timeout(500)
        try:
            await try_close_guide(page, "channels")
        except Exception:
            pass
        # 填充标题和话题
        await self.add_title_tags(page)
        # 添加商品
        # await self.add_product(page)
        # 合集功能
        await self.add_collection(page)
        # 原创选择
        await self.add_original(page)
        # 检测上传状态
        await self.detect_upload_status(page)
        if self.publish_date != 0:
            try:
                await try_close_guide(page, "channels")
            except Exception:
                pass
            await self.set_schedule_time_tencent(page, self.publish_date)
        # 添加短标题
        await self.add_short_title(page)

        await self.click_publish(page)

        await context.storage_state(path=f"{self.account_file}")  # 保存cookie
        tencent_logger.success('  [-]cookie更新完毕！')
        await asyncio.sleep(2)  # 这里延迟是为了方便眼睛直观的观看
        # 关闭浏览器上下文和浏览器实例
        await context.close()
        await browser.close()

    async def add_short_title(self, page):
        short_title_element = page.get_by_text("短标题", exact=True).locator("..").locator(
            "xpath=following-sibling::div").locator(
            'span input[type="text"]')
        if await short_title_element.count():
            short_title = format_str_for_short_title(self.title)
            await short_title_element.fill(short_title)

    async def click_publish(self, page):
        while True:
            try:
                # 2025修正：优先使用 primary class 按钮
                publish_button = page.locator('button.weui-desktop-btn_primary:has-text("发表")')
                if await publish_button.count() == 0:
                    # Fallback
                    publish_button = page.locator('div.form-btns button:has-text("发表")')
                
                if await publish_button.count():
                    await publish_button.dispatch_event('click') # 有时候click()会被拦截，尝试dispatch click
                    try:
                        await publish_button.click(timeout=1000)
                    except:
                        pass
                
                # 检查是否出现成功跳转或列表页
                try:
                    await page.wait_for_url("**/platform/post/list", timeout=3000)
                    tencent_logger.success("  [-]视频发布成功")
                    break
                except:
                    pass
                
                # 再次检查URL
                current_url = page.url
                if "platform/post/list" in current_url:
                    tencent_logger.success("  [-]视频发布成功")
                    break
                else:
                    tencent_logger.info("  [-] 视频目前 URL: " + current_url)
                    await asyncio.sleep(0.5)
            except Exception as e:
                current_url = page.url
                if "https://channels.weixin.qq.com/platform/post/list" in current_url:
                    tencent_logger.success("  [-]视频发布成功")
                    break
                else:
                    tencent_logger.exception(f"  [-] Exception: {e}")
                    tencent_logger.info("  [-] 视频正在发布中...")
                    await asyncio.sleep(0.5)

    async def detect_upload_status(self, page):
        """检测视频上传状态（优化版：缩短轮询间隔，增加进度反馈）"""
        upload_start_time = asyncio.get_event_loop().time()
        last_log_time = upload_start_time
        check_count = 0

        while True:
            check_count += 1
            current_time = asyncio.get_event_loop().time()
            elapsed = int(current_time - upload_start_time)

            try:
                # 检查"发表"按钮状态
                publish_btn = page.get_by_role("button", name="发表")
                btn_class = await publish_btn.get_attribute('class')

                if btn_class and "weui-desktop-btn_disabled" not in btn_class:
                    tencent_logger.success(f"  [-]视频上传完毕（耗时 {elapsed} 秒）")
                    break

                # 检查是否有上传错误
                if await page.locator('div.status-msg.error').count() > 0:
                    if await page.locator('div.media-status-content div.tag-inner:has-text("删除")').count() > 0:
                        tencent_logger.error("  [-] 发现上传出错了...准备重试")
                        await self.handle_upload_error(page)
                        upload_start_time = asyncio.get_event_loop().time()  # 重置计时
                        continue

                # 尝试获取上传进度（如果页面有显示）
                progress_text = ""
                try:
                    # 常见的进度显示选择器
                    progress_selectors = [
                        'div.upload-progress',
                        'span.progress-text',
                        'div.percent',
                        'div:has-text("%")',
                    ]
                    for selector in progress_selectors:
                        progress_elem = page.locator(selector).first
                        if await progress_elem.count() > 0:
                            progress_text = await progress_elem.inner_text()
                            break
                except Exception:
                    pass

                # 每 5 秒输出一次日志（避免刷屏）
                if current_time - last_log_time >= 5:
                    if progress_text:
                        tencent_logger.info(f"  [-] 上传中... {progress_text} (已用 {elapsed}s, 检查 {check_count} 次)")
                    else:
                        tencent_logger.info(f"  [-] 上传中... (已用 {elapsed}s, 检查 {check_count} 次)")
                    last_log_time = current_time

                # 优化：缩短轮询间隔到 0.5 秒（响应更快）
                await asyncio.sleep(0.5)

            except Exception as e:
                # 出现异常时也缩短间隔
                tencent_logger.debug(f"  [-] 状态检查异常: {e}")
                await asyncio.sleep(0.5)

    async def add_title_tags(self, page):
        # 2025: selector updated to .input-editor
        await page.locator(".input-editor").click()
        await page.keyboard.type(self.title)
        await page.keyboard.press("Enter")
        for index, tag in enumerate(self.tags, start=1):
            await page.keyboard.type("#" + tag)
            await page.keyboard.press("Space")
        tencent_logger.info(f"成功添加hashtag: {len(self.tags)}")

    async def add_collection(self, page):
        collection_elements = page.get_by_text("添加到合集").locator("xpath=following-sibling::div").locator(
            '.option-list-wrap > div')
        if await collection_elements.count() > 1:
            await page.get_by_text("添加到合集").locator("xpath=following-sibling::div").click()
            await collection_elements.first.click()

    async def add_original(self, page):
        # 2025修正：原创选项可能不存在（由于账号权限或UI改版），增加存在性检查
        try:
            # 方式1: Label check
            if await page.get_by_label("视频为原创").is_visible():
                await page.get_by_label("视频为原创").check()

            # 方式2: 显式文本查找
            original_checkbox = page.locator('.weui-desktop-form__check-label:has-text("视频为原创")')
            if await original_checkbox.count() > 0:
                # check inside input
                checkbox_input = original_checkbox.locator('input[type="checkbox"]')
                if await checkbox_input.count() > 0 and not await checkbox_input.is_checked():
                     await original_checkbox.click()
            
            # 检查 "我已阅读并同意 《视频号原创声明使用条款》" 元素是否存在
            terms_label = page.locator('label:has-text("我已阅读并同意 《视频号原创声明使用条款》")')
            if await terms_label.is_visible():
                # 勾选条款
                checkbox = terms_label.locator('input[type="checkbox"]')
                if not await checkbox.is_checked():
                    await terms_label.click()
                # 点击声明
                declare_btn = page.get_by_role("button", name="声明原创")
                if await declare_btn.is_visible():
                    await declare_btn.click()

            # 兼容旧版本/弹窗逻辑
            if await page.locator('div.label span:has-text("声明原创")').count() and self.category:
                if not await page.locator('div.declare-original-checkbox input.ant-checkbox-input').is_disabled():
                    await page.locator('div.declare-original-checkbox input.ant-checkbox-input').click()
                    if not await page.locator('div.declare-original-dialog label.ant-checkbox-wrapper.ant-checkbox-wrapper-checked:visible').count():
                         await page.locator('div.declare-original-dialog input.ant-checkbox-input:visible').click()
                if await page.locator('div.original-type-form > div.form-label:has-text("原创类型"):visible').count():
                    await page.locator('div.form-content:visible').click()
                    await page.locator(f'div.form-content:visible ul.weui-desktop-dropdown__list li.weui-desktop-dropdown__list-ele:has-text("{self.category}")').first.click()
                    await page.wait_for_timeout(1000)
                if await page.locator('button:has-text("声明原创"):visible').count():
                    await page.locator('button:has-text("声明原创"):visible').click()
        except Exception as e:
            tencent_logger.warning(f"[-] 声明原创步骤出现异常(可能是非原创账号/UI变动)，跳过: {e}")

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
