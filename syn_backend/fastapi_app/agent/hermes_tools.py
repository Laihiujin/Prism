"""
自定义 OpenClaw 工具（精简版）
只保留核心功能：平台账号发布 + 视频数据查询
"""
import os
from typing import Any, Dict, Optional, List
import httpx
import json
import re

from .tool_runtime import BaseTool, ToolResult


# 后端 API 基础 URL（本地）
API_BASE_URL = os.getenv("AGENT_API_BASE_URL", os.getenv("MANUS_API_BASE_URL", "http://localhost:7000/api/v1"))

_PLATFORM_CODE_MAP = {
    1: "xiaohongshu",
    2: "channels",
    3: "douyin",
    4: "kuaishou",
    5: "bilibili",
}
_PLACEHOLDER_ACCOUNT_RE = re.compile(r"^acc\d+$", re.IGNORECASE)


def _is_placeholder_account_id(account_id: str) -> bool:
    if not account_id:
        return True
    return bool(_PLACEHOLDER_ACCOUNT_RE.match(account_id.strip()))


async def _fetch_valid_account_ids(platform: Optional[int] = None) -> List[str]:
    params: Dict[str, Any] = {"status": "valid"}
    platform_code = _PLATFORM_CODE_MAP.get(platform)
    if platform_code:
        params["platform"] = platform_code

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{API_BASE_URL}/accounts", params=params)
        response.raise_for_status()
        result = response.json()

    accounts = result.get("items", [])
    return [acc.get("account_id") for acc in accounts if acc.get("account_id")]


async def _resolve_account_ids(
    requested: Optional[List[str]],
    platform: Optional[int] = None
) -> List[str]:
    valid_ids = await _fetch_valid_account_ids(platform)
    if not requested:
        return valid_ids

    normalized = [acc.strip() for acc in requested if acc and acc.strip()]
    cleaned = [acc for acc in normalized if not _is_placeholder_account_id(acc)]
    if not cleaned:
        return valid_ids
    if not valid_ids:
        return cleaned

    filtered = [acc for acc in cleaned if acc in valid_ids]
    return filtered or valid_ids


# ============================================
# 账号管理工具
# ============================================

