"""
Dashboard API - 为前端仪表盘提供聚合数据
"""
from fastapi import APIRouter
from fastapi_app.db.session import get_db
from datetime import datetime

router = APIRouter(tags=["Dashboard"])


@router.get("/api/dashboard")
async def get_dashboard():
    """
    获取仪表盘数据

    Returns:
        聚合的仪表盘数据，包括账号、素材、任务、发布统计
    """
    db = get_db()

    try:
        # 获取账号统计
        cursor = db.execute("SELECT COUNT(*) FROM accounts WHERE status = 'valid'")
        valid_accounts = cursor.fetchone()[0]

        # 获取素材统计
        cursor = db.execute("SELECT COUNT(*), status FROM files GROUP BY status")
        files_stats = dict(cursor.fetchall())
        total_files = sum(files_stats.values())
        pending_files = files_stats.get('pending', 0)

        # 获取任务数据
        cursor = db.execute("""
            SELECT id, title, platform, account, created_at, status, scheduled_at
            FROM publish_history
            ORDER BY created_at DESC
            LIMIT 10
        """)
        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                "id": row[0],
                "title": row[1] or "视频发布任务",
                "platform": row[2] or "未知平台",
                "account": row[3] or "未知账号",
                "createdAt": row[4] or datetime.now().isoformat(),
                "status": row[5] or "pending",
                "scheduledAt": row[6]
            })

        # 获取发布统计
        cursor = db.execute("""
            SELECT COUNT(*) FROM publish_history
            WHERE status = 'success'
        """)
        total_published = cursor.fetchone()[0]

        cursor = db.execute("""
            SELECT COUNT(*) FROM publish_history
            WHERE DATE(created_at) = DATE('now')
        """)
        todays_publish = cursor.fetchone()[0]

        cursor = db.execute("""
            SELECT COUNT(*) FROM publish_history
            WHERE status IN ('pending', 'running')
        """)
        pending_alerts = cursor.fetchone()[0]

        return {
            "code": 200,
            "msg": "success",
            "data": {
                "accounts": {
                    "total": valid_accounts,
                    "valid": valid_accounts
                },
                "materials": {
                    "total": total_files,
                    "byStatus": {
                        "pending": pending_files,
                        "published": total_files - pending_files
                    }
                },
                "publish": {
                    "totalPublished": total_published,
                    "todaysPublish": todays_publish,
                    "pendingAlerts": pending_alerts
                },
                "tasks": tasks,
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        return {
            "code": 500,
            "msg": f"Error: {str(e)}",
            "data": {
                "accounts": {"total": 0},
                "materials": {"total": 0, "byStatus": {"pending": 0}},
                "publish": {"totalPublished": 0, "todaysPublish": 0, "pendingAlerts": 0},
                "tasks": [],
                "timestamp": datetime.now().isoformat()
            }
        }


@router.get("/api/publish")
async def get_publish_meta():
    """
    获取发布相关的元数据和快捷操作

    Returns:
        发布预设、快捷操作等
    """
    return {
        "code": 200,
        "msg": "success",
        "quickActions": [
            {
                "id": "1",
                "label": "批量发布",
                "description": "选择多个素材批量发布到平台",
                "href": "/campaigns/publish",
                "accent": "from-purple-500/30 to-blue-500/30"
            },
            {
                "id": "2",
                "label": "定时任务",
                "description": "创建定时发布计划",
                "href": "/campaigns",
                "accent": "from-orange-500/30 to-pink-500/30"
            },
            {
                "id": "3",
                "label": "账号验证",
                "description": "批量验证所有账号Cookie状态",
                "href": "/account",
                "accent": "from-cyan-500/30 to-blue-500/30"
            },
            {
                "id": "4",
                "label": "数据分析",
                "description": "查看发布数据和趋势",
                "href": "/analytics",
                "accent": "from-green-500/30 to-emerald-500/30"
            }
        ]
    }
