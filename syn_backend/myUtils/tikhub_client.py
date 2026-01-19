from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
from sqlalchemy import text

from fastapi_app.core.config import settings
from fastapi_app.db.runtime import mysql_enabled, sa_connection


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

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._client:
            self._client = httpx.AsyncClient(timeout=60.0)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.api_root}{path}"
        resp = await self._client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def fetch_kuaishou_user_posts(self, user_id: str, pcursor: Optional[str] = None) -> Dict[str, Any]:
        params = {"user_id": user_id}
        if pcursor:
            params["pcursor"] = pcursor
        return await self._get("/kuaishou/web/fetch_user_post", params=params)

    async def fetch_xiaohongshu_home_notes(self, user_id: str, cursor: Optional[str] = None) -> Dict[str, Any]:
        params = {"user_id": user_id}
        if cursor:
            params["cursor"] = cursor
        return await self._get("/xiaohongshu/web_v2/fetch_home_notes", params=params)

    async def fetch_channels_home(self, username: str, last_buffer: Optional[str] = None) -> Dict[str, Any]:
        params = {"username": username}
        if last_buffer:
            params["last_buffer"] = last_buffer
        return await self._get("/wechat_channels/fetch_home_page", params=params)

    async def fetch_channels_hot_words(self) -> Dict[str, Any]:
        return await self._get("/wechat_channels/fetch_hot_words")

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
