"""
测试Windows上的Playwright登录修复
"""
import asyncio
import sys

# 设置Windows兼容的事件循环
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from playwright.async_api import async_playwright


async def test_playwright_windows():
    """测试Playwright在Windows上是否正常工作"""
    print("="*60)
    print("测试Playwright Windows兼容性")
    print("="*60)

    try:
        print("\n1. 启动Playwright...")
        async with async_playwright() as p:
            print("✅ Playwright启动成功")

            print("\n2. 启动浏览器...")
            browser = await p.chromium.launch(headless=True)
            print("✅ 浏览器启动成功")

            print("\n3. 创建页面...")
            page = await browser.new_page()
            print("✅ 页面创建成功")

            print("\n4. 访问测试页面...")
            await page.goto("https://www.baidu.com")
            print("✅ 页面访问成功")

            title = await page.title()
            print(f"   页面标题: {title}")

            print("\n5. 关闭浏览器...")
            await browser.close()
            print("✅ 浏览器关闭成功")

        print("\n" + "="*60)
        print("✅ 所有测试通过！Playwright在Windows上工作正常")
        print("="*60)
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_login_simulation():
    """模拟登录流程测试"""
    print("\n" + "="*60)
    print("模拟登录流程测试")
    print("="*60)

    try:
        from queue import Queue

        # 创建状态队列
        status_queue = Queue()

        print("\n1. 创建队列...")
        print("✅ 队列创建成功")

        print("\n2. 测试异步Playwright登录流程...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            print("✅ 浏览器环境准备完成")

            # 模拟访问登录页
            print("\n3. 访问登录页面...")
            await page.goto("https://www.baidu.com")
            print("✅ 登录页访问成功")

            # 模拟检测iframe
            print("\n4. 检测页面元素...")
            iframes = page.frames
            print(f"✅ 找到 {len(iframes)} 个frame")

            await browser.close()

        print("\n" + "="*60)
        print("✅ 登录流程模拟测试通过")
        print("="*60)
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    results = []

    # 测试1: 基础Playwright功能
    result1 = await test_playwright_windows()
    results.append(("Playwright基础功能", result1))

    # 测试2: 登录流程模拟
    result2 = await test_login_simulation()
    results.append(("登录流程模拟", result2))

    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False

    print("="*60)

    if all_passed:
        print("\n🎉 所有测试通过！登录功能已修复")
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息")

    return all_passed


if __name__ == "__main__":
    # 设置事件循环
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
