"""
MediaCrawler login helpers (persistent www profiles).
"""
from typing import Optional, Dict, Any
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from fastapi_app.core.config import settings
from fastapi_app.core.logger import logger
from fastapi_app.schemas.common import Response
from playwright_worker.client import get_worker_client

router = APIRouter(prefix="/mediacrawler", tags=["MediaCrawler"])

_LOGIN_URLS: Dict[str, str] = {
    "kuaishou": "https://www.kuaishou.com",
    "xiaohongshu": "https://www.xiaohongshu.com",
}


def _default_profile_id(platform: str) -> str:
    return f"mediacrawler_{platform}"


def _ensure_cookie_file(platform: str) -> str:
    cookie_dir = Path(settings.COOKIE_FILES_DIR)
    cookie_dir.mkdir(parents=True, exist_ok=True)
    cookie_path = cookie_dir / f"mediacrawler_{platform}.json"
    if not cookie_path.exists():
        cookie_path.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    return str(cookie_path)


class MediaCrawlerLoginOpen(BaseModel):
    platform: str = Field(..., description="kuaishou/xiaohongshu")
    account_id: Optional[str] = Field(None, description="可选，持久化 profile 标识")
    headless: Optional[bool] = Field(False, description="是否无头模式")


@router.post("/login/open", response_model=Response[dict])
async def open_mediacrawler_login(payload: MediaCrawlerLoginOpen):
    platform = (payload.platform or "").strip().lower()
    if platform not in _LOGIN_URLS:
        raise HTTPException(status_code=400, detail="Unsupported platform")

    account_id = payload.account_id or _default_profile_id(platform)
    cookie_file = _ensure_cookie_file(platform)

    client = get_worker_client()
    try:
        data = await client.open_creator_center(
            platform=platform,
            storage_state={},
            account_id=account_id,
            apply_fingerprint=True,
            headless=bool(payload.headless),
            url=_LOGIN_URLS[platform],
        )
        data.update({"account_id": account_id, "cookie_file": cookie_file})
        return Response(success=True, data=data)
    except Exception as exc:
        logger.error(f"[MediaCrawler] Open login failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/login/close/{session_id}", response_model=Response[dict])
async def close_mediacrawler_login(session_id: str):
    client = get_worker_client()
    try:
        ok = await client.close_creator_center(session_id)
        return Response(success=True, data={"closed": ok})
    except Exception as exc:
        logger.error(f"[MediaCrawler] Close login failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
