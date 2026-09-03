"""
Prism MCP Server — 暴露给 AI 工具 / 智能体的 4 个动作工具。

参照 MatrixMedia 的 MCP 设计（list_accounts / list_history / publish_video /
publish_article），为 Prism 提供同构、语义清晰的工具集，让 OpenClaw /
Claude Code / Dify / n8n 等能直接调用 Prism 的后端发布能力。

传输：stdio（标准输入输出）。启动方式（项目根）：
    python prism_cli.py mcp
等价：
    python -m fastapi_app.agent.mcp_server       # 暴露 tool_catalog 全部工具（含这 4 个）

工具复用了 fastapi_app.services.platform_api 的 HTTP 客户端，与
`prism tool list` 中登记的 4 个工具同构（同一份后端逻辑，无重复实现）。
发布走 /api/v1/publish/batch（Celery + 浏览器模式），不会引入 HTTP 逆向登录。

工具返回始终是 JSON 字符串（TextContent），字段：
    {"ok": bool, "message": str, "data": ...}
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import List, Optional

from mcp.server.mcpserver import MCPServer


def _emit(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False)


server = MCPServer(
    name="prism",
    version="0.1.0",
    description=(
        "Prism 多平台矩阵发布系统工具。可列出账号、查询发布历史、"
        "按素材批量发布视频。所有发布均在本地浏览器模式下执行。"
    ),
)


@server.tool()
async def list_accounts(count: int = 100) -> str:
    """列出所有平台账号（id / 名称 / 平台 / 状态）。

    Args:
        count: 最多返回的账号条数（默认 100）。
    """
    from fastapi_app.services.platform_api import fetch_accounts
    return _emit(await fetch_accounts(count=count))


@server.tool()
async def list_history(
    platform: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> str:
    """查询最近的发布历史记录。

    Args:
        platform: 平台代码（1 小红书, 2 视频号, 3 抖音, 4 快手, 5 B站, 6 TikTok, 7 YouTube, 8 百家号）。
        status: 状态过滤（success / failed / running / pending / cancelled / scheduled）。
        limit: 返回条数上限（默认 100，最大 500）。
    """
    from fastapi_app.services.platform_api import fetch_history
    return _emit(await fetch_history(platform=platform, status=status, limit=limit))


@server.tool()
async def publish_video(
    file_ids: List[int],
    accounts: List[str],
    title: str,
    platform: Optional[int] = None,
    description: Optional[str] = None,
    topics: Optional[List[str]] = None,
    scheduled_time: Optional[str] = None,
) -> str:
    """把素材批量发布到账号（视频/图文均可）。

    素材必须是后端「素材库」里已存在的文件（file_ids）；账号为账号 id
    列表。platform 为空时按账号所属平台自动分组。

    Args:
        file_ids: 素材文件 id 列表（至少 1 个）。
        accounts: 目标账号 id 列表。
        title: 统一标题。
        platform: 平台代码（可选，不传则按账号分组）。
        description: 统一描述。
        topics: 话题标签列表。
        scheduled_time: 定时发布时间，格式 YYYY-MM-DD HH:MM（可选）。
    """
    from fastapi_app.services.platform_api import publish_batch
    return _emit(
        await publish_batch(
            file_ids=file_ids,
            accounts=accounts,
            title=title,
            platform=platform,
            description=description,
            topics=topics,
            scheduled_time=scheduled_time,
        )
    )


@server.tool()
async def publish_article(
    file_ids: List[int],
    accounts: List[str],
    title: str,
    content: str,
    platform: Optional[int] = None,
    scheduled_time: Optional[str] = None,
) -> str:
    """把图文/素材作为内容发布（当前 Prism 以文件作为内容载体）。

    Prism 的发布链路以「素材文件」为内容单元，因此图文/文章同样通过
    素材库中的 file_ids 发布。`content` 写入描述，用作正文/补充说明。

    Args:
        file_ids: 素材文件 id 列表（图文用图片 id）。
        accounts: 目标账号 id 列表。
        title: 标题。
        content: 正文/描述。
        platform: 平台代码（可选）。
        scheduled_time: 定时发布时间 YYYY-MM-DD HH:MM（可选）。
    """
    from fastapi_app.services.platform_api import publish_batch
    return _emit(
        await publish_batch(
            file_ids=file_ids,
            accounts=accounts,
            title=title,
            platform=platform,
            description=content,
            scheduled_time=scheduled_time,
        )
    )


if __name__ == "__main__":
    print("Prism MCP server ready (stdio)", file=os.sys.stderr)
    asyncio.run(server.run_stdio_async())
