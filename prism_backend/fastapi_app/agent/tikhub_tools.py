"""TikHub-backed tools for Kuaishou, WeChat Channels, and Xiaohongshu."""

from __future__ import annotations

from typing import Optional

from myUtils.tikhub_client import get_tikhub_client

from .tool_runtime import BaseTool, ToolResult


def _missing_client() -> ToolResult:
    return ToolResult(error="TikHub API key is not configured.")


class TikHubKuaishouUserInfoTool(BaseTool):
    name = "tikhub_kuaishou_user_info"
    description = "Fetch Kuaishou user info from TikHub by eid."
    parameters = {
        "type": "object",
        "properties": {"user_id": {"type": "string", "description": "Kuaishou eid from profile URL."}},
        "required": ["user_id"],
    }

    async def execute(self, user_id: str, **kwargs) -> ToolResult:
        client = get_tikhub_client()
        if not client:
            return _missing_client()
        async with client:
            payload = await client.fetch_kuaishou_user_info(user_id=user_id)
        data = payload.get("data") or {}
        output = f"Kuaishou user info loaded for {user_id}."
        if isinstance(data, dict) and data.get("user_name"):
            output += f" nickname={data.get('user_name')}"
        return ToolResult(output=output, data=payload)


class TikHubKuaishouUserPostsTool(BaseTool):
    name = "tikhub_kuaishou_user_posts"
    description = "Fetch Kuaishou user posts from TikHub by eid."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "Kuaishou eid from profile URL."},
            "pcursor": {"type": "string", "description": "Pagination cursor.", "default": ""},
        },
        "required": ["user_id"],
    }

    async def execute(self, user_id: str, pcursor: Optional[str] = None, **kwargs) -> ToolResult:
        client = get_tikhub_client()
        if not client:
            return _missing_client()
        async with client:
            payload = await client.fetch_kuaishou_user_posts(user_id=user_id, pcursor=pcursor)
        videos, next_cursor = client.parse_kuaishou_posts(payload)
        return ToolResult(
            output=f"Fetched {len(videos)} Kuaishou posts. next_cursor={next_cursor or ''}",
            data={"payload": payload, "videos": videos, "next_cursor": next_cursor},
        )


class TikHubXiaohongshuUserInfoTool(BaseTool):
    name = "tikhub_xiaohongshu_user_info"
    description = "Fetch Xiaohongshu user info from TikHub by user_id."
    parameters = {
        "type": "object",
        "properties": {"user_id": {"type": "string", "description": "Xiaohongshu user_id."}},
        "required": ["user_id"],
    }

    async def execute(self, user_id: str, **kwargs) -> ToolResult:
        client = get_tikhub_client()
        if not client:
            return _missing_client()
        async with client:
            payload = await client.fetch_xiaohongshu_user_info(user_id=user_id)
        return ToolResult(output=f"Fetched Xiaohongshu user info for {user_id}.", data=payload)


class TikHubXiaohongshuUserNotesTool(BaseTool):
    name = "tikhub_xiaohongshu_user_notes"
    description = "Fetch Xiaohongshu user notes from TikHub."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "Xiaohongshu user_id."},
            "last_cursor": {"type": "string", "description": "Pagination cursor.", "default": ""},
        },
        "required": ["user_id"],
    }

    async def execute(self, user_id: str, last_cursor: Optional[str] = None, **kwargs) -> ToolResult:
        client = get_tikhub_client()
        if not client:
            return _missing_client()
        async with client:
            payload = await client.fetch_xiaohongshu_user_notes_v2(user_id=user_id, last_cursor=last_cursor)
        notes, next_cursor = client.parse_xiaohongshu_notes(payload)
        return ToolResult(
            output=f"Fetched {len(notes)} Xiaohongshu notes. next_cursor={next_cursor or ''}",
            data={"payload": payload, "notes": notes, "next_cursor": next_cursor},
        )


class TikHubXiaohongshuNoteIdTool(BaseTool):
    name = "tikhub_xiaohongshu_note_id"
    description = "Extract Xiaohongshu note id and xsec_token from a share URL."
    parameters = {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "Xiaohongshu share URL."}},
        "required": ["url"],
    }

    async def execute(self, url: str, **kwargs) -> ToolResult:
        client = get_tikhub_client()
        if not client:
            return _missing_client()
        async with client:
            payload = await client.fetch_xiaohongshu_note_id_and_xsec_token(url=url)
        return ToolResult(output="Extracted Xiaohongshu note id metadata.", data=payload)


class TikHubWeChatChannelsHomeTool(BaseTool):
    name = "tikhub_wechat_channels_home"
    description = "Fetch WeChat Channels home page videos from TikHub."
    parameters = {
        "type": "object",
        "properties": {
            "username": {"type": "string", "description": "WeChat Channels username."},
            "last_buffer": {"type": "string", "description": "Pagination buffer.", "default": ""},
        },
        "required": ["username"],
    }

    async def execute(self, username: str, last_buffer: Optional[str] = None, **kwargs) -> ToolResult:
        client = get_tikhub_client()
        if not client:
            return _missing_client()
        async with client:
            payload = await client.fetch_channels_home(username=username, last_buffer=last_buffer)
        videos, next_buffer = client.parse_channels_home(payload)
        return ToolResult(
            output=f"Fetched {len(videos)} WeChat Channels videos. next_buffer={next_buffer or ''}",
            data={"payload": payload, "videos": videos, "next_buffer": next_buffer},
        )


class TikHubWeChatChannelsVideoDetailTool(BaseTool):
    name = "tikhub_wechat_channels_video_detail"
    description = "Fetch WeChat Channels video detail from TikHub by id or exportId."
    parameters = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Video id."},
            "export_id": {"type": "string", "description": "Temporary export id."},
        },
    }

    async def execute(
        self,
        id: Optional[str] = None,
        export_id: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        if not id and not export_id:
            return ToolResult(error="Provide id or export_id.")
        client = get_tikhub_client()
        if not client:
            return _missing_client()
        async with client:
            payload = await client.fetch_channels_video_detail(video_id=id, export_id=export_id)
        return ToolResult(output="Fetched WeChat Channels video detail.", data=payload)
