"""
持久化浏览器配置管理 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from loguru import logger

from myUtils.browser_context import persistent_browser_manager
from myUtils.cookie_manager import cookie_manager
from fastapi_app.schemas.common import Response

router = APIRouter(prefix="/browser-profiles", tags=["Browser Profiles"])


class ProfileInfo(BaseModel):
    """持久化配置信息"""
    platform: str
    account_id: str
    path: str
    size_bytes: int
    size_mb: float


class ProfilesListResponse(BaseModel):
    """配置列表响应"""
    profiles: List[ProfileInfo]
    total_count: int
    total_size_mb: float
    total_size_gb: float


class CleanupRequest(BaseModel):
    """清理请求"""
    days: Optional[int] = 30  # 清理超过多少天未使用的配置


class CleanupResponse(BaseModel):
    """清理响应"""
    cleaned_count: int
    message: str


@router.get("/list", response_model=Response[ProfilesListResponse])
async def list_browser_profiles():
    """
    列出所有持久化浏览器配置

    返回:
    - 所有账号的持久化配置信息
    - 包含平台、账号ID、路径、大小等
    """
    try:
        size_info = persistent_browser_manager.get_total_size()

        profiles_data = ProfilesListResponse(
            profiles=[ProfileInfo(**p) for p in size_info["profiles"]],
            total_count=size_info["profile_count"],
            total_size_mb=size_info["total_mb"],
            total_size_gb=size_info["total_gb"]
        )

        return Response(
            success=True,
            data=profiles_data,
            message=f"找到 {size_info['profile_count']} 个持久化配置"
        )
    except Exception as e:
        logger.error(f"列出持久化配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup-old", response_model=Response[CleanupResponse])
async def cleanup_old_profiles(request: CleanupRequest):
    """
    清理超过指定天数未使用的持久化配置

    参数:
    - days: 天数阈值，默认30天

    注意:
    - 此操作不可逆，请谨慎使用
    - 只清理超过指定天数未修改的目录
    """
    try:
        days = request.days or 30
        cleaned_count = persistent_browser_manager.cleanup_old_profiles(days)

        response_data = CleanupResponse(
            cleaned_count=cleaned_count,
            message=f"已清理 {cleaned_count} 个超过 {days} 天未使用的配置"
        )

        logger.info(f"清理旧配置: {cleaned_count} 个, 阈值: {days} 天")

        return Response(
            success=True,
            data=response_data,
            message=response_data.message
        )
    except Exception as e:
        logger.error(f"清理旧配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{platform}/{account_id}", response_model=Response[Dict[str, Any]])
async def delete_profile(platform: str, account_id: str):
    """
    删除指定账号的持久化浏览器配置

    参数:
    - platform: 平台名称 (如 douyin, bilibili)
    - account_id: 账号ID

    注意:
    - 此操作不可逆，请谨慎使用
    - 不会删除账号本身，只删除浏览器配置文件
    """
    try:
        account = cookie_manager.get_account_by_id(account_id)
        user_id = account.get("user_id") if account else None
        if not user_id:
            raise HTTPException(status_code=400, detail="Missing user_id for account")
        success = persistent_browser_manager.cleanup_user_data(account_id, platform, user_id=user_id)

        if success:
            logger.info(f"删除持久化配置成功: {platform}_{account_id}")
            return Response(
                success=True,
                data={"platform": platform, "account_id": account_id},
                message=f"已删除 {platform}_{account_id} 的持久化配置"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"未找到 {platform}_{account_id} 的持久化配置"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除持久化配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=Response[Dict[str, Any]])
async def get_profile_stats():
    """
    获取持久化配置统计信息

    返回:
    - 总配置数量
    - 总占用空间
    - 各平台分布
    """
    try:
        size_info = persistent_browser_manager.get_total_size()
        profiles = size_info["profiles"]

        # 按平台统计
        platform_stats = {}
        for profile in profiles:
            platform = profile["platform"]
            if platform not in platform_stats:
                platform_stats[platform] = {
                    "count": 0,
                    "size_mb": 0
                }
            platform_stats[platform]["count"] += 1
            platform_stats[platform]["size_mb"] += profile["size_mb"]

        # 四舍五入
        for platform in platform_stats:
            platform_stats[platform]["size_mb"] = round(platform_stats[platform]["size_mb"], 2)

        stats = {
            "total_count": size_info["profile_count"],
            "total_size_mb": size_info["total_mb"],
            "total_size_gb": size_info["total_gb"],
            "by_platform": platform_stats
        }

        return Response(
            success=True,
            data=stats,
            message="统计信息获取成功"
        )
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
