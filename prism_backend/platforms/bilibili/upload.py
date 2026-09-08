"""
B站上传模块 - 平台层统一入口

说明：
- 当前复用 `uploader/bilibili_uploader/main.py` 的 biliup 实现（同步），在协程中通过线程执行。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ..base import BasePlatform
from ..path_utils import resolve_cookie_file, resolve_video_file


class BilibiliUpload(BasePlatform):
    def __init__(self):
        super().__init__(platform_code=5, platform_name="B站")

    async def login(self, account_id: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError("请使用 FastAPI auth V2 登录服务")

    async def upload(
        self,
        account_file: str,
        title: str,
        file_path: str,
        tags: list,
        publish_date: Optional[Any] = None,
        category_id: int = 160,
        description: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        from uploader.bilibili_uploader.main import (
            BilibiliUploader,
            read_cookie_json_file,
            extract_keys_from_json,
        )

        account_file = resolve_cookie_file(account_file)
        file_path = resolve_video_file(file_path)

        # 分P：video_parts = 其余 P2..Pn 的本地路径（可选），P1 = file_path
        video_parts: list = kwargs.get("video_parts") or []
        if isinstance(video_parts, (list, tuple)):
            video_parts = [resolve_video_file(p) for p in video_parts]
        part_titles: list = kwargs.get("part_titles") or []

        # 稿件级配置：从 platform_settings.bilibili 解包（面板字段见 skill）
        ps = kwargs.get("platform_settings") or {}
        if not isinstance(ps, dict):
            ps = {}
        extra = {
            "copyright": kwargs.get("copyright") or ps.get("copyright"),
            "source": kwargs.get("source") or ps.get("source"),
            "cover": kwargs.get("cover") or ps.get("cover"),
            "dynamic": kwargs.get("dynamic") or ps.get("dynamic"),
            "open_subtitle": kwargs.get("open_subtitle", ps.get("open_subtitle", False)),
        }
        # cover_local：本地封面文件路径（优先于 URL）
        cover_local = kwargs.get("cover_local") or ps.get("cover_local")
        if cover_local:
            extra["cover_local"] = str(cover_local)
        extra = {k: v for k, v in extra.items() if v not in (None, "", False)}

        dtime: Optional[int] = None
        if publish_date:
            if isinstance(publish_date, datetime):
                dtime = int(publish_date.timestamp())
            elif isinstance(publish_date, (int, float)):
                # Assume seconds timestamp
                dtime = int(publish_date)
            elif isinstance(publish_date, str):
                s = publish_date.strip().replace("T", " ").replace("Z", "")
                try:
                    dtime = int(datetime.fromisoformat(s).timestamp())
                except Exception:
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                        try:
                            dtime = int(datetime.strptime(s, fmt).timestamp())
                            break
                        except Exception:
                            continue

            # B站要求：定时发布时间必须距离当前时间至少2小时，不超过15天
            if dtime:
                now = datetime.now().timestamp()
                min_delay = 2 * 3600  # 2小时（秒）
                max_delay = 15 * 24 * 3600  # 15天（秒）

                if dtime - now < min_delay:
                    return {
                        "success": False,
                        "message": f"B站要求定时发布时间必须在2小时后，当前距离: {int((dtime - now) / 60)}分钟"
                    }
                if dtime - now > max_delay:
                    return {
                        "success": False,
                        "message": f"B站要求定时发布时间不能超过15天，当前距离: {int((dtime - now) / 86400)}天"
                    }

        desc = description or title

        cookie_raw = read_cookie_json_file(Path(account_file))
        cookie_data = extract_keys_from_json(cookie_raw)

        uploader = BilibiliUploader(
            cookie_data=cookie_data,
            file=Path(file_path),
            title=title,
            desc=desc,
            tid=category_id,
            tags=tags or [],
            dtime=dtime,
            files=[Path(p) for p in video_parts] or None,
            part_titles=part_titles,
            extra=extra or None,
        )

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, uploader.upload)
        parts_desc = f"（含 {1 + len(video_parts)} 个分P）" if video_parts else ""
        return {"success": True, "message": f"上传成功{parts_desc}"}


bilibili_upload = BilibiliUpload()
