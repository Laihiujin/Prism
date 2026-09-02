# -*- coding: utf-8 -*-
"""临时观测脚本：用真实登录账号 + 系统 Chrome 打开抖音发布页，dump DOM。仅观测，不发布。"""
import asyncio, os, sys, json
from pathlib import Path

BASE = Path("/Users/laihiujin/Documents/siuyechu/Prism/prism_backend")
OUT = BASE / "_edu_obs"
OUT.mkdir(exist_ok=True)

from patchright.async_api import async_playwright
import sys
sys.path.insert(0, str(BASE))
from utils.base_social_media import set_init_script

ACCOUNT = BASE / "cookiesFile" / "douyin_Siuyechu_.json"
VIDEO = BASE / "videoFile" / "60d455f2-8501-4488-bedc-3b58bc8767db.MP4"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(
            executable_path=CHROME,
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = await b.new_context(
            storage_state=str(ACCOUNT),
            permissions=["geolocation"],
        )
        ctx = await set_init_script(ctx)
        page = await ctx.new_page()
        await page.goto("https://creator.douyin.com/creator-micro/content/upload",
                       wait_until="domcontentloaded", timeout=90000)
        print("URL after goto:", page.url)

        # detect login page
        login = await page.get_by_text("扫码登录", exact=True).count() + await page.get_by_text("手机号登录", exact=True).count()
        print("login markers count:", login)
        if login:
            (OUT / "LOGIN_PAGE.html").write_text(await page.content(), encoding="utf-8")
            await page.screenshot(path=str(OUT / "LOGIN_PAGE.png"), full_page=True)
            await b.close()
            return

        # upload test video
        await page.wait_for_selector("div[class^='container'] input", state="attached", timeout=60000)
        await page.locator("div[class^='container'] input").set_input_files(str(VIDEO))
        print("video set_input_files done")

        # wait for publish form
        for _ in range(120):
            if "content/publish" in page.url or "post/video" in page.url:
                break
            await asyncio.sleep(0.5)
        print("publish form URL:", page.url)

        # wait for title input (form rendered)
        try:
            await page.locator('input[placeholder*="填写作品标题"]').first.wait_for(state="visible", timeout=120000)
            print("title input visible -> form ready")
        except Exception as e:
            print("title input NOT visible:", e)

        await page.wait_for_timeout(4000)
        html = await page.content()
        (OUT / "PUBLISH_PAGE.html").write_text(html, encoding="utf-8")
        await page.screenshot(path=str(OUT / "PUBLISH_PAGE_full.png"), full_page=True)
        await page.screenshot(path=str(OUT / "PUBLISH_PAGE_top.png"))

        # dump some AX/console info
        print("== page url ==", page.url)
        print("== title placeholder count ==",
              await page.locator('input[placeholder*="填写作品标题"]').count())
        # list candidate text labels present on the page (interactive controls)
        for label in ["选择封面", "添加位置", "添加标签", "添加到合集", "添加声明",
                      "请选择自主声明", "关联热点", "谁可以看", "保存权限",
                      "允许他人保存", "公开", "好友可见", "仅自己可见", "定时发布",
                      "立即发布", "购物车", "发布图文"]:
            c = await page.get_by_text(label, exact=False).count()
            if c:
                print(f"TEXT[{label}] count={c}")

        await b.close()
        print("DONE")


asyncio.run(main())
