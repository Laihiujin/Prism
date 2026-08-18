"""
投放计划模块依赖注入

提供:
- 数据库会话
- 服务实例
- 任务池实例
- 限流器实例
"""

from typing import Generator
from pathlib import Path

from ....core.async_task_pool import get_task_pool, AsyncTaskPool
from ....core.rate_limiter import get_rate_limiter, RateLimiter
from .....config.conf import BASE_DIR


# ========== 数据库路径 ==========

def get_db_path() -> Path:
    """获取数据库路径"""
    return Path(BASE_DIR) / "db" / "database.db"


# ========== 任务池 ==========

def get_async_task_pool() -> AsyncTaskPool:
    """
    获取异步任务池实例
    
    Returns:
        AsyncTaskPool实例
    """
    return get_task_pool(max_workers=5)


# ========== 限流器 ==========

def get_rate_limiter_instance() -> RateLimiter:
    """
    获取限流器实例
    
    Returns:
        RateLimiter实例
    """
    return get_rate_limiter()


# ========== 服务实例 ==========

async def get_campaign_service():
    """
    获取投放计划服务实例（依赖注入）
    
    在路由中使用:
    ```python
    @router.get("/plans")
    async def list_plans(
        service: CampaignService = Depends(get_campaign_service)
    ):
        return await service.list_plans()
    ```
    """
    # 延迟导入避免循环依赖
    from .services import CampaignService
    
    service = CampaignService(
        db_path=get_db_path(),
        task_pool=get_async_task_pool(),
        rate_limiter=get_rate_limiter_instance()
    )
    
    try:
        yield service
    finally:
        # 清理资源（如果需要）
        pass
