"""
创作者中心相关API路由 - 登录状态检测
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from loguru import logger
import httpx

router = APIRouter(prefix="/creator", tags=["创作者中心"])


class LoginStatusCheckRequest(BaseModel):
    """登录状态检查请求"""
    account_ids: Optional[List[str]] = Field(None, description="账号ID列表(为空则检查下一批)")
    batch_size: int = Field(default=5, ge=1, le=100, description="批量检查数量")


@router.post("/check-login-status")
async def check_login_status(request: LoginStatusCheckRequest):
    """
    检查账号登录状态 (代理到 Playwright Worker)

    - 如果提供 account_ids,则检查指定账号
    - 如果不提供,则使用轮询策略检查下一批账号
    """
    try:
        # 调用 Playwright Worker API
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://127.0.0.1:7001/creator/check-login-status",
                json=request.dict()
            )

            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_detail = error_data.get("error") or error_data.get("detail") or response.text
                except Exception:
                    error_detail = response.text or f"HTTP {response.status_code}"

                logger.error(f"[CreatorAPI] Worker返回错误 {response.status_code}: {error_detail}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_detail
                )

            return response.json()

    except httpx.ConnectError as e:
        logger.error(f"[CreatorAPI] 无法连接到 Playwright Worker: {e}")
        raise HTTPException(
            status_code=503,
            detail="无法连接到 Playwright Worker,请确保 Worker 服务正在运行"
        )
    except Exception as e:
        logger.error(f"[CreatorAPI] 登录状态检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查失败: {str(e)}")
