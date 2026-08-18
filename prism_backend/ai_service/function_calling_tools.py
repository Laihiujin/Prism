"""
Function Calling 工具函数集合

定义了所有可供 AI 调用的工具函数
"""
import httpx
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger
from .function_calling_service import Tool


def _resolve_backend_cwd() -> Path:
    env_root = os.getenv("SYNAPSE_APP_ROOT") or os.getenv("SYNAPSE_RESOURCES_PATH")
    if env_root:
        root = Path(env_root).resolve()
        if root.name.lower() in {"syn_backend", "backend"}:
            return root
        for name in ("syn_backend", "backend"):
            candidate = root / name
            if candidate.exists():
                return candidate
    return Path(__file__).resolve().parents[1]


# ============================================
# 系统信息工具
# ============================================

async def get_system_info() -> Dict[str, Any]:
    """
    获取系统信息和可用资源

    Returns:
        {
            "accounts_count": int,  # 账号数量
            "videos_count": int,    # 视频数量
            "platforms": List[str]  # 可用平台
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 获取账号信息
            accounts_resp = await client.get("http://localhost:7000/api/v1/accounts/")
            accounts_data = accounts_resp.json()
            accounts_items = accounts_data.get("items") or accounts_data.get("data") or []
            accounts_count = len(accounts_items)

            # 获取视频信息
            videos_resp = await client.get("http://localhost:7000/api/v1/files/")
            videos_data = videos_resp.json()
            videos_count = len(videos_data.get("data", []))

            # 可用平台
            platforms = ["douyin", "xiaohongshu", "bilibili", "kuaishou", "xigua", "weibo"]

            return {
                "accounts_count": accounts_count,
                "videos_count": videos_count,
                "platforms": platforms
            }
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        return {"error": str(e)}


get_system_info_tool = Tool(
    name="get_system_info",
    description="获取系统信息，包括账号数量、视频数量、可用平台等",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    },
    function=get_system_info
)


# ============================================
# 账号管理工具
# ============================================

async def list_accounts(platform: Optional[str] = None) -> Dict[str, Any]:
    """
    列出所有账号

    Args:
        platform: 平台筛选（可选）

    Returns:
        {
            "accounts": List[Dict],  # 账号列表
            "total": int
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = "http://localhost:7000/api/v1/accounts/"
            if platform:
                url += f"?platform={platform}"

            resp = await client.get(url)
            data = resp.json()

            # `/api/v1/accounts/` 返回 AccountListResponse: {success,total,items}
            # 兼容旧格式 {data:[...]}
            accounts = data.get("items") or data.get("data") or []
            return {
                "accounts": accounts,
                "total": len(accounts)
            }
    except Exception as e:
        logger.error(f"列出账号失败: {e}")
        return {"error": str(e)}


list_accounts_tool = Tool(
    name="list_accounts",
    description="列出所有账号或特定平台的账号",
    parameters={
        "type": "object",
        "properties": {
            "platform": {
                "type": "string",
                "description": "平台名称（可选），如 'douyin', 'xiaohongshu' 等",
                "enum": ["douyin", "xiaohongshu", "bilibili", "kuaishou", "xigua", "weibo"]
            }
        },
        "required": []
    },
    function=list_accounts
)


# ============================================
# 素材管理工具
# ============================================

async def list_videos(limit: int = 20) -> Dict[str, Any]:
    """
    列出视频素材

    Args:
        limit: 返回数量限制

    Returns:
        {
            "videos": List[Dict],
            "total": int
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"http://localhost:7000/api/v1/files/?limit={limit}"
            )
            data = resp.json()

            # API返回格式: {"status": "success", "data": [...]}
            if data.get("status") == "success":
                videos = data.get("data", [])
                return {
                    "videos": videos,
                    "total": len(videos)
                }
            else:
                return {"error": data.get("message", "获取文件列表失败"), "videos": [], "total": 0}
    except Exception as e:
        logger.error(f"列出视频失败: {e}")
        return {"error": str(e), "videos": [], "total": 0}


list_videos_tool = Tool(
    name="list_videos",
    description="列出可用的视频素材",
    parameters={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "返回数量限制，默认 20",
                "default": 20
            }
        },
        "required": []
    },
    function=list_videos
)


# ============================================
# 发布任务工具
# ============================================

async def create_publish_task(
    account_ids: List[str],
    video_path: str,
    title: str,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    创建视频发布任务

    Args:
        account_ids: 账号 ID 列表
        video_path: 视频路径
        title: 视频标题
        description: 视频描述（可选）
        tags: 标签列表（可选）

    Returns:
        {
            "task_id": str,
            "status": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "http://localhost:7000/api/v1/tasks/publish",
                json={
                    "account_ids": account_ids,
                    "video_path": video_path,
                    "title": title,
                    "description": description or "",
                    "tags": tags or []
                }
            )
            data = resp.json()

            if data.get("success"):
                return data.get("data", {})
            else:
                return {"error": data.get("message", "创建任务失败")}
    except Exception as e:
        logger.error(f"创建发布任务失败: {e}")
        return {"error": str(e)}


create_publish_task_tool = Tool(
    name="create_publish_task",
    description="创建视频发布任务，可以批量发布到多个账号",
    parameters={
        "type": "object",
        "properties": {
            "account_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要发布的账号 ID 列表"
            },
            "video_path": {
                "type": "string",
                "description": "视频文件路径"
            },
            "title": {
                "type": "string",
                "description": "视频标题"
            },
            "description": {
                "type": "string",
                "description": "视频描述（可选）"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "标签列表（可选）"
            }
        },
        "required": ["account_ids", "video_path", "title"]
    },
    function=create_publish_task
)


# ============================================
# 任务查询工具
# ============================================

async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    查询任务状态

    Args:
        task_id: 任务 ID

    Returns:
        {
            "task_id": str,
            "status": str,
            "progress": float,
            "result": Dict
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"http://localhost:7000/api/v1/tasks/{task_id}"
            )
            data = resp.json()

            if data.get("success"):
                return data.get("data", {})
            else:
                return {"error": data.get("message", "查询任务失败")}
    except Exception as e:
        logger.error(f"查询任务状态失败: {e}")
        return {"error": str(e)}


get_task_status_tool = Tool(
    name="get_task_status",
    description="查询任务执行状态",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "任务 ID"
            }
        },
        "required": ["task_id"]
    },
    function=get_task_status
)


# ============================================
# 脚本执行工具
# ============================================

async def execute_python_script(
    script_path: str,
    args: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    执行 Python 脚本

    Args:
        script_path: 脚本路径
        args: 命令行参数（可选）

    Returns:
        {
            "returncode": int,
            "stdout": str,
            "stderr": str
        }
    """
    try:
        import subprocess
        import time

        start_time = time.time()

        backend_dir = _resolve_backend_cwd()
        cwd = str(backend_dir) if backend_dir.exists() else None
        result = subprocess.run(
            ["python", script_path] + (args or []),
            capture_output=True,
            text=True,
            timeout=300,  # 5分钟超时
            cwd=cwd,
        )

        duration = time.time() - start_time

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration": round(duration, 2)
        }
    except subprocess.TimeoutExpired:
        return {"error": "脚本执行超时（5分钟）"}
    except Exception as e:
        logger.error(f"执行脚本失败: {e}")
        return {"error": str(e)}


