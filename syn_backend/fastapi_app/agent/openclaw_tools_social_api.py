"""
OpenClaw 社交媒体 API 工具
用于调用 Douyin/TikTok API 获取用户、视频、评论等数据
"""
import os
from typing import Optional, List
import re
import httpx

from .tool_runtime import BaseTool, ToolResult

# TikTok/Douyin/Bilibili API 基础 URL (已集成到后端 7000 端口)
# 注意: douyin_tiktok_api 已挂载在 /api/v1/douyin-tiktok 路径下
DOUYIN_API_BASE_URL = os.getenv("DOUYIN_API_BASE_URL", "http://localhost:7000/api/v1/douyin-tiktok/api/douyin/web")
TIKTOK_API_BASE_URL = os.getenv("TIKTOK_API_BASE_URL", "http://localhost:7000/api/v1/douyin-tiktok/api/tiktok/web")
BILIBILI_API_BASE_URL = os.getenv("BILIBILI_API_BASE_URL", "http://localhost:7000/api/v1/douyin-tiktok/api/bilibili/web")


# ============================================
# 抖音 API 工具
# ============================================

class DouyinFetchUserInfoTool(BaseTool):
    """抖音获取用户信息工具"""

    name: str = "douyin_fetch_user_info"
    description: str = (
        "获取抖音用户的详细信息。"
        "支持通过用户主页链接或 sec_user_id 获取。"
        "返回用户昵称、粉丝数、获赞数、简介等信息。"
        "示例链接: https://www.douyin.com/user/MS4wLjABAAAA..."
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "url_or_sec_user_id": {
                "type": "string",
                "description": "用户主页链接或 sec_user_id（如：MS4wLjABAAAANXSltcLCzDGmdNFI2Q_QixVTr67NiYzjKOIP5s03CAE）"
            }
        },
        "required": ["url_or_sec_user_id"]
    }

    async def execute(
        self,
        url_or_sec_user_id: str,
        **kwargs
    ) -> ToolResult:
        """获取抖音用户信息"""
        try:
            # 提取 sec_user_id（如果是链接）
            sec_user_id = url_or_sec_user_id
            if "douyin.com/user/" in url_or_sec_user_id:
                sec_user_id = url_or_sec_user_id.split("/user/")[-1].split("?")[0]

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{DOUYIN_API_BASE_URL}/fetch_user_detail",
                    params={"sec_user_id": sec_user_id}
                )
                response.raise_for_status()
                result = response.json()

                if result.get("code") == 200:
                    user_data = result.get("data", {})
                    output = f"✅ 成功获取用户信息\n\n"
                    output += f"- 昵称: {user_data.get('nickname', 'N/A')}\n"
                    output += f"- 抖音号: {user_data.get('unique_id', 'N/A')}\n"
                    output += f"- 粉丝数: {user_data.get('follower_count', 0)}\n"
                    output += f"- 获赞数: {user_data.get('total_favorited', 0)}\n"
                    output += f"- 作品数: {user_data.get('aweme_count', 0)}\n"
                    output += f"- 简介: {user_data.get('signature', 'N/A')}\n"
                    output += f"- sec_user_id: {sec_user_id}\n"
                    return ToolResult(output=output)
                else:
                    return ToolResult(error=f"API 返回错误: {result.get('message', '未知错误')}")

        except httpx.HTTPStatusError as e:
            return ToolResult(error=f"HTTP 错误 ({e.response.status_code}): {e.response.text[:200]}")
        except Exception as e:
            return ToolResult(error=f"获取用户信息失败: {str(e)}")


