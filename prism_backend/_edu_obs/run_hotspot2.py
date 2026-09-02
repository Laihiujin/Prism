# -*- coding: utf-8 -*-
"""诊断 set_hotspot：打印相关 select 的占位/文本、点击后 input 数量、选项数量。"""
import asyncio, sys
from pathlib import Path
BASE = Path("/Users/laihiujin/Documents/siuyechu/Prism/prism_backend")
sys.path.insert(0, str(BASE))
from patchright.async_api import async_playwright
from utils.base_social_media import set_init_script
from config.conf import LOCAL_CHROME_PATH


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=LOCAL_CHROME_PATH, headless=False,
                                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx = await b.new_context(storage_state=str(BASE / "cookiesFile/douyin_Siuyechu_.json"), permissions=["geolocation"])
        ctx = await set_init_script(ctx)
        page = await ctx.new_page()
        await page.goto("https://creator.douyin.com/creator-micro/content/upload", wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_selector("div[class^='container'] input", state="attached", timeout=60000)
        await page.locator("div[class^='container'] input").set_input_files(str(BASE / "videoFile/60d455f2-8501-4488-bedc-3b58bc8767db.MP4"))
        for _ in range(120):
            if "post/video" in page.url or "content/publish" in page.url:
                break
            await asyncio.sleep(0.5)
        await page.locator('input[placeholder*="填写作品标题"]').first.wait_for(state="visible", timeout=120000)
        await page.wait_for_timeout(3000)

        # 列出所有 semi-select 及其文本
        sels = page.locator("div.semi-select")
        n = await sels.count()
        print(f"total semi-select: {n}")
        for i in range(n):
            try:
                txt = (await sels.nth(i).inner_text()).strip().replace("\n", " | ")
            except Exception:
                txt = "<err>"
            print(f"  select[{i}]: {txt[:60]!r}")

        # 热点 select（按占位过滤）
        hot = page.locator("div.semi-select").filter(has_text="点击输入热点词").first
        print("hotspot select count:", await hot.count())
        if await hot.count():
            await hot.click()
            await page.wait_for_timeout(800)
            inp_inside = hot.locator("input")
            print("hotspot .locator('input') count:", await inp_inside.count())
            # 全局 filterable input
            finp = page.locator("div.semi-select-single.semi-select-filterable input")
            print("global filterable input count:", await finp.count())
            for j in range(await finp.count()):
                ph = await finp.nth(j).get_attribute("placeholder")
                print(f"  filterable input[{j}] placeholder={ph!r}")
            # 尝试用全局第一个 filterable input 的 placeholder 判断该点哪个
            # 先看点击后出现的角色 option
            opts = page.locator('[role="option"], .semi-select-option')
            print("options after click(no input):", await opts.count())
            await b.close()

asyncio.run(main())
