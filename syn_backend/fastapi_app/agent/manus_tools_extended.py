"""
扩展的 OpenManus 工具集
包含数据采集、IP池管理、脚本执行等高级功能

NOTE: 此模块必须在 OpenManus Agent 初始化之后才能导入
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, List
import httpx
import json

# 添加 OpenManus-worker 到 Python 路径（确保优先级最高，避免 app 命名冲突）
OPENMANUS_PATH = Path(__file__).parent.parent.parent / "OpenManus-worker"

def _ensure_openmanus_path() -> None:
    if not OPENMANUS_PATH.exists():
        return
    try:
        sys.path.remove(str(OPENMANUS_PATH))
    except ValueError:
        pass
    sys.path.insert(0, str(OPENMANUS_PATH))

_ensure_openmanus_path()

from app.tool.base import BaseTool, ToolResult

# 后端 API 基础 URL（本地）
API_BASE_URL = os.getenv("MANUS_API_BASE_URL", "http://localhost:7000/api/v1")


# ============================================
# 数据采集工具
# ============================================

# ============================================
# IP 池管理工具
# ============================================

class IPPoolTool(BaseTool):
    """IP 池管理工具"""

    name: str = "ip_pool_manager"
    description: str = (
        "管理代理 IP 池。"
        "支持查询可用 IP、添加 IP、删除 IP、测试 IP 可用性等操作。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "add", "remove", "test"],
                "description": "操作类型"
            },
            "ip_address": {
                "type": "string",
                "description": "IP 地址（用于 add/remove/test）"
            },
            "port": {
                "type": "integer",
                "description": "端口号（用于 add）"
            },
            "username": {
                "type": "string",
                "description": "认证用户名（可选）"
            },
            "password": {
                "type": "string",
                "description": "认证密码（可选）"
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        ip_address: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """执行 IP 池操作"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                if action == "list":
                    response = await client.get(f"{API_BASE_URL}/ip-pool")
                    response.raise_for_status()
                    result = response.json()
                    ips = result.get("data", [])
                    output = f"📋 IP 池列表（共 {len(ips)} 个）:\n"
                    for ip in ips:
                        output += f"- {ip.get('ip')}:{ip.get('port')} (状态: {ip.get('status')})\n"
                    return ToolResult(output=output)

                elif action == "add":
                    add_data = {
                        "ip": ip_address,
                        "port": port,
                        "username": username,
                        "password": password
                    }
                    response = await client.post(
                        f"{API_BASE_URL}/ip-pool",
                        json=add_data
                    )
                    response.raise_for_status()
                    return ToolResult(output=f"✅ IP {ip_address}:{port} 已添加到池中")

                elif action == "remove":
                    response = await client.delete(
                        f"{API_BASE_URL}/ip-pool/{ip_address}"
                    )
                    response.raise_for_status()
                    return ToolResult(output=f"✅ IP {ip_address} 已从池中移除")

                elif action == "test":
                    response = await client.post(
                        f"{API_BASE_URL}/ip-pool/test",
                        json={"ip": ip_address}
                    )
                    response.raise_for_status()
                    result = response.json()
                    is_valid = result.get("data", {}).get("valid", False)
                    msg = "可用" if is_valid else "不可用"
                    return ToolResult(output=f"IP {ip_address} 测试结果: {msg}")

        except Exception as e:
            return ToolResult(error=f"IP 池操作失败: {str(e)}")


# ============================================
# 数据分析工具
# ============================================

