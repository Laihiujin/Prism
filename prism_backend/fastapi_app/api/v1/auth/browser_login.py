"""
TikTok / YouTube 交互式浏览器登录（方案 C：本机非 headless 弹出浏览器）。

背景：
- 抖音/快手/视频号/小红书/B站 走网页内扫码（/auth/qrcode/*）。
- TikTok / YouTube 无官方网页扫码，需要真实浏览器人工登录（验证码 / Google 2FA）。
  本模块直接在本机调用 CLI 同款登录函数（tiktok_setup / youtube_setup），
  它会弹出一个真实的浏览器窗口让用户完成登录，登录成功后把 cookie
  写入账号 cookie 文件，再由 deep_sync 把账号注册进账号库。

适用：后端/登录在「本机（带桌面/显示器）」运行时，浏览器窗口可见。
（若在无头 Docker 容器内运行，浏览器无法弹出，登录无法人工完成。）
"""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from fastapi_app.core.config import settings

router = APIRouter(prefix="/auth/login/browser", tags=["浏览器登录"])

# 内存中的登录任务: login_id -> 记录
_tasks: Dict[str, Dict[str, Any]] = {}
_tasks_lock = asyncio.Lock()

# 允许的浏览器登录平台
_BROWSER_LOGIN_PLATFORMS = {"tiktok", "youtube"}


def _cookie_file_path(platform: str, account: str) -> Path:
    base = Path(settings.COOKIE_FILES_DIR)
    return base / f"{platform}_{account}.json"


async def _run_login(platform: str, account: str, cookie_path: Path) -> Dict[str, Any]:
    """在后台任务中运行平台登录；本机运行时会弹出真实浏览器窗口。"""
    if platform == "tiktok":
        from uploader.tk_uploader.main_chrome import tiktok_setup
        result = await tiktok_setup(str(cookie_path), handle=True)
        return {"success": bool(result), "platform": platform, "account": account, "account_file": str(cookie_path)}
    if platform == "youtube":
        from uploader.youtube_uploader.main_refactored import youtube_setup
        result = await youtube_setup(str(cookie_path), handle=True, return_detail=True, headless=False)
        if isinstance(result, dict):
            ok = bool(result.get("success"))
        else:
            ok = bool(result)
        return {"success": ok, "platform": platform, "account": account, "account_file": str(cookie_path)}
    raise ValueError(f"不支持的浏览器登录平台: {platform}")


@router.post("/start", summary="启动 TikTok/YouTube 浏览器登录")
async def browser_login_start(
    platform: str = Query(..., description="平台: tiktok / youtube"),
    account_id: str = Query(..., description="账号ID"),
):
    platform = (platform or "").lower()
    if platform not in _BROWSER_LOGIN_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"平台 {platform} 不支持浏览器登录")

    cookie_path = _cookie_file_path(platform, account_id)
    cookie_path.parent.mkdir(parents=True, exist_ok=True)

    login_id = str(uuid.uuid4())
    task = asyncio.create_task(_run_login(platform, account_id, cookie_path))

    async with _tasks_lock:
        _tasks[login_id] = {
            "platform": platform,
            "account_id": account_id,
            "cookie_file": str(cookie_path),
            "task": task,
            "status": "running",
            "result": None,
            "error": None,
        }

    logger.info(f"[BrowserLogin] started platform={platform} account={account_id} login_id={login_id[:8]}")

    return {
        "success": True,
        "login_id": login_id,
        "message": "已启动浏览器登录，请在本机弹出的浏览器窗口中完成登录",
        "account_file": str(cookie_path),
    }


@router.get("/status", summary="查询浏览器登录状态")
async def browser_login_status(login_id: str = Query(..., description="登录会话ID")):
    async with _tasks_lock:
        rec = _tasks.get(login_id)
    if not rec:
        raise HTTPException(status_code=404, detail="登录会话不存在或已过期")

    task: asyncio.Task = rec["task"]

    if not task.done():
        return {"success": True, "status": "running", "message": "请在本机弹出的浏览器窗口中完成登录，等待确认..."}

    # 任务已完成
    if rec["status"] == "running":
        try:
            rec["result"] = task.result()
            rec["status"] = "success" if (rec["result"] or {}).get("success") else "failed"
            if rec["status"] == "success":
                # 登录成功：deep_sync 扫描 cookie 文件，把账号注册进账号库
                try:
                    from myUtils.cookie_manager import cookie_manager
                    await asyncio.to_thread(cookie_manager.deep_sync_accounts)
                except Exception as exc:
                    logger.warning(f"[BrowserLogin] deep_sync failed: {exc}")
        except Exception as exc:
            rec["status"] = "failed"
            rec["error"] = str(exc) or type(exc).__name__
            logger.error(f"[BrowserLogin] login task error: {rec['error']}", exc_info=True)

    if rec["status"] == "success":
        return {
            "success": True,
            "status": "success",
            "message": "登录成功",
            "account_file": rec["cookie_file"],
            "result": rec["result"],
        }

    if rec["status"] == "failed":
        return {
            "success": False,
            "status": "failed",
            "message": rec["error"] or "登录失败",
            "account_file": rec["cookie_file"],
        }

    return {"success": True, "status": "running", "message": "登录中..."}


@router.delete("/cancel/{login_id}", summary="取消浏览器登录")
async def browser_login_cancel(login_id: str):
    async with _tasks_lock:
        rec = _tasks.pop(login_id, None)
    if not rec:
        raise HTTPException(status_code=404, detail="登录会话不存在")
    task: asyncio.Task = rec["task"]
    if not task.done():
        task.cancel()
    return {"success": True, "message": "登录会话已取消"}
