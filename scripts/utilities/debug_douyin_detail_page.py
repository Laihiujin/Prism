"""
抖音详情页结构诊断脚本
"""
import asyncio
import sys
import os
from pathlib import Path

if sys.platform == "win32":
    os.system("chcp 65001 >nul")
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "syn_backend"))

from playwright.async_api import async_playwright

async def main():
    print("=" * 60)
    print("抖音详情页结构诊断")
    print("=" * 60)

    from myUtils.cookie_manager import cookie_manager
    from fastapi_app.core.config import settings

    # 获取第一个抖音账号
    accounts = cookie_manager.list_flat_accounts()
    douyin_accounts = [
        acc for acc in accounts
        if acc.get("platform") == "douyin" and acc.get("status") == "valid"
    ]

    if not douyin_accounts:
        print("❌ 未找到有效的抖音账号")
        return

    test_account = douyin_accounts[0]
    cookie_file = test_account.get('cookie_file')
    cookie_path = Path(__file__).parent.parent.parent / "syn_backend" / "cookiesFile" / cookie_file

    print(f"\n使用账号: {test_account.get('name')}")
    print(f"Cookie文件: {cookie_path}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # 非headless模式以便观察
        context = await browser.new_context(
            storage_state=str(cookie_path),
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
        )
        page = await context.new_page()

        try:
            # 访问内容管理页
            print("\n[1/3] 访问内容管理页...")
            await page.goto("https://creator.douyin.com/creator-micro/content/manage", timeout=45000)
            await page.wait_for_load_state("networkidle")

            # 等待视频卡片出现
            print("[2/3] 等待视频卡片...")
            await page.wait_for_selector("div[class*='video-card-info']", timeout=30000)

            # 点击第一个视频
            print("[3/3] 点击第一个视频进入详情页...")
            first_card = page.locator("div[class*='video-card-info']").first
            await first_card.click()
            await page.wait_for_timeout(3000)  # 等待详情页加载

            # 检查是否是新标签页
            detail_page = page
            if len(context.pages) > 1:
                detail_page = context.pages[-1]
                print("✅ 详情页在新标签页中打开")
            else:
                print("✅ 详情页在同一标签页中打开")

            await detail_page.wait_for_load_state("domcontentloaded")
            print(f"\n当前 URL: {detail_page.url}")

            # 保存页面截图
            screenshot_path = Path(__file__).parent / "logs" / "douyin_detail_debug.png"
            screenshot_path.parent.mkdir(exist_ok=True)
            await detail_page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"✅ 截图已保存: {screenshot_path}")

            # 保存页面 HTML
            html_path = Path(__file__).parent / "logs" / "douyin_detail_debug.html"
            html_content = await detail_page.content()
            html_path.write_text(html_content, encoding='utf-8')
            print(f"✅ HTML已保存: {html_path}")

            # 尝试多个选择器查找标题
            print("\n" + "=" * 60)
            print("测试标题选择器:")
            print("=" * 60)

            title_selectors = [
                ("textarea[placeholder*='添加标题']", "input_value"),
                ("input[placeholder*='标题']", "input_value"),
                (".title-input", "text"),
                ("[class*='title-input']", "text"),
                ("h1", "text"),
                (".video-title", "text"),
                ("[class*='video-title']", "text"),
                ("[class*='work-title']", "text"),
                ("textarea", "input_value"),
                ("input[type='text']", "input_value"),
            ]

            for selector, get_type in title_selectors:
                try:
                    loc = detail_page.locator(selector).first
                    count = await loc.count()
                    if count > 0:
                        if get_type == "input_value":
                            value = await loc.input_value()
                        else:
                            value = await loc.inner_text()

                        if value and value.strip():
                            print(f"✅ {selector:45s} => '{value.strip()[:40]}'")
                        else:
                            print(f"⚠️  {selector:45s} => (空值)")
                    else:
                        print(f"❌ {selector:45s} => 未找到")
                except Exception as e:
                    print(f"❌ {selector:45s} => 错误: {e}")

            # 尝试多个选择器查找数据
            print("\n" + "=" * 60)
            print("测试数据选择器:")
            print("=" * 60)

            stat_selectors = [
                "[class*='data-card']",
                "[class*='work-data']",
                "[class*='data-item']",
                ".data-list",
                "[class*='stat']",
                "[class*='count']",
                "[class*='number']"
            ]

            for selector in stat_selectors:
                try:
                    items = await detail_page.locator(selector).all()
                    if items:
                        print(f"\n✅ {selector} => 找到 {len(items)} 个元素")
                        for i, item in enumerate(items[:3]):  # 只显示前3个
                            text = await item.inner_text()
                            print(f"   [{i}] {text[:60]}")
                    else:
                        print(f"❌ {selector} => 未找到")
                except Exception as e:
                    print(f"❌ {selector} => 错误: {e}")

            print("\n暂停 30 秒以便手动检查页面...")
            await page.wait_for_timeout(30000)

        finally:
            await browser.close()

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main())