execute_python_script_tool = Tool(
    name="execute_python_script",
    description="执行指定的 Python 脚本",
    parameters={
        "type": "object",
        "properties": {
            "script_path": {
                "type": "string",
                "description": "脚本文件路径"
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "命令行参数列表（可选）"
            }
        },
        "required": ["script_path"]
    },
    function=execute_python_script
)


# ============================================
# 视频发布工具
# ============================================

async def publish_video_to_tencent(file_id: str, custom_title: Optional[str] = None) -> Dict[str, Any]:
    """
    发布视频到视频号（腾讯视频）
    - 如果不提供 custom_title，会使用 AI 根据文件名生成标题

    Args:
        file_id: 文件ID（从 list_videos 获取）
        custom_title: 自定义标题（可选）

    Returns:
        {
            "task_id": str,  # 任务ID
            "title": str,    # 使用的标题
            "file_path": str,  # 文件路径
            "message": str    # 结果信息
        }
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. 获取文件信息
            file_resp = await client.get(f"http://localhost:7000/api/v1/files/{file_id}")
            file_data = file_resp.json()

            if file_data.get("status") != "success":
                return {"error": "文件不存在"}

            file_info = file_data["data"]
            file_path = file_info.get("file_path") or file_info.get("path")
            filename = file_info.get("filename")

            # 2. 生成标题（如果未提供）
            if not custom_title:
                # 使用 AI 生成标题
                ai_resp = await client.post(
                    "http://localhost:7000/api/v1/ai/chat",
                    json={
                        "message": f"根据文件名生成一个吸引人的视频标题（不超过30字）：{filename}",
                        "stream": False
                    }
                )
                ai_data = ai_resp.json()
                custom_title = ai_data.get("content", filename).strip()

            # 3. 获取视频号账号
            accounts_resp = await client.get("http://localhost:8000/api/v1/accounts/?platform=tencent")
            accounts_data = accounts_resp.json()

            if not accounts_data.get("data"):
                return {"error": "没有可用的视频号账号，请先添加视频号账号"}

            account = accounts_data["data"][0]
            account_file = f"cookies/tencent_uploader/{account['id']}.json"

            # 4. 调用统一发布接口（direct）
            upload_resp = await client.post(
                "http://localhost:7000/api/v1/publish/direct",
                json={
                    "platform": 2,
                    "cookie_file": account_file,
                    "title": custom_title,
                    "file_path": file_path,
                    "tags": [],
                }
            )

            upload_data = upload_resp.json()

            if not upload_data.get("success"):
                return {"error": upload_data.get("detail", "上传失败")}

            return {
                "task_id": upload_data["data"]["task_id"],
                "title": custom_title,
                "file_path": upload_data["data"].get("file_path", file_path),
                "message": f"视频已提交发布，标题：{custom_title}"
            }

    except Exception as e:
        logger.error(f"发布视频到视频号失败: {e}")
        return {"error": str(e)}


publish_video_to_tencent_tool = Tool(
    name="publish_video_to_tencent",
    description="发布视频到视频号（腾讯视频）。会自动根据文件名生成标题，也可以指定自定义标题",
    parameters={
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "文件ID（从 list_videos 获取）"
            },
            "custom_title": {
                "type": "string",
                "description": "自定义标题（可选），如果不提供则 AI 自动生成"
            }
        },
        "required": ["file_id"]
    },
    function=publish_video_to_tencent
)


# ============================================
# 文件管理工具
# ============================================

async def search_files(keyword: Optional[str] = None, file_type: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """
    搜索文件

    Args:
        keyword: 搜索关键词（可选）
        file_type: 文件类型筛选 video/image（可选）
        limit: 返回数量限制

    Returns:
        {
            "files": List[Dict],
            "total": int
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            params = {"limit": limit}
            if keyword:
                params["keyword"] = keyword
            if file_type:
                params["file_type"] = file_type

            resp = await client.get(
                "http://localhost:7000/api/v1/files/",
                params=params
            )

            if resp.status_code != 200:
                return {"error": f"API 错误: {resp.status_code}", "files": [], "total": 0}

            data = resp.json()
            files = data.get("data", [])

            return {
                "files": [{
                    "id": f.get("id"),
                    "filename": f.get("filename"),
                    "file_type": f.get("file_type"),
                    "duration": f.get("duration"),
                    "size_mb": round(f.get("size", 0) / 1024 / 1024, 2) if f.get("size") else 0
                } for f in files],
                "total": len(files)
            }
    except Exception as e:
        logger.error(f"搜索文件失败: {e}")
        return {"error": str(e), "files": [], "total": 0}


search_files_tool = Tool(
    name="search_files",
    description="搜索视频或图片文件，可按关键词和类型筛选",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词（可选）"
            },
            "file_type": {
                "type": "string",
                "enum": ["video", "image"],
                "description": "文件类型（可选）"
            },
            "limit": {
                "type": "integer",
                "description": "返回数量限制，默认10",
                "default": 10
            }
        }
    },
    function=search_files
)


