"""YouTube adapter exposed through Prism's uniform platform registry."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..base import BasePlatform
from ..path_utils import resolve_cookie_file, resolve_video_file


class YouTubeUpload(BasePlatform):
    def __init__(self) -> None:
        super().__init__(platform_code=7, platform_name="YouTube")

    async def login(self, account_id: str, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Use `prism youtube login --account <name>` for interactive Google login")

    async def upload(
        self,
        account_file: str,
        title: str,
        file_path: str,
        tags: list,
        description: str = "",
        thumbnail_path: Optional[str] = None,
        playlist: Optional[str] = None,
        visibility: str = "public",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        # Keep the CLI and queued-task paths on the same upstream-compatible
        # Studio flow; do not maintain a second, simplified YouTube publisher.
        from uploader.youtube_uploader.main_refactored import YouTubeVideo

        uploader = YouTubeVideo(
            title=title,
            file_path=resolve_video_file(file_path),
            tags=tags or [],
            account_file=resolve_cookie_file(account_file),
            description=description,
            thumbnail_path=thumbnail_path,
            playlist=playlist,
            visibility=visibility,
        )
        return await uploader.main()


youtube_upload = YouTubeUpload()
