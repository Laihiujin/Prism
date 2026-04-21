from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from myUtils.tikhub_client import get_tikhub_client
from myUtils.video_collector import collector

router = APIRouter(prefix="/recovery", tags=["recovery"])


class RecoveryCollectRequest(BaseModel):
    account_ids: Optional[List[str]] = Field(None, description="Optional account IDs to recover")
    platform: Optional[str] = Field(None, description="Platform filter: kuaishou/xiaohongshu/channels")


def _require_client():
    client = get_tikhub_client()
    if not client:
        raise HTTPException(status_code=400, detail="TikHub API key not configured")
    return client


@router.get("/health")
async def health_check():
    client = get_tikhub_client()
    return {
        "status": "ok",
        "module": "recovery",
        "tikhub_configured": bool(client),
    }


@router.get("/kuaishou/user-info")
async def kuaishou_user_info(user_id: str):
    client = _require_client()
    return await client.fetch_kuaishou_user_info(user_id=user_id)


@router.get("/kuaishou/user-posts")
async def kuaishou_user_posts(user_id: str, pcursor: Optional[str] = None):
    client = _require_client()
    return await client.fetch_kuaishou_user_posts(user_id=user_id, pcursor=pcursor)


@router.get("/xiaohongshu/user-info")
async def xiaohongshu_user_info(user_id: str):
    client = _require_client()
    return await client.fetch_xiaohongshu_user_info(user_id=user_id)


@router.get("/xiaohongshu/user-notes")
async def xiaohongshu_user_notes(user_id: str, last_cursor: Optional[str] = None):
    client = _require_client()
    return await client.fetch_xiaohongshu_user_notes_v2(user_id=user_id, last_cursor=last_cursor)


@router.get("/channels/home")
async def channels_home(username: str, last_buffer: Optional[str] = None):
    client = _require_client()
    return await client.fetch_channels_home(username=username, last_buffer=last_buffer)


@router.get("/channels/video-detail")
async def channels_video_detail(id: Optional[str] = None, export_id: Optional[str] = None):
    if not id and not export_id:
        raise HTTPException(status_code=422, detail="Provide id or export_id")
    client = _require_client()
    return await client.fetch_channels_video_detail(video_id=id, export_id=export_id)


@router.post("/collect")
async def collect_recovery_data(payload: RecoveryCollectRequest):
    results = await collector.collect_all_accounts(
        account_ids=payload.account_ids,
        platform_filter=payload.platform,
    )
    return {"status": "success", "data": results}
