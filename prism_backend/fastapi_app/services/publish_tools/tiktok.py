"""TikTok 发布工具 —— 独立模块：改这里只影响 TikTok，其他平台不受牵连。"""

from __future__ import annotations

from typing import Any, Callable, Dict

from ._base import (
    ToolSpec, _common_video_params, check_params, clean_tags, display_name,
    login_params, parse_schedule, require_video_args, run_main,
)

NAME = "tiktok"


def _video_params() -> Dict[str, Any]:
    props = _common_video_params()
    return {"type": "object", "properties": props, "required": ["account_file", "file_path", "title"]}


def _video_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file, file_path, title = require_video_args(kwargs)
        tags = clean_tags(kwargs.get("tags"))
        desc = str(kwargs.get("description") or "")
        schedule = parse_schedule(kwargs.get("schedule"))
        thumbnail = str(kwargs.get("thumbnail") or "")

        from uploader.tk_uploader.main_chrome import TiktokVideo
        app = TiktokVideo(
            "\n\n".join(x for x in (title, desc) if x), file_path, tags, schedule, account_file,
            thumbnail_path=str(thumbnail) if thumbnail else None,
        )
        await run_main(app)
        return {"success": True, "platform": NAME, "kind": "video", "message": f"{display_name(NAME)} 视频发布成功"}

    return handler


def _login_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file = str(kwargs.get("account_file") or "").strip()
        if not account_file:
            raise ValueError("account_file 必填")
        from uploader.tk_uploader.main_chrome import tiktok_setup
        result = await tiktok_setup(str(account_file), handle=True)
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
        from uploader.tk_uploader.main_chrome import cookie_auth
        valid = await cookie_auth(str(account_file))
        return {"success": bool(valid), "account_file": account_file}

    return handler


SPECS = [
    ToolSpec(name="publish_video_to_tiktok", description="发布视频到 TikTok。account_file 为 TikTok 账号 cookie json 路径，file_path 为本地视频，title 为题。",
             parameters=_video_params(), handler=_video_handler(), category="tiktok_publish",
             output_summary="向 TikTok 发布单个视频；成功返回 success=True"),
    ToolSpec(name="login_to_tiktok", description="登录 TikTok 账号并写入 account_file（storage_state）。",
             parameters=login_params(), handler=_login_handler(), category="tiktok_login",
             output_summary="登录 TikTok 账号；成功返回 success=True"),
    ToolSpec(name="check_account_tiktok", description="校验 TikTok 账号登录态（account_file 是否有效）。",
             parameters=check_params(), handler=_check_handler(), category="tiktok_login",
             output_summary="返回 TikTok 账号登录态是否有效"),
]