class ListAccountsTool(BaseTool):
    """列出可用账号"""

    name: str = "list_accounts"
    description: str = (
        "获取系统中所有可用的社交媒体账号。"
        "用于规划发布任务时选择目标账号。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "platform": {
                "type": "string",
                "description": "筛选平台（可选）：douyin, kuaishou, bilibili, xiaohongshu, channels"
            },
            "status": {
                "type": "string",
                "enum": ["active", "inactive", "all"],
                "description": "筛选状态（默认 active）",
                "default": "active"
            }
        }
    }

    async def execute(
        self,
        platform: Optional[str] = None,
        status: str = "active",
        **kwargs
    ) -> ToolResult:
        """列出账号"""
        try:
            # 状态映射：工具层 -> API层
            status_map = {
                "active": "valid",      # 活跃 -> 有效
                "inactive": "expired",   # 不活跃 -> 过期
                "all": None             # 全部 -> 不过滤
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {}
                if platform:
                    params["platform"] = platform

                # 使用映射后的状态值
                mapped_status = status_map.get(status, "valid")
                if mapped_status:  # 如果不是 None（all）
                    params["status"] = mapped_status

                response = await client.get(
                    f"{API_BASE_URL}/accounts",
                    params=params
                )
                response.raise_for_status()
                result = response.json()

                accounts = result.get("items", [])
                total = result.get("total", 0)

                # 格式化输出
                output_lines = [f"📋 找到 {total} 个账号：\n"]
                for acc in accounts:
                    output_lines.append(
                        f"- [ID: {acc.get('account_id')}] "
                        f"{acc.get('platform', 'unknown')} - "
                        f"{acc.get('name', acc.get('username', 'N/A'))} "
                        f"({acc.get('status', 'unknown')})"
                    )

                return ToolResult(output="\n".join(output_lines))

        except Exception as e:
            return ToolResult(error=f"获取账号列表时出错: {str(e)}")


# ============================================
# 视频素材查询工具
# ============================================

class ListFilesTool(BaseTool):
    """列出视频素材"""

    name: str = "list_files"
    description: str = (
        "获取素材库中的视频列表。"
        "用于查找可用于发布的视频素材。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "返回数量限制（默认20）",
                "default": 20
            },
            "keyword": {
                "type": "string",
                "description": "搜索关键词（可选）"
            }
        }
    }

    async def execute(
        self,
        limit: int = 20,
        keyword: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """列出视频文件"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {"limit": limit}
                if keyword:
                    params["keyword"] = keyword

                response = await client.get(
                    f"{API_BASE_URL}/files",
                    params=params
                )
                response.raise_for_status()
                result = response.json()

                files_data = result.get("data", {})
                files = files_data.get("items", []) if isinstance(files_data, dict) else files_data

                # 格式化输出
                output_lines = [f"🎬 找到 {len(files)} 个视频：\n"]
                for file in files:
                    file_id = file.get('id', 'N/A')
                    filename = file.get('filename', '未命名')
                    size = file.get('size', 0)
                    size_mb = f"{size / 1024 / 1024:.2f} MB" if size else "未知"

                    output_lines.append(
                        f"- [ID: {file_id}] {filename} ({size_mb})"
                    )

                return ToolResult(output="\n".join(output_lines))

        except httpx.HTTPStatusError as e:
            return ToolResult(error=f"获取视频列表失败 (HTTP {e.response.status_code}): {e.response.text[:200]}")
        except Exception as e:
            return ToolResult(error=f"获取视频列表时出错: {str(e)}")


class GetFileDetailTool(BaseTool):
    """获取视频详情"""

    name: str = "get_file_detail"
    description: str = (
        "获取指定视频的详细信息，包含文件路径、大小、时长等。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "file_id": {
                "type": "integer",
                "description": "视频文件ID"
            }
        },
        "required": ["file_id"]
    }

    async def execute(self, file_id: int, **kwargs) -> ToolResult:
        """获取文件详情"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{API_BASE_URL}/files/{file_id}")
                response.raise_for_status()
                # 修复：API 直接返回 FileResponse JSON，不需要 .get("data")
                file_data = response.json()

                output = f"📄 视频详情：\n\n"
                output += f"- ID: {file_data.get('id')}\n"
                output += f"- 文件名: {file_data.get('filename')}\n"
                output += f"- 路径: {file_data.get('file_path')}\n"
                output += f"- 大小: {file_data.get('filesize', 0):.2f} MB\n"

                if file_data.get('duration'):
                    output += f"- 时长: {file_data.get('duration')}秒\n"

                output += f"- 状态: {file_data.get('status', 'unknown')}\n"
                output += f"- 上传时间: {file_data.get('upload_time', 'N/A')}\n"

                return ToolResult(output=output)

        except httpx.HTTPStatusError as e:
            return ToolResult(error=f"获取视频详情失败 (HTTP {e.response.status_code}): {e.response.text[:200]}")
        except Exception as e:
            return ToolResult(error=f"获取视频详情时出错: {str(e)}")


# ============================================
# AI 元数据生成工具
# ============================================

class GenerateAIMetadataTool(BaseTool):
    """AI生成视频标题和标签"""

    name: str = "generate_ai_metadata"
    description: str = (
        "⭐ 基于视频文件名自动生成标题和标签\n"
        "在发布前使用此工具，可以为视频生成合适的标题和 4 个标签。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "file_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "视频文件ID列表"
            },
            "force_regenerate": {
                "type": "boolean",
                "description": "是否强制重新生成（即使已有AI内容）",
                "default": False
            }
        },
        "required": ["file_ids"]
    }

    async def execute(
        self,
        file_ids: List[int],
        force_regenerate: bool = False,
        **kwargs
    ) -> ToolResult:
        """生成AI元数据"""
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{API_BASE_URL}/files/batch-generate-metadata",
                    json={
                        "file_ids": file_ids,
                        "force_regenerate": force_regenerate
                    }
                )
                response.raise_for_status()
                result = response.json()

                results = result.get("results", [])
                output_lines = [
                    f"✅ AI元数据生成完成：成功 {result.get('success_count', 0)}，失败 {result.get('failed_count', 0)}\n"
                ]
                for item in results:
                    status = item.get("status")
                    file_id = item.get("file_id")
                    if status == "success":
                        output_lines.append(
                            f"- [ID: {file_id}] 标题: {item.get('ai_title')} | 标签: {item.get('ai_tags')}"
                        )
                    else:
                        reason = item.get("error") or item.get("message") or "未知原因"
                        output_lines.append(f"- [ID: {file_id}] {status}: {reason}")

                return ToolResult(output="\n".join(output_lines))

        except httpx.HTTPStatusError as e:
            return ToolResult(error=f"AI元数据生成失败 (HTTP {e.response.status_code}): {e.response.text[:200]}")
        except Exception as e:
            return ToolResult(error=f"AI元数据生成出错: {str(e)}")


