"""
抖音平台路由（FastAPI版本）
提供登录、上传等API接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging

from ..task_manager import task_manager
from myUtils.fast_cookie_validator import FastCookieValidator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platforms/douyin", tags=["platforms-douyin"])

# 注意：平台直传上传接口已移除；请使用 `/api/v1/publish/direct` 替代。


class DouyinLoginRequest(BaseModel):
    account_id: str


class DouyinVerifyCookieRequest(BaseModel):
    account_file: str


@router.post("/login")
async def api_douyin_login(request: DouyinLoginRequest):
    """
    抖音扫码登录接口（异步任务）
    """
    try:
        logger.info(f"[DouyinAPI] 创建登录任务: {request.account_id}")
        
        # 创建后台任务
        task_id = task_manager.create_task(
            task_type="login",
            platform="douyin",
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
        logger.error(f"[DouyinAPI] 创建登录任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务状态
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
        logger.error(f"[DouyinAPI] 查询任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-cookie")
async def api_verify_cookie(request: DouyinVerifyCookieRequest):
    """
    验证抖音Cookie是否有效
    """
    try:
        validator = FastCookieValidator()
        result = await validator.validate_cookie_fast("douyin", account_file=request.account_file)
        is_valid = result.get("status") == "valid"
        if result.get("status") in ("error", "network_error"):
            return {"success": False, "data": result, "message": result.get("error", "Cookie验证失败")}
        return {
            "success": True,
            "data": {"is_valid": is_valid, **result},
            "message": "Cookie有效" if is_valid else "Cookie已失效",
        }

    except Exception as e:
        logger.error(f"[DouyinAPI] Cookie验证失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

