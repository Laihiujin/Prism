"""TikTok adapter that exposes the legacy uploader through Prism's platform API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from ..base import BasePlatform
from ..path_utils import resolve_cookie_file, resolve_video_file


def _parse_publish_date(value: Any) -> Any:
    if not value:
        return 0
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    return datetime.strptime(normalized, pattern)
                except ValueError:
                    continue
    raise ValueError("TikTok publish_date must be an ISO date/time or timestamp")


class TikTokUpload(BasePlatform):
    def __init__(self) -> None:
        super().__init__(platform_code=6, platform_name="TikTok")

    async def login(self, account_id: str, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Use `prism tiktok login --account <name>` for interactive TikTok login")

    async def upload(
        self,
        account_file: str,
        title: str,
        file_path: str,
        tags: list,
        publish_date: Optional[Any] = None,
        description: str = "",
        thumbnail_path: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        from uploader.tk_uploader.main_chrome import TiktokVideo

        account_path = resolve_cookie_file(account_file)
        video_path = resolve_video_file(file_path)
        caption = "\n\n".join(part.strip() for part in (title, description) if part and part.strip())
        uploader = TiktokVideo(
            caption or title,
            video_path,
            tags or [],
            _parse_publish_date(publish_date),
            account_path,
            thumbnail_path=thumbnail_path,
        )
        await uploader.main()
        return {
            "success": True,
            "message": "TikTok upload submitted",
            "platform": "tiktok",
        }


tiktok_upload = TikTokUpload()