class DouyinFetchUserVideosTool(BaseTool):
    """抖音获取用户视频列表工具"""

    name: str = "douyin_fetch_user_videos"
    description: str = (
        "获取抖音用户发布的视频列表。"
        "支持分页获取，返回视频标题、播放量、点赞数、评论数等信息。"
        "可用于分析用户内容、寻找爆款视频。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "url_or_sec_user_id": {
                "type": "string",
                "description": "用户主页链接或 sec_user_id"
            },
            "max_cursor": {
                "type": "integer",
                "description": "分页游标（从0开始）",
                "default": 0
            },
            "count": {
                "type": "integer",
                "description": "每页数量（建议20-50）",
                "default": 20
            }
        },
        "required": ["url_or_sec_user_id"]
    }

    async def execute(
        self,
        url_or_sec_user_id: str,
        max_cursor: int = 0,
        count: int = 20,
        **kwargs
    ) -> ToolResult:
        """获取用户视频列表"""
        try:
            # 提取 sec_user_id
            sec_user_id = url_or_sec_user_id
            if "douyin.com/user/" in url_or_sec_user_id:
                sec_user_id = url_or_sec_user_id.split("/user/")[-1].split("?")[0]

            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.get(
                    f"{DOUYIN_API_BASE_URL}/fetch_user_post_videos",
                    params={
                        "sec_user_id": sec_user_id,
                        "max_cursor": max_cursor,
                        "count": count
                    }
                )
                response.raise_for_status()
                result = response.json()

                if result.get("code") == 200:
                    data = result.get("data", {})
                    videos = data.get("aweme_list", [])
                    has_more = data.get("has_more", False)

                    output = f"📹 找到 {len(videos)} 个视频\n\n"

                    for idx, video in enumerate(videos, 1):
                        stats = video.get("statistics", {})
                        output += f"{idx}. {video.get('desc', '无标题')[:50]}\n"
                        output += f"   - ID: {video.get('aweme_id')}\n"
                        output += f"   - 播放: {stats.get('play_count', 0):,}\n"
                        output += f"   - 点赞: {stats.get('digg_count', 0):,}\n"
                        output += f"   - 评论: {stats.get('comment_count', 0):,}\n"
                        output += f"   - 分享: {stats.get('share_count', 0):,}\n\n"

                    if has_more:
                        output += f"\n还有更多视频，下一页游标: {data.get('max_cursor')}"

                    return ToolResult(output=output)
                else:
                    return ToolResult(error=f"API 返回错误: {result.get('message', '未知错误')}")

        except Exception as e:
            return ToolResult(error=f"获取视频列表失败: {str(e)}")


class DouyinFetchVideoDetailTool(BaseTool):
    """抖音获取单个视频详情工具"""

    name: str = "douyin_fetch_video_detail"
    description: str = (
        "获取抖音单个视频的详细信息。"
        "支持通过视频链接或 aweme_id 获取。"
        "返回视频标题、描述、播放量、点赞、评论、作者信息等。"
        "示例链接: https://www.douyin.com/video/7372484719365098803"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "url_or_aweme_id": {
                "type": "string",
                "description": "视频链接或 aweme_id（如：7372484719365098803）"
            }
        },
        "required": ["url_or_aweme_id"]
    }

    async def execute(
        self,
        url_or_aweme_id: str,
        **kwargs
    ) -> ToolResult:
        """获取视频详情"""
        try:
            def extract_url(text: str) -> str:
                match = re.search(r"https?://\\S+", text or "")
                return match.group(0) if match else text

            def extract_aweme_id(url_or_id: str) -> str:
                candidate = (url_or_id or "").strip()
                if candidate.isdigit():
                    return candidate
                if "aweme_id=" in candidate:
                    return candidate.split("aweme_id=")[-1].split("&")[0]
                if "item_id=" in candidate:
                    return candidate.split("item_id=")[-1].split("&")[0]
                if "/video/" in candidate:
                    return candidate.split("/video/")[-1].split("?")[0].split("/")[0]
                return candidate

            raw_input = url_or_aweme_id.strip()
            url_or_id = extract_url(raw_input)

            # Resolve short link if needed
            if "v.douyin.com/" in url_or_id:
                try:
                    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                        resp = await client.get(url_or_id)
                        if resp.url:
                            url_or_id = str(resp.url)
                except Exception:
                    pass

            aweme_id = extract_aweme_id(url_or_id)

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{DOUYIN_API_BASE_URL}/fetch_one_video",
                    params={"aweme_id": aweme_id}
                )
                response.raise_for_status()
                result = response.json()

                if result.get("code") == 200:
                    video = result.get("data", {})
                    stats = video.get("statistics", {})
                    author = video.get("author", {})

                    output = f"🎬 视频详情\n\n"
                    output += f"**标题**: {video.get('desc', '无标题')}\n\n"
                    output += f"**作者**: {author.get('nickname', 'N/A')} (@{author.get('unique_id', 'N/A')})\n"
                    output += f"**aweme_id**: {aweme_id}\n\n"
                    output += f"**数据统计**:\n"
                    output += f"- 播放量: {stats.get('play_count', 0):,}\n"
                    output += f"- 点赞数: {stats.get('digg_count', 0):,}\n"
                    output += f"- 评论数: {stats.get('comment_count', 0):,}\n"
                    output += f"- 分享数: {stats.get('share_count', 0):,}\n"
                    output += f"- 收藏数: {stats.get('collect_count', 0):,}\n\n"
                    output += f"**发布时间**: {video.get('create_time', 'N/A')}\n"

                    return ToolResult(output=output)
                else:
                    return ToolResult(error=f"API 返回错误: {result.get('message', '未知错误')}")

        except Exception as e:
            return ToolResult(error=f"获取视频详情失败: {str(e)}")


