"""
数据抓取路由
提供视频、用户、评论等数据的抓取接口
"""
from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from pydantic import BaseModel, Field
from myUtils.data_crawler_service import get_data_crawler_service
from fastapi_app.core.config import settings
from pathlib import Path

router = APIRouter(prefix="/data", tags=["data"])


class CollectRequest(BaseModel):
    account_ids: Optional[List[str]] = Field(None, description="可选：指定账号ID列表")
    platform: Optional[str] = Field(None, description="可选：指定平台过滤器")


@router.get("/health")
async def data_health():
    """健康检查"""
    return {"status": "success", "message": "data module ready"}


def _db_path() -> Path:
    return Path(settings.BASE_DIR) / "db" / "database.db"


@router.post("/collect", summary="全量采集数据并回传到数据库")
async def trigger_collect(payload: CollectRequest):
    """
    手动触发作品数据全量采集。
    使用各平台已存 Cookie 访问助手后台，通过 Playwright/DOM/XPath 抓取数据并持久化。
    """
    try:
        from myUtils.video_collector import collector
        results = await collector.collect_all_accounts(
            account_ids=payload.account_ids,
            platform_filter=payload.platform
        )

        return {"status": "success", "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 通用数据抓取 ====================

@router.get("/video/parse")
async def parse_video_url(
    url: str = Query(..., description="视频URL，支持抖音/B站/小红书/快手")
):
    """
    根据URL解析视频信息（支持多平台）

    Args:
        url: 视频URL

    Returns:
        视频信息
    """
    try:
        crawler = get_data_crawler_service()
        result = await crawler.fetch_video_by_url(url)

        if result.get("success"):
            return {
                "status": "success",
                "data": result.get("data"),
                "platform": result.get("platform"),
                "message": "视频信息解析成功"
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "视频信息解析失败")
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