class DataAnalyticsTool(BaseTool):
    """数据分析工具"""

    name: str = "data_analytics"
    description: str = (
        "获取数据分析报告。"
        "支持查看发布统计、互动数据、粉丝增长等指标。"
        "可按平台、时间范围筛选。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "report_type": {
                "type": "string",
                "enum": ["publish_stats", "engagement", "growth", "trends"],
                "description": "报告类型"
            },
            "platform": {
                "type": "string",
                "description": "平台筛选（可选）"
            },
            "start_date": {
                "type": "string",
                "description": "开始日期 (YYYY-MM-DD)"
            },
            "end_date": {
                "type": "string",
                "description": "结束日期 (YYYY-MM-DD)"
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


# ============================================
# 脚本执行工具
# ============================================

class RunScriptTool(BaseTool):
    """运行后端脚本工具"""

    name: str = "run_backend_script"
    description: str = (
        "执行后端预定义的 Python 脚本。"
        "支持数据导出、批量处理、系统维护等操作。"
        "可传递参数给脚本。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "script_name": {
                "type": "string",
                "description": "脚本名称（不含 .py 后缀）"
            },
            "args": {
                "type": "object",
                "description": "脚本参数（键值对）"
            }
        },
        "required": ["script_name"]
    }

    async def execute(
        self,
        script_name: str,
        args: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ToolResult:
        """执行后端脚本"""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                script_data = {
                    "script_name": script_name,
                    "args": args or {}
                }

                response = await client.post(
                    f"{API_BASE_URL}/scripts/run",
                    json=script_data
                )
                response.raise_for_status()
                result = response.json()

                data = result.get("data", {})
                task_id = data.get("task_id")
                status = data.get("status")

                output = f"✅ 脚本执行已启动！\n"
                output += f"- 脚本名称: {script_name}\n"
                output += f"- 任务 ID: {task_id}\n"
                output += f"- 状态: {status}\n"

                return ToolResult(output=output)

        except Exception as e:
            return ToolResult(error=f"脚本执行失败: {str(e)}")


# ============================================
# Cookie 管理工具
# ============================================

class CookieManagerTool(BaseTool):
    """Cookie 管理工具"""

    name: str = "cookie_manager"
    description: str = (
        "管理账号 Cookie。"
        "支持导入、导出、刷新 Cookie 等操作。"
        "用于账号状态维护和迁移。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "export", "import", "refresh"],
                "description": "操作类型"
            },
            "account_id": {
                "type": "string",
                "description": "账号 ID（用于 export/refresh）"
            },
            "platform": {
                "type": "string",
                "description": "平台名称（用于 list/import）"
            },
            "cookie_data": {
                "type": "string",
                "description": "Cookie 数据（JSON 字符串，用于 import）"
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        account_id: Optional[str] = None,
        platform: Optional[str] = None,
        cookie_data: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """执行 Cookie 操作"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                if action == "list":
                    params = {}
                    if platform:
                        params["platform"] = platform
                    response = await client.get(
                        f"{API_BASE_URL}/cookies",
                        params=params
                    )
                    response.raise_for_status()
                    result = response.json()
                    cookies = result.get("data", [])
                    output = f"📋 Cookie 列表（共 {len(cookies)} 个）:\n"
                    for cookie in cookies:
                        output += f"- {cookie.get('account_id')} ({cookie.get('platform')}) - 过期时间: {cookie.get('expires')}\n"
                    return ToolResult(output=output)

                elif action == "export":
                    response = await client.get(
                        f"{API_BASE_URL}/cookies/{account_id}/export"
                    )
                    response.raise_for_status()
                    result = response.json()
                    cookie_json = json.dumps(result.get("data", {}), ensure_ascii=False, indent=2)
                    return ToolResult(output=f"✅ Cookie 导出成功:\n```json\n{cookie_json}\n```")

                elif action == "import":
                    import_data = {
                        "platform": platform,
                        "cookie_data": json.loads(cookie_data) if cookie_data else {}
                    }
                    response = await client.post(
                        f"{API_BASE_URL}/cookies/import",
                        json=import_data
                    )
                    response.raise_for_status()
                    return ToolResult(output=f"✅ Cookie 已导入")

                elif action == "refresh":
                    response = await client.post(
                        f"{API_BASE_URL}/cookies/{account_id}/refresh"
                    )
                    response.raise_for_status()
                    result = response.json()
                    new_expires = result.get("data", {}).get("expires")
                    return ToolResult(output=f"✅ Cookie 已刷新，新过期时间: {new_expires}")

        except Exception as e:
            return ToolResult(error=f"Cookie 操作失败: {str(e)}")


# ============================================
# 视频数据抓取工具
# ============================================

class ExternalVideoCrawlerTool(BaseTool):
    """外部视频链接数据抓取工具（混合爬虫）"""

    name: str = "external_video_crawler"
    description: str = (
        "抓取外部视频链接的数据（混合爬虫）。"
        "支持抖音、TikTok、Bilibili三个平台，自动识别平台类型。"
        "可用于外部视频数据分析、竞品监控、素材收集等场景。"
        "示例链接："
        "- 抖音: https://v.douyin.com/xxx/"
        "- TikTok: https://www.tiktok.com/@user/video/xxx"
        "- Bilibili: https://www.bilibili.com/video/BVxxx 或 https://b23.tv/xxx"
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
                "description": "是否返回最小数据集（默认 False，返回完整数据）",
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
    """项目内账号视频数据抓取工具（专用爬虫）"""

    name: str = "account_video_crawler"
    description: str = (
        "抓取项目内已登录账号的视频列表数据（专用爬虫）。"
        "支持抖音和Bilibili平台，可根据账号 user_id 或 name 匹配账号库。"
        "适用于项目内账号数据分析、内容管理、数据统计等场景。"
        "参数优先级：user_id > name。"
        "抖音: sec_user_id（如 MS4wLjABAAAA...）"
        "Bilibili: mid（数字ID）"
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
                        return ToolResult(error=f"账号 {resolved_name} 未找到 user_id，请提供 user_id")
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

                # 格式化输出
                output = f"✅ 账号视频列表抓取成功！\n\n"
                output += f"📱 平台: {platform.upper()}\n"
                output += f"👤 用户ID: {resolved_user_id}\n"
                if resolved_name:
                    output += f"账号名称: {resolved_name}\n"
                output += f"📄 页码: {max_cursor + 1}\n"

                # 根据平台解析视频列表
                if platform == "douyin":
                    aweme_list = data.get('aweme_list', [])
                    output += f"📹 视频数量: {len(aweme_list)}\n\n"
                    if aweme_list:
                        output += "📋 视频列表:\n"
                        for i, video in enumerate(aweme_list[:10], 1):  # 只显示前10个
                            desc = video.get('desc', 'N/A')[:50]
                            stats = video.get('statistics', {})
                            output += f"{i}. {desc}...\n"
                            output += f"   ❤️  {stats.get('digg_count', 0):,}  💬 {stats.get('comment_count', 0):,}\n"
                        if len(aweme_list) > 10:
                            output += f"\n... 还有 {len(aweme_list) - 10} 个视频\n"
                    has_more = data.get('has_more', False)
                    if has_more:
                        next_cursor = data.get('max_cursor', 0)
                        output += f"\n➡️  还有更多视频，下一页游标: {next_cursor}"
                elif platform == "bilibili":
                    vlist = data.get('list', {}).get('vlist', [])
                    output += f"📹 视频数量: {len(vlist)}\n\n"
                    if vlist:
                        output += "📋 视频列表:\n"
                        for i, video in enumerate(vlist[:10], 1):
                            title = video.get('title', 'N/A')[:50]
                            play = video.get('play', 0)
                            output += f"{i}. {title}...\n"
                            output += f"   👀 {play:,} 播放\n"
                        if len(vlist) > 10:
                            output += f"\n... 还有 {len(vlist) - 10} 个视频\n"

                output += f"\n💾 完整数据已返回"

                return ToolResult(output=output, data=data)

        except httpx.HTTPStatusError as e:
            return ToolResult(error=f"API 请求失败: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            return ToolResult(error=f"账号视频数据抓取失败: {str(e)}")
