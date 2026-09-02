# -*- coding: utf-8 -*-
"""交互式观测 pass 2：打开 挂载内容/合集/关联热点/封面 的下拉与弹窗，dump 真实选项 DOM。仅观测，不发布。"""
import asyncio, sys
from pathlib import Path

BASE = Path("/Users/laihiujin/Documents/siuyechu/Prism/prism_backend")
OUT = BASE / "_edu_obs"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(BASE))
from patchright.async_api import async_playwright
from utils.base_social_media import set_init_script

ACCOUNT = BASE / "cookiesFile" / "douyin_Siuyechu_.json"
VIDEO = BASE / "videoFile" / "60d455f2-8501-4488-bedc-3b58bc8767db.MP4"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


async def dump_options(page, tag, save_name):
    """dump 当前打开的 role=option 列表 + 容器片段"""
    opts = page.locator('[role="option"], [class*="select-dropdown-option"], .semi-select-option')
    n = await opts.count()
    texts = []
    for i in range(min(n, 40)):
        try:
            texts.append((await opts.nth(i).inner_text()).strip())
        except Exception:
            pass
    html = await page.content()
    (OUT / f"{save_name}.html").write_text(html, encoding="utf-8")
    print(f"[{tag}] option count={n}")
    print(f"[{tag}] option texts = {texts}")
    try:
        await page.screenshot(path=str(OUT / f"{save_name}.png"), full_page=True)
    except Exception:
        pass
    return n


async def close_popup(page):
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(600)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, headless=False,
                                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx = await b.new_context(storage_state=str(ACCOUNT), permissions=["geolocation"])
        ctx = await set_init_script(ctx)
        page = await ctx.new_page()
        await page.goto("https://creator.douyin.com/creator-micro/content/upload",
                        wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_selector("div[class^='container'] input", state="attached", timeout=60000)
        await page.locator("div[class^='container'] input").set_input_files(str(VIDEO))
        for _ in range(120):
            if "content/publish" in page.url or "post/video" in page.url:
                break
            await asyncio.sleep(0.5)
        await page.locator('input[placeholder*="填写作品标题"]').first.wait_for(state="visible", timeout=120000)
        await page.wait_for_timeout(3000)

        # --- 1) 添加标签 => 挂载内容 select (current '位置') ---
        anchor_sel = page.locator("div.anchor-container-hgj7gj div.semi-select").first
        print("添加标签 select count:", await anchor_sel.count())
        if await anchor_sel.count():
            await anchor_sel.click()
            await page.wait_for_timeout(1200)
            await dump_options(page, "anchor/挂载内容", "obs_anchor_options")

        # --- 2) 合集 select (select-collection-nkL6sA, placeholder 请选择合集) ---
        coll_sel = page.locator("div.select-collection-nkL6sA").first
        print("合集 select count:", await coll_sel.count())
        if await coll_sel.count():
            await coll_sel.click()
            await page.wait_for_timeout(1200)
            await dump_options(page, "collection", "obs_collection_options")

        # --- 3) 关联热点 filterable select ---
        hot = page.locator("div.semi-select-single.semi-select-filterable").first
        print("热点 select count:", await hot.count())
        if await hot.count():
            await hot.click()
            await page.wait_for_timeout(600)
            inp = page.locator("div.semi-select-single.semi-select-filterable input").first
            if await inp.count():
                await inp.fill("热点")
                await page.wait_for_timeout(1500)
                await dump_options(page, "hotspot", "obs_hotspot_options")

        # --- 4) 封面：点「选择封面」打开封面弹窗 ---
        await close_popup(page)
        try:
            await page.get_by_text("选择封面", exact=True).first.click(force=True)
        except Exception as e:
            print("封面点不动:", e)
        await page.wait_for_timeout(2500)
        modal = page.locator("div.dy-creator-content-modal").first
        print("封面 modal count:", await modal.count())
        if await modal.count() > 0:
            html = await page.content()
            (OUT / "obs_cover_modal.html").write_text(html, encoding="utf-8")
            await page.screenshot(path=str(OUT / "obs_cover_modal.png"), full_page=True)
            # 列出每个隐藏 file input 及其 accept
            fis = page.locator("input.semi-upload-hidden-input")
            print("封面 modal hidden file inputs:", await fis.count())
            for i in range(await fis.count()):
                acc = await fis.nth(i).get_attribute("accept")
                print(f"  file input[{i}]: accept={acc}")
            # 小按钮文字
            for t in ["上传封面", "设置横封面", "设置竖封面", "AI生成", "完成", "暂不设置"]:
                c = await modal.get_by_text(t, exact=False).count()
                if c:
                    print(f"  封面按钮文本[{t}] count={c}")

        print("DONE")
        await b.close()


asyncio.run(main())
