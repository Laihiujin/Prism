"""
平台扫码登录（简化版，无官方API、无 SSE）
支持：抖音、快手、视频号（channels）、小红书、腾讯（别名 channels）
流程：
- /platforms/login/start  通过 Playwright Worker 生成二维码，返回 login_id + 二维码(base64)
- /platforms/login/status 轮询登录状态；成功则保存 Cookie 文件并写入 cookie_store
"""
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from myUtils.cookie_manager import cookie_manager
from playwright_worker.client import get_worker_client

router = APIRouter(prefix="/platforms", tags=["平台接口"])

LOGIN_TIMEOUT = 300  # seconds

# 内存登录会话: login_id -> session dict
login_sessions = {}


class LoginStartRequest(BaseModel):
    platform: str
    account_id: str


class LoginStatusResponse(BaseModel):
    success: bool
    message: str
    qr_base64: Optional[str] = None
    account_id: Optional[str] = None


PLATFORM_LOGIN_URL = {
    "douyin": "https://creator.douyin.com/",
    "kuaishou": "https://cp.kuaishou.com/",
    "xiaohongshu": "https://creator.xiaohongshu.com/",
    "channels": "https://channels.weixin.qq.com/",
    "tencent": "https://channels.weixin.qq.com/",
}


def _cleanup_sessions():
    now = time.time()
    expired = [k for k, v in login_sessions.items() if now - v.get("created_at", 0) > LOGIN_TIMEOUT]
    for k in expired:
        login_sessions.pop(k, None)


def _extract_base64(data_uri_or_b64: str) -> str:
    if not data_uri_or_b64:
        return ""
    if data_uri_or_b64.startswith("data:image"):
        return data_uri_or_b64.split("base64,", 1)[-1]
    return data_uri_or_b64


async def _new_login_session(platform: str, account_id: str) -> dict:
    platform = platform.lower()
    if platform not in PLATFORM_LOGIN_URL:
        raise ValueError(f"Unsupported platform: {platform}")

    worker = get_worker_client()
    from config.conf import PLAYWRIGHT_HEADLESS
    qr = await worker.generate_qrcode(platform=platform, account_id=account_id, headless=bool(PLAYWRIGHT_HEADLESS))

    login_id = str(uuid.uuid4())
    qr_image = qr.get("qr_image", "")
    login_sessions[login_id] = {
        "platform": platform,
        "account_id": account_id,
        "worker_session_id": qr["session_id"],
        "qr_base64": _extract_base64(qr_image),
        "qr_image": qr_image,
        "created_at": time.time(),
    }
    return login_sessions[login_id] | {"login_id": login_id}


@router.get("/ping")
async def ping():
    return {"status": "success", "message": "platforms ready"}


@router.post("/login/start", response_model=LoginStatusResponse)
async def login_start(req: LoginStartRequest):
    """
    启动扫码登录，返回 login_id + 当前二维码截图（base64）。
    前端用 login_id 轮询 /login/status。
    """
    _cleanup_sessions()
    try:
        session = await _new_login_session(req.platform, req.account_id)
        return LoginStatusResponse(
            success=True,
            message="login started",
            qr_base64=session.get("qr_base64"),
            account_id=req.account_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/login/status", response_model=LoginStatusResponse)
async def login_status(login_id: str):
    """
    轮询登录状态；成功则保存 Cookie 文件并写入 cookie_store。
    """
    _cleanup_sessions()
    session = login_sessions.get(login_id)
    if not session:
        raise HTTPException(status_code=404, detail="login session not found or expired")

    try:
        worker = get_worker_client()
        result = await worker.poll_status(session["worker_session_id"])
        status = (result.get("status") or "").lower()

        if status == "confirmed":
            account_id = session["account_id"]
            platform = session["platform"]

            user_info = result.get("user_info") or {}
            cookie_payload = result.get("full_state") or {"raw_cookies": result.get("cookies", {})}

            cookie_manager.add_account(
                platform,
                {
                    "id": account_id,
                    "name": user_info.get("name") or account_id,
                    "cookie": cookie_payload,
                    "status": "valid",
                    "user_id": user_info.get("user_id"),
                    "avatar": user_info.get("avatar"),
                },
            )

            login_sessions.pop(login_id, None)
            return LoginStatusResponse(success=True, message="logged in", account_id=account_id)

        return LoginStatusResponse(
            success=False,
            message=status or "pending",
            qr_base64=session.get("qr_base64"),
            account_id=session["account_id"],
        )
    except Exception as exc:
        login_sessions.pop(login_id, None)
        raise HTTPException(status_code=500, detail=str(exc))