async def delete_file(file_id: str) -> Dict[str, Any]:
    """
    删除文件

    Args:
        file_id: 文件ID

    Returns:
        {
            "success": bool,
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(f"http://localhost:7000/api/v1/files/{file_id}")

            if resp.status_code != 200:
                return {"success": False, "error": f"删除失败: {resp.status_code}"}

            return {"success": True, "message": "文件已删除"}
    except Exception as e:
        logger.error(f"删除文件失败: {e}")
        return {"success": False, "error": str(e)}


delete_file_tool = Tool(
    name="delete_file",
    description="删除指定的文件",
    parameters={
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "文件ID"
            }
        },
        "required": ["file_id"]
    },
    function=delete_file
)


# ============================================
# 多平台发布工具
# ============================================

async def publish_to_multiple_platforms(
    file_id: str,
    platforms: List[str],
    title: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    发布视频到多个平台

    Args:
        file_id: 文件ID
        platforms: 平台列表 ["douyin", "xiaohongshu", "bilibili", "tencent"]
        title: 标题（可选，不提供则 AI 生成）
        description: 描述（可选）

    Returns:
        {
            "tasks": List[Dict],  # 每个平台的任务ID
            "title": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 获取文件信息
            file_resp = await client.get(f"http://localhost:7000/api/v1/files/{file_id}")
            file_data = file_resp.json()

            if file_data.get("status") != "success":
                return {"error": "文件不存在"}

            file_info = file_data["data"]
            filename = file_info.get("filename")

            # 生成标题（如果未提供）
            if not title:
                ai_resp = await client.post(
                    "http://localhost:7000/api/v1/ai/chat",
                    json={
                        "message": f"根据文件名生成一个吸引人的视频标题（不超过30字）：{filename}",
                        "stream": False
                    }
                )
                ai_data = ai_resp.json()
                title = ai_data.get("content", filename).strip()

            # 调用批量发布接口
            publish_resp = await client.post(
                "http://localhost:7000/api/v1/publish/batch",
                json={
                    "file_ids": [file_id],
                    "platforms": platforms,
                    "title": title,
                    "description": description or "",
                    "publish_time": None  # 立即发布
                }
            )

            publish_data = publish_resp.json()

            if publish_data.get("status") != "success":
                return {"error": publish_data.get("detail", "发布失败")}

            return {
                "tasks": publish_data.get("data", {}).get("task_ids", []),
                "title": title,
                "message": f"已提交到 {len(platforms)} 个平台发布"
            }

    except Exception as e:
        logger.error(f"多平台发布失败: {e}")
        return {"error": str(e)}


publish_to_multiple_platforms_tool = Tool(
    name="publish_to_multiple_platforms",
    description="发布视频到多个平台（抖音、小红书、B站、视频号）",
    parameters={
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "文件ID"
            },
            "platforms": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["douyin", "xiaohongshu", "bilibili", "tencent"]
                },
                "description": "目标平台列表"
            },
            "title": {
                "type": "string",
                "description": "标题（可选，不提供则 AI 生成）"
            },
            "description": {
                "type": "string",
                "description": "描述（可选）"
            }
        },
        "required": ["file_id", "platforms"]
    },
    function=publish_to_multiple_platforms
)


# ============================================
# 数据分析工具
# ============================================

async def get_analytics_summary(days: int = 7) -> Dict[str, Any]:
    """
    获取数据分析摘要

    Args:
        days: 统计天数，默认7天

    Returns:
        {
            "total_views": int,
            "total_likes": int,
            "total_comments": int,
            "platform_breakdown": Dict
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            from datetime import datetime, timedelta

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            resp = await client.get(
                "http://localhost:7000/api/v1/analytics/",
                params={
                    "startDate": start_date.strftime("%Y-%m-%d"),
                    "endDate": end_date.strftime("%Y-%m-%d")
                }
            )

            if resp.status_code != 200:
                return {"error": f"获取分析数据失败: {resp.status_code}"}

            data = resp.json()
            summary = data.get("summary", {})

            return {
                "total_views": summary.get("total_views", 0),
                "total_likes": summary.get("total_likes", 0),
                "total_comments": summary.get("total_comments", 0),
                "days": days,
                "message": f"最近{days}天的数据统计"
            }

    except Exception as e:
        logger.error(f"获取分析数据失败: {e}")
        return {"error": str(e)}


get_analytics_summary_tool = Tool(
    name="get_analytics_summary",
    description="获取视频数据分析摘要（播放量、点赞数、评论数等）",
    parameters={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "统计天数，默认7天",
                "default": 7
            }
        }
    },
    function=get_analytics_summary
)


