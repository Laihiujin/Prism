#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试抖音封面设置 - 使用 Selenium + Playwright 双引擎
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from automation.selenium_dom import new_chrome_driver, capture_debug_bundle
from myUtils.cookie_manager import cookie_manager
from utils.base_social_media import set_init_script, HEADLESS_FLAG
from myUtils.browser_context import build_context_options
from platforms.path_utils import resolve_cookie_file
from loguru import logger
import time


async def debug_cover_with_selenium(page, platform="douyin"):
    """使用 Selenium 抓取封面弹窗的详细信息"""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By

        logger.info("[Selenium] 启动 Chrome 驱动...")
        driver = new_chrome_driver(headless=False)

        # 获取当前页面 URL 和 cookies
        url = page.url
        cookies = await page.context.cookies()

        # 导航到同一页面
        driver.get(url)

        # 添加 cookies
        for c in cookies:
            try:
                driver.add_cookie({
                    "name": c.get("name"),
                    "value": c.get("value"),
                    "domain": c.get("domain"),
                    "path": c.get("path") or "/",
                })
            except Exception:
                continue

        # 刷新页面
        driver.get(url)
        time.sleep(3)

        # 抓取所有可能的封面相关元素
        logger.info("[Selenium] 查找封面相关元素...")

        # 1. 查找所有包含"封面"文字的元素
        elements = driver.find_elements(By.XPATH, "//*[contains(text(), '封面')]")
        logger.info(f"[Selenium] 找到 {len(elements)} 个包含'封面'文字的元素")

        for idx, elem in enumerate(elements):
            try:
                tag = elem.tag_name
                text = elem.text
                classes = elem.get_attribute("class")
                xpath = driver.execute_script("""
                    function getXPath(element) {
                        if (element.id !== '')
                            return '//*[@id="' + element.id + '"]';
                        if (element === document.body)
                            return '/html/body';

                        var ix = 0;
                        var siblings = element.parentNode.childNodes;
                        for (var i = 0; i < siblings.length; i++) {
                            var sibling = siblings[i];
                            if (sibling === element)
                                return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                            if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                                ix++;
                        }
                    }
                    return getXPath(arguments[0]);
                """, elem)

                logger.info(f"  [{idx}] <{tag}> class='{classes}' text='{text[:50]}...'")
                logger.info(f"       XPath: {xpath}")
            except Exception as e:
                logger.error(f"  [{idx}] 获取元素信息失败: {e}")

        # 2. 查找所有 modal/dialog 元素
        logger.info("[Selenium] 查找所有弹窗元素...")
        modals = driver.find_elements(By.CSS_SELECTOR, "[class*='modal'], [class*='dialog'], [class*='portal'], [role='dialog']")
        logger.info(f"[Selenium] 找到 {len(modals)} 个弹窗元素")

        for idx, modal in enumerate(modals):
            try:
                classes = modal.get_attribute("class")
                is_visible = modal.is_displayed()
                logger.info(f"  [{idx}] class='{classes}' visible={is_visible}")
            except:
                pass

        # 3. 保存调试信息
        logger.info("[Selenium] 保存调试截图和 HTML...")
        result = capture_debug_bundle(
            driver,
            out_dir=str(Path(__file__).parent.parent / "logs"),
            prefix="douyin_cover_debug",
            run_ocr=False
        )

        logger.info(f"[Selenium] 调试文件已保存:")
        logger.info(f"  HTML: {result.html_path}")
        logger.info(f"  截图: {result.screenshot_path}")

        return result

    finally:
        try:
            driver.quit()
        except:
            pass


async def debug_cover_with_playwright(page):
    """使用 Playwright 的 evaluate 获取封面元素信息"""
    logger.info("[Playwright] 使用 page.evaluate() 获取元素信息...")

    # 执行 JavaScript 获取所有封面相关元素
    elements_info = await page.evaluate("""
        () => {
            const results = [];

            // 1. 查找所有包含"封面"文字的元素
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT
            );

            while (walker.nextNode()) {
                const node = walker.currentNode;
                if (node.nodeType === Node.TEXT_NODE && node.textContent.includes('封面')) {
                    const element = node.parentElement;
                    results.push({
                        type: 'text',
                        tag: element.tagName,
                        text: node.textContent.trim(),
                        className: element.className,
                        id: element.id,
                        visible: element.offsetParent !== null
                    });
                }
            }

            // 2. 查找所有 modal/dialog
            const modals = document.querySelectorAll('[class*="modal"], [class*="dialog"], [class*="portal"], [role="dialog"]');
            modals.forEach(modal => {
                results.push({
                    type: 'modal',
                    tag: modal.tagName,
                    className: modal.className,
                    id: modal.id,
                    visible: modal.offsetParent !== null,
                    display: window.getComputedStyle(modal).display,
                    visibility: window.getComputedStyle(modal).visibility
                });
            });

            return results;
        }
    """)

    logger.info(f"[Playwright] 找到 {len(elements_info)} 个相关元素:")
    for idx, elem in enumerate(elements_info):
        logger.info(f"  [{idx}] {elem}")

    return elements_info


async def main():
    """主调试流程"""
    logger.info("="*60)
    logger.info("抖音封面设置调试工具")
    logger.info("="*60)

    # 获取账号
    accounts = cookie_manager.list_flat_accounts()
    douyin_accounts = [a for a in accounts if a['platform'] == 'douyin' and a['status'] == 'valid']

    if not douyin_accounts:
        logger.error("没有可用的抖音账号")
        return

    account = douyin_accounts[0]
    account_file = resolve_cookie_file(account['cookie_file'])

    logger.info(f"使用账号: {account['name']}")

    async with async_playwright() as playwright:
        # 启动浏览器
        browser = await playwright.chromium.launch(headless=HEADLESS_FLAG)
        context = await browser.new_context(**build_context_options(storage_state=account_file))
        context = await set_init_script(context)
        page = await context.new_page()

        # 访问上传页面
        upload_url = "https://creator.douyin.com/creator-micro/content/upload"
        logger.info(f"访问上传页面: {upload_url}")
        await page.goto(upload_url, wait_until="domcontentloaded", timeout=60000)

        # 等待页面加载
        await page.wait_for_timeout(3000)

        logger.info("请在浏览器中手动点击'选择封面'按钮...")
        logger.info("然后按 Enter 继续调试...")
        input("按 Enter 继续...")

        # 使用 Playwright evaluate 调试
        logger.info("\n" + "="*60)
        logger.info("1. Playwright evaluate 调试")
        logger.info("="*60)
        await debug_cover_with_playwright(page)

        # 使用 Selenium 调试
        logger.info("\n" + "="*60)
        logger.info("2. Selenium 调试")
        logger.info("="*60)
        result = await debug_cover_with_selenium(page, "douyin")

        logger.info("\n" + "="*60)
        logger.info("调试完成！")
        logger.info("="*60)
        logger.info(f"请查看以下文件获取详细信息:")
        logger.info(f"  HTML: {result.html_path}")
        logger.info(f"  截图: {result.screenshot_path}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
