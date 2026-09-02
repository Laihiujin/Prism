# -*- coding: utf-8 -*-
"""聚焦验证 set_hotspot：登录→上传→填表→只调 set_hotspot。"""
import asyncio, sys
from pathlib import Path
BASE = Path("/Users/laihiujin/Documents/siuyechu/Prism/prism_backend")
sys.path.insert(0, str(BASE))
from uploader.douyin_uploader.main_refactored import DouYinVideo


async def main():
    app = DouYinVideo(
        title="自动化验证 热点",
        file_path=str(BASE / "videoFile" / "60d455f2-8501-4488-bedc-3b58bc8767db.MP4"),
        tags=[],
        publish_date=0,
        account_file=str(BASE / "cookiesFile" / "douyin_Siuyechu_.json"),
        desc="仅验证热点",
        publish_strategy="immediate",
        debug=False,
        headless=False,
        preview_only=True,
    )
    # 手动构造 page：复用 upload() 的前半段较重，改用直接 playright+branch
    from patchright.async_api import async_playwright
    from utils.base_social_media import set_init_script
    from config.conf import LOCAL_CHROME_PATH
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
        ok = await app.set_hotspot(page, "热点")
        print("HOTSPOT ok =", ok, flush=True)
        await b.close()

asyncio.run(main())
