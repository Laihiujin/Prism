"""Resolve material presets without dispatching publishing tasks."""
import json
import re
from pathlib import Path

PLATFORM_KEYS = {1: "xiaohongshu", 2: "wechat", 3: "douyin", 4: "kuaishou", 5: "bilibili", 6: "tiktok", 7: "youtube", 9: "twitter"}


def resolve_material_preset(video_dir, file_id, platform, selections):
    key = PLATFORM_KEYS.get(int(platform), str(platform))
    preset_id = (selections or {}).get(str(platform)) or (selections or {}).get(key)
    if not preset_id and key == "wechat":
        preset_id = (selections or {}).get("channels")
    if not preset_id:
        return None
    library = json.loads((Path(video_dir) / "covers" / f"library_{file_id}.json").read_text(encoding="utf-8"))
    preset = library.get("presets", {}).get(preset_id)
    if not preset:
        raise ValueError(f"素材 {file_id} 的预设不存在，请重新选择")
    if preset.get("platform", "all") not in ("all", key):
        raise ValueError(f"素材 {file_id} 的预设与发布平台不匹配")
    form = preset.get("data", {}).get("form", {})
    tags = form.get("tags") or []
    topics = tags if isinstance(tags, list) else [part.lstrip("#") for part in re.split(r"[\s,，]+", tags) if part.lstrip("#")]
    return {"title": form.get("title") or "", "description": form.get("description") or "", "topics": topics, "cover": form.get("cover_image") or ""}
