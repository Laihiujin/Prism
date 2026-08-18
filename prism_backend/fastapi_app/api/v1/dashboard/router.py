from fastapi import APIRouter, HTTPException, Request, Query
from myUtils.cookie_manager import cookie_manager
from fastapi_app.core.config import settings
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import json
from fastapi_app.db.runtime import mysql_enabled, sa_connection
from sqlalchemy import text
from fastapi_app.cache.redis_client import get_redis

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])

DB_PATH = Path(settings.DATABASE_PATH)

@router.get("/", summary="获取仪表盘数据")
async def get_dashboard_root():
    """获取仪表盘数据（兼容根路径调用）"""
    return await get_dashboard_stats()

@router.get("/stats", summary="获取仪表盘统计数据")
async def get_dashboard_stats():
    """获取账号、素材、发布任务的统计数据"""
    try:
        r = get_redis()
        cache_key = "dashboard:stats:v1"
        if r is not None:
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)

        # 获取账号统计
        accounts = cookie_manager.list_flat_accounts()
        total_accounts = len(accounts)

        # 按状态分组
        status_counts = {"valid": 0, "expired": 0, "error": 0, "file_missing": 0, "unknown": 0}
        for acc in accounts:
            status = acc.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1

        # 按平台分组
        platform_counts = {}
        for acc in accounts:
            platform = acc.get('platform', 'unknown')
            platform_counts[platform] = platform_counts.get(platform, 0) + 1

        # 获取素材/任务统计
        if mysql_enabled():
            with sa_connection() as conn:
                # total_materials / status breakdown
                total_materials = conn.execute(text("SELECT COUNT(*) AS c FROM file_records")).mappings().one()["c"]
                material_rows = conn.execute(text("SELECT status, COUNT(*) AS c FROM file_records GROUP BY status")).mappings().all()
                material_status = {row["status"]: row["c"] for row in material_rows if row.get("status") is not None}
                last_upload_row = conn.execute(text("SELECT MAX(upload_time) AS t FROM file_records")).mappings().one()
                last_upload = last_upload_row.get("t")

                todays_publish = conn.execute(
                    text("SELECT COUNT(*) AS c FROM publish_tasks WHERE date(created_at) = date(now()) AND status = 'success'")
                ).mappings().one()["c"]
                pending_alerts = conn.execute(
                    text("SELECT COUNT(*) AS c FROM publish_tasks WHERE status = 'error'")
                ).mappings().one()["c"]
        else:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                # 确保表存在（file_records 会被 files/publish API 使用，必须包含 status 等字段）
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS file_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT,
                        filesize REAL,
                        file_path TEXT,
                        upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'pending',
                        published_at DATETIME,
                        last_platform INTEGER,
                        last_accounts TEXT,
                        note TEXT,
                        group_name TEXT
                    )
                """)

                # 兼容旧库：缺字段则补齐
                cursor.execute("PRAGMA table_info(file_records)")
                cols = {row[1] for row in cursor.fetchall()}
                if "status" not in cols:
                    cursor.execute("ALTER TABLE file_records ADD COLUMN status TEXT DEFAULT 'pending'")
                if "note" not in cols:
                    cursor.execute("ALTER TABLE file_records ADD COLUMN note TEXT")
                if "group_name" not in cols:
                    cursor.execute("ALTER TABLE file_records ADD COLUMN group_name TEXT")
                conn.commit()

                # 总素材数
                cursor.execute("SELECT COUNT(*) FROM file_records")
                total_materials = cursor.fetchone()[0]

                # 按状态分组
                cursor.execute("SELECT status, COUNT(*) FROM file_records GROUP BY status")
                material_status = {row[0]: row[1] for row in cursor.fetchall()}

                # 最近上传时间
                cursor.execute("SELECT MAX(upload_time) FROM file_records")
                last_upload_row = cursor.fetchone()
                last_upload = last_upload_row[0] if last_upload_row else None

                # 发布任务统计
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS publish_tasks (
                        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        platform TEXT,
                        account_id TEXT,
                        material_id TEXT,
                        title TEXT,
                        tags TEXT,
                        schedule_time TEXT,
                        status TEXT,
                        error_message TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("SELECT COUNT(*) FROM publish_tasks WHERE date(created_at) = date('now','localtime') AND status = 'success'")
                todays_publish = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM publish_tasks WHERE status = 'error'")
                pending_alerts = cursor.fetchone()[0]

        result = {
            "success": True,
            "data": {
                "accounts": {
                    "total": total_accounts,
                    "by_status": status_counts,
                    "by_platform": platform_counts
                },
                "materials": {
                    "total": total_materials,
                    "by_status": material_status,
                    "last_upload": last_upload
                },
                "publish": {
                    "todays_publish": todays_publish,
                    "pending_alerts": pending_alerts
                }
            }
        }
        if r is not None:
            try:
                r.setex(cache_key, 5, json.dumps(result, ensure_ascii=False))
            except Exception:
                pass
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview", summary="获取仪表盘概览")
async def get_dashboard_overview(request: Request):
    """
    获取完整的仪表盘概览数据
    包含任务队列状态、最近发布记录、账号健康状态等
    """
    try:
        # 获取任务管理器
        tm = getattr(request.app.state, "task_manager", None)

        # 基础统计
        stats_response = await get_dashboard_stats()
        base_stats = stats_response["data"]

        # 任务队列统计
        task_stats = {}
        recent_tasks = []
        if tm:
            task_stats = tm.get_queue_stats() if hasattr(tm, "get_queue_stats") else {}
            tasks = tm.list_tasks(limit=500) if hasattr(tm, "list_tasks") else []

            # 计算任务状态分布
            task_summary = {
                "pending": 0,
                "running": 0,
                "success": 0,
                "failed": 0,
                "retry": 0,
                "total": len(tasks)
            }

            for task in tasks:
                status = (task.get("status") or "").lower()
                if status in task_summary:
                    task_summary[status] += 1
                elif status == "cancelled":
                    pass  # 可选：添加cancelled统计

            task_stats["summary"] = task_summary

            # 最近10个任务
            recent_tasks = tasks[:10]

        # 最近发布记录
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 最近发布记录
            cursor.execute("""
                SELECT
                    task_id,
                    platform,
                    account_id,
                    title,
                    status,
                    error_message,
                    created_at,
                    updated_at
                FROM publish_tasks
                ORDER BY created_at DESC
                LIMIT 20
            """)
            recent_publishes = [dict(row) for row in cursor.fetchall()]

            # 平台发布分布（今日）
            cursor.execute("""
                SELECT platform, COUNT(*) as count
                FROM publish_tasks
                WHERE date(created_at) = date('now','localtime')
                AND status = 'success'
                GROUP BY platform
            """)
            platform_distribution = {row[0]: row[1] for row in cursor.fetchall()}

            # 过去7天发布趋势
            cursor.execute("""
                SELECT
                    date(created_at) as date,
                    COUNT(*) as count
                FROM publish_tasks
                WHERE created_at >= date('now', '-7 days')
                AND status = 'success'
                GROUP BY date(created_at)
                ORDER BY date ASC
            """)
            publish_trend = [{"date": row[0], "count": row[1]} for row in cursor.fetchall()]

        return {
            "success": True,
            "data": {
                **base_stats,
                "tasks": {
                    "stats": task_stats,
                    "recent": recent_tasks
                },
                "recent_publishes": recent_publishes,
                "platform_distribution": platform_distribution,
                "publish_trend_7days": publish_trend,
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/summary", summary="任务队列摘要")
async def get_tasks_summary(request: Request):
    """获取任务队列摘要统计"""
    try:
        tm = getattr(request.app.state, "task_manager", None)
        if not tm:
            return {
                "success": False,
                "message": "任务队列服务未启用",
                "data": None
            }

        tasks = tm.list_tasks(limit=1000) if hasattr(tm, "list_tasks") else []

        summary = {
            "pending": 0,
            "running": 0,
            "success": 0,
            "failed": 0,
            "retry": 0,
            "cancelled": 0,
            "total": len(tasks)
        }

        for task in tasks:
            status = (task.get("status") or "").lower()
            if status in summary:
                summary[status] += 1

        # 按任务类型统计
        by_type = {}
        for task in tasks:
            task_type = task.get("task_type", "unknown")
            by_type[task_type] = by_type.get(task_type, 0) + 1

        return {
            "success": True,
            "data": {
                "summary": summary,
                "by_type": by_type,
                "queue_stats": tm.get_queue_stats() if hasattr(tm, "get_queue_stats") else {}
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", summary="系统健康检查")
async def health_check(request: Request):
    """
    系统健康检查
    检查各个组件的运行状态
    """
    try:
        health_status = {
            "overall": "healthy",
            "components": {}
        }

        # 检查数据库
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                health_status["components"]["database"] = "healthy"
        except Exception as e:
            health_status["components"]["database"] = f"unhealthy: {str(e)}"
            health_status["overall"] = "degraded"

        # 检查任务队列
        tm = getattr(request.app.state, "task_manager", None)
        if tm:
            health_status["components"]["task_queue"] = "healthy"
        else:
            health_status["components"]["task_queue"] = "not_enabled"

        # 检查账号管理器
        try:
            accounts = cookie_manager.list_flat_accounts()
            health_status["components"]["account_manager"] = "healthy"
            health_status["components"]["account_count"] = len(accounts)
        except Exception as e:
            health_status["components"]["account_manager"] = f"unhealthy: {str(e)}"
            health_status["overall"] = "degraded"

        return {
            "success": True,
            "data": health_status,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
