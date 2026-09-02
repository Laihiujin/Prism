from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
from sqlalchemy import text

from fastapi_app.core.config import settings
from fastapi_app.db.runtime import mysql_enabled, sa_connection

# TikHub 端点配置：由 scripts/update_tikhub_api.py 从官网 OpenAPI 自动生成。
# 当官方升级接口（v4/v5/v6…）后，运行该脚本即可自动更新，无需手改代码。
_TIKHUB_ENDPOINTS_FILE = Path(__file__).resolve().parent / "tikhub_endpoints.json"

# 内置默认端点（兜底）：若配置文件缺失或语义键未匹配，则回退到这些路径。
# 注意：这些默认值会随官方 API 演进而过期，请优先使用 update_tikhub_api.py 生成的配置。
DEFAULT_ENDPOINTS: Dict[str, Dict[str, Any]] = {
    "kuaishou_user_posts": {"path": "/api/v1/kuaishou/app/fetch_user_post_v2", "method": "GET", "params": {"user_id": "user_id", "pcursor": "pcursor"}},
    "kuaishou_user_info": {"path": "/api/v1/kuaishou/web/fetch_user_info", "method": "GET", "params": {"user_id": "user_id"}},
    "kuaishou_one_video": {"path": "/api/v1/kuaishou/web/fetch_one_video", "method": "GET", "params": {"share_text": "share_text"}},
    "kuaishou_one_video_by_url": {"path": "/api/v1/kuaishou/web/fetch_one_video_by_url", "method": "GET", "params": {"url": "url"}},
    "kuaishou_hot_list": {"path": "/api/v1/kuaishou/web/fetch_kuaishou_hot_list_v1", "method": "GET", "params": {}},
    "xhs_user_notes": {"path": "/api/v1/xiaohongshu/app_v2/get_user_posted_notes", "method": "GET", "params": {"user_id": "user_id", "cursor": "cursor"}},
    "xhs_user_info": {"path": "/api/v1/xiaohongshu/web_v3/fetch_user_info", "method": "GET", "params": {"user_id": "user_id"}},
    "xhs_note_id_and_xsec_token": {"path": "/api/v1/xiaohongshu/web/get_note_id_and_xsec_token", "method": "GET", "params": {"url": "url"}},
    "channels_user_videos": {"path": "/api/v1/wechat_channels/v2/fetch_user_videos", "method": "POST", "params": {"username": "username", "last_buffer": "last_buffer"}},
    "channels_channel_info": {"path": "/api/v1/wechat_channels/v2/fetch_channel_info", "method": "POST", "params": {"username": "username"}},
    "channels_video_detail": {"path": "/api/v1/wechat_channels/v2/fetch_video_detail", "method": "POST", "params": {"object_id": "object_id", "export_id": "export_id"}},
    "tiktok_user_profile": {"path": "/api/v1/tiktok/web/fetch_user_profile", "method": "GET", "params": {"secUid": "secUid", "unique_id": "uniqueId"}},
    "tiktok_user_posts": {"path": "/api/v1/tiktok/web/fetch_user_post", "method": "GET", "params": {"secUid": "secUid", "cursor": "cursor", "count": "count", "cover_format": "coverFormat"}},
    "youtube_channel_id": {"path": "/api/v1/youtube/web/get_channel_id", "method": "GET", "params": {"channel_name": "channel_name"}},
    "youtube_channel_id_v2": {"path": "/api/v1/youtube/web/get_channel_id_v2", "method": "GET", "params": {"channel_url": "channel_url"}},
    "youtube_channel_info": {"path": "/api/v1/youtube/web/get_channel_info", "method": "GET", "params": {"channel_id": "channel_id"}},
    "youtube_channel_videos": {"path": "/api/v1/youtube/web/get_channel_videos_v2", "method": "GET", "params": {"channel_id": "channel_id", "next_token": "nextToken", "sort_by": "sortBy", "content_type": "contentType"}},
    "health_check": {"path": "/api/v1/health/check", "method": "GET", "params": {}},
    "tikhub_user_info": {"path": "/api/v1/tikhub/user/get_user_info", "method": "GET", "params": {}},
}


