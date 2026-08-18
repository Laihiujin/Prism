"""
视频号上传模块 - 平台层统一入口
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ..base import BasePlatform
from ..path_utils import resolve_cookie_file, resolve_video_file

logger = logging.getLogger(__name__)


class TencentUpload(BasePlatform):
    """视频号上传处理类（平台层入口）。"""

    def __init__(self):
        super().__init__(platform_code=2, platform_name="视频号")

    async def login(self, account_id: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError("请使用 FastAPI auth V2 登录服务")

    async def upload(
        self,
        account_file: str,
        title: str,
        file_path: str,
        tags: list,
        publish_date: Optional[Any] = None,
        thumbnail_path: Optional[str] = None,
        category: Optional[int] = None,
        description: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        上传并发布视频号视频（目前复用旧 uploader 实现）。
        """
        from uploader.tencent_uploader.main import TencentVideo
        from utils.constant import TencentZoneTypes

        account_file = resolve_cookie_file(account_file)
        file_path = resolve_video_file(file_path)

        publish_value: Any = 0
        if publish_date:
            if isinstance(publish_date, datetime):
                publish_value = publish_date
            elif isinstance(publish_date, (int, float)):
                publish_value = datetime.fromtimestamp(publish_date)
            elif isinstance(publish_date, str):
                s = publish_date.strip().replace("T", " ").replace("Z", "")
                try:
                    publish_value = datetime.fromisoformat(s)
                except Exception:
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                        try:
                            publish_value = datetime.strptime(s, fmt)
                            break
                        except Exception:
                            continue
            else:
                publish_value = publish_date

        uploader = TencentVideo(
            title=title,
            file_path=file_path,
            tags=tags or [],
            publish_date=publish_value,
            account_file=account_file,
            category=category or TencentZoneTypes.LIFESTYLE.value,
            thumbnail_path=thumbnail_path,
        )

        # 旧实现内部使用 async_playwright；这里直接 await
        await uploader.main()

        return {
            "success": True,
            "message": "上传成功",
            "data": {
                "title": title,
                "file_path": file_path,
                "description": description,
            },
        }


tencent_upload = TencentUpload()