# ============================================
# TikTok API 工具（国际版）
# ============================================

class TikTokFetchUserInfoTool(BaseTool):
    """TikTok 获取用户信息工具"""

    name: str = "tiktok_fetch_user_info"
    description: str = (
        "获取 TikTok 用户的详细信息（国际版）。"
        "支持通过用户主页链接或 unique_id 获取。"
        "返回用户昵称、粉丝数、获赞数、简介等信息。"
        "示例链接: https://www.tiktok.com/@username"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "url_or_unique_id": {
                "type": "string",
                "description": "用户主页链接或 unique_id（如：@username）"
            }
        },
        "required": ["url_or_unique_id"]
    }

    async def execute(
        self,
        url_or_unique_id: str,
        **kwargs
    ) -> ToolResult:
        """获取 TikTok 用户信息"""
        try:
            # 提取 unique_id
            unique_id = url_or_unique_id
            if "tiktok.com/@" in url_or_unique_id:
                unique_id = url_or_unique_id.split("@")[-1].split("?")[0].split("/")[0]
            unique_id = unique_id.lstrip("@")

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{TIKTOK_API_BASE_URL}/fetch_user_detail",
                    params={"unique_id": unique_id}
                )
                response.raise_for_status()
                result = response.json()

                if result.get("code") == 200:
                    user_data = result.get("data", {})
                    output = f"✅ 成功获取 TikTok 用户信息\n\n"
                    output += f"- 昵称: {user_data.get('nickname', 'N/A')}\n"
                    output += f"- 用户名: @{user_data.get('unique_id', 'N/A')}\n"
                    output += f"- 粉丝数: {user_data.get('follower_count', 0):,}\n"
                    output += f"- 获赞数: {user_data.get('total_favorited', 0):,}\n"
                    output += f"- 作品数: {user_data.get('video_count', 0)}\n"
                    output += f"- 简介: {user_data.get('signature', 'N/A')}\n"
                    return ToolResult(output=output)
                else:
                    return ToolResult(error=f"API 返回错误: {result.get('message', '未知错误')}")

        except Exception as e:
            return ToolResult(error=f"获取 TikTok 用户信息失败: {str(e)}")


