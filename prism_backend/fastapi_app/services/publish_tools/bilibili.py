"""B站（bilibili）发布工具 —— 独立模块：改这里只影响B站，其他平台不受牵连。

说明：
- 单视频默认路径：biliup CLI（`run_biliup_command`），与历史一致（参数仅用
  CLI 确定支持的 --title/--desc/--tid/--tag/--cover/--dtime）。
- 分P/多P发布与稿件级配置（copyright/source/cover_local/dynamic）：走
  python biliup 库（platforms/bilibili/upload.py 的 BilibiliUploader，
  支持 files 列表分P + 本地封面上传）。
- 登录：本地交互终端 biliup login；另有多方式 API（/api/v1/auth/bilibili/*：
  扫码/短信/账密/Cookie），见 docs 或 skill。
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
        "copyright": {"type": "integer", "description": "版权：1=自制 2=转载（走 python 库时生效）", "default": 1},
        "source": {"type": "string", "description": "转载来源（copyright=2 时建议填写）", "default": ""},
        "dynamic": {"type": "string", "description": "粉丝动态文案（可选）", "default": ""},
    })
    return {"type": "object", "properties": props, "required": ["account_file", "file_path", "title", "tid"]}


def _multipart_params() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "account_file": {"type": "string", "description": "账号 cookie json 路径"},
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "分P视频本地绝对路径"},
                        "title": {"type": "string", "description": "该分P标题（可选，缺省用主标题+P序号）"},
                    },
                    "required": ["path"],
                },
                "description": "分P文件列表（顺序 = P1..Pn）",
            },
            "title": {"type": "string", "description": "稿件主标题"},
            "description": {"type": "string", "description": "稿件简介", "default": ""},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表", "default": []},
            "tid": {"type": "integer", "description": "分区 ID（必填）"},
            "schedule": {"type": "string", "description": "定时发布时间 'YYYY-MM-DD HH:MM'（≥2h ≤15d）", "default": ""},
            "copyright": {"type": "integer", "description": "版权：1=自制 2=转载", "default": 1},
            "source": {"type": "string", "description": "转载来源", "default": ""},
            "cover": {"type": "string", "description": "封面 URL 或本地图片路径（可选）", "default": ""},
            "dynamic": {"type": "string", "description": "粉丝动态（可选）", "default": ""},
        },
        "required": ["account_file", "files", "title", "tid"],
    }


def _python_upload_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """把工具入参整理成 platforms.bilibili uploader 能接收的 kwargs。"""
    from pathlib import Path
    out: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}
    copyright_val = kwargs.get("copyright", 1)
    if copyright_val not in (None, "", 1):
        extra["copyright"] = int(copyright_val)
    if kwargs.get("source"):
        extra["source"] = str(kwargs["source"])
    if kwargs.get("dynamic"):
        extra["dynamic"] = str(kwargs["dynamic"])
    cover = str(kwargs.get("cover") or "")
    if cover:
        if cover.startswith("http"):
            extra["cover"] = cover
        elif Path(cover).is_file():
            extra["cover_local"] = cover
    out["platform_settings"] = {}
    for key, value in extra.items():
        out[key] = value
    return out


async def _run_python_upload(
    account_file: str, file_path: str, title: str, desc: str,
    tags: list, tid: Any, schedule, kwargs: Dict[str, Any],
    files=None, part_titles=None,
) -> Dict[str, Any]:
    """通过 python biliup 上传器发布（单文件或分P + 稿件级配置）。"""
    from platforms.bilibili.upload import BilibiliUpload
    import inspect

    upload_kwargs = _python_upload_kwargs(kwargs)
    uploader = BilibiliUpload()
    call_kwargs = {
        "account_file": account_file,
        "title": title,
        "file_path": file_path,
        "tags": tags or [],
        "publish_date": schedule or None,
        "category_id": int(tid) if str(tid).isdigit() else 160,
        "description": desc or "",
        "video_parts": files or None,
        "part_titles": part_titles or None,
        **upload_kwargs,
    }
    sig = inspect.signature(uploader.upload)
    allowed = {name for name in sig.parameters if name not in ("self", "kwargs")}
    call_kwargs = {k: v for k, v in call_kwargs.items() if k in allowed or k == "platform_settings" or v is not None}
    result = await uploader.upload(**call_kwargs)
    if not result or not result.get("success"):
        raise RuntimeError((result or {}).get("message") or "Bilibili upload failed")
    return {"success": True, "platform": NAME, "kind": "multipart" if files else "video",
            "message": result.get("message") or "B站发布成功"}


def _video_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file, file_path, title = require_video_args(kwargs)
        desc = str(kwargs.get("description") or "")
        tags = clean_tags(kwargs.get("tags") or kwargs.get("tag"))
        schedule = parse_schedule(kwargs.get("schedule"))
        tid = kwargs.get("tid") or 0
        thumbnail = str(kwargs.get("thumbnail") or "")
        cover = str(kwargs.get("cover") or thumbnail or "")

        needs_python_lib = bool(
            cover and not cover.startswith("http")  # 本地封面图（走 cover_up）
            or kwargs.get("copyright") not in (None, "", 1)
            or kwargs.get("source")
            or kwargs.get("dynamic")
        )
        if needs_python_lib:
            return await _run_python_upload(
                account_file, file_path, title, desc, tags, tid, schedule, kwargs,
            )

        # 默认路径：biliup CLI（参数保持与历史一致，避免旧版 CLI 报错）
        from uploader.bilibili_uploader.runtime import run_biliup_command
        command = ["-u", account_file, "upload", file_path, "--title", title, "--desc", desc,
                   "--tid", str(int(tid) if str(tid).isdigit() else 0)]
        if tags:
            command.extend(["--tag", ",".join(tags)])
        if cover and cover.startswith("http"):
            command.extend(["--cover", cover])
        elif cover and Path(cover).is_file():
            # CLI 需要 URL 封面；本地图降级用库上传
            return await _run_python_upload(account_file, file_path, title, desc, tags, tid, schedule, kwargs)
        if schedule:
            command.extend(["--dtime", str(int(schedule.timestamp()))])
        result = run_biliup_command(command)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout or "Bilibili upload failed").strip())
        return {"success": True, "platform": NAME, "kind": "video", "message": "B站视频发布成功"}

    return handler


def _multipart_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        from pathlib import Path
        account_file = str(kwargs.get("account_file") or "").strip()
        title = str(kwargs.get("title") or "").strip()
        tid = kwargs.get("tid") or 0
        raw_files = kwargs.get("files") or []
        if not account_file or not title or not raw_files:
            raise ValueError("account_file / title / files 均为必填")
        paths: list = []
        part_titles: list = []
        for entry in raw_files:
            if isinstance(entry, dict):
                p = str(entry.get("path") or "")
                paths.append(p)
                part_titles.append(str(entry.get("title") or ""))
            else:
                paths.append(str(entry))
                part_titles.append("")
        for p in paths:
            if not Path(p).is_file():
                raise FileNotFoundError(p)
        desc = str(kwargs.get("description") or "")
        tags = clean_tags(kwargs.get("tags") or [])
        schedule = parse_schedule(kwargs.get("schedule"))
        return await _run_python_upload(
            account_file, paths[0], title, desc, tags, tid, schedule, kwargs,
            files=paths[1:],
            part_titles=[t for t in part_titles[1:] if t] or None,
        )

    return handler


def _login_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file = str(kwargs.get("account_file") or "").strip()
        if not account_file:
            raise ValueError("account_file 必填")
        import sys
        from uploader.bilibili_uploader.runtime import run_biliup_command
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return {"success": False, "account_file": account_file,
                    "message": "Bilibili 登录需要本地交互终端（biliup）；亦可使用 API /api/v1/auth/bilibili/*（扫码/短信/账密/Cookie）"}
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
    ToolSpec(name="publish_video_to_bilibili",
             description="发布视频到B站。tid 分区 ID 必填；account_file 为 B站账号 cookie json 路径；cover 传 http URL（CLI）或本地图片路径（库上传）；copyright/source/dynamic 走库上传。",
             parameters=_video_params(), handler=_video_handler(), category="bilibili_publish",
             output_summary="向B站发布单个视频；成功返回 success=True"),
    ToolSpec(name="publish_multipart_to_bilibili",
             description="分P（多P）发布到B站：一个稿件包含多个视频（P1..Pn）。files 数组顺序即分P顺序；tid 分区必填；走 python biliup 库。",
             parameters=_multipart_params(), handler=_multipart_handler(), category="bilibili_publish",
             output_summary="向B站发布分P稿件；成功返回 success=True"),
    ToolSpec(name="login_to_bilibili",
             description="登录B站账号（biliup）。必须在本机交互终端执行；非交互环境返回失败并提示改用 /api/v1/auth/bilibili/*。",
             parameters=login_params(), handler=_login_handler(), category="bilibili_login",
             output_summary="登录B站账号；成功返回 success=True"),
    ToolSpec(name="check_account_bilibili",
             description="校验B站账号登录态（biliup renew）。",
             parameters=check_params(), handler=_check_handler(), category="bilibili_login",
             output_summary="返回 B站 账号登录态是否有效"),
]
