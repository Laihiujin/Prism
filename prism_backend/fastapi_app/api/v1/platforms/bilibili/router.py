"""
B站平台路由（FastAPI版本）
提供登录、上传等API接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging
import asyncio
from queue import Queue as ThreadQueue

from ..task_manager import task_manager
from myUtils.fast_cookie_validator import FastCookieValidator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platforms/bilibili", tags=["platforms-bilibili"])


class BilibiliLoginRequest(BaseModel):
    """B站登录请求"""
    account_id: str
    use_biliup: Optional[bool] = True  # 默认使用biliup.exe


class BilibiliVerifyCookieRequest(BaseModel):
    """B站Cookie验证请求"""
    account_file: str


@router.post("/login")
async def api_bilibili_login(request: BilibiliLoginRequest):
    """
    B站扫码登录接口（支持biliup.exe和Playwright两种方式）

    - use_biliup=True: 使用biliup.exe登录（推荐）
    - use_biliup=False: 使用Playwright登录（备用）
    """
    try:
        logger.info(f"[BilibiliAPI] 创建登录任务: {request.account_id}, use_biliup={request.use_biliup}")

        if request.use_biliup:
            # 使用V2服务（已集成）
            from fastapi_app.api.v1.auth.services_v2 import BilibiliLoginServiceV2

            logger.info(f"[BilibiliAPI] 使用V2服务生成二维码")

            # 生成二维码
            session_id, qr_url, qr_image = await BilibiliLoginServiceV2.get_qrcode()

            return {
                "success": True,
                "message": "B站二维码已生成",
                "data": {
                    "session_id": session_id,
                    "qr_url": qr_url,
                    "qr_image": qr_image,
                    "account_id": request.account_id,
                    "method": "v2_service"
                }
            }

        else:
            # 使用任务管理器（Playwright登录）
            task_id = task_manager.create_task(
                task_type="login",
                platform="bilibili",
                params={"account_id": request.account_id}
            )

            return {
                "success": True,
                "message": "登录任务已创建（Playwright）",
                "data": {
                    "task_id": task_id,
                    "account_id": request.account_id,
                    "method": "playwright"
                }
            }

    except Exception as e:
        logger.error(f"[BilibiliAPI] 创建登录任务失败: {e}")
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
        logger.error(f"[BilibiliAPI] 查询任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-cookie")
async def api_verify_cookie(request: BilibiliVerifyCookieRequest):
    """
    验证B站Cookie是否有效
    """
    try:
        validator = FastCookieValidator()
        result = await validator.validate_cookie_fast("bilibili", account_file=request.account_file)
        is_valid = result.get("status") == "valid"
        if result.get("status") in ("error", "network_error"):
            return {"success": False, "data": result, "message": result.get("error", "Cookie验证失败")}
        return {
            "success": True,
            "data": {"is_valid": is_valid, **result},
            "message": "Cookie有效" if is_valid else "Cookie已失效",
        }

    except Exception as e:
        logger.error(f"[BilibiliAPI] Cookie验证失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


