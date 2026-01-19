# -*- coding: utf-8 -*-
from datetime import datetime

from playwright.async_api import Playwright, async_playwright, Page
import os
import asyncio

from config.conf import LOCAL_CHROME_PATH
from utils.base_social_media import set_init_script, HEADLESS_FLAG
from myUtils.browser_context import build_context_options
from myUtils.close_guide import try_close_guide
from utils.log import xiaohongshu_logger

XHS_TOUR_CONTAINERS = [
    ".semi-modal",
    ".guide-modal",
    "[role='dialog']",
    ".semi-modal-content",
    ".semi-modal-body",
]

XHS_TOUR_BTNS = [
    'button:has-text("我知道了")',
    'button:has-text("知道了")',
    'button:has-text("关闭")',
    '[aria-label="关闭"]',
    '[aria-label="close"]',
]


async def dismiss_xhs_tour(page, max_attempts: int = 6):
    """尝试关闭小红书发布页/创作中心的新手引导弹窗。"""
    for _ in range(max_attempts):
        has_popup = False
        for sel in XHS_TOUR_CONTAINERS:
            loc = page.locator(sel)
            if await loc.count() > 0 and await loc.first.is_visible():
                has_popup = True
                break
        if not has_popup:
            return

        clicked = False
        for btn_sel in XHS_TOUR_BTNS:
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


XHS_TOUR_CONTAINERS = [
    '[role="dialog"]',
    '[aria-modal="true"]',
    '.modal-wrap',
    '.guide-dialog',
    '.tour-modal',
    '.xh-dialog',
    '.xh-guide',
    '.guide-container',
]

XHS_TOUR_BTNS = [
    'button:has-text("下一步")',
    'button:has-text("知道了")',
    'button:has-text("我知道了")',
    'button:has-text("跳过")',
    'button:has-text("完成")',
    '[aria-label="关闭"]',
]


async def dismiss_xhs_tour(page, max_attempts: int = 6):
    """尝试关闭小红书发布页的新手引导弹窗。"""
    for _ in range(max_attempts):
        has_popup = False
        for sel in XHS_TOUR_CONTAINERS:
            loc = page.locator(sel)
            if await loc.count() > 0 and await loc.first.is_visible():
                has_popup = True
                break
        if not has_popup:
            return

        clicked = False
        for btn_sel in XHS_TOUR_BTNS:
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


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=HEADLESS_FLAG)
        context = await browser.new_context(**build_context_options(storage_state=account_file))
        context = await set_init_script(context)
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://creator.xiaohongshu.com/creator-micro/content/upload")
        try:
            await try_close_guide(page, "xiaohongshu")
        except Exception:
            pass
        try:
            await page.wait_for_url("https://creator.xiaohongshu.com/creator-micro/content/upload", timeout=5000)
        except:
            print("[+] 等待5秒 cookie 失效")
            await context.close()
            await browser.close()
            return False
        # 2024.06.17 抖音创作者中心改版
        if await page.get_by_text('手机号登录').count() or await page.get_by_text('扫码登录').count():
            print("[+] 等待5秒 cookie 失效")
            return False
        else:
            print("[+] cookie 有效")
            return True


async def xiaohongshu_setup(account_file, handle=False):
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            # Todo alert message
            return False
        xiaohongshu_logger.info('[+] cookie文件不存在或已失效，即将自动打开浏览器，请扫码登录，登陆后会自动生成cookie文件')
        await xiaohongshu_cookie_gen(account_file)
    return True


async def xiaohongshu_cookie_gen(account_file):
    async with async_playwright() as playwright:
        options = {
            'headless': HEADLESS_FLAG
        }
        # Make sure to run headed.
        browser = await playwright.chromium.launch(**options)
        # Setup context however you like.
        context = await browser.new_context(**build_context_options())  # Pass any options
        context = await set_init_script(context)
        # Pause the page, and start recording manually.
        page = await context.new_page()
        await page.goto("https://creator.xiaohongshu.com/")
        await page.pause()
        # 点击调试器的继续，保存cookie
        await context.storage_state(path=account_file)


