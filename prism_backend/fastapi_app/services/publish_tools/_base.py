"""publish_tools 包共享基座 —— 只放**稳定、真正跨平台通用**的辅助。

平台相关的一切（参数 schema、handler、SPECS）都放在各自的平台模块里
（douyin.py / kuaishou.py ...），这样改一个平台不会碰到其他平台的代码。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..tool_catalog import ToolSpec  # noqa: F401  (re-export so平台模块统一从此导入)

_SCHEDULE_FORMAT = "%Y-%m-%d %H:%M"

# 平台展示名（仅展示用；改它不影响任何平台逻辑）
_DISPLAY_NAMES = {
    "douyin": "抖音", "kuaishou": "快手", "xiaohongshu": "小红书",
    "bilibili": "B站", "channels": "视频号", "baijiahao": "百家号",
    "tiktok": "TikTok", "youtube": "YouTube",
}


def display_name(platform: str) -> str:
    return _DISPLAY_NAMES.get(platform, platform)


def parse_schedule(schedule: Optional[str]) -> Any:
    """'YYYY-MM-DD HH:MM' -> datetime；空/非法 -> 0（立即发布）。"""
    if not schedule:
        return 0
    try:
        return datetime.strptime(str(schedule).strip(), _SCHEDULE_FORMAT)
    except ValueError:
        return 0


def clean_tags(tags: Any) -> List[str]:
    if not tags:
        return []
    if isinstance(tags, str):
        items = tags.replace("，", ",").replace(" ", ",").split(",")
    else:
        items = tags
    return [str(t).strip().lstrip("#") for t in items if str(t).strip()]


def require_video_args(kwargs: Dict[str, Any]) -> tuple[str, str, str]:
    """校验视频发布必填项并返回 (account_file, file_path, title)。跨平台通用。"""
    from pathlib import Path

    account_file = str(kwargs.get("account_file") or "").strip()
    file_path = str(kwargs.get("file_path") or "").strip()
    title = str(kwargs.get("title") or "").strip()
    if not account_file or not file_path or not title:
        raise ValueError("account_file / file_path / title 均为必填")
    if not Path(file_path).is_file():
        raise FileNotFoundError(file_path)
    return account_file, file_path, title


def require_note_args(kwargs: Dict[str, Any]) -> tuple[str, str, list]:
    """校验图文发布必填项并返回 (account_file, title, images)。跨平台通用。"""
    from pathlib import Path

    account_file = str(kwargs.get("account_file") or "").strip()
    title = str(kwargs.get("title") or "").strip()
    images = [str(x) for x in (kwargs.get("images") or []) if str(x).strip()]
    if not account_file or not title or not images:
        raise ValueError("account_file / title / images 均为必填")
    for img in images:
        if not Path(img).is_file():
            raise FileNotFoundError(img)
    return account_file, title, images


def _common_video_params() -> Dict[str, Any]:
    """视频发布通用参数（跨平台）；平台模块在其上追加专属参数。"""
    return {
        "account_file": {"type": "string", "description": "账号 cookie json 路径（相对 prism_backend/ 或绝对路径）"},
        "file_path": {"type": "string", "description": "本地视频文件绝对路径"},
        "title": {"type": "string", "description": "作品标题"},
        "description": {"type": "string", "description": "作品简介/描述", "default": ""},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "话题标签列表", "default": []},
        "schedule": {"type": "string", "description": "定时发布时间 'YYYY-MM-DD HH:MM'；留空立即发布", "default": ""},
        "thumbnail": {"type": "string", "description": "封面图片路径（可选）", "default": ""},
        "debug": {"type": "boolean", "description": "debug 日志", "default": False},
        "headless": {"type": "boolean", "description": "无头浏览器；false 开可见窗口便于观察", "default": True},
    }


def _common_note_params() -> Dict[str, Any]:
    """图文/笔记发布通用参数；平台模块在其上追加专属参数。"""
    return {
        "account_file": {"type": "string", "description": "账号 cookie json 路径（相对 prism_backend/ 或绝对路径）"},
        "images": {"type": "array", "items": {"type": "string"}, "description": "本地图片绝对路径列表"},
        "title": {"type": "string", "description": "图文/笔记标题"},
        "note": {"type": "string", "description": "笔记正文", "default": ""},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "话题标签列表", "default": []},
        "schedule": {"type": "string", "description": "定时发布时间 'YYYY-MM-DD HH:MM'；留空立即发布", "default": ""},
        "debug": {"type": "boolean", "description": "debug 日志", "default": False},
        "headless": {"type": "boolean", "description": "无头浏览器；false 开可见窗口", "default": True},
    }


def login_params() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "account_file": {"type": "string", "description": "登录后 cookie json 要写入的路径（相对 prism_backend/ 或绝对路径）"},
            "headless": {"type": "boolean", "description": "无头浏览器；扫码登录建议 false", "default": False},
        },
        "required": ["account_file"],
    }


def check_params() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "account_file": {"type": "string", "description": "账号 cookie json 路径"},
        },
        "required": ["account_file"],
    }


async def run_main(app: Any) -> Any:
    """调用上传器 main()（async 或 sync），返回其结果。在 async handler 内 await 它。"""
    import inspect

    result = app.main()
    if inspect.isawaitable(result):
        result = await result
    return result
