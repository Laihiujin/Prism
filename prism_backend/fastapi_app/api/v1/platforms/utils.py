"""
平台路由辅助函数
处理 Playwright 在 Windows 上的异步问题
"""
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# 创建线程池用于运行 Playwright 任务
_executor = ThreadPoolExecutor(max_workers=4)


def run_in_threadpool(func):
    """
    装饰器：在线程池中运行函数，避免 Windows 上的 asyncio 问题
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, lambda: asyncio.run(func(*args, **kwargs)))
    return wrapper


async def run_playwright_task(coro):
    """
    在新的事件循环中运行 Playwright 协程
    适用于 Windows 平台
    """
    try:
        # 在线程池中运行，避免事件循环冲突
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            lambda: asyncio.run(coro)
        )
        return result
    except Exception as e:
        logger.error(f"Playwright task failed: {e}")
        raise
