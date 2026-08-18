"""
快手平台路由（FastAPI版本）
使用后台任务队列支持高并发
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging

from ..task_manager import task_manager
from myUtils.fast_cookie_validator import FastCookieValidator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platforms/kuaishou", tags=["platforms-kuaishou"])


class KuaishouLoginRequest(BaseModel):
    """快手登录请求"""
    account_id: str


class KuaishouVerifyCookieRequest(BaseModel):
    """快手Cookie验证请求"""
    account_file: str


@router.post("/login")
async def api_kuaishou_login(request: KuaishouLoginRequest):
    """
    快手扫码登录接口（异步任务）
    
    Args:
        request: 包含 account_id 的登录请求
        
    Returns:
        任务ID，用于查询登录状态
    """
    try:
        logger.info(f"[KuaishouAPI] 创建登录任务: {request.account_id}")
        
        # 创建后台任务
        task_id = task_manager.create_task(
            task_type="login",
            platform="kuaishou",
            params={"account_id": request.account_id}
        )
        
        return {
            "success": True,
            "message": "登录任务已创建",
            "data": {
                "task_id": task_id,
                "account_id": request.account_id
            }
        }

    except Exception as e:
        logger.error(f"[KuaishouAPI] 创建登录任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        任务状态信息
    """
    try:
        status = task_manager.get_task_status(task_id)
        
        if status is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        return {
            "success": True,
            "data": status
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[KuaishouAPI] 查询任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-cookie")
async def api_verify_cookie(request: KuaishouVerifyCookieRequest):
    """
    验证快手Cookie是否有效
    
    Args:
        request: 包含 account_file 的验证请求
        
    Returns:
        Cookie有效性验证结果
    """
    try:
        validator = FastCookieValidator()
        result = await validator.validate_cookie_fast("kuaishou", account_file=request.account_file)
        is_valid = result.get("status") == "valid"
        if result.get("status") in ("error", "network_error"):
            return {"success": False, "data": result, "message": result.get("error", "Cookie验证失败")}
        return {
            "success": True,
            "data": {"is_valid": is_valid, **result},
            "message": "Cookie有效" if is_valid else "Cookie已失效",
        }

    except Exception as e:
        logger.error(f"[KuaishouAPI] Cookie验证失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