# ============================================
# 发布功能工具
# ============================================

class PublishBatchVideosTool(BaseTool):
    """发布视频到平台"""

    name: str = "publish_batch_videos"
    description: str = (
        "⭐ 核心功能：发布视频到社交媒体平台\n"
        "\n"
        "使用步骤：\n"
        "1. 先用 list_accounts 获取账号ID\n"
        "2. 用 list_files 获取视频ID\n"
        "3. 调用本工具发布\n"
        "\n"
        "必填参数说明：\n"
        "- file_ids: 视频ID数组，如 [1, 2, 3]\n"
        "- accounts: 账号ID数组，如 ['账号A', '账号B']\n"
        "- title: 标题字符串\n"
        "- topics: 必须恰好4个标签的数组，如 ['美食', '探店', '推荐', '种草']\n"
        "\n"
        "平台代码（可选）：1=小红书, 2=视频号, 3=抖音, 4=快手, 5=B站\n"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "file_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "视频ID列表，例如 [1, 2, 3]"
            },
            "accounts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "账号ID列表，例如 ['抖音账号1', '快手账号2']"
            },
            "title": {
                "type": "string",
                "description": "视频标题"
            },
            "topics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "必须恰好4个标签，例如 ['美食', '探店', '推荐', '种草']",
                "minItems": 4,
                "maxItems": 4
            },
            "platform": {
                "type": "integer",
                "description": "（可选）平台代码: 1=小红书, 2=视频号, 3=抖音, 4=快手, 5=B站。不填则自动根据账号分配"
            },
            "description": {
                "type": "string",
                "description": "（可选）视频描述",
                "default": ""
            }
        },
        "required": ["file_ids", "accounts", "title", "topics"]
    }

    async def execute(
        self,
        file_ids: List[int],
        accounts: List[str],
        title: str,
        topics: List[str],
        platform: Optional[int] = None,
        description: Optional[str] = "",
        **kwargs
    ) -> ToolResult:
        """批量发布视频"""
        try:
            # 验证话题标签数量
            if len(topics) != 4:
                return ToolResult(
                    error=f"❌ 话题标签必须恰好 4 个，当前提供了 {len(topics)} 个。请重新生成。"
                )

            batch_data = {
                "file_ids": file_ids,
                "accounts": accounts,
                "title": title,
                "description": description or "",
                "topics": topics,
                "priority": 5  # 固定优先级
            }

            if platform is not None:
                batch_data["platform"] = platform

            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{API_BASE_URL}/publish/batch",
                    json=batch_data
                )
                response.raise_for_status()
                result = response.json()

                batch_info = result.get("data", {})

                output = f"✅ 批量发布任务已创建！\n"
                output += f"- 批次 ID: {batch_info.get('batch_id')}\n"
                output += f"- 总任务数: {batch_info.get('total_tasks')}\n"
                output += f"- 成功: {batch_info.get('success_count')}\n"
                output += f"- 失败: {batch_info.get('failed_count')}\n"
                output += f"- 视频数: {len(file_ids)}\n"
                output += f"- 账号数: {len(accounts)}\n"

                return ToolResult(output=output)

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text[:500]
            return ToolResult(
                error=f"❌ 批量发布失败 (HTTP {e.response.status_code}): {error_detail}"
            )
        except Exception as e:
            return ToolResult(error=f"❌ 批量发布视频时出错: {str(e)}")


