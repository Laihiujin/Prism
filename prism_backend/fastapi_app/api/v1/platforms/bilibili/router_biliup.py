"""
B站登录路由 - 使用 biliup Python 库
纯 Python 实现，不依赖 biliup.exe
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import asyncio
from queue import Queue as ThreadQueue

# 使用V2服务
from fastapi_app.api.v1.auth.services_v2 import BilibiliLoginServiceV2

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platforms/bilibili", tags=["platforms-bilibili"])


class BilibiliLoginBiliupRequest(BaseModel):
    """B站登录请求（使用biliup）"""
    account_id: str


@router.post("/login/biliup")
async def api_bilibili_login_biliup(request: BilibiliLoginBiliupRequest):
    """
    B站扫码登录接口（使用 V2 服务）

    此接口使用新的V2登录服务：
    1. 生成二维码
    2. 用户扫描二维码
    3. 自动保存 Cookie

    Note: 使用统一的V2服务接口
    """
    try:
        logger.info(f"[B站登录-V2] 开始登录: {request.account_id}")

        # 使用V2服务生成二维码
        session_id, qr_url, qr_image = await BilibiliLoginServiceV2.get_qrcode()

        logger.info(f"[B站登录-V2] 二维码已生成: session={session_id[:8]}")

        # 返回二维码信息
        return {
            "success": True,
            "message": "请扫描二维码登录",
            "data": {
                "account_id": request.account_id,
                "session_id": session_id,
                "qr_url": qr_url,
                "qr_image": qr_image,
                "note": "请使用统一的登录轮询接口 /api/v1/auth/qrcode/poll"
            }
        }

    except Exception as e:
        logger.error(f"[B站登录-V2] 登录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/login/biliup/check")
async def check_biliup_available():
    """
    检查 biliup Python 库是否可用
    """
    try:
        # 检查 biliup 库是否已安装
        try:
            import biliup
            biliup_version = getattr(biliup, '__version__', 'unknown')
            
            return {
                "success": True,
                "message": "biliup Python 库可用",
                "data": {
                    "available": True,
                    "version": biliup_version,
                    "method": "python_library"
                }
            }
        except ImportError:
            return {
                "success": False,
                "message": "biliup Python 库未安装",
                "data": {
                    "available": False,
                    "hint": "请运行: pip install biliup"
                }
            }

    except Exception as e:
        logger.error(f"[B站登录] 检查biliup失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