class TikTokFetchUserVideosTool(BaseTool):
    """TikTok 获取用户视频列表工具"""

    name: str = "tiktok_fetch_user_videos"
    description: str = (
        "获取 TikTok 用户发布的视频列表（国际版）。"
        "支持分页获取，返回视频标题、播放量、点赞数、评论数等信息。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "url_or_unique_id": {
                "type": "string",
                "description": "用户主页链接或 unique_id"
            },
            "max_cursor": {
                "type": "integer",
                "description": "分页游标（从0开始）",
                "default": 0
            },
            "count": {
                "type": "integer",
                "description": "每页数量（建议20-50）",
                "default": 20
            }
        },
        "required": ["url_or_unique_id"]
    }

    async def execute(
        self,
        url_or_unique_id: str,
        max_cursor: int = 0,
        count: int = 20,
        **kwargs
    ) -> ToolResult:
        """获取 TikTok 用户视频列表"""
        try:
            # 提取 unique_id
            unique_id = url_or_unique_id
            if "tiktok.com/@" in url_or_unique_id:
                unique_id = url_or_unique_id.split("@")[-1].split("?")[0].split("/")[0]
            unique_id = unique_id.lstrip("@")

            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.get(
                    f"{TIKTOK_API_BASE_URL}/fetch_user_post_videos",
                    params={
                        "unique_id": unique_id,
                        "max_cursor": max_cursor,
                        "count": count
                    }
                )
                response.raise_for_status()
                result = response.json()

                if result.get("code") == 200:
                    data = result.get("data", {})
                    videos = data.get("itemList", [])
                    has_more = data.get("hasMore", False)

                    output = f"📹 找到 {len(videos)} 个 TikTok 视频\n\n"

                    for idx, video in enumerate(videos, 1):
                        stats = video.get("stats", {})
                        output += f"{idx}. {video.get('desc', '无标题')[:50]}\n"
                        output += f"   - ID: {video.get('id')}\n"
                        output += f"   - 播放: {stats.get('playCount', 0):,}\n"
                        output += f"   - 点赞: {stats.get('diggCount', 0):,}\n"
                        output += f"   - 评论: {stats.get('commentCount', 0):,}\n"
                        output += f"   - 分享: {stats.get('shareCount', 0):,}\n\n"

                    if has_more:
                        output += f"\n还有更多视频，下一页游标: {data.get('cursor')}"

                    return ToolResult(output=output)
                else:
                    return ToolResult(error=f"API 返回错误: {result.get('message', '未知错误')}")

        except Exception as e:
            return ToolResult(error=f"获取 TikTok 视频列表失败: {str(e)}")


class TikTokFetchVideoDetailTool(BaseTool):
    """TikTok 获取单个视频详情工具"""

    name: str = "tiktok_fetch_video_detail"
    description: str = (
        "获取 TikTok 单个视频的详细信息（国际版）。"
        "支持通过视频链接或 video_id 获取。"
        "示例链接: https://www.tiktok.com/@username/video/1234567890123456789"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "url_or_video_id": {
                "type": "string",
                "description": "视频链接或 video_id"
            }
        },
        "required": ["url_or_video_id"]
    }

    async def execute(
        self,
        url_or_video_id: str,
        **kwargs
    ) -> ToolResult:
        """获取 TikTok 视频详情"""
        try:
            # 提取 video_id
            video_id = url_or_video_id
            if "tiktok.com/" in url_or_video_id and "/video/" in url_or_video_id:
                video_id = url_or_video_id.split("/video/")[-1].split("?")[0]

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{TIKTOK_API_BASE_URL}/fetch_one_video",
                    params={"aweme_id": video_id}
                )
                response.raise_for_status()
                result = response.json()

                if result.get("code") == 200:
                    video = result.get("data", {})
                    stats = video.get("stats", {})
                    author = video.get("author", {})

                    output = f"🎬 TikTok 视频详情\n\n"
                    output += f"**标题**: {video.get('desc', '无标题')}\n\n"
                    output += f"**作者**: {author.get('nickname', 'N/A')} (@{author.get('uniqueId', 'N/A')})\n"
                    output += f"**video_id**: {video_id}\n\n"
                    output += f"**数据统计**:\n"
                    output += f"- 播放量: {stats.get('playCount', 0):,}\n"
                    output += f"- 点赞数: {stats.get('diggCount', 0):,}\n"
                    output += f"- 评论数: {stats.get('commentCount', 0):,}\n"
                    output += f"- 分享数: {stats.get('shareCount', 0):,}\n"
                    output += f"- 收藏数: {stats.get('collectCount', 0):,}\n\n"
                    output += f"**发布时间**: {video.get('createTime', 'N/A')}\n"

                    return ToolResult(output=output)
                else:
                    return ToolResult(error=f"API 返回错误: {result.get('message', '未知错误')}")

        except Exception as e:
            return ToolResult(error=f"获取 TikTok 视频详情失败: {str(e)}")


