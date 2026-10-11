"""
OTP验证码路由（FastAPI版）
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import sys
from pathlib import Path
from loguru import logger

# 添加platforms模块到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from platforms.verification import verification_manager

router = APIRouter(prefix="/verification", tags=["验证码"])


class SubmitCodeRequest(BaseModel):
    """提交验证码请求"""
    account_id: str
    code: str


@router.get("/otp-events")
async def pending_verification_events():
    return {"events": verification_manager.get_pending_events()}




@router.post("/submit-code")
async def submit_verification_code(request: SubmitCodeRequest):
    """
    提交验证码
    前端用户输入验证码后调用此接口
    """
    success = verification_manager.submit_code(
        account_id=request.account_id,
        code=request.code
    )

    if success:
        return {
            "success": True,
            "message": "验证码已提交"
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="提交验证码失败"
        )


class ResendRequest(BaseModel):
    account_id: str


@router.post("/resend-code")
async def resend_verification_code(request: ResendRequest):
    try:
        if not verification_manager.request_resend(request.account_id):
            raise HTTPException(status_code=409, detail="验证请求已过期或不支持重新发送")
    except ValueError as error:
        raise HTTPException(status_code=429, detail=str(error))
    return {"success": True, "message": "已通知发布浏览器重新获取，请以平台发送结果为准"}
