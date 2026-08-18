"""
小红书上传模块 - 平台层统一入口

说明：
- 当前复用旧实现 `uploader/xiaohongshu_uploader/main.py`
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from ..base import BasePlatform
from ..path_utils import resolve_cookie_file, resolve_video_file


class XiaohongshuUpload(BasePlatform):
    def __init__(self):
        super().__init__(platform_code=1, platform_name="小红书")

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
        description: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        from uploader.xiaohongshu_uploader.main import XiaoHongShuVideo

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

            # 小红书定时发布规则验证：1小时后~14天内
            if publish_value and isinstance(publish_value, datetime):
                now = datetime.now()
                time_diff = (publish_value - now).total_seconds()
                min_delay = 1 * 3600  # 1小时
                max_delay = 14 * 24 * 3600  # 14天

                if time_diff < min_delay:
                    raise ValueError(
                        f"小红书定时发布时间必须在1小时后，当前距离: {int(time_diff / 60)}分钟"
                    )
                if time_diff > max_delay:
                    raise ValueError(
                        f"小红书定时发布时间不能超过14天，当前距离: {int(time_diff / 86400)}天"
                    )

        uploader = XiaoHongShuVideo(
            title=title,
            file_path=file_path,
            tags=tags or [],
            publish_date=publish_value,
            account_file=account_file,
            thumbnail_path=thumbnail_path,
        )
        await uploader.main()

        return {"success": True, "message": "上传成功", "data": {"description": description}}


xiaohongshu_upload = XiaohongshuUpload()
