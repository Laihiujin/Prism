"""Baijiahao adapter exposed through Prism's platform registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from ..base import BasePlatform
from ..path_utils import resolve_cookie_file, resolve_video_file


class BaijiahaoUpload(BasePlatform):
    def __init__(self) -> None:
        super().__init__(platform_code=8, platform_name="百家号")

    async def login(self, account_id: str, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Use prism baijiahao login --account <name> for interactive login")

    async def upload(
        self,
        account_file: str,
        title: str,
        file_path: str,
        tags: list,
        publish_date: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        from uploader.baijiahao_uploader.main import BaiJiaHaoVideo

        value: Any = 0
        if publish_date:
            if isinstance(publish_date, datetime):
                value = publish_date
            elif isinstance(publish_date, (int, float)):
                value = datetime.fromtimestamp(publish_date)
            elif isinstance(publish_date, str):
                value = datetime.fromisoformat(publish_date.strip().replace("Z", "+00:00"))
            else:
                raise ValueError("Baijiahao publish_date must be datetime, timestamp, or ISO date/time")

        uploader = BaiJiaHaoVideo(
            title,
            resolve_video_file(file_path),
            tags or [],
            value,
            resolve_cookie_file(account_file),
        )
        await uploader.main()
        return {"success": True, "message": "Baijiahao upload submitted", "platform": "baijiahao"}


baijiahao_upload = BaijiahaoUpload()