def _load_endpoint_config() -> Dict[str, Dict[str, Any]]:
    """加载 update_tikhub_api.py 生成的端点配置；缺失时回退到内置默认值。"""
    try:
        if _TIKHUB_ENDPOINTS_FILE.exists():
            raw = json.loads(_TIKHUB_ENDPOINTS_FILE.read_text(encoding="utf-8"))
            endpoints = raw.get("endpoints") or {}
            merged = dict(DEFAULT_ENDPOINTS)
            for key, entry in endpoints.items():
                if isinstance(entry, dict) and entry.get("path"):
                    merged[key] = entry
            return merged
    except Exception:
        pass
    return dict(DEFAULT_ENDPOINTS)


# 模块级缓存：进程内只解析一次；通过 _reload_endpoint_config() 可强制刷新（供 CLI 热更新使用）。
_ENDPOINT_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def _reload_endpoint_config() -> Dict[str, Dict[str, Any]]:
    global _ENDPOINT_CACHE
    _ENDPOINT_CACHE = _load_endpoint_config()
    return _ENDPOINT_CACHE


def _get_endpoint_config() -> Dict[str, Dict[str, Any]]:
    global _ENDPOINT_CACHE
    if _ENDPOINT_CACHE is None:
        _ENDPOINT_CACHE = _load_endpoint_config()
    return _ENDPOINT_CACHE


@dataclass(frozen=True)
class TikHubConfig:
    api_key: str
    base_url: str
    is_active: bool = True


def _normalize_base_url(value: str) -> str:
    base = (value or "").strip()
    if not base:
        return "https://api.tikhub.io"
    if not base.startswith("http://") and not base.startswith("https://"):
        base = f"https://{base}"
    return base.rstrip("/")