# ============================================
# Bilibili API 工具
# ============================================

class BilibiliFetchUserInfoTool(BaseTool):
    """B站获取用户信息工具"""

    name: str = "bilibili_fetch_user_info"
    description: str = (
        "获取 B站（哔哩哔哩）用户的详细信息。"
        "支持通过用户主页链接或 UID 获取。"
        "返回用户昵称、粉丝数、获赞数、简介等信息。"
        "示例链接: https://space.bilibili.com/178360345"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "url_or_uid": {
                "type": "string",
                "description": "用户主页链接或 UID（如：178360345）"
            }
        },
        "required": ["url_or_uid"]
    }

    async def execute(
        self,
        url_or_uid: str,
        **kwargs
    ) -> ToolResult:
        """获取 B站用户信息"""
        try:
            # 提取 UID
            uid = url_or_uid
            if "space.bilibili.com/" in url_or_uid:
                uid = url_or_uid.split("/")[-1].split("?")[0]

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{BILIBILI_API_BASE_URL}/fetch_user_profile",
                    params={"uid": uid}
                )
                response.raise_for_status()
                result = response.json()

                if result.get("code") == 200:
                    user_data = result.get("data", {})
                    output = f"✅ 成功获取 B站用户信息\n\n"
                    output += f"- 昵称: {user_data.get('name', 'N/A')}\n"
                    output += f"- UID: {uid}\n"
                    output += f"- 粉丝数: {user_data.get('follower', 0):,}\n"
                    output += f"- 关注数: {user_data.get('following', 0):,}\n"
                    output += f"- 获赞数: {user_data.get('likes', 0):,}\n"
                    output += f"- 投稿数: {user_data.get('videos', 0)}\n"
                    output += f"- 简介: {user_data.get('sign', 'N/A')}\n"
                    return ToolResult(output=output)
                else:
                    return ToolResult(error=f"API 返回错误: {result.get('message', '未知错误')}")

        except Exception as e:
            return ToolResult(error=f"获取 B站用户信息失败: {str(e)}")


