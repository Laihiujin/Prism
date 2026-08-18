"""
Windows Playwright兼容性修复
解决asyncio subprocess NotImplementedError问题
"""
import asyncio
import sys


def setup_windows_playwright_policy():
    """
    设置Windows环境下Playwright所需的事件循环策略

    解决问题：
    - Windows上asyncio.create_subprocess_exec的NotImplementedError
    - Playwright需要创建子进程来启动浏览器

    必须在创建任何事件循环之前调用
    """
    if sys.platform == 'win32':
        # Playwright 需要 asyncio subprocess 支持（Windows 上由 ProactorEventLoop 提供）。
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


async def create_playwright_browser_windows(playwright_instance, headless=True):
    """
    在Windows上创建Playwright浏览器的兼容性wrapper

    Args:
        playwright_instance: Playwright实例
        headless: 是否无头模式

    Returns:
        浏览器实例
    """
    try:
        browser = await playwright_instance.chromium.launch(
            headless=headless,
            # Windows特定选项
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',  # 在某些Windows环境下需要
            ]
        )
        return browser
    except Exception as e:
        # 如果失败，尝试使用不同的参数
        print(f"第一次启动失败: {e}，尝试备用方案...")
        browser = await playwright_instance.chromium.launch(
            headless=headless,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        return browser


# 导出便捷函数
__all__ = ['setup_windows_playwright_policy', 'create_playwright_browser_windows']
