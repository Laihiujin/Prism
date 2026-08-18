"""
并发控制 API 路由
提供动态并发配置和监控接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

from fastapi_app.schemas.common import Response
from fastapi_app.tasks.concurrency_controller import concurrency_controller
from fastapi_app.core.logger import logger


router = APIRouter(prefix="/concurrency", tags=["并发控制"])


class ConcurrencyConfig(BaseModel):
    """并发控制配置"""
    global_max: Optional[int] = Field(None, description="全局最大并发数", ge=1, le=100)
    platform_max: Optional[Dict[str, int]] = Field(None, description="平台级别最大并发数")
    account_max: Optional[int] = Field(None, description="账号级别最大并发数", ge=1, le=10)
    task_type_max: Optional[Dict[str, int]] = Field(None, description="任务类型最大并发数")
    enabled: Optional[bool] = Field(None, description="是否启用并发控制")
    timeout: Optional[int] = Field(None, description="令牌超时时间（秒）", ge=60, le=3600)


class ConcurrencyUsageResponse(BaseModel):
    """并发使用情况响应"""
    global_: Dict[str, int] = Field(..., alias="global", description="全局并发使用情况")
    platforms: Dict[str, Dict[str, int]] = Field(..., description="平台并发使用情况")
    task_types: Dict[str, Dict[str, int]] = Field(..., description="任务类型并发使用情况")


class ConcurrencyStatsResponse(BaseModel):
    """并发统计响应"""
    counters: Dict[str, int] = Field(..., description="统计计数器")


@router.get(
    "/config",
    response_model=Response[Dict[str, Any]],
    summary="获取并发控制配置"
)
async def get_concurrency_config():
    """
    获取当前并发控制配置

    返回:
    - global_max: 全局最大并发数
    - platform_max: 平台级别最大并发数
    - account_max: 账号级别最大并发数（防止同账号冲突）
    - task_type_max: 任务类型最大并发数
    - enabled: 是否启用并发控制
    - timeout: 令牌超时时间（秒）
    """
    try:
        from fastapi_app.tasks.concurrency_controller import concurrency_controller
        config = concurrency_controller._get_config()

        return Response(
            success=True,
            data=config,
            message="获取并发配置成功"
        )
    except Exception as e:
        logger.error(f"获取并发配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/config",
    response_model=Response[Dict[str, Any]],
    summary="更新并发控制配置"
)
async def update_concurrency_config(config: ConcurrencyConfig):
    """
    动态更新并发控制配置（立即生效）

    参数:
    - global_max: 全局最大并发数（1-100）
    - platform_max: 平台级别最大并发数
      - douyin: 抖音最大并发数
      - xiaohongshu: 小红书最大并发数
      - kuaishou: 快手最大并发数
      - bilibili: B站最大并发数
      - channels: 视频号最大并发数
    - account_max: 账号级别最大并发数（1-10，建议1）
    - task_type_max: 任务类型最大并发数
      - publish: 发布任务最大并发数
      - batch_publish: 批量发布任务最大并发数
    - enabled: 是否启用并发控制
    - timeout: 令牌超时时间（秒，60-3600）

    说明:
    - 只需要传递需要更新的字段
    - 配置立即生效，无需重启服务
    - 配置保存在 Redis，所有 Worker 共享
    """
    try:
        # 获取现有配置
        current_config = concurrency_controller._get_config()

        # 合并更新
        update_data = config.dict(exclude_unset=True)
        if "platform_max" in update_data and update_data["platform_max"]:
            # 合并平台配置
            current_config["platform_max"].update(update_data["platform_max"])
            update_data["platform_max"] = current_config["platform_max"]

        if "task_type_max" in update_data and update_data["task_type_max"]:
            # 合并任务类型配置
            current_config["task_type_max"].update(update_data["task_type_max"])
            update_data["task_type_max"] = current_config["task_type_max"]

        current_config.update(update_data)

        # 保存配置
        success = concurrency_controller.update_config(current_config)

        if not success:
            raise HTTPException(status_code=500, detail="更新配置失败")

        return Response(
            success=True,
            data=current_config,
            message="并发配置更新成功，已立即生效"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新并发配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/usage",
    response_model=Response[Dict[str, Any]],
    summary="获取当前并发使用情况"
)
async def get_concurrency_usage():
    """
    获取当前并发使用情况（实时）

    返回:
    - global: 全局并发使用情况
      - current: 当前并发数
      - max: 最大并发数
    - platforms: 各平台并发使用情况
    - task_types: 各任务类型并发使用情况
    """
    try:
        usage = concurrency_controller.get_current_usage()

        return Response(
            success=True,
            data=usage,
            message="获取并发使用情况成功"
        )
    except Exception as e:
        logger.error(f"获取并发使用情况失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stats",
    response_model=Response[Dict[str, int]],
    summary="获取并发统计信息"
)
async def get_concurrency_stats():
    """
    获取并发统计信息（24小时内）

    返回:
    - acquired:total: 总获取次数
    - released:total: 总释放次数
    - acquired:platform:{platform}: 各平台获取次数
    - acquired:task_type:{task_type}: 各任务类型获取次数
    """
    try:
        stats = concurrency_controller.get_stats()

        return Response(
            success=True,
            data=stats,
            message="获取并发统计成功"
        )
    except Exception as e:
        logger.error(f"获取并发统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/reset",
    response_model=Response[Dict[str, Any]],
    summary="重置并发配置为默认值"
)
async def reset_concurrency_config():
    """
    重置并发配置为默认值

    默认配置:
    - global_max: 0（无限制）
    - platform_max: 所有平台均为0（无限制）
      - douyin: 0
      - xiaohongshu: 0
      - kuaishou: 0
      - bilibili: 0
      - channels: 0
    - account_max: 1（每个账号最多1个并发，防止冲突）
    - task_type_max: 所有类型均为0（无限制）
      - publish: 0
      - batch_publish: 0
    - enabled: true
    - timeout: 300

    说明:
    - 默认只启用账号级并发控制（防止同账号冲突）
    - 全局、平台、任务类型级均不限制
    - 设置为0表示无限制
    """
    try:
        default_config = concurrency_controller._default_config()
        success = concurrency_controller.update_config(default_config)

        if not success:
            raise HTTPException(status_code=500, detail="重置配置失败")

        return Response(
            success=True,
            data=default_config,
            message="并发配置已重置为默认值"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置并发配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