# ============================================
# Phase 2: 文件管理工具扩展
# ============================================

async def upload_file(file_path: str, file_type: Optional[str] = None) -> Dict[str, Any]:
    """
    上传文件到系统

    Args:
        file_path: 文件路径
        file_type: 文件类型 (video/image)，可选

    Returns:
        {
            "file_id": str,
            "filename": str,
            "file_type": str
        }
    """
    try:
        import aiofiles
        from pathlib import Path

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return {"error": f"文件不存在: {file_path}"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with aiofiles.open(file_path, 'rb') as f:
                file_content = await f.read()

            files = {'file': (file_path_obj.name, file_content)}
            data = {}
            if file_type:
                data['file_type'] = file_type

            resp = await client.post(
                "http://localhost:7000/api/v1/files/upload",
                files=files,
                data=data
            )

            if resp.status_code != 200:
                return {"error": f"上传失败: {resp.status_code}"}

            result = resp.json()
            return result.get("data", {})

    except Exception as e:
        logger.error(f"上传文件失败: {e}")
        return {"error": str(e)}


upload_file_tool = Tool(
    name="upload_file",
    description="上传视频或图片文件到系统",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "文件路径"
            },
            "file_type": {
                "type": "string",
                "enum": ["video", "image"],
                "description": "文件类型（可选）"
            }
        },
        "required": ["file_path"]
    },
    function=upload_file
)


async def get_file_details(file_id: str) -> Dict[str, Any]:
    """
    获取文件详细信息

    Args:
        file_id: 文件ID

    Returns:
        {
            "id": str,
            "filename": str,
            "file_type": str,
            "size": int,
            "duration": float,
            "created_at": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"http://localhost:7000/api/v1/files/{file_id}")

            if resp.status_code != 200:
                return {"error": f"获取文件详情失败: {resp.status_code}"}

            data = resp.json()
            return {
                "events": data.get("events", []),
                "total": data.get("count", 0),
            }

    except Exception as e:
        logger.error(f"获取文件详情失败: {e}")
        return {"error": str(e)}


get_file_details_tool = Tool(
    name="get_file_details",
    description="获取文件的完整详细信息",
    parameters={
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "文件ID"
            }
        },
        "required": ["file_id"]
    },
    function=get_file_details
)


async def update_file(file_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新文件信息

    Args:
        file_id: 文件ID
        updates: 更新内容（可包含 title, tags, description 等）

    Returns:
        {
            "success": bool,
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"http://localhost:7000/api/v1/files/{file_id}",
                json=updates
            )

            if resp.status_code != 200:
                return {"success": False, "error": f"更新失败: {resp.status_code}"}

            return {"success": True, "message": "文件信息已更新"}

    except Exception as e:
        logger.error(f"更新文件失败: {e}")
        return {"success": False, "error": str(e)}


update_file_tool = Tool(
    name="update_file",
    description="更新文件信息（标题、标签、描述等）",
    parameters={
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "文件ID"
            },
            "updates": {
                "type": "object",
                "description": "更新内容，可包含 title, tags, description 等字段"
            }
        },
        "required": ["file_id", "updates"]
    },
    function=update_file
)


async def batch_delete_files(file_ids: List[str]) -> Dict[str, Any]:
    """
    批量删除文件

    Args:
        file_ids: 文件ID列表

    Returns:
        {
            "deleted_count": int,
            "failed_count": int
        }
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "http://localhost:7000/api/v1/files/batch-delete",
                json={"file_ids": file_ids}
            )

            if resp.status_code != 200:
                return {"error": f"批量删除失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"批量删除文件失败: {e}")
        return {"error": str(e)}


batch_delete_files_tool = Tool(
    name="batch_delete_files",
    description="批量删除多个文件",
    parameters={
        "type": "object",
        "properties": {
            "file_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要删除的文件ID列表"
            }
        },
        "required": ["file_ids"]
    },
    function=batch_delete_files
)


