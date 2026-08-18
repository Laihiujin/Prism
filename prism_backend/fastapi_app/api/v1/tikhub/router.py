from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from myUtils.tikhub_client import get_tikhub_client

router = APIRouter(prefix="/tikhub", tags=["tikhub"])


class TikHubCollectRequest(BaseModel):
    account_ids: Optional[List[str]] = Field(None, description="Optional account IDs to collect")
    platform: Optional[str] = Field(None, description="Optional platform filter: kuaishou/xiaohongshu/channels")


def _require_client():
    client = get_tikhub_client()
    if not client:
        raise HTTPException(status_code=400, detail="TikHub API key not configured")
    return client


@router.get("/health", summary="Check TikHub configuration")
async def tikhub_health():
    client = get_tikhub_client()
    return {
        "status": "success",
        "configured": bool(client),
        "message": "TikHub API key configured" if client else "TikHub API key not configured",
    }


@router.get("/kuaishou/user-info", summary="Fetch Kuaishou user info via TikHub")
async def kuaishou_user_info(user_id: str):
    client = _require_client()
    return await client.fetch_kuaishou_user_info(user_id=user_id)


@router.get("/kuaishou/user-posts", summary="Fetch Kuaishou user posts via TikHub")
async def kuaishou_user_posts(user_id: str, pcursor: Optional[str] = None):
    client = _require_client()
    return await client.fetch_kuaishou_user_posts(user_id=user_id, pcursor=pcursor)


@router.get("/kuaishou/video", summary="Fetch Kuaishou video detail via TikHub")
async def kuaishou_video(share_text: str):
    client = _require_client()
    return await client.fetch_kuaishou_video_by_share_text(share_text=share_text)


@router.get("/kuaishou/video-by-url", summary="Fetch Kuaishou video by URL via TikHub")
async def kuaishou_video_by_url(url: str):
    client = _require_client()
    return await client.fetch_kuaishou_video_by_url(url=url)


@router.get("/xiaohongshu/user-info", summary="Fetch Xiaohongshu user info via TikHub")
async def xiaohongshu_user_info(user_id: str):
    client = _require_client()
    return await client.fetch_xiaohongshu_user_info(user_id=user_id)


@router.get("/xiaohongshu/user-notes", summary="Fetch Xiaohongshu user notes via TikHub")
async def xiaohongshu_user_notes(user_id: str, last_cursor: Optional[str] = None):
    client = _require_client()
    return await client.fetch_xiaohongshu_user_notes_v2(user_id=user_id, last_cursor=last_cursor)


@router.get("/xiaohongshu/note-id", summary="Extract Xiaohongshu note id and xsec_token via TikHub")
async def xiaohongshu_note_id(url: str):
    client = _require_client()
    return await client.fetch_xiaohongshu_note_id_and_xsec_token(url=url)


@router.get("/wechat-channels/home", summary="Fetch WeChat Channels home page via TikHub")
async def wechat_channels_home(username: str, last_buffer: Optional[str] = None):
    client = _require_client()
    return await client.fetch_channels_home(username=username, last_buffer=last_buffer)


@router.get("/wechat-channels/video-detail", summary="Fetch WeChat Channels video detail via TikHub")
async def wechat_channels_video_detail(id: Optional[str] = None, export_id: Optional[str] = None):
    if not id and not export_id:
        raise HTTPException(status_code=422, detail="Provide id or export_id")
    client = _require_client()
    return await client.fetch_channels_video_detail(video_id=id, export_id=export_id)


@router.post("/collect", summary="Collect account videos via TikHub (with fallback)")
async def collect_videos_via_tikhub(payload: TikHubCollectRequest):
    client = get_tikhub_client()
    if not client:
        raise HTTPException(status_code=400, detail="TikHub API key not configured")

    from myUtils.video_collector import collector

    results = await collector.collect_all_accounts(
        account_ids=payload.account_ids,
        platform_filter=payload.platform,
    )
    return {"status": "success", "data": results}
