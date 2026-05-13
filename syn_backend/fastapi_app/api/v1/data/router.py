"""
数据抓取路由
提供视频、用户、评论等数据的抓取接口
"""
import importlib
import sqlite3

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from pydantic import BaseModel, Field
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


def _count_rows(cursor: sqlite3.Cursor, table: str, where: str = "", params: tuple = ()) -> int:
    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,))
    if not cursor.fetchone():
        return 0
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql += f" WHERE {where}"
    cursor.execute(sql, params)
    return int(cursor.fetchone()[0] or 0)


def _get_data_crawler_service():
    module = importlib.import_module("myUtils.data_crawler_service")
    return getattr(module, "get_data_crawler_service")


@router.get("/center")
async def data_center_summary():
    db_path = _db_path()
    totals = {
        "videos": 0,
        "materials": 0,
        "accounts": 0,
        "publish_tasks": 0,
    }
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            totals["videos"] = _count_rows(cursor, "video_analytics")
            totals["materials"] = _count_rows(cursor, "file_records")
            totals["accounts"] = _count_rows(cursor, "accounts")
            totals["publish_tasks"] = _count_rows(cursor, "publish_tasks")

    return {"status": "success", "data": {"totals": totals}}


@router.get("/videos")
async def data_videos(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    db_path = _db_path()
    items = []
    total = 0
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'video_analytics'")
            if cursor.fetchone():
                total = _count_rows(cursor, "video_analytics")
                cursor.execute("SELECT * FROM video_analytics LIMIT ? OFFSET ?", (limit, offset))
                items = [dict(row) for row in cursor.fetchall()]

    return {"status": "success", "items": items, "total": total}


@router.get("/trends")
async def data_trends():
    return {"status": "success", "series": []}


@router.get("/publish-status")
async def data_publish_status():
    db_path = _db_path()
    stats = {"total": 0, "published": 0, "pending": 0, "failed": 0}
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            stats["total"] = _count_rows(cursor, "publish_tasks")
            stats["published"] = _count_rows(cursor, "publish_tasks", "status IN (?, ?)", ("published", "success"))
            stats["pending"] = _count_rows(cursor, "publish_tasks", "status = ?", ("pending",))
            stats["failed"] = _count_rows(cursor, "publish_tasks", "status = ?", ("failed",))

    return {"status": "success", "data": stats}


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
        crawler = _get_data_crawler_service()()
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