async def get_file_tags() -> Dict[str, Any]:
    """
    获取所有文件标签

    Returns:
        {
            "tags": List[str],
            "total": int
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("http://localhost:7000/api/v1/files/tags")

            if resp.status_code != 200:
                return {"error": f"获取标签失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"获取文件标签失败: {e}")
        return {"error": str(e)}


get_file_tags_tool = Tool(
    name="get_file_tags",
    description="获取系统中所有的文件标签列表",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    },
    function=get_file_tags
)


async def add_file_tags(file_id: str, tags: List[str]) -> Dict[str, Any]:
    """
    为文件添加标签

    Args:
        file_id: 文件ID
        tags: 标签列表

    Returns:
        {
            "success": bool,
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"http://localhost:7000/api/v1/files/{file_id}/tags",
                json={"tags": tags}
            )

            if resp.status_code != 200:
                return {"success": False, "error": f"添加标签失败: {resp.status_code}"}

            return {"success": True, "message": "标签已添加"}

    except Exception as e:
        logger.error(f"添加文件标签失败: {e}")
        return {"success": False, "error": str(e)}


add_file_tags_tool = Tool(
    name="add_file_tags",
    description="为文件添加标签，方便分类",
    parameters={
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "文件ID"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "标签列表"
            }
        },
        "required": ["file_id", "tags"]
    },
    function=add_file_tags
)


# ============================================
# Phase 2: 发布管理工具扩展
# ============================================

async def get_publish_presets() -> Dict[str, Any]:
    """
    获取所有发布预设

    Returns:
        {
            "presets": List[Dict],
            "total": int
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("http://localhost:7000/api/v1/publish/presets")

            if resp.status_code != 200:
                return {"error": f"获取预设失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"获取发布预设失败: {e}")
        return {"error": str(e)}


get_publish_presets_tool = Tool(
    name="get_publish_presets",
    description="获取所有保存的发布预设配置",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    },
    function=get_publish_presets
)


async def create_preset(name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    创建发布预设

    Args:
        name: 预设名称
        config: 预设配置（包含平台、标题模板等）

    Returns:
        {
            "preset_id": str,
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "http://localhost:7000/api/v1/publish/presets",
                json={"name": name, "config": config}
            )

            if resp.status_code != 200:
                return {"error": f"创建预设失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"创建发布预设失败: {e}")
        return {"error": str(e)}


create_preset_tool = Tool(
    name="create_preset",
    description="创建发布预设配置，方便快速发布",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "预设名称"
            },
            "config": {
                "type": "object",
                "description": "预设配置，包含平台、标题模板等信息"
            }
        },
        "required": ["name", "config"]
    },
    function=create_preset
)


async def delete_preset(preset_id: str) -> Dict[str, Any]:
    """
    删除发布预设

    Args:
        preset_id: 预设ID

    Returns:
        {
            "success": bool,
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"http://localhost:7000/api/v1/publish/presets/{preset_id}"
            )

            if resp.status_code != 200:
                return {"success": False, "error": f"删除预设失败: {resp.status_code}"}

            return {"success": True, "message": "预设已删除"}

    except Exception as e:
        logger.error(f"删除发布预设失败: {e}")
        return {"success": False, "error": str(e)}


delete_preset_tool = Tool(
    name="delete_preset",
    description="删除发布预设",
    parameters={
        "type": "object",
        "properties": {
            "preset_id": {
                "type": "string",
                "description": "预设ID"
            }
        },
        "required": ["preset_id"]
    },
    function=delete_preset
)


