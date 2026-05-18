import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

async def run():
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"

    print("环境变量 PLAYWRIGHT_HEADLESS =", os.getenv("PLAYWRIGHT_HEADLESS"))
    print("最终 headless =", headless)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        await page.goto("https://www.baidu.com")
        await page.screenshot(path="test.png")
        print("截图完成 → test.png")
        await browser.close()

import asyncio
asyncio.run(run())