class CreatePublishPlanTool(BaseTool):
    """创建发布预设"""

    name: str = "create_publish_preset"
    description: str = (
        "创建一个发布预设模板，保存发布配置以便重复使用。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "预设名称"
            },
            "platform": {
                "type": "integer",
                "description": "平台代码: 1=小红书, 2=视频号, 3=抖音, 4=快手, 5=B站"
            },
            "accounts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "账号ID列表"
            },
            "default_title_template": {
                "type": "string",
                "description": "默认标题模板"
            },
            "default_topics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "默认话题标签"
            }
        },
        "required": ["name", "platform", "accounts"]
    }

    async def execute(
        self,
        name: str,
        platform: int,
        accounts: List[str],
        default_title_template: Optional[str] = "",
        default_topics: Optional[List[str]] = None,
        **kwargs
    ) -> ToolResult:
        """创建发布预设"""
        try:
            # 构建预设数据
            resolved_accounts = await _resolve_account_ids(accounts, platform)
            if not resolved_accounts:
                return ToolResult(error="没有找到可用的账号。")
            preset_data = {
                "name": name,
                "platform": platform,
                "accounts": resolved_accounts,
                "default_title_template": default_title_template or "",
                "default_description": "",
                "default_topics": default_topics or [],
                "schedule_enabled": False,
                "videos_per_day": 1,
                "schedule_date": "",
                "time_point": ""
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{API_BASE_URL}/publish/presets",
                    json=preset_data
                )
                response.raise_for_status()
                result = response.json()

                preset_id = result.get("data", {}).get("id")

                output = f"✅ 发布预设创建成功！\n"
                output += f"- 预设名称: {name}\n"
                output += f"- 预设 ID: {preset_id}\n"
                output += f"- 平台: {platform}\n"
                output += f"- 账号数量: {len(resolved_accounts)}\n"

                return ToolResult(output=output)

        except Exception as e:
            return ToolResult(error=f"创建发布预设时出错: {str(e)}")


class ListPublishPlansTool(BaseTool):
    """列出发布预设"""

    name: str = "list_publish_presets"
    description: str = (
        "获取所有发布预设列表，可以查看预设配置。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {}
    }

    async def execute(self, **kwargs) -> ToolResult:
        """列出发布预设"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{API_BASE_URL}/publish/presets")
                response.raise_for_status()
                result = response.json()

                presets = result.get("data", [])

                output_lines = [f"📋 找到 {len(presets)} 个发布预设：\n"]
                for preset in presets:
                    output_lines.append(
                        f"- [ID: {preset.get('id')}] "
                        f"{preset.get('name', '未命名')} "
                        f"(平台: {preset.get('platform')}, 账号数: {len(preset.get('accounts', []))})"
                    )

                return ToolResult(output="\n".join(output_lines))

        except Exception as e:
            return ToolResult(error=f"获取发布预设列表时出错: {str(e)}")


class UsePresetToPublishTool(BaseTool):
    """使用预设发布视频"""

    name: str = "use_preset_to_publish"
    description: str = (
        "使用已有的发布预设来快速发布视频。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "preset_id": {
                "type": "integer",
                "description": "预设ID（从 list_publish_presets 获取）"
            },
            "file_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "视频文件ID列表"
            },
            "override_title": {
                "type": "string",
                "description": "覆盖预设中的标题（可选）"
            }
        },
        "required": ["preset_id", "file_ids"]
    }

    async def execute(
        self,
        preset_id: int,
        file_ids: List[int],
        override_title: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """使用预设发布"""
        try:
            params = {"file_ids": file_ids}
            if override_title:
                params["override_title"] = override_title

            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{API_BASE_URL}/publish/presets/{preset_id}/use",
                    params=params
                )
                response.raise_for_status()
                result = response.json()

                batch_info = result.get("data", {})

                output = f"✅ 使用预设发布成功！\n"
                output += f"- 预设 ID: {preset_id}\n"
                output += f"- 成功任务: {batch_info.get('success_count')}\n"
                output += f"- 失败任务: {batch_info.get('failed_count')}\n"

                return ToolResult(output=output)

        except Exception as e:
            return ToolResult(error=f"使用预设发布时出错: {str(e)}")


# ============================================
# 任务管理工具
# ============================================

class GetTaskStatusTool(BaseTool):
    """获取任务状态"""

    name: str = "get_task_status"
    description: str = (
        "获取指定任务的执行状态、进度、错误信息等。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "任务 ID"
            }
        },
        "required": ["task_id"]
    }

    async def execute(self, task_id: str, **kwargs) -> ToolResult:
        """获取任务状态"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{API_BASE_URL}/tasks/{task_id}"
                )
                response.raise_for_status()
                result = response.json()

                task = result.get("data", {})

                output = f"📊 任务状态：\n"
                output += f"- 任务 ID: {task_id}\n"
                output += f"- 状态: {task.get('status', 'unknown')}\n"
                output += f"- 进度: {task.get('progress', 0)}%\n"

                if task.get('error'):
                    output += f"- 错误: {task.get('error')}\n"

                return ToolResult(output=output)

        except Exception as e:
            return ToolResult(error=f"获取任务状态时出错: {str(e)}")