async def apply_preset(preset_id: str, file_ids: List[str]) -> Dict[str, Any]:
    """
    应用发布预设

    Args:
        preset_id: 预设ID
        file_ids: 文件ID列表

    Returns:
        {
            "task_ids": List[str],
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"http://localhost:7000/api/v1/publish/presets/{preset_id}/apply",
                json={"file_ids": file_ids}
            )

            if resp.status_code != 200:
                return {"error": f"应用预设失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"应用发布预设失败: {e}")
        return {"error": str(e)}


apply_preset_tool = Tool(
    name="apply_preset",
    description="使用预设配置快速发布视频",
    parameters={
        "type": "object",
        "properties": {
            "preset_id": {
                "type": "string",
                "description": "预设ID"
            },
            "file_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要发布的文件ID列表"
            }
        },
        "required": ["preset_id", "file_ids"]
    },
    function=apply_preset
)


async def get_otp_events() -> Dict[str, Any]:
    """
    获取验证码事件

    Returns:
        {
            "events": List[Dict],
            "total": int
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("http://localhost:7000/api/v1/verification/otp-events")

            if resp.status_code != 200:
                return {"error": f"获取验证码事件失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"获取验证码事件失败: {e}")
        return {"error": str(e)}


get_otp_events_tool = Tool(
    name="get_otp_events",
    description="获取当前需要输入验证码的发布事件",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    },
    function=get_otp_events
)


async def batch_publish(
    file_ids: List[str],
    platforms: List[str],
    title: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    批量发布多个视频到多个平台

    Args:
        file_ids: 文件ID列表
        platforms: 平台列表
        title: 标题（可选）
        description: 描述（可选）

    Returns:
        {
            "task_ids": List[str],
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "http://localhost:7000/api/v1/publish/batch",
                json={
                    "file_ids": file_ids,
                    "platforms": platforms,
                    "title": title,
                    "description": description
                }
            )

            if resp.status_code != 200:
                return {"error": f"批量发布失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"批量发布失败: {e}")
        return {"error": str(e)}


batch_publish_tool = Tool(
    name="batch_publish",
    description="批量发布多个视频到多个平台",
    parameters={
        "type": "object",
        "properties": {
            "file_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "文件ID列表"
            },
            "platforms": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["douyin", "xiaohongshu", "bilibili", "tencent", "kuaishou", "xigua", "weibo"]
                },
                "description": "目标平台列表"
            },
            "title": {
                "type": "string",
                "description": "标题（可选）"
            },
            "description": {
                "type": "string",
                "description": "描述（可选）"
            }
        },
        "required": ["file_ids", "platforms"]
    },
    function=batch_publish
)


# ============================================
# Phase 2: 平台登录工具
# ============================================

async def platform_login(platform: str, credentials: Dict[str, str]) -> Dict[str, Any]:
    """
    平台登录

    Args:
        platform: 平台名称
        credentials: 登录凭据（username, password等）

    Returns:
        {
            "session_id": str,
            "status": str,
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"http://localhost:7000/api/v1/platforms/{platform}/login",
                json=credentials
            )

            if resp.status_code != 200:
                return {"error": f"登录失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"平台登录失败: {e}")
        return {"error": str(e)}


platform_login_tool = Tool(
    name="platform_login",
    description="通过自动化方式登录社交平台",
    parameters={
        "type": "object",
        "properties": {
            "platform": {
                "type": "string",
                "enum": ["douyin", "xiaohongshu", "bilibili", "tencent", "kuaishou", "xigua", "weibo"],
                "description": "平台名称"
            },
            "credentials": {
                "type": "object",
                "description": "登录凭据，包含 username, password 等"
            }
        },
        "required": ["platform", "credentials"]
    },
    function=platform_login
)


async def verify_cookie(platform: str, cookie_data: str) -> Dict[str, Any]:
    """
    验证Cookie

    Args:
        platform: 平台名称
        cookie_data: Cookie数据

    Returns:
        {
            "valid": bool,
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"http://localhost:7000/api/v1/platforms/{platform}/verify-cookie",
                json={"cookie_data": cookie_data}
            )

            if resp.status_code != 200:
                return {"error": f"验证失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"验证Cookie失败: {e}")
        return {"error": str(e)}


verify_cookie_tool = Tool(
    name="verify_cookie",
    description="验证平台Cookie是否有效",
    parameters={
        "type": "object",
        "properties": {
            "platform": {
                "type": "string",
                "enum": ["douyin", "xiaohongshu", "bilibili", "tencent", "kuaishou", "xigua", "weibo"],
                "description": "平台名称"
            },
            "cookie_data": {
                "type": "string",
                "description": "Cookie数据"
            }
        },
        "required": ["platform", "cookie_data"]
    },
    function=verify_cookie
)


async def get_login_status(session_id: str) -> Dict[str, Any]:
    """
    获取登录状态

    Args:
        session_id: 会话ID

    Returns:
        {
            "status": str,
            "progress": int,
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"http://localhost:7000/api/v1/platforms/login/status?session_id={session_id}"
            )

            if resp.status_code != 200:
                return {"error": f"获取状态失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"获取登录状态失败: {e}")
        return {"error": str(e)}


get_login_status_tool = Tool(
    name="get_login_status",
    description="查询平台登录会话的进度和状态",
    parameters={
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "会话ID"
            }
        },
        "required": ["session_id"]
    },
    function=get_login_status
)


async def start_login_session(platform: str, account_id: str) -> Dict[str, Any]:
    """
    启动登录会话

    Args:
        platform: 平台名称
        account_id: 账号ID

    Returns:
        {
            "session_id": str,
            "status": str,
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "http://localhost:7000/api/v1/platforms/login/start",
                json={"platform": platform, "account_id": account_id}
            )

            if resp.status_code != 200:
                return {"error": f"启动登录失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"启动登录会话失败: {e}")
        return {"error": str(e)}


start_login_session_tool = Tool(
    name="start_login_session",
    description="启动平台登录流程",
    parameters={
        "type": "object",
        "properties": {
            "platform": {
                "type": "string",
                "enum": ["douyin", "xiaohongshu", "bilibili", "tencent", "kuaishou", "xigua", "weibo"],
                "description": "平台名称"
            },
            "account_id": {
                "type": "string",
                "description": "账号ID"
            }
        },
        "required": ["platform", "account_id"]
    },
    function=start_login_session
)


# ============================================
# Phase 3: 矩阵发布工具
# ============================================

async def create_matrix_task(
    platforms: List[str],
    account_ids: List[str],
    material_ids: List[str],
    title: Optional[str] = None,
    description: Optional[str] = None,
    batch_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建矩阵发布任务

    支持多平台、多账号、多素材的组合发布

    Args:
        platforms: 平台列表
        account_ids: 账号ID列表
        material_ids: 素材ID列表
        title: 标题（可选）
        description: 描述（可选）
        batch_name: 批次名称（可选）

    Returns:
        {
            "count": int,
            "batch_id": str,
            "tasks": List[Dict]
        }
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "http://localhost:7000/api/v1/matrix/generate_tasks",
                json={
                    "platforms": platforms,
                    "accounts": account_ids,
                    "materials": material_ids,
                    "title": title,
                    "description": description,
                    "batch_name": batch_name
                }
            )

            if resp.status_code != 200:
                return {"error": f"创建矩阵任务失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"创建矩阵任务失败: {e}")
        return {"error": str(e)}


create_matrix_task_tool = Tool(
    name="create_matrix_task",
    description="创建矩阵发布任务，支持多平台、多账号、多素材的批量发布",
    parameters={
        "type": "object",
        "properties": {
            "platforms": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["douyin", "xiaohongshu", "bilibili", "tencent", "kuaishou", "xigua", "weibo"]
                },
                "description": "平台列表"
            },
            "account_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "账号ID列表"
            },
            "material_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "素材ID列表"
            },
            "title": {
                "type": "string",
                "description": "标题（可选）"
            },
            "description": {
                "type": "string",
                "description": "描述（可选）"
            },
            "batch_name": {
                "type": "string",
                "description": "批次名称（可选）"
            }
        },
        "required": ["platforms", "account_ids", "material_ids"]
    },
    function=create_matrix_task
)