class BilibiliFetchUserVideosTool(BaseTool):
    """B站获取用户视频列表工具"""

    name: str = "bilibili_fetch_user_videos"
    description: str = (
        "获取 B站用户发布的视频列表。"
        "支持分页获取，返回视频标题、播放量、点赞数、评论数等信息。"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "url_or_uid": {
                "type": "string",
                "description": "用户主页链接或 UID"
            },
            "pn": {
                "type": "integer",
                "description": "页码（从1开始）",
                "default": 1
            }
        },
        "required": ["url_or_uid"]
    }

    async def execute(
        self,
        url_or_uid: str,
        pn: int = 1,
        **kwargs
    ) -> ToolResult:
        """获取 B站用户视频列表"""
        try:
            # 提取 UID
            uid = url_or_uid
            if "space.bilibili.com/" in url_or_uid:
                uid = url_or_uid.split("/")[-1].split("?")[0]

            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.get(
                    f"{BILIBILI_API_BASE_URL}/fetch_user_post_videos",
                    params={
                        "uid": uid,
                        "pn": pn
                    }
                )
                response.raise_for_status()
                result = response.json()

                if result.get("code") == 200:
                    data = result.get("data", {})
                    videos = data.get("vlist", [])
                    total = data.get("count", 0)

                    output = f"📹 找到 {len(videos)} 个 B站视频（共 {total} 个）\n\n"

                    for idx, video in enumerate(videos, 1):
                        output += f"{idx}. {video.get('title', '无标题')}\n"
                        output += f"   - BV号: {video.get('bvid', 'N/A')}\n"
                        output += f"   - 播放: {video.get('play', 0):,}\n"
                        output += f"   - 弹幕: {video.get('video_review', 0):,}\n"
                        output += f"   - 评论: {video.get('comment', 0):,}\n"
                        output += f"   - 时长: {video.get('length', 'N/A')}\n\n"

                    if total > len(videos):
                        output += f"\n还有更多视频，当前第 {pn} 页"

                    return ToolResult(output=output)
                else:
                    return ToolResult(error=f"API 返回错误: {result.get('message', '未知错误')}")

        except Exception as e:
            return ToolResult(error=f"获取 B站视频列表失败: {str(e)}")


class BilibiliFetchVideoDetailTool(BaseTool):
    """B站获取单个视频详情工具"""

    name: str = "bilibili_fetch_video_detail"
    description: str = (
        "获取 B站单个视频的详细信息。"
        "支持通过视频链接或 BV号 获取。"
        "返回视频标题、描述、播放量、点赞、评论、UP主信息等。"
        "示例链接: https://www.bilibili.com/video/BV1M1421t7hT"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "url_or_bvid": {
                "type": "string",
                "description": "视频链接或 BV号（如：BV1M1421t7hT）"
            }
        },
        "required": ["url_or_bvid"]
    }

    async def execute(
        self,
        url_or_bvid: str,
        **kwargs
    ) -> ToolResult:
        """获取 B站视频详情"""
        try:
            # 提取 BV号
            bvid = url_or_bvid
            if "bilibili.com/video/" in url_or_bvid:
                bvid = url_or_bvid.split("/video/")[-1].split("?")[0].split("/")[0]
            elif "b23.tv/" in url_or_bvid:
                # 处理短链接（需要先解析）
                pass

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{BILIBILI_API_BASE_URL}/fetch_one_video",
                    params={"bv_id": bvid}
                )
                response.raise_for_status()
                result = response.json()

                if result.get("code") == 200:
                    video = result.get("data", {})
                    stat = video.get("stat", {})
                    owner = video.get("owner", {})

                    output = f"🎬 B站视频详情\n\n"
                    output += f"**标题**: {video.get('title', '无标题')}\n\n"
                    output += f"**描述**: {video.get('desc', '无描述')[:100]}...\n\n"
                    output += f"**UP主**: {owner.get('name', 'N/A')} (UID: {owner.get('mid', 'N/A')})\n"
                    output += f"**BV号**: {bvid}\n\n"
                    output += f"**数据统计**:\n"
                    output += f"- 播放量: {stat.get('view', 0):,}\n"
                    output += f"- 点赞数: {stat.get('like', 0):,}\n"
                    output += f"- 投币数: {stat.get('coin', 0):,}\n"
                    output += f"- 收藏数: {stat.get('favorite', 0):,}\n"
                    output += f"- 分享数: {stat.get('share', 0):,}\n"
                    output += f"- 弹幕数: {stat.get('danmaku', 0):,}\n"
                    output += f"- 评论数: {stat.get('reply', 0):,}\n\n"
                    output += f"**发布时间**: {video.get('pubdate', 'N/A')}\n"
                    output += f"**时长**: {video.get('duration', 'N/A')} 秒\n"

                    return ToolResult(output=output)
                else:
                    return ToolResult(error=f"API 返回错误: {result.get('message', '未知错误')}")

        except Exception as e:
            return ToolResult(error=f"获取 B站视频详情失败: {str(e)}")


