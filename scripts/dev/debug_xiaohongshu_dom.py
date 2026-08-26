"""
调试脚本：分析小红书创作中心页面DOM结构
用于找出正确的账号信息选择器
"""
import asyncio
import json
import sys
from pathlib import Path
from patchright.async_api import async_playwright

# 设置stdout编码为utf-8
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

async def analyze_xiaohongshu_dom():
    """分析小红书创作中心页面的DOM结构"""

    # 读取小红书账号的Cookie文件
    cookie_file = Path("E:/Prism/cookiesFile/xiaohongshu_68c517584902993541365760aurlhgiuqjwr0rj4.json")

    if not cookie_file.exists():
        print(f"[ERROR] Cookie file not found: {cookie_file}")
        return

    with open(cookie_file, 'r', encoding='utf-8') as f:
        storage_state = json.load(f)

    print("🚀 启动 Playwright 浏览器...")

    async with async_playwright() as p:
        # 启动浏览器（非无头模式，方便观察）
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=storage_state)
        page = await context.new_page()

        print("📖 打开小红书创作中心...")
        await page.goto("https://creator.xiaohongshu.com/creator/home", wait_until="domcontentloaded")
        await asyncio.sleep(3)  # 等待页面完全加载

        print("\n🔍 分析页面DOM结构...\n")

        # 1. 尝试点击空白区域关闭弹窗
        print("1️⃣ 尝试点击空白区域关闭弹窗...")
        try:
            header_blank = await page.query_selector('#header-area > div > div > div:nth-child(1) > div')
            if header_blank:
                await header_blank.click()
                await asyncio.sleep(0.5)
                print("   ✅ 成功点击空白区域")
            else:
                print("   ⚠️ 未找到空白区域元素")
        except Exception as e:
            print(f"   ❌ 点击失败: {e}")

        # 2. 截图保存
        screenshot_path = "E:/Prism/xiaohongshu_dom_debug.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"\n📸 页面截图已保存: {screenshot_path}")

        # 3. 尝试所有可能的选择器
        print("\n2️⃣ 测试各种选择器...\n")

        selectors = [
            '.others.description-text',
            '.description-text',
            'text=/小红书账号[:：]?\\s*[\\w_]+/',
            '.account-info',
            '.user-info',
            '[class*="description"]',
            '[class*="account"]',
        ]

        for selector in selectors:
            try:
                elem = await page.query_selector(selector)
                if elem:
                    text = await elem.inner_text()
                    html = await elem.inner_html()
                    print(f"✅ {selector}")
                    print(f"   文本: {text[:100]}")
                    print(f"   HTML: {html[:150]}...\n")
                else:
                    print(f"❌ {selector} - 未找到\n")
            except Exception as e:
                print(f"❌ {selector} - 错误: {e}\n")

        # 4. 提取所有包含"小红书账号"或"小红书号"的元素
        print("3️⃣ 搜索包含'小红书账号'或'小红书号'的所有元素...\n")

        all_text_elements = await page.query_selector_all('*')
        found_elements = []

        for elem in all_text_elements[:500]:  # 限制前500个元素
            try:
                text = await elem.inner_text()
                if text and ("小红书账号" in text or "小红书号" in text):
                    tag_name = await elem.evaluate("el => el.tagName")
                    class_name = await elem.get_attribute("class") or ""
                    found_elements.append({
                        'tag': tag_name,
                        'class': class_name,
                        'text': text[:100]
                    })
            except:
                continue

        if found_elements:
            print(f"找到 {len(found_elements)} 个包含'小红书账号'的元素：\n")
            for idx, elem_info in enumerate(found_elements[:10], 1):
                print(f"{idx}. <{elem_info['tag']} class=\"{elem_info['class']}\">")
                print(f"   {elem_info['text']}\n")
        else:
            print("❌ 未找到任何包含'小红书账号'的元素")

        # 5. 提取JS全局变量中的用户信息
        print("\n4️⃣ 检查JS全局变量中的用户信息...\n")

        js_user_info = await page.evaluate("""() => {
            const sources = {
                '__INITIAL_SSR_STATE__': window.__INITIAL_SSR_STATE__?.Main?.user,
                'userInfo': window.userInfo,
                '__INITIAL_STATE__': window.__INITIAL_STATE__?.user
            };
            return sources;
        }""")

        for source, data in js_user_info.items():
            if data:
                print(f"✅ {source}:")
                print(f"   {json.dumps(data, indent=2, ensure_ascii=False)[:300]}...\n")
            else:
                print(f"❌ {source}: null\n")

        # 6. 提取Cookie中的user_id
        print("5️⃣ 检查Cookie中的user_id...\n")

        cookies = await context.cookies()
        for cookie in cookies:
            if 'user' in cookie.get('name', '').lower() or cookie.get('name') == 'x-user-id-creator.xiaohongshu.com':
                print(f"Cookie: {cookie.get('name')}")
                print(f"Value: {cookie.get('value')}\n")

        print("\n⏸️ 浏览器将保持打开状态，按Enter键关闭...")
        input()

        await browser.close()

if __name__ == "__main__":
    asyncio.run(analyze_xiaohongshu_dom())
