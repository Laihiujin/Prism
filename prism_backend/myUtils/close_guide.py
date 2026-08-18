from __future__ import annotations

from typing import Any, Dict

from loguru import logger


async def close_platform_guide(
    page: Any,
    platform: str,
    timeout: int = 5000,
    max_attempts: int = 5,
) -> Dict[str, Any]:
    logger.debug(f"[{platform}] close guide disabled, skipping")
    return {
        "success": True,
        "closed_count": 0,
        "method": "disabled",
        "message": "guide closing disabled",
    }


async def auto_close_guide_wrapper(page: Any, platform: str):
    return await close_platform_guide(page, platform)


async def try_close_guide(page: Any, platform: str) -> bool:
    logger.debug(f"[{platform}] try_close_guide disabled, returning success")
    return True
