from __future__ import annotations

from functools import lru_cache
from typing import Optional, Any

from fastapi_app.core.config import settings


@lru_cache(maxsize=1)
def get_redis() -> Optional[Any]:
    """获取 Redis 客户端实例"""
    # 默认 Redis URL
    default_url = "redis://localhost:6379/0"

    # 获取配置的 URL，如果为空则使用默认值
    url = getattr(settings, 'REDIS_URL', None)
    if not url or not isinstance(url, str):
        url = default_url

    url = url.strip()
    if not url:
        url = default_url

    # 确保 URL 格式正确
    if not url.startswith(('redis://', 'rediss://', 'unix://')):
        url = f"redis://{url}"

    try:
        import redis  # type: ignore
    except ImportError:
        return None

    try:
        return redis.Redis.from_url(url, decode_responses=True)
    except Exception as e:
        # 如果连接失败，记录错误但不抛出异常
        import logging
        logging.warning(f"Failed to connect to Redis at {url}: {e}")
        return None
