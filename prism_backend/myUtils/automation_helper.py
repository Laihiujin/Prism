"""
Playwright Helper for Windows AsyncIO Compatibility

On Windows, Playwright requires asyncio subprocess support (provided by ProactorEventLoop).
This module provides a wrapper to run Playwright tasks in a dedicated thread to reduce
event-loop contention with the main server.
"""
import asyncio
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Coroutine
from loguru import logger


# Thread pool for running Playwright tasks
_playwright_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="playwright_")


def _run_with_selector_loop(coro: Coroutine) -> Any:
    """
    Run an async coroutine with a dedicated event loop.

    This function runs in a separate thread to avoid interfering with FastAPI's ProactorEventLoop.
    """
    # Ensure subprocess support for THIS THREAD ONLY
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Verify we got the right type of loop
    logger.debug(f"Event loop type: {type(loop).__name__}")

    try:
        result = loop.run_until_complete(coro)
        return result
    except Exception as e:
        logger.error(f"Playwright task failed: {e}", exc_info=True)
        raise
    finally:
        loop.close()


async def run_playwright_task(coro: Coroutine) -> Any:
    """
    Run a Playwright async task in a thread with SelectorEventLoop.

    Usage:
        result = await run_playwright_task(check_cookie(platform, file_path))

    Args:
        coro: Async coroutine that uses Playwright

    Returns:
        Result of the coroutine
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_playwright_executor, _run_with_selector_loop, coro)


def run_playwright_sync(coro: Coroutine) -> Any:
    """
    Synchronously run a Playwright async task (for non-async contexts).

    Usage:
        result = run_playwright_sync(check_cookie(platform, file_path))

    Args:
        coro: Async coroutine that uses Playwright

    Returns:
        Result of the coroutine
    """
    return _run_with_selector_loop(coro)
