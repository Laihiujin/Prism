"""B站（bilibili）发布工具 —— 独立模块：改这里只影响B站，其他平台不受牵连。

说明：B站走 biliup 命令行上传（非浏览器自动化）；登录必须在用户本地交互终端执行。
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from ._base import (
    ToolSpec, _common_video_params, check_params, clean_tags, display_name,
    login_params, parse_schedule, require_video_args,
)

NAME = "bilibili"


def _video_params() -> Dict[str, Any]:
    props = _common_video_params()
    props.update({
        "tid": {"type": "integer", "description": "分区 ID（必填）"},
        "tag": {"type": "string", "description": "独立标签（逗号分隔，可选）", "default": ""},
    })
    return {"type": "object", "properties": props, "required": ["account_file", "file_path", "title", "tid"]}


def _video_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file, file_path, title = require_video_args(kwargs)
        desc = str(kwargs.get("description") or "")
        tags = clean_tags(kwargs.get("tags") or kwargs.get("tag"))
        schedule = parse_schedule(kwargs.get("schedule"))
        thumbnail = str(kwargs.get("thumbnail") or "")

        from uploader.bilibili_uploader.runtime import run_biliup_command
        command = ["-u", account_file, "upload", file_path, "--title", title, "--desc", desc, "--tid", str(int(kwargs.get("tid") or 0))]
        if tags:
            command.extend(["--tag", ",".join(tags)])
        if thumbnail:
            command.extend(["--cover", thumbnail])
        if schedule:
            command.extend(["--dtime", str(int(schedule.timestamp()))])
        result = run_biliup_command(command)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout or "Bilibili upload failed").strip())
        return {"success": True, "platform": NAME, "kind": "video", "message": "B站视频发布成功"}

    return handler


def _login_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file = str(kwargs.get("account_file") or "").strip()
        if not account_file:
            raise ValueError("account_file 必填")
        import sys
        from uploader.bilibili_uploader.runtime import run_biliup_command
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return {"success": False, "account_file": account_file, "message": "Bilibili 登录需要本地交互终端（biliup）"}
        ok = run_biliup_command(["-u", str(account_file), "login"], interactive=True).returncode == 0
        return {"success": bool(ok), "account_file": account_file}

    return handler


def _check_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        from pathlib import Path
        account_file = str(kwargs.get("account_file") or "").strip()
        if not account_file:
            raise ValueError("account_file 必填")
        if not Path(account_file).is_file():
            return {"success": False, "account_file": account_file, "message": "cookie 文件不存在"}
        from uploader.bilibili_uploader.runtime import run_biliup_command
        valid = run_biliup_command(["-u", str(account_file), "renew"]).returncode == 0
        return {"success": bool(valid), "account_file": account_file}

    return handler


SPECS = [
    ToolSpec(name="publish_video_to_bilibili", description="发布视频到B站（biliup）。tid 分区 ID 必填；account_file 为 B站账号 cookie json 路径。",
             parameters=_video_params(), handler=_video_handler(), category="bilibili_publish",
             output_summary="向B站发布单个视频；成功返回 success=True"),
    ToolSpec(name="login_to_bilibili", description="登录B站账号（biliup）。必须在本机交互终端执行；非交互环境返回失败。",
             parameters=login_params(), handler=_login_handler(), category="bilibili_login",
             output_summary="登录B站账号；成功返回 success=True"),
    ToolSpec(name="check_account_bilibili", description="校验B站账号登录态（biliup renew）。",
             parameters=check_params(), handler=_check_handler(), category="bilibili_login",
             output_summary="返回 B站 账号登录态是否有效"),
]