class ListTasksStatusTool(BaseTool):
    """列出任务状态"""

    name: str = "list_tasks_status"
    description: str = (
        "获取发布任务队列的状态列表，查看所有任务的执行情况。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "状态筛选：pending, running, success, error, all（默认all）",
                "default": "all"
            },
            "limit": {
                "type": "integer",
                "description": "返回数量限制（默认20）",
                "default": 20
            }
        }
    }

    async def execute(
        self,
        status: str = "all",
        limit: int = 20,
        **kwargs
    ) -> ToolResult:
        """列出任务状态"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {"limit": limit}
                if status and status != "all":
                    params["status"] = status

                response = await client.get(
                    f"{API_BASE_URL}/tasks",
                    params=params
                )
                response.raise_for_status()
                result = response.json()

                tasks_data = result.get("data", {})
                tasks = tasks_data.get("items", []) if isinstance(tasks_data, dict) else tasks_data

                # 格式化输出
                output_lines = [f"📋 找到 {len(tasks)} 个任务：\n"]
                for task in tasks:
                    task_id = task.get('task_id', 'N/A')
                    platform = task.get('platform', 'unknown')
                    task_status = task.get('status', 'unknown')
                    progress = task.get('progress', 0)

                    status_icon = "✅" if task_status == "success" else "❌" if task_status == "error" else "🔄"

                    output_lines.append(
                        f"{status_icon} [ID: {task_id}] {platform} - {task_status} ({progress}%)"
                    )

                    if task.get('error_message'):
                        output_lines.append(f"   错误: {task.get('error_message')[:100]}")

                return ToolResult(output="\n".join(output_lines))

        except httpx.HTTPStatusError as e:
            return ToolResult(error=f"获取任务列表失败 (HTTP {e.response.status_code}): {e.response.text[:200]}")
        except Exception as e:
            return ToolResult(error=f"获取任务列表时出错: {str(e)}")


# ============================================
# 视频数据查询工具
# ============================================

class DataAnalyticsTool(BaseTool):
    """获取数据分析报告"""

    name: str = "data_analytics"
    description: str = (
        "获取发布数据分析报告，包含互动数据、粉丝增长等指标。\n"
        "可按平台、时间范围筛选。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "report_type": {
                "type": "string",
                "enum": ["publish_stats", "engagement", "growth", "trends"],
                "description": "报告类型：publish_stats=发布统计, engagement=互动数据, growth=增长, trends=趋势"
            },
            "platform": {
                "type": "string",
                "description": "平台筛选（可选）：douyin, kuaishou, bilibili, xiaohongshu, channels"
            },
            "start_date": {
                "type": "string",
                "description": "开始日期 (YYYY-MM-DD，可选）"
            },
            "end_date": {
                "type": "string",
                "description": "结束日期 (YYYY-MM-DD，可选）"
            }
        },
        "required": ["report_type"]
    }

    async def execute(
        self,
        report_type: str,
        platform: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """获取数据分析报告"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                params = {
                    "report_type": report_type
                }
                if platform:
                    params["platform"] = platform
                if start_date:
                    params["start_date"] = start_date
                if end_date:
                    params["end_date"] = end_date

                response = await client.get(
                    f"{API_BASE_URL}/analytics/report",
                    params=params
                )
                response.raise_for_status()
                result = response.json()

                data = result.get("data", {})

                output = f"📊 数据分析报告 - {report_type}\n\n"
                output += f"**时间范围**: {start_date or '全部'} ~ {end_date or '至今'}\n"
                if platform:
                    output += f"**平台**: {platform}\n"
                output += f"\n**统计数据**:\n"
                output += f"```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"

                return ToolResult(output=output)

        except Exception as e:
            return ToolResult(error=f"获取数据分析报告失败: {str(e)}")


