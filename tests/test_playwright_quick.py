"""
快速测试新Python 3.11环境下的Playwright
"""
import asyncio
import sys
import io

# 修复Windows GBK编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from playwright.async_api import async_playwright


async def test_playwright():
    print("测试Playwright (Python 3.11环境)...")

    async with async_playwright() as p:
        print("OK Playwright启动成功")

        browser = await p.chromium.launch(headless=True)
        print("OK Chromium浏览器启动成功")

        page = await browser.new_page()
        await page.goto("https://www.baidu.com")
        print(f"OK 页面访问成功: {await page.title()}")

        await browser.close()
        print("OK 测试完成！")


if __name__ == "__main__":
    asyncio.run(test_playwright())