class XiaoHongShuVideo(object):
    def __init__(self, title, file_path, tags, publish_date: datetime, account_file, thumbnail_path=None, proxy=None):
        self.title = title  # 视频标题
        self.file_path = file_path
        self.tags = tags
        self.publish_date = publish_date
        self.account_file = account_file
        self.date_format = '%Y年%m月%d日 %H:%M'
        self.local_executable_path = LOCAL_CHROME_PATH
        self.thumbnail_path = thumbnail_path
        self.proxy = proxy

    async def set_schedule_time_xiaohongshu(self, page, publish_date):
        print("  [-] 正在设置定时发布时间...")
        print(f"publish_date: {publish_date}")

        # 使用文本内容定位元素
        # element = await page.wait_for_selector(
        #     'label:has-text("定时发布")',
        #     timeout=5000  # 5秒超时时间
        # )
        # await element.click()

        # # 选择包含特定文本内容的 label 元素
        label_element = page.locator("label:has-text('定时发布')")
        # # 在选中的 label 元素下点击 checkbox
        await label_element.click()
        await asyncio.sleep(1)
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")
        print(f"publish_date_hour: {publish_date_hour}")

        await asyncio.sleep(1)
        await page.locator('.el-input__inner[placeholder="选择日期和时间"]').click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")

        await asyncio.sleep(1)

    async def handle_upload_error(self, page):
        xiaohongshu_logger.info('视频出错了，重新上传中')
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
            xiaohongshu_logger.info(f"Using Proxy: {self.proxy.get('server')}")

        browser = await playwright.chromium.launch(**launch_kwargs)
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(
            **build_context_options(
                viewport={"width": 1600, "height": 900},
                storage_state=f"{self.account_file}"
            )
        )
        context = await set_init_script(context)

        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video")
        await dismiss_xhs_tour(page)
        xiaohongshu_logger.info(f'[+]正在上传-------{self.title}.mp4')
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        xiaohongshu_logger.info(f'[-] 正在打开主页...')
        await page.wait_for_url("https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video")
        # 点击 "上传视频" 按钮
        await page.locator("div[class^='upload-content'] input[class='upload-input']").set_input_files(self.file_path)

        # 等待页面跳转到指定的 URL 2025.01.08修改在原有基础上兼容两种页面
        while True:
            try:
                # 等待upload-input元素出现
                upload_input = await page.wait_for_selector('input.upload-input', timeout=3000)
                # 获取下一个兄弟元素
                preview_new = await upload_input.query_selector(
                    'xpath=following-sibling::div[contains(@class, "preview-new")]')
                if preview_new:
                    # 在preview-new元素中查找包含"上传成功"的stage元素
                    stage_elements = await preview_new.query_selector_all('div.stage')
                    upload_success = False
                    for stage in stage_elements:
                        text_content = await page.evaluate('(element) => element.textContent', stage)
                        if '上传成功' in text_content:
                            upload_success = True
                            break
                    if upload_success:
                        xiaohongshu_logger.info("[+] 检测到上传成功标识!")
                        break  # 成功检测到上传成功后跳出循环
                    else:
                        print("  [-] 未找到上传成功标识，继续等待...")
                else:
                    print("  [-] 未找到预览元素，继续等待...")
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"  [-] 检测过程出错: {str(e)}，重新尝试...")
                await asyncio.sleep(0.5)  # 等待0.5秒后重新尝试

        # 填充标题和话题
        # 检查是否存在包含输入框的元素
        # 这里为了避免页面变化，故使用相对位置定位：作品标题父级右侧第一个元素的input子元素
        await asyncio.sleep(1)
        xiaohongshu_logger.info(f'  [-] 正在填充标题和话题...')

        # 尝试多种标题输入框定位方式
        title_filled = False
        title_selectors = [
            'div.plugin.title-container input.d-text',
            'input[placeholder*="填写标题"]',
            'input[placeholder*="请输入标题"]',
            '.title-container input',
            '.c-input_inner',
        ]

        for selector in title_selectors:
            try:
                title_container = page.locator(selector).first
                if await title_container.count() > 0 and await title_container.is_visible():
                    await title_container.fill(self.title[:30])
                    xiaohongshu_logger.info(f'  [+] 使用选择器 {selector} 成功填充标题')
                    title_filled = True
                    break
            except Exception as e:
                xiaohongshu_logger.debug(f'  [-] 选择器 {selector} 失败: {str(e)}')
                continue

        if not title_filled:
            xiaohongshu_logger.warning('  [-] 所有标题选择器失败，尝试备用方案')
            try:
                titlecontainer = page.locator(".notranslate").first
                await titlecontainer.click()
                await page.keyboard.press("Control+KeyA")
                await page.keyboard.press("Delete")
                await page.keyboard.type(self.title[:30])
                await page.keyboard.press("Enter")
                xiaohongshu_logger.info('  [+] 使用备用方案成功填充标题')
            except Exception as e:
                xiaohongshu_logger.error(f'  [-] 标题填充完全失败: {str(e)}')

        # 填写内容和标签 - 尝试多种定位方式
        await asyncio.sleep(1)
        content_filled = False
        content_selectors = [
            ".ql-editor",
            "div[contenteditable='true']",
            ".publish-editor .ql-editor",
            "div.ql-container .ql-editor",
            "[data-placeholder]",
        ]

        for selector in content_selectors:
            try:
                content_box = page.locator(selector).first
                if await content_box.count() > 0 and await content_box.is_visible():
                    # 点击激活编辑器
                    await content_box.click()
                    await asyncio.sleep(0.3)

                    # 填写标签 - 小红书标签流程：
                    # 1. 输入 #标签 → 触发 API 获取推荐
                    # 2. 等待下拉列表出现 (.suggestion)
                    # 3. 按 Enter 选中 → 转换为 <a class="tiptap-topic">
                    for index, tag in enumerate(self.tags, start=1):
                        xiaohongshu_logger.info(f'  [-] 正在添加标签 {index}/{len(self.tags)}: #{tag}')

                        # 输入标签
                        await page.type(selector, "#" + tag)
                        await asyncio.sleep(0.3)

                        # 等待下拉列表出现（小红书会请求 API 获取推荐标签）
                        try:
                            # 等待建议列表出现
                            await page.wait_for_selector('.suggestion, [class*="suggestion"], [data-decoration-id]', timeout=2000, state='visible')
                            await asyncio.sleep(0.2)
                            xiaohongshu_logger.debug(f'  [+] 标签 #{tag} 的推荐列表已出现')
                        except Exception as e:
                            xiaohongshu_logger.warning(f'  [!] 标签 #{tag} 未找到推荐列表，直接确认: {str(e)[:50]}')

                        # 按 Enter 选择第一个推荐项（将 <span class="suggestion"> 转换为 <a class="tiptap-topic">）
                        await page.press(selector, "Enter")
                        await asyncio.sleep(0.3)

                        # 验证标签是否成功转换为链接
                        try:
                            topic_link = await page.locator('a.tiptap-topic').count()
                            if topic_link >= index:
                                xiaohongshu_logger.success(f'  [✓] 标签 #{tag} 已成功转换为话题链接')
                            else:
                                xiaohongshu_logger.warning(f'  [!] 标签 #{tag} 可能未正确转换')
                        except Exception:
                            pass

                    xiaohongshu_logger.info(f'  [+] 使用选择器 {selector} 成功添加{len(self.tags)}个话题')
                    content_filled = True
                    break
            except Exception as e:
                xiaohongshu_logger.debug(f'  [-] 内容选择器 {selector} 失败: {str(e)}')
                continue

        if not content_filled:
            xiaohongshu_logger.error('  [-] 所有内容选择器失败，标签未能添加')

        # while True:
        #     # 判断重新上传按钮是否存在，如果不存在，代表视频正在上传，则等待
        #     try:
        #         #  新版：定位重新上传
        #         number = await page.locator('[class^="long-card"] div:has-text("重新上传")').count()
        #         if number > 0:
        #             xiaohongshu_logger.success("  [-]视频上传完毕")
        #             break
        #         else:
        #             xiaohongshu_logger.info("  [-] 正在上传视频中...")
        #             await asyncio.sleep(2)

        #             if await page.locator('div.progress-div > div:has-text("上传失败")').count():
        #                 xiaohongshu_logger.error("  [-] 发现上传出错了... 准备重试")
        #                 await self.handle_upload_error(page)
        #     except:
        #         xiaohongshu_logger.info("  [-] 正在上传视频中...")
        #         await asyncio.sleep(2)
        
        # 上传视频封面
        await self.set_thumbnail(page, self.thumbnail_path)

        # 更换可见元素
        # await self.set_location(page, "青岛市")

        # # 頭條/西瓜
        # third_part_element = '[class^="info"] > [class^="first-part"] div div.semi-switch'
        # # 定位是否有第三方平台
        # if await page.locator(third_part_element).count():
        #     # 检测是否是已选中状态
        #     if 'semi-switch-checked' not in await page.eval_on_selector(third_part_element, 'div => div.className'):
        #         await page.locator(third_part_element).locator('input.semi-switch-native-control').click()

        if self.publish_date != 0:
            await self.set_schedule_time_xiaohongshu(page, self.publish_date)

        # 判断视频是否发布成功
        xiaohongshu_logger.info("  [-] 准备点击发布按钮...")
        await asyncio.sleep(1)  # 减少延迟：2秒 → 1秒

        # 尝试多种发布按钮定位方式
        publish_clicked = False
        if self.publish_date != 0:
            publish_button_selectors = [
                'button:has-text("定时发布")',
                'button.publish-btn:has-text("定时发布")',
                '.publish-footer button:has-text("定时发布")',
                'button[type="button"]:has-text("定时发布")',
            ]
        else:
            publish_button_selectors = [
                'button:has-text("发布")',
                'button.publish-btn:has-text("发布")',
                '.publish-footer button:has-text("发布")',
                'button[type="button"]:has-text("发布")',
                '.footer-btn button:has-text("发布")',
            ]

        for selector in publish_button_selectors:
            try:
                publish_btn = page.locator(selector).first
                if await publish_btn.count() > 0 and await publish_btn.is_visible():
                    # 检查按钮是否可点击（未被禁用）
                    is_disabled = await publish_btn.is_disabled()
                    if not is_disabled:
                        xiaohongshu_logger.info(f'  [+] 找到发布按钮，选择器: {selector}')
                        await publish_btn.click()
                        publish_clicked = True
                        xiaohongshu_logger.info('  [+] 已点击发布按钮')
                        break
                    else:
                        xiaohongshu_logger.debug(f'  [-] 按钮存在但被禁用: {selector}')
            except Exception as e:
                xiaohongshu_logger.debug(f'  [-] 发布按钮选择器 {selector} 失败: {str(e)}')
                continue

        if not publish_clicked:
            xiaohongshu_logger.error('  [-] 所有发布按钮选择器失败，尝试截图保存当前页面状态')
            await page.screenshot(path='logs/xhs_publish_fail.png', full_page=True)

        # 等待发布成功跳转
        while True:
            try:
                await page.wait_for_url(
                    "https://creator.xiaohongshu.com/publish/success?**",
                    timeout=3000
                )  # 如果自动跳转到作品页面，则代表发布成功
                xiaohongshu_logger.success("  [-]视频发布成功")
                break
            except:
                xiaohongshu_logger.info("  [-] 等待发布完成中...")
                await asyncio.sleep(0.5)

        await context.storage_state(path=self.account_file)  # 保存cookie
        xiaohongshu_logger.success('  [-]cookie更新完毕！')
        await asyncio.sleep(0.5)  # 减少延迟：2秒 → 0.5秒
        # 关闭浏览器上下文和浏览器实例
        await context.close()
        await browser.close()

    async def set_thumbnail(self, page: Page, thumbnail_path: str):
        if thumbnail_path:
            await page.click('text="选择封面"')
            await page.wait_for_selector("div.semi-modal-content:visible")
            await page.click('text="设置竖封面"')
            await page.wait_for_timeout(1000)  # 减少延迟：2秒 → 1秒
            # 定位到上传区域并点击
            await page.locator("div[class^='semi-upload upload'] >> input.semi-upload-hidden-input").set_input_files(thumbnail_path)
            await page.wait_for_timeout(1000)  # 减少延迟：2秒 → 1秒
            await page.locator("div[class^='extractFooter'] button:visible:has-text('完成')").click()
            # finish_confirm_element = page.locator("div[class^='confirmBtn'] >> div:has-text('完成')")
            # if await finish_confirm_element.count():
            #     await finish_confirm_element.click()
            # await page.locator("div[class^='footer'] button:has-text('完成')").click()

    async def set_location(self, page: Page, location: str = "青岛市"):
        print(f"开始设置位置: {location}")
        
        # 点击地点输入框
        print("等待地点输入框加载...")
        loc_ele = await page.wait_for_selector('div.d-text.d-select-placeholder.d-text-ellipsis.d-text-nowrap')
        print(f"已定位到地点输入框: {loc_ele}")
        await loc_ele.click()
        print("点击地点输入框完成")
        
        # 输入位置名称
        print(f"等待1秒后输入位置名称: {location}")
        await page.wait_for_timeout(1000)
        await page.keyboard.type(location)
        print(f"位置名称输入完成: {location}")

        # 等待下拉列表加载
        print("等待下拉列表加载...")
        dropdown_selector = 'div.d-popover.d-popover-default.d-dropdown.--size-min-width-large'
        await page.wait_for_timeout(1000)  # 减少延迟：3秒 → 1秒
        try:
            await page.wait_for_selector(dropdown_selector, timeout=3000)
            print("下拉列表已加载")
        except:
            print("下拉列表未按预期显示，可能结构已变化")

        # 增加等待时间以确保内容加载完成
        print("额外等待0.5秒确保内容渲染完成...")
        await page.wait_for_timeout(500)  # 减少延迟：1秒 → 0.5秒

        # 尝试更灵活的XPath选择器
        print("尝试使用更灵活的XPath选择器...")
        flexible_xpath = (
            f'//div[contains(@class, "d-popover") and contains(@class, "d-dropdown")]'
            f'//div[contains(@class, "d-options-wrapper")]'
            f'//div[contains(@class, "d-grid") and contains(@class, "d-options")]'
            f'//div[contains(@class, "name") and text()="{location}"]'
        )
        await page.wait_for_timeout(500)  # 减少延迟：3秒 → 0.5秒
        
        # 尝试定位元素
        print(f"尝试定位包含'{location}'的选项...")
        try:
            # 先尝试使用更灵活的选择器
            location_option = await page.wait_for_selector(
                flexible_xpath,
                timeout=3000
            )
            
            if location_option:
                print(f"使用灵活选择器定位成功: {location_option}")
            else:
                # 如果灵活选择器失败，再尝试原选择器
                print("灵活选择器未找到元素，尝试原始选择器...")
                location_option = await page.wait_for_selector(
                    f'//div[contains(@class, "d-popover") and contains(@class, "d-dropdown")]'
                    f'//div[contains(@class, "d-options-wrapper")]'
                    f'//div[contains(@class, "d-grid") and contains(@class, "d-options")]'
                    f'/div[1]//div[contains(@class, "name") and text()="{location}"]',
                    timeout=2000
                )
            
            # 滚动到元素并点击
            print("滚动到目标选项...")
            await location_option.scroll_into_view_if_needed()
            print("元素已滚动到视图内")
            
            # 增加元素可见性检查
            is_visible = await location_option.is_visible()
            print(f"目标选项是否可见: {is_visible}")
            
            # 点击元素
            print("准备点击目标选项...")
            await location_option.click()
            print(f"成功选择位置: {location}")
            return True
            
        except Exception as e:
            print(f"定位位置失败: {e}")
            
            # 打印更多调试信息
            print("尝试获取下拉列表中的所有选项...")
            try:
                all_options = await page.query_selector_all(
                    '//div[contains(@class, "d-popover") and contains(@class, "d-dropdown")]'
                    '//div[contains(@class, "d-options-wrapper")]'
                    '//div[contains(@class, "d-grid") and contains(@class, "d-options")]'
                    '/div'
                )
                print(f"找到 {len(all_options)} 个选项")
                
                # 打印前3个选项的文本内容
                for i, option in enumerate(all_options[:3]):
                    option_text = await option.inner_text()
                    print(f"选项 {i+1}: {option_text.strip()[:50]}...")
                    
            except Exception as e:
                print(f"获取选项列表失败: {e}")
                
            # 截图保存（取消注释使用）
            # await page.screenshot(path=f"location_error_{location}.png")
            return False

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