class ExternalVideoCrawlerTool(BaseTool):
    """抓取外部平台视频数据"""

    name: str = "external_video_crawler"
    description: str = (
        "抓取外部视频链接的数据（支持抖音、TikTok、Bilibili）。\n"
        "适用于竞品分析、素材收集等场景。\n"
        "\n"
        "示例链接：\n"
        "- 抖音: https://v.douyin.com/xxx/\n"
        "- TikTok: https://www.tiktok.com/@user/video/xxx\n"
        "- Bilibili: https://www.bilibili.com/video/BVxxx"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "视频分享链接（支持抖音/TikTok/Bilibili）",
                "pattern": "^https?://"
            },
            "minimal": {
                "type": "boolean",
                "description": "是否返回最小数据集（默认 False）",
                "default": False
            }
        },
        "required": ["url"]
    }

    async def execute(
        self,
        url: str,
        minimal: bool = False,
        **kwargs
    ) -> ToolResult:
        """执行外部视频数据抓取"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                crawl_data = {
                    "url": url,
                    "minimal": minimal
                }

                response = await client.post(
                    f"{API_BASE_URL}/crawler/fetch_video",
                    json=crawl_data
                )
                response.raise_for_status()
                result = response.json()

                if not result.get("success"):
                    return ToolResult(error=f"抓取失败: {result.get('error', '未知错误')}")

                data = result.get("data", {})
                platform = result.get("platform", "unknown")

                # 格式化输出
                output = f"✅ 视频数据抓取成功！\n\n"
                output += f"📱 平台: {platform.upper()}\n"
                output += f"🔗 链接: {url}\n\n"

                # 根据平台格式化数据
                if platform == "douyin" or platform == "tiktok":
                    output += f"📝 标题: {data.get('desc', 'N/A')}\n"
                    author = data.get('author', {})
                    output += f"👤 作者: {author.get('nickname', 'N/A')}\n"
                    stats = data.get('statistics', {})
                    output += f"\n📊 数据统计:\n"
                    output += f"  ❤️  点赞: {stats.get('digg_count', 0):,}\n"
                    output += f"  💬 评论: {stats.get('comment_count', 0):,}\n"
                    output += f"  🔄 分享: {stats.get('share_count', 0):,}\n"
                    output += f"  ⭐ 收藏: {stats.get('collect_count', 0):,}\n"
                elif platform == "bilibili":
                    output += f"📝 标题: {data.get('title', 'N/A')}\n"
                    owner = data.get('owner', {})
                    output += f"👤 UP主: {owner.get('name', 'N/A')}\n"
                    stat = data.get('stat', {})
                    output += f"\n📊 数据统计:\n"
                    output += f"  👀 播放: {stat.get('view', 0):,}\n"
                    output += f"  👍 点赞: {stat.get('like', 0):,}\n"
                    output += f"  💰 投币: {stat.get('coin', 0):,}\n"
                    output += f"  ⭐ 收藏: {stat.get('favorite', 0):,}\n"
                    output += f"  🔄 转发: {stat.get('share', 0):,}\n"

                output += f"\n💾 完整数据已返回，包含 {len(data)} 个字段"

                return ToolResult(output=output, data=data)

        except httpx.HTTPStatusError as e:
            return ToolResult(error=f"API 请求失败: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            return ToolResult(error=f"外部视频数据抓取失败: {str(e)}")


class AccountVideoCrawlerTool(BaseTool):
    """抓取账号视频列表数据"""

    name: str = "account_video_crawler"
    description: str = (
        "抓取项目内已登录账号的视频列表数据。\n"
        "支持抖音和Bilibili平台，用于账号数据分析、内容管理等。\n"
        "\n"
        "使用方法：\n"
        "1. 可以提供 user_id（抖音: sec_user_id, B站: mid）\n"
        "2. 或提供账号名称（会自动从账号库匹配）"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "platform": {
                "type": "string",
                "enum": ["douyin", "bilibili"],
                "description": "平台名称"
            },
            "user_id": {
                "type": "string",
                "description": "用户ID（抖音: sec_user_id, B站: mid）"
            },
            "name": {
                "type": "string",
                "description": "账号名称（可选，用于账号库匹配）"
            },
            "max_cursor": {
                "type": "integer",
                "description": "分页游标（默认 0）",
                "default": 0
            },
            "count": {
                "type": "integer",
                "description": "每页数量（默认 20，最大 100）",
                "default": 20,
                "minimum": 1,
                "maximum": 100
            }
        },
        "required": ["platform"]
    }

    async def execute(
        self,
        platform: str,
        user_id: Optional[str] = None,
        name: Optional[str] = None,
        max_cursor: int = 0,
        count: int = 20,
        **kwargs
    ) -> ToolResult:
        """执行账号视频列表抓取"""
        try:
            platform = (platform or "").lower()
            resolved_user_id = user_id
            resolved_name = None

            async with httpx.AsyncClient(timeout=120.0) as client:
                # 如果没有 user_id，尝试通过 name 从账号库匹配
                if not resolved_user_id:
                    if not name:
                        return ToolResult(error="请提供 user_id 或 name（账号库名称）")

                    response = await client.get(
                        f"{API_BASE_URL}/accounts",
                        params={"platform": platform}
                    )
                    response.raise_for_status()
                    result = response.json()
                    accounts = result.get("items", [])

                    name_key = name.strip().lower()
                    matched = None
                    for acc in accounts:
                        if (acc.get("platform") or "").lower() != platform:
                            continue
                        for field in ("name", "username", "original_name", "user_id", "account_id"):
                            value = acc.get(field)
                            if value and str(value).strip().lower() == name_key:
                                matched = acc
                                break
                        if matched:
                            break

                    if not matched:
                        return ToolResult(error=f"未找到匹配账号: {name}")

                    resolved_name = matched.get("name") or matched.get("username") or name
                    resolved_user_id = matched.get("user_id")
                    if not resolved_user_id:
                        return ToolResult(error=f"账号 {resolved_name} 未找到 user_id")

                # 抓取视频列表
                crawl_data = {
                    "platform": platform,
                    "user_id": resolved_user_id,
                    "max_cursor": max_cursor,
                    "count": count
                }

                response = await client.post(
                    f"{API_BASE_URL}/crawler/fetch_account_videos",
                    json=crawl_data
                )
                response.raise_for_status()
                result = response.json()

                if not result.get("success"):
                    return ToolResult(error=f"抓取失败: {result.get('error', '未知错误')}")

                data = result.get("data", {})
                videos = data.get("videos", [])

                # 格式化输出
                output = f"✅ 账号视频列表抓取成功！\n\n"
                output += f"📱 平台: {platform.upper()}\n"
                if resolved_name:
                    output += f"👤 账号: {resolved_name}\n"
                output += f"🆔 User ID: {resolved_user_id}\n"
                output += f"📊 视频数量: {len(videos)}\n\n"

                # 显示前几个视频
                for i, video in enumerate(videos[:5], 1):
                    if platform == "douyin":
                        title = video.get("desc", "无标题")[:50]
                        stats = video.get("statistics", {})
                        likes = stats.get("digg_count", 0)
                        output += f"{i}. {title}\n"
                        output += f"   ❤️  {likes:,} 点赞\n"
                    elif platform == "bilibili":
                        title = video.get("title", "无标题")[:50]
                        stat = video.get("stat", {})
                        view = stat.get("view", 0)
                        output += f"{i}. {title}\n"
                        output += f"   👀 {view:,} 播放\n"

                if len(videos) > 5:
                    output += f"\n... 还有 {len(videos) - 5} 个视频\n"

                output += f"\n💾 完整数据已返回（共 {len(videos)} 个视频）"

                return ToolResult(output=output, data=data)

        except httpx.HTTPStatusError as e:
            return ToolResult(error=f"API 请求失败: {e.response.status_code} - {e.response.text[:200]}")
        except Exception as e:
            return ToolResult(error=f"账号视频列表抓取失败: {str(e)}")
