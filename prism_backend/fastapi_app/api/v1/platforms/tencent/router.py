"""
视频号平台路由（FastAPI版本）
提供登录、上传等API接口
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import logging
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent.parent))

from ..task_manager import task_manager
from myUtils.fast_cookie_validator import FastCookieValidator


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platforms/tencent", tags=["platforms-tencent"])


class TencentLoginRequest(BaseModel):
    """视频号登录请求"""
    account_id: str


class TencentVerifyCookieRequest(BaseModel):
    """视频号Cookie验证请求"""
    account_file: str



@router.post("/login")
async def api_tencent_login(request: TencentLoginRequest):
    """
    视频号扫码登录接口（异步任务）
    """
    try:
        logger.info(f"[TencentAPI] 创建登录任务: {request.account_id}")
        
        # 创建后台任务
        task_id = task_manager.create_task(
            task_type="login",
            platform="tencent",
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
        logger.error(f"[TencentAPI] 创建登录任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}")
async def get_task_status(task_id: str, request: Request):
    """
    查询任务状态
    """
    try:
        # 优先查统一发布队列（与 /api/v1/publish/* 同源）
        tm = getattr(request.app.state, "task_manager", None)
        if tm:
            status = tm.get_task_status(task_id)
            if status is not None:
                return {"success": True, "data": status}

        # 回退：旧平台任务管理器（login/upload 旧链路）
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
        logger.error(f"[TencentAPI] 查询任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-cookie")
async def api_verify_cookie(request: TencentVerifyCookieRequest):
    """
    验证视频号Cookie是否有效
    """
    try:
        validator = FastCookieValidator()
        result = await validator.validate_cookie_fast("channels", account_file=request.account_file)
        is_valid = result.get("status") == "valid"
        if result.get("status") in ("error", "network_error"):
            return {"success": False, "data": result, "message": result.get("error", "Cookie验证失败")}
        return {
            "success": True,
            "data": {"is_valid": is_valid, **result},
            "message": "Cookie有效" if is_valid else "Cookie已失效",
        }

    except Exception as e:
        logger.error(f"[TencentAPI] Cookie验证失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


