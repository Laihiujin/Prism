"""
通用的平台引导关闭工具 - 已禁用
所有引导关闭功能已被禁用，直接返回成功
"""
from playwright.async_api import Page
from loguru import logger
from typing import Dict


async def close_platform_guide(
    page: Page,
    platform: str,
    timeout: int = 5000,
    max_attempts: int = 5
) -> Dict[str, any]:
    """
    关闭平台的引导组件 - 已禁用

    直接返回成功，不进行任何操作
    """
    logger.debug(f"[{platform}] 引导关闭功能已禁用，跳过")
    return {
        "success": True,
        "closed_count": 0,
        "method": "disabled",
        "message": "引导关闭功能已禁用"
    }


async def auto_close_guide_wrapper(page: Page, platform: str):
    """
    自动关闭引导的包装函数 - 已禁用
    """
    return await close_platform_guide(page, platform)


# 导出一个简化的函数，方便上传器调用
async def try_close_guide(page: Page, platform: str) -> bool:
    """
    简化版本：尝试关闭引导，返回是否成功 - 已禁用
    直接返回 True
    """
    logger.debug(f"[{platform}] try_close_guide 已禁用，直接返回成功")
    return True
