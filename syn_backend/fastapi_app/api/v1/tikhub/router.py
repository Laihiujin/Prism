from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from myUtils.tikhub_client import get_tikhub_client
from myUtils.video_collector import collector

router = APIRouter(prefix="/tikhub", tags=["tikhub"])


class TikHubCollectRequest(BaseModel):
    account_ids: Optional[List[str]] = Field(None, description="Optional account IDs to collect")
    platform: Optional[str] = Field(None, description="Optional platform filter: kuaishou/xiaohongshu/channels")


@router.get("/health", summary="Check TikHub configuration")
async def tikhub_health():
    client = get_tikhub_client()
    return {
        "status": "success",
        "configured": bool(client),
        "message": "TikHub API key configured" if client else "TikHub API key not configured",
    }


@router.post("/collect", summary="Collect account videos via TikHub (with fallback)")
async def collect_videos_via_tikhub(payload: TikHubCollectRequest):
    client = get_tikhub_client()
    if not client:
        raise HTTPException(status_code=400, detail="TikHub API key not configured")

    results = await collector.collect_all_accounts(
        account_ids=payload.account_ids,
        platform_filter=payload.platform,
    )
    return {"status": "success", "data": results}