async def get_matrix_tasks(status: Optional[str] = None) -> Dict[str, Any]:
    """
    获取矩阵任务列表

    Args:
        status: 状态筛选 (pending/running/success/failed/retry)

    Returns:
        {
            "tasks": List[Dict],
            "total": int
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = "http://localhost:7000/api/v1/matrix/tasks"
            if status:
                url += f"?status={status}"

            resp = await client.get(url)

            if resp.status_code != 200:
                return {"error": f"获取矩阵任务失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"获取矩阵任务失败: {e}")
        return {"error": str(e)}


get_matrix_tasks_tool = Tool(
    name="get_matrix_tasks",
    description="获取矩阵发布任务列表",
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["pending", "running", "success", "failed", "retry"],
                "description": "状态筛选（可选）"
            }
        },
        "required": []
    },
    function=get_matrix_tasks
)


async def get_matrix_statistics() -> Dict[str, Any]:
    """
    获取矩阵发布统计信息

    Returns:
        {
            "total": int,
            "pending": int,
            "running": int,
            "success": int,
            "failed": int
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("http://localhost:7000/api/v1/matrix/stats")

            if resp.status_code != 200:
                return {"error": f"获取统计信息失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"获取矩阵统计失败: {e}")
        return {"error": str(e)}


get_matrix_statistics_tool = Tool(
    name="get_matrix_statistics",
    description="获取矩阵发布的统计信息",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    },
    function=get_matrix_statistics
)


# ============================================
# Phase 3: 账号管理扩展
# ============================================

async def get_account_details(account_id: str) -> Dict[str, Any]:
    """
    获取账号详细信息

    Args:
        account_id: 账号ID

    Returns:
        {
            "id": str,
            "name": str,
            "platform": str,
            "status": str,
            "cookie_status": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"http://localhost:7000/api/v1/accounts/{account_id}")

            if resp.status_code != 200:
                return {"error": f"获取账号详情失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"获取账号详情失败: {e}")
        return {"error": str(e)}


get_account_details_tool = Tool(
    name="get_account_details",
    description="获取账号的详细信息",
    parameters={
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "账号ID"
            }
        },
        "required": ["account_id"]
    },
    function=get_account_details
)


async def create_account(
    platform: str,
    name: str,
    cookie_data: str,
    note: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建账号

    Args:
        platform: 平台名称
        name: 账号名称
        cookie_data: Cookie数据
        note: 备注（可选）

    Returns:
        {
            "account_id": str,
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "http://localhost:7000/api/v1/accounts/",
                json={
                    "platform": platform,
                    "name": name,
                    "cookie_data": cookie_data,
                    "note": note
                }
            )

            if resp.status_code not in [200, 201]:
                return {"error": f"创建账号失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"创建账号失败: {e}")
        return {"error": str(e)}


create_account_tool = Tool(
    name="create_account",
    description="创建新账号",
    parameters={
        "type": "object",
        "properties": {
            "platform": {
                "type": "string",
                "enum": ["douyin", "xiaohongshu", "bilibili", "tencent", "kuaishou", "xigua", "weibo"],
                "description": "平台名称"
            },
            "name": {
                "type": "string",
                "description": "账号名称"
            },
            "cookie_data": {
                "type": "string",
                "description": "Cookie数据"
            },
            "note": {
                "type": "string",
                "description": "备注（可选）"
            }
        },
        "required": ["platform", "name", "cookie_data"]
    },
    function=create_account
)


async def update_account(account_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新账号信息

    Args:
        account_id: 账号ID
        updates: 更新内容（可包含 name, note, status 等）

    Returns:
        {
            "success": bool,
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"http://localhost:7000/api/v1/accounts/{account_id}",
                json=updates
            )

            if resp.status_code != 200:
                return {"success": False, "error": f"更新账号失败: {resp.status_code}"}

            return {"success": True, "message": "账号信息已更新"}

    except Exception as e:
        logger.error(f"更新账号失败: {e}")
        return {"success": False, "error": str(e)}


update_account_tool = Tool(
    name="update_account",
    description="更新账号信息",
    parameters={
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "账号ID"
            },
            "updates": {
                "type": "object",
                "description": "更新内容，可包含 name, note, status 等字段"
            }
        },
        "required": ["account_id", "updates"]
    },
    function=update_account
)


async def delete_account(account_id: str) -> Dict[str, Any]:
    """
    删除账号

    Args:
        account_id: 账号ID

    Returns:
        {
            "success": bool,
            "message": str
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(f"http://localhost:7000/api/v1/accounts/{account_id}")

            if resp.status_code != 200:
                return {"success": False, "error": f"删除账号失败: {resp.status_code}"}

            return {"success": True, "message": "账号已删除"}

    except Exception as e:
        logger.error(f"删除账号失败: {e}")
        return {"success": False, "error": str(e)}


delete_account_tool = Tool(
    name="delete_account",
    description="删除账号",
    parameters={
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "账号ID"
            }
        },
        "required": ["account_id"]
    },
    function=delete_account
)


