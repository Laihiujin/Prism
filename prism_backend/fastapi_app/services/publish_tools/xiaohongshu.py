"""小红书发布工具 —— 独立模块：改这里只影响小红书，其他平台不受牵连。"""

from __future__ import annotations

from typing import Any, Callable, Dict

from ._base import (
    ToolSpec, _common_note_params, _common_video_params, check_params,
    clean_tags, display_name, login_params, parse_schedule, require_note_args,
    require_video_args, run_main,
)

NAME = "xiaohongshu"


def _video_params() -> Dict[str, Any]:
    props = _common_video_params()
    props["headless"] = {"type": "boolean", "description": "无头浏览器；小红书发布建议 false（有头）；false 可见窗口便于观察", "default": False}
    return {"type": "object", "properties": props, "required": ["account_file", "file_path", "title"]}


def _note_params() -> Dict[str, Any]:
    props = _common_note_params()
    return {"type": "object", "properties": props, "required": ["account_file", "images", "title"]}


def _video_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file, file_path, title = require_video_args(kwargs)
        tags = clean_tags(kwargs.get("tags"))
        desc = str(kwargs.get("description") or "")
        schedule = parse_schedule(kwargs.get("schedule"))
        thumbnail = str(kwargs.get("thumbnail") or "")
        debug = bool(kwargs.get("debug", False))
        headless = bool(kwargs.get("headless", False))

        from uploader.xiaohongshu_uploader.main_refactored import XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED, XiaoHongShuVideo
        app = XiaoHongShuVideo(
            title, file_path, tags, schedule, account_file,
            thumbnail_path=str(thumbnail) if thumbnail else None,
            desc=desc, debug=debug, headless=headless,
            publish_strategy=XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED if schedule else "immediate",
        )
        await run_main(app)
        return {"success": True, "platform": NAME, "kind": "video", "message": f"{display_name(NAME)} 视频发布成功"}

    return handler


def _note_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file, title, images = require_note_args(kwargs)
        body = str(kwargs.get("note") or "")
        tags = clean_tags(kwargs.get("tags"))
        schedule = parse_schedule(kwargs.get("schedule"))
        debug = bool(kwargs.get("debug", False))
        headless = bool(kwargs.get("headless", False))

        from uploader.xiaohongshu_uploader.main_refactored import XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED, XiaoHongShuNote
        app = XiaoHongShuNote(
            images, body, tags, schedule, account_file, title=title,
            publish_strategy=XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED if schedule else "immediate",
            debug=debug, headless=headless,
        )
        await run_main(app)
        return {"success": True, "platform": NAME, "kind": "note", "message": "小红书 图文/笔记发布成功"}

    return handler


def _login_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file = str(kwargs.get("account_file") or "").strip()
        if not account_file:
            raise ValueError("account_file 必填")
        headless = bool(kwargs.get("headless", False))
        from uploader.xiaohongshu_uploader.main_refactored import xiaohongshu_setup
        result = await xiaohongshu_setup(str(account_file), handle=True, return_detail=True, headless=headless)
        success = result.get("success") if isinstance(result, dict) else bool(result)
        return {"success": bool(success), "account_file": account_file, "message": (result.get("message") if isinstance(result, dict) else "")}

    return handler


def _check_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        from pathlib import Path
        account_file = str(kwargs.get("account_file") or "").strip()
        if not account_file:
            raise ValueError("account_file 必填")
        if not Path(account_file).is_file():
            return {"success": False, "account_file": account_file, "message": "cookie 文件不存在"}
        from uploader.xiaohongshu_uploader.main_refactored import cookie_auth
        valid = await cookie_auth(str(account_file))
        return {"success": bool(valid), "account_file": account_file}

    return handler


SPECS = [
    ToolSpec(name="publish_video_to_xiaohongshu", description="发布视频到小红书。account_file 为小红书账号 cookie json 路径，file_path 为本地视频，title 为题。",
             parameters=_video_params(), handler=_video_handler(), category="xiaohongshu_publish",
             output_summary="向小红书发布单个视频；成功返回 success=True"),
    ToolSpec(name="publish_note_to_xiaohongshu", description="发布图文/笔记到小红书（图片流）。images 为本地图片路径列表，title 为题，note 为正文。",
             parameters=_note_params(), handler=_note_handler(), category="xiaohongshu_publish",
             output_summary="向小红书发布图文/笔记；成功返回 success=True"),
    ToolSpec(name="login_to_xiaohongshu", description="登录小红书账号并写入 account_file（storage_state）。扫码/有头交互。",
             parameters=login_params(), handler=_login_handler(), category="xiaohongshu_login",
             output_summary="登录小红书账号；成功返回 success=True"),
    ToolSpec(name="check_account_xiaohongshu", description="校验小红书账号登录态（account_file 是否有效）。",
             parameters=check_params(), handler=_check_handler(), category="xiaohongshu_login",
             output_summary="返回 小红书 账号登录态是否有效"),
]
