# -*- coding: utf-8 -*-
"""端到端预览验证：DouYinVideo preview_only，带新字段；确认跑到发布前不崩。"""
import asyncio
from pathlib import Path
import sys

BASE = Path("/Users/laihiujin/Documents/siuyechu/Prism/prism_backend")
sys.path.insert(0, str(BASE))

from uploader.douyin_uploader.main_refactored import DouYinVideo


async def main():
    app = DouYinVideo(
        title="Hermes 自动化验证 预览",
        file_path=str(BASE / "videoFile" / "60d455f2-8501-4488-bedc-3b58bc8767db.MP4"),
        tags=["自动化测试"],
        publish_date=0,
        account_file=str(BASE / "cookiesFile" / "douyin_Siuyechu_.json"),
        desc="自动化验证，preview_only 不真正发布",
        publish_strategy="immediate",
        debug=True,
        headless=False,
        preview_only=True,
        random_cover=False,
        thumbnail_landscape_path=str(BASE / "videoFile" / "covers" / "first_frame_1.png"),
        thumbnail_portrait_path=str(BASE / "videoFile" / "covers" / "first_frame_2.png"),
        cover_orientation="landscape",
        who_can_see="仅自己可见",
        save_permission="不允许",
        hotspot="热点",
        collection="",
        miniProgram=None,
    )
    print("PREVIEW: before main()", flush=True)
    await app.main()
    print("PREVIEW: after main() — 已到发布前，未真正发布", flush=True)


asyncio.run(main())