async def sync_account_info(account_id: str) -> Dict[str, Any]:
    """
    同步账号信息

    从平台同步账号的最新信息（头像、昵称等）

    Args:
        account_id: 账号ID

    Returns:
        {
            "success": bool,
            "message": str,
            "updated_fields": List[str]
        }
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"http://localhost:7000/api/v1/accounts/{account_id}/sync"
            )

            if resp.status_code != 200:
                return {"success": False, "error": f"同步失败: {resp.status_code}"}

            data = resp.json()
            return data.get("data", {})

    except Exception as e:
        logger.error(f"同步账号信息失败: {e}")
        return {"success": False, "error": str(e)}


sync_account_info_tool = Tool(
    name="sync_account_info",
    description="从平台同步账号的最新信息",
    parameters={
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "账号ID"
            }
        },
        "required": ["account_id"]
    },
    function=sync_account_info
)


# ============================================
# 工具集合
# ============================================

ALL_TOOLS = [
    # 系统信息
    get_system_info_tool,

    # 账号管理 (Phase 1)
    list_accounts_tool,

    # 账号管理 (Phase 3)
    get_account_details_tool,
    create_account_tool,
    update_account_tool,
    delete_account_tool,
    sync_account_info_tool,

    # 文件管理 (Phase 1)
    list_videos_tool,
    search_files_tool,
    delete_file_tool,

    # 文件管理 (Phase 2)
    upload_file_tool,
    get_file_details_tool,
    update_file_tool,
    batch_delete_files_tool,
    get_file_tags_tool,
    add_file_tags_tool,

    # 发布任务 (Phase 1)
    create_publish_task_tool,
    get_task_status_tool,
    publish_video_to_tencent_tool,
    publish_to_multiple_platforms_tool,

    # 发布管理 (Phase 2)
    get_publish_presets_tool,
    create_preset_tool,
    delete_preset_tool,
    apply_preset_tool,
    get_otp_events_tool,
    batch_publish_tool,

    # 矩阵发布 (Phase 3)
    create_matrix_task_tool,
    get_matrix_tasks_tool,
    get_matrix_statistics_tool,

    # 平台登录 (Phase 2)
    platform_login_tool,
    verify_cookie_tool,
    get_login_status_tool,
    start_login_session_tool,

    # 数据分析
    get_analytics_summary_tool,

    # 脚本执行
    execute_python_script_tool,
]