def load_tikhub_config() -> Optional[TikHubConfig]:
    api_key = (os.getenv("TIKHUB_API_KEY") or "").strip()
    base_url = _normalize_base_url(os.getenv("TIKHUB_BASE_URL") or "https://api.tikhub.io")

    try:
        row: Optional[Dict[str, Any]] = None
        if mysql_enabled():
            with sa_connection() as conn:
                row = conn.execute(
                    text("SELECT * FROM ai_model_configs WHERE service_type = :t"),
                    {"t": "tikhub"},
                ).mappings().first()
                row = dict(row) if row else None
        else:
            import sqlite3

            conn = sqlite3.connect(settings.DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_model_configs WHERE service_type = ?", ("tikhub",))
            fetched = cursor.fetchone()
            conn.close()
            row = dict(fetched) if fetched else None

        if row:
            api_key = (row.get("api_key") or api_key).strip()
            base_url = _normalize_base_url(row.get("base_url") or base_url)
            is_active = bool(row.get("is_active", 1))
            if api_key:
                return TikHubConfig(api_key=api_key, base_url=base_url, is_active=is_active)
    except Exception:
        if api_key:
            return TikHubConfig(api_key=api_key, base_url=base_url, is_active=True)
        return None

    if api_key:
        return TikHubConfig(api_key=api_key, base_url=base_url, is_active=True)
    return None


def get_tikhub_client() -> Optional["TikHubClient"]:
    config = load_tikhub_config()
    if not config or not config.api_key or not config.is_active:
        return None
    return TikHubClient(api_key=config.api_key, base_url=config.base_url)


def _choose(*values: Any) -> Optional[Any]:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        return int(digits) if digits else 0
    return 0


def _normalize_timestamp(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            try:
                return _normalize_timestamp(int(text))
            except Exception:
                return text
        return text
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts = ts / 1000.0
        elif ts > 1e10:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts).isoformat()
        except Exception:
            return str(value)
    return str(value)


def _extract_url(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("url", "url_default", "url_default2", "url_default3"):
            if key in value and value.get(key):
                return value.get(key)
        for key in ("url_list", "urlList", "urls"):
            urls = value.get(key)
            if isinstance(urls, list) and urls:
                first = urls[0]
                if isinstance(first, str):
                    return first
    return None


class TikHubClient:
    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key.strip()
        self.base_url = _normalize_base_url(base_url)
        self.api_root = f"{self.base_url}/api/v1"
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "TikHubClient":
        if not self._client:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _endpoint(self, key: str) -> Dict[str, Any]:
        """按语义键取端点（路径/方法/参数映射），配置缺失时回退默认值。"""
        config = _get_endpoint_config()
        return config.get(key) or DEFAULT_ENDPOINTS.get(key) or {"path": "", "method": "GET", "params": {}}

    def _ensure_client(self) -> httpx.AsyncClient:
        if not self._client:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def _request(self, key: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """按语义键 + 语义参数发起请求，自动处理 query 参数与 JSON body。"""
        ep = self._endpoint(key)
        path = ep.get("path") or ""
        if not path:
            raise ValueError(f"TikHub endpoint not configured: {key}")
        # 配置文件里的路径自带 /api/v1 前缀，api_root 已包含，需去掉避免重复
        if path.lower().startswith("/api/v1"):
            path = path[len("/api/v1"):]
        method = (ep.get("method") or "GET").upper()
        param_map = ep.get("params") or {}

        # 将语义参数名映射为官方实际参数名，并剔除 None/空值
        final: Dict[str, Any] = {}
        for semantic, value in params.items():
            if value is None or value == "":
                continue
            actual = param_map.get(semantic, semantic)
            final[actual] = value

        client = self._ensure_client()
        headers = {"Authorization": f"Bearer {self.api_key}", "User-Agent": "Prism/1.0"}
        url = f"{self.api_root}{path}"
        if method == "POST":
            resp = await client.post(url, json=final, headers=headers)
        else:
            resp = await client.get(url, params=final, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def fetch_kuaishou_user_posts(self, user_id: str, pcursor: Optional[str] = None) -> Dict[str, Any]:
        return await self._request("kuaishou_user_posts", {"user_id": user_id, "pcursor": pcursor})

    async def fetch_kuaishou_user_info(self, user_id: str) -> Dict[str, Any]:
        return await self._request("kuaishou_user_info", {"user_id": user_id})

    async def fetch_kuaishou_video_by_share_text(self, share_text: str) -> Dict[str, Any]:
        return await self._request("kuaishou_one_video", {"share_text": share_text})

    async def fetch_kuaishou_video_by_url(self, url: str) -> Dict[str, Any]:
        return await self._request("kuaishou_one_video_by_url", {"url": url})

    async def fetch_kuaishou_hot_list(self) -> Dict[str, Any]:
        return await self._request("kuaishou_hot_list", {})

    async def fetch_xiaohongshu_home_notes(self, user_id: str, cursor: Optional[str] = None) -> Dict[str, Any]:
        return await self._request("xhs_user_notes", {"user_id": user_id, "cursor": cursor})

    async def fetch_xiaohongshu_user_info(self, user_id: str) -> Dict[str, Any]:
        return await self._request("xhs_user_info", {"user_id": user_id})

    async def fetch_xiaohongshu_user_notes_v2(
        self,
        user_id: str,
        last_cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self.fetch_xiaohongshu_home_notes(user_id=user_id, cursor=last_cursor)

    async def fetch_xiaohongshu_note_id_and_xsec_token(self, url: str) -> Dict[str, Any]:
        return await self._request("xhs_note_id_and_xsec_token", {"url": url})

    async def fetch_channels_home(self, username: str, last_buffer: Optional[str] = None) -> Dict[str, Any]:
        return await self._request("channels_user_videos", {"username": username, "last_buffer": last_buffer})

    async def fetch_channels_video_detail(
        self,
        video_id: Optional[str] = None,
        export_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._request(
            "channels_video_detail",
            {"object_id": video_id, "export_id": export_id},
        )

    async def fetch_channels_hot_words(self) -> Dict[str, Any]:
        # 旧端点已移除：改为健康检查 + 用户信息，用于连通性测试
        return await self.health_check()

    async def fetch_tiktok_user_profile(self, secUid: Optional[str] = None, unique_id: Optional[str] = None) -> Dict[str, Any]:
        return await self._request("tiktok_user_profile", {"secUid": secUid, "unique_id": unique_id})

    async def fetch_tiktok_user_posts(self, secUid: str, cursor: Optional[str] = None, count: int = 15) -> Dict[str, Any]:
        return await self._request("tiktok_user_posts", {"secUid": secUid, "cursor": cursor, "count": count, "cover_format": 2})

    async def fetch_youtube_channel_id(self, channel_name: str) -> Dict[str, Any]:
        return await self._request("youtube_channel_id", {"channel_name": channel_name})

    async def fetch_youtube_channel_id_v2(self, channel_url: str) -> Dict[str, Any]:
        return await self._request("youtube_channel_id_v2", {"channel_url": channel_url})

    async def fetch_youtube_channel_info(self, channel_id: str) -> Dict[str, Any]:
        return await self._request("youtube_channel_info", {"channel_id": channel_id})

    async def fetch_youtube_channel_videos(self, channel_id: str, next_token: Optional[str] = None) -> Dict[str, Any]:
        return await self._request(
            "youtube_channel_videos",
            {"channel_id": channel_id, "next_token": next_token, "sort_by": "newest", "content_type": "video"},
        )

    async def health_check(self) -> Dict[str, Any]:
        return await self._request("health_check", {})

    async def get_tikhub_user_info(self) -> Dict[str, Any]:
        return await self._request("tikhub_user_info", {})

    def parse_kuaishou_posts(self, payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        data = payload.get("data") or {}
        feeds = data.get("feeds") or []
        videos: List[Dict[str, Any]] = []
        for feed in feeds:
            photo = feed.get("photo") or {}
            video_id = _choose(photo.get("id"), photo.get("photoId"), photo.get("photo_id"))
            title = _choose(photo.get("caption"), photo.get("title"), photo.get("desc")) or ""
            cover = _choose(
                photo.get("coverUrl"),
                photo.get("overrideCoverUrl"),
                photo.get("animatedCoverUrl"),
                photo.get("cover_url"),
            )
            videos.append(
                {
                    "video_id": video_id,
                    "title": title,
                    "cover_url": cover,
                    "play_count": _to_int(_choose(photo.get("viewCount"), photo.get("playCount"), photo.get("view_count"))),
                    "like_count": _to_int(_choose(photo.get("likeCount"), photo.get("like_count"))),
                    "comment_count": _to_int(_choose(photo.get("commentCount"), photo.get("comment_count"), (feed.get("comment") or {}).get("us_c"))),
                    "share_count": _to_int(_choose(photo.get("shareCount"), photo.get("share_count"))),
                    "collect_count": _to_int(_choose(photo.get("collectCount"), photo.get("collect_count"))),
                    "publish_time": _normalize_timestamp(_choose(photo.get("timestamp"), photo.get("publishTime"), photo.get("uploadTime"))),
                }
            )
        return videos, data.get("pcursor")

    def parse_xiaohongshu_notes(self, payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        data = payload.get("data") if isinstance(payload, dict) else payload
        cursor = None
        items: List[Any] = []

        if isinstance(data, dict):
            cursor = _choose(data.get("cursor"), data.get("next_cursor"), data.get("nextCursor"))
            for key in ("items", "notes", "note_list", "list", "data"):
                candidate = data.get(key)
                if isinstance(candidate, list):
                    items = candidate
                    break
        elif isinstance(data, list):
            items = data

        videos: List[Dict[str, Any]] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            note = raw.get("note_card") or raw.get("note") or raw.get("note_info") or raw
            video_id = _choose(
                note.get("id"),
                note.get("note_id"),
                note.get("noteId"),
                note.get("note_id_str"),
            )
            title = _choose(note.get("display_title"), note.get("title"), note.get("desc"), note.get("description")) or ""

            cover = note.get("cover") or note.get("cover_url") or note.get("coverUrl")
            cover_url = _extract_url(cover)

            if not cover_url:
                image_list = note.get("image_list") or note.get("images") or []
                if isinstance(image_list, list) and image_list:
                    cover_url = _extract_url(image_list[0]) or cover_url

            video_block = note.get("video") or {}
            if not cover_url and isinstance(video_block, dict):
                cover_url = _extract_url(
                    _choose(
                        video_block.get("cover"),
                        video_block.get("cover_url"),
                        video_block.get("coverUrl"),
                        video_block.get("cover_image"),
                    )
                )

            interact = note.get("interact_info") or note.get("interactInfo") or note.get("interaction_info") or {}

            videos.append(
                {
                    "video_id": video_id,
                    "title": title,
                    "cover_url": cover_url,
                    "play_count": _to_int(_choose(note.get("view_count"), video_block.get("view_count"), video_block.get("play_count"))),
                    "like_count": _to_int(_choose(interact.get("liked_count"), interact.get("like_count"), interact.get("likes"))),
                    "comment_count": _to_int(_choose(interact.get("comment_count"), interact.get("comments"))),
                    "share_count": _to_int(_choose(interact.get("share_count"), interact.get("share"))),
                    "collect_count": _to_int(_choose(interact.get("collected_count"), interact.get("collect_count"), interact.get("collects"))),
                    "publish_time": _normalize_timestamp(
                        _choose(
                            note.get("time"),
                            note.get("publish_time"),
                            note.get("update_time"),
                            note.get("post_time"),
                        )
                    ),
                }
            )
        return videos, cursor

    def parse_channels_home(self, payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        data = payload.get("data") or {}
        items = data.get("object_list") or []
        last_buffer = None
        if isinstance(items, list) and items:
            last_item = items[-1]
            if isinstance(last_item, dict):
                last_buffer = last_item.get("last_buffer")

        videos: List[Dict[str, Any]] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            obj = raw.get("object_desc") or {}
            media_list = obj.get("media") or []
            media = media_list[0] if isinstance(media_list, list) and media_list else {}
            cover_url = _extract_url(_choose(media.get("cover_url"), media.get("thumb_url"), media.get("url")))
            videos.append(
                {
                    "video_id": _choose(raw.get("id"), raw.get("object_id"), obj.get("object_id"), obj.get("id")),
                    "title": _choose(obj.get("description"), obj.get("title"), obj.get("feed_title")) or "",
                    "cover_url": cover_url,
                    "play_count": _to_int(_choose(obj.get("play_count"), obj.get("playCount"))),
                    "like_count": _to_int(_choose(obj.get("like_count"), obj.get("likeCount"))),
                    "comment_count": _to_int(_choose(obj.get("comment_count"), obj.get("commentCount"))),
                    "share_count": _to_int(_choose(obj.get("share_count"), obj.get("shareCount"))),
                    "collect_count": _to_int(_choose(obj.get("collect_count"), obj.get("collectCount"))),
                    "publish_time": _normalize_timestamp(
                        _choose(obj.get("create_time"), obj.get("publish_time"), raw.get("create_time"))
                    ),
                }
            )
        return videos, last_buffer

    async def collect_kuaishou_posts(self, user_id: str, max_pages: int = 5) -> Tuple[List[Dict[str, Any]], int]:
        pcursor: Optional[str] = None
        videos: List[Dict[str, Any]] = []
        pages = 0
        while pages < max_pages:
            payload = await self.fetch_kuaishou_user_posts(user_id=user_id, pcursor=pcursor)
            batch, next_cursor = self.parse_kuaishou_posts(payload)
            if not batch:
                break
            videos.extend(batch)
            pages += 1
            if not next_cursor or next_cursor == pcursor:
                break
            pcursor = next_cursor
        return videos, pages

    async def collect_xiaohongshu_notes(self, user_id: str, max_pages: int = 5) -> Tuple[List[Dict[str, Any]], int]:
        cursor: Optional[str] = None
        videos: List[Dict[str, Any]] = []
        pages = 0
        while pages < max_pages:
            payload = await self.fetch_xiaohongshu_home_notes(user_id=user_id, cursor=cursor)
            batch, next_cursor = self.parse_xiaohongshu_notes(payload)
            if not batch:
                break
            videos.extend(batch)
            pages += 1
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        return videos, pages

    async def collect_channels_home(self, username: str, max_pages: int = 5) -> Tuple[List[Dict[str, Any]], int]:
        last_buffer: Optional[str] = None
        videos: List[Dict[str, Any]] = []
        pages = 0
        while pages < max_pages:
            payload = await self.fetch_channels_home(username=username, last_buffer=last_buffer)
            batch, next_cursor = self.parse_channels_home(payload)
            if not batch:
                break
            videos.extend(batch)
            pages += 1
            if not next_cursor or next_cursor == last_buffer:
                break
            last_buffer = next_cursor
        return videos, pages

    def parse_tiktok_posts(self, payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """解析 TikTok fetch_user_post 响应，返回 (视频列表, 下一页游标)。

        TikTok Web API 响应结构: data.itemList = [{id, desc, createTime, stats, video, author, ...}]
        """
        data = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(data, dict):
            return [], None

        items = data.get("itemList") or data.get("item_list") or []
        has_more = data.get("hasMore") or False
        cursor = data.get("cursor") if has_more else None

        videos: List[Dict[str, Any]] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            video_id = _choose(raw.get("id"), raw.get("aweme_id"), raw.get("itemId"), raw.get("item_id"))
            stats = raw.get("stats") or raw.get("statistics") or {}
            video_block = raw.get("video") or {}
            author = raw.get("author") or {}

            videos.append(
                {
                    "video_id": video_id,
                    "title": _choose(raw.get("desc"), raw.get("title"), raw.get("description")) or "",
                    "cover_url": _extract_url(
                        _choose(
                            video_block.get("cover"),
                            video_block.get("originCover"),
                            video_block.get("dynamicCover"),
                        )
                    ),
                    "play_count": _to_int(_choose(stats.get("playCount"), stats.get("play_count"), stats.get("vv"))),
                    "like_count": _to_int(_choose(stats.get("diggCount"), stats.get("digg_count"), stats.get("like_count"))),
                    "comment_count": _to_int(_choose(stats.get("commentCount"), stats.get("comment_count"))),
                    "share_count": _to_int(_choose(stats.get("shareCount"), stats.get("share_count"))),
                    "collect_count": _to_int(_choose(stats.get("collectCount"), stats.get("collect_count"), stats.get("favoriteCount"))),
                    "publish_time": _normalize_timestamp(
                        _choose(raw.get("createTime"), raw.get("create_time"), raw.get("timestamp"))
                    ),
                    "author_name": author.get("nickname") or author.get("uniqueId") or "",
                }
            )
        return videos, cursor

    def parse_youtube_channel_id(self, payload: Dict[str, Any]) -> Optional[str]:
        """解析 YouTube get_channel_id 响应，返回 channel_id。"""
        data = payload.get("data") if isinstance(payload, dict) else payload
        if isinstance(data, dict):
            for key in ("channel_id", "channelId", "browseId"):
                value = data.get(key)
                if value:
                    return str(value)
            for key in ("content", "result", "data"):
                nested = data.get(key)
                if isinstance(nested, dict):
                    for k2 in ("channel_id", "channelId", "browseId"):
                        v2 = nested.get(k2)
                        if v2:
                            return str(v2)
        return None

    def parse_youtube_channel_videos(self, payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """解析 YouTube get_channel_videos_v2 响应，返回 (视频列表, 下一页游标)。"""
        data = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(data, dict):
            return [], None

        items: List[Any] = []
        # v2 接口返回结构通常为 data.data / data.content / data.items
        for key in ("items", "videos", "video_list", "contents"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                items = candidate
                break
        else:
            nested = data.get("data") or data.get("content") or data.get("result")
            if isinstance(nested, dict):
                for key in ("items", "videos", "video_list", "contents"):
                    candidate = nested.get(key)
                    if isinstance(candidate, list):
                        items = candidate
                        break

        next_token = _choose(data.get("nextToken"), data.get("next_token"), data.get("continuation_token"))
        if isinstance(next_token, dict):
            next_token = next_token.get("token") or next_token.get("continuation") or None

        videos: List[Dict[str, Any]] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            item = raw.get("video") or raw.get("videoRenderer") or raw.get("content") or raw
            video_id = _choose(
                item.get("video_id"),
                item.get("videoId"),
                item.get("id"),
                raw.get("video_id"),
                raw.get("videoId"),
                raw.get("id"),
            )
            title = _choose(item.get("title"), raw.get("title"), raw.get("name")) or ""
            if isinstance(title, dict):
                title = title.get("runs") or title.get("simpleText") or ""
                if isinstance(title, list):
                    title = "".join(r.get("text", "") if isinstance(r, dict) else "" for r in title)
                elif isinstance(title, dict):
                    title = ""
            elif isinstance(title, list):
                title = "".join(r.get("text", "") if isinstance(r, dict) else str(r) for r in title)

            thumbnails = item.get("thumbnail") or item.get("thumbnails") or raw.get("thumbnail") or {}
            cover_url = _extract_url(thumbnails) if isinstance(thumbnails, dict) else None

            view_text = _choose(item.get("view_count"), item.get("viewCount"), item.get("views"), raw.get("view_count"))
            if isinstance(view_text, dict):
                view_text = view_text.get("simpleText") or ""

            videos.append(
                {
                    "video_id": video_id,
                    "title": str(title),
                    "cover_url": cover_url,
                    "play_count": _to_int(view_text),
                    "like_count": 0,
                    "comment_count": 0,
                    "share_count": 0,
                    "collect_count": 0,
                    "publish_time": _normalize_timestamp(
                        _choose(item.get("published_time"), item.get("publishedTime"), item.get("publish_date"), raw.get("published_time"))
                    ),
                }
            )
        return videos, next_token

    async def resolve_tiktok_sec_uid(self, user_id: str) -> Optional[str]:
        """把账号 user_id（数字 id 或 uniqueId）解析为完整 secUid。

        TikTok 账号注册时 user_id 可能是数字 id（如 7314926308239590401），
        而 fetch_user_post 需要完整 secUid（MS4wLjAB... 格式）。
        """
        user_id = (user_id or "").strip().lstrip("@")
        if not user_id:
            return None
        try:
            profile = await self.fetch_tiktok_user_profile(secUid=user_id if user_id.isdigit() else None, unique_id=None if user_id.isdigit() else user_id)
        except Exception:
            profile = await self.fetch_tiktok_user_profile(secUid=user_id, unique_id=None)
        user = ((profile or {}).get("data") or {}).get("userInfo", {}).get("user") or {}
        sec_uid = user.get("secUid") or user.get("sec_uid")
        return str(sec_uid) if sec_uid else None

    async def collect_tiktok_posts(self, user_id: str, max_pages: int = 5) -> Tuple[List[Dict[str, Any]], int]:
        """通过 TikHub 拉取 TikTok 用户作品列表（自动解析 secUid + 翻页）。"""
        sec_uid = await self.resolve_tiktok_sec_uid(user_id)
        if not sec_uid:
            return [], 0
        cursor: Optional[str] = None
        videos: List[Dict[str, Any]] = []
        pages = 0
        while pages < max_pages:
            payload = await self.fetch_tiktok_user_posts(secUid=sec_uid, cursor=cursor, count=15)
            batch, next_cursor = self.parse_tiktok_posts(payload)
            if not batch:
                break
            videos.extend(batch)
            pages += 1
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        return videos, pages

    async def resolve_youtube_channel_id(self, channel: str) -> Optional[str]:
        """把 YouTube 频道（channel_id / handle / URL / 频道名）解析为 channel_id。

        解析策略（免费端点优先）：
        - 输入已是 channel_id（UCxxx）→ 直接返回；
        - handle（@xxx）→ 拼接为频道 URL 走 get_channel_id_v2（免费）；
        - URL → get_channel_id_v2（免费）；
        - 其余（频道名等）→ 旧版 get_channel_id（付费，可能 402，失败返回 None）。
        """
        channel = (channel or "").strip()
        if not channel:
            return None
        try:
            if re.match(r"^UC[\w-]{16,}$", channel):
                return channel
            url = channel
            if not url.startswith("http"):
                # handle 形如 @xxx；频道名无 @ 时也尝试拼 handle URL
                url = f"https://www.youtube.com/@{channel.lstrip('@')}"
            payload = await self.fetch_youtube_channel_id_v2(channel_url=url)
            cid = self.parse_youtube_channel_id(payload)
            if cid:
                return cid
            # v2 拿不到（如纯频道名），回退旧版按名称查询（付费端点，可能失败）
            payload = await self.fetch_youtube_channel_id(channel_name=channel)
            return self.parse_youtube_channel_id(payload)
        except Exception:
            return None

    async def fetch_account_profile(self, platform: str, user_id: str) -> Dict[str, Any]:
        """按平台拉取账号资料（用于登录后自动回填账号名/昵称/头像）。

        - tiktok: fetch_user_profile(secUid/uniqueId)
        - youtube: get_channel_id → get_channel_info
        - 其他平台返回空 dict（不依赖 TikHub）
        """
        user_id = (user_id or "").strip().lstrip("@")
        if not user_id:
            return {}
        try:
            if platform == "tiktok":
                profile = await self.fetch_tiktok_user_profile(
                    secUid=user_id if user_id.isdigit() else None,
                    unique_id=None if user_id.isdigit() else user_id,
                )
                data = (profile or {}).get("data") or {}
                user = (data.get("userInfo") or {}).get("user") or {}
                stats = (data.get("userInfo") or {}).get("stats") or {}
                if user.get("uniqueId") or user.get("nickname"):
                    return {
                        "user_id": str(user.get("id") or user_id),
                        "name": _choose(user.get("nickname"), user.get("uniqueId")) or "",
                        "original_name": user.get("uniqueId") or user.get("nickname") or "",
                        "avatar": _choose(user.get("avatarLarger"), user.get("avatarMedium"), user.get("avatarThumb")) or "",
                        "follower_count": _to_int(stats.get("followerCount")),
                        "video_count": _to_int(stats.get("videoCount")),
                    }
            elif platform == "youtube":
                channel_id = await self.resolve_youtube_channel_id(user_id)
                if not channel_id:
                    return {}
                info = await self.fetch_youtube_channel_info(channel_id=channel_id)
                channel = self.parse_youtube_channel_info(info)
                if channel:
                    channel["user_id"] = channel_id
                    return channel
        except Exception:
            return {}
        return {}

    def parse_youtube_channel_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """解析 YouTube get_channel_info 响应，返回 {name, original_name, avatar, ...}。"""
        data = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(data, dict):
            return {}
        # 常见的频道信息结构
        channel: Dict[str, Any] = {}
        for key in ("channel", "channel_info", "info", "header", "content"):
            nested = data.get(key)
            if isinstance(nested, dict):
                channel = nested
                break
        else:
            channel = data

        # 名称：可能嵌套在 metadata / title / basicInfo
        name = ""
        for key in ("name", "title", "channel_name", "channelName"):
            val = channel.get(key)
            if val:
                if isinstance(val, dict):
                    val = val.get("simpleText") or val.get("runs") or val.get("text") or ""
                    if isinstance(val, list):
                        val = "".join(r.get("text", "") if isinstance(r, dict) else str(r) for r in val)
                name = str(val)
                break
        if not name:
            metadata = channel.get("metadata") or channel.get("meta") or {}
            for key in ("title", "name", "channel_name"):
                val = metadata.get(key)
                if val:
                    if isinstance(val, dict):
                        val = val.get("simpleText") or val.get("content") or ""
                    name = str(val)
                    break

        # 头像
        avatar = ""
        for key in ("avatar", "avatar_url", "avatarUrl", "thumbnail", "thumbnails"):
            val = channel.get(key)
            if val:
                avatar = _extract_url(val) if isinstance(val, (dict, list)) else str(val)
                break
        if not avatar:
            meta = channel.get("metadata") or {}
            avatar = _extract_url(meta.get("avatar") or meta.get("thumbnail") or {})

        if not name and not avatar:
            return {}
        return {"name": name, "original_name": name, "avatar": avatar}

    async def collect_youtube_videos(self, channel: str, max_pages: int = 5) -> Tuple[List[Dict[str, Any]], int]:
        """通过 TikHub 拉取 YouTube 频道视频列表（自动解析 channel_id + 翻页）。"""
        channel_id = await self.resolve_youtube_channel_id(channel)
        if not channel_id:
            return [], 0
        next_token: Optional[str] = None
        videos: List[Dict[str, Any]] = []
        pages = 0
        while pages < max_pages:
            payload = await self.fetch_youtube_channel_videos(channel_id=channel_id, next_token=next_token)
            batch, next_cursor = self.parse_youtube_channel_videos(payload)
            if not batch:
                break
            videos.extend(batch)
            pages += 1
            if not next_cursor or next_cursor == next_token:
                break
            next_token = next_cursor
        return videos, pages
