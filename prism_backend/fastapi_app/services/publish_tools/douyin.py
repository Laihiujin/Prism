"""抖音发布工具 —— 独立模块：改这里只影响抖音，其他平台不受牵连。"""

from __future__ import annotations

from typing import Any, Callable, Dict

from ._base import (
    ToolSpec, _common_note_params, _common_video_params, check_params,
    clean_tags, display_name, login_params, parse_schedule, require_note_args,
    require_video_args, run_main,
)

NAME = "douyin"


def _video_params() -> Dict[str, Any]:
    props = _common_video_params()
    props.update({
        "thumbnail_landscape": {"type": "string", "description": "横版封面图片（可选）", "default": ""},
        "thumbnail_portrait": {"type": "string", "description": "竖版封面图片（可选）", "default": ""},
        "product_link": {"type": "string", "description": "商品链接（购物车）", "default": ""},
        "product_title": {"type": "string", "description": "商品短标题", "default": ""},
        "declaration": {"type": "string", "description": "自主声明内容（如 '内容由AI生成'）", "default": ""},
        "location": {"type": "string", "description": "地理位置 POI", "default": ""},
        "random_cover": {"type": "boolean", "description": "随机选推荐封面", "default": False},
        "mini_program_link": {"type": "string", "description": "小程序链接", "default": ""},
        "mini_program_title": {"type": "string", "description": "小程序标题", "default": ""},
        "mini_program_name": {"type": "string", "description": "挂载小程序/对象名", "default": ""},
        "mini_program_type": {"type": "string", "description": "挂载对象类型", "default": ""},
        "who_can_see": {"type": "string", "description": "谁可以看：公开/好友可见/仅自己可见", "default": ""},
        "save_permission": {"type": "string", "description": "保存权限：允许/不允许", "default": ""},
        "hotspot": {"type": "string", "description": "关联热点词", "default": ""},
        "collection": {"type": "string", "description": "合集名/不选择合集", "default": ""},
        "cover_orientation": {"type": "string", "enum": ["landscape", "portrait"], "description": "封面朝向", "default": "landscape"},
        "cover_file": {"type": "string", "description": "自定义封面文件路径", "default": ""},
        "preview": {"type": "boolean", "description": "预览模式：跑到发布前停住，绝不真正发布", "default": False},
    })
    return {"type": "object", "properties": props, "required": ["account_file", "file_path", "title"]}


def _note_params() -> Dict[str, Any]:
    props = _common_note_params()
    props.update({
        "bgm": {"type": "string", "description": "BGM（可选）", "default": ""},
        "declaration": {"type": "string", "description": "自主声明内容", "default": ""},
        "location": {"type": "string", "description": "地理位置 POI", "default": ""},
    })
    return {"type": "object", "properties": props, "required": ["account_file", "images", "title"]}


def _video_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file, file_path, title = require_video_args(kwargs)
        tags = clean_tags(kwargs.get("tags"))
        desc = str(kwargs.get("description") or "")
        schedule = parse_schedule(kwargs.get("schedule"))
        thumbnail = str(kwargs.get("thumbnail") or "")
        debug = bool(kwargs.get("debug", False))
        headless = bool(kwargs.get("headless", True))

        from uploader.douyin_uploader.main_refactored import DOUYIN_PUBLISH_STRATEGY_SCHEDULED, DouYinVideo
        app = DouYinVideo(
            title, file_path, tags, schedule, account_file,
            thumbnail_landscape_path=(str(kwargs["thumbnail_landscape"]) if kwargs.get("thumbnail_landscape") else None),
            thumbnail_portrait_path=(str(kwargs.get("thumbnail_portrait") or thumbnail) if (kwargs.get("thumbnail_portrait") or thumbnail) else None),
            productLink=str(kwargs.get("product_link") or ""),
            productTitle=str(kwargs.get("product_title") or ""),
            desc=desc,
            publish_strategy=DOUYIN_PUBLISH_STRATEGY_SCHEDULED if schedule else "immediate",
            debug=debug, headless=headless,
            declaration=(kwargs.get("declaration") or None),
            random_cover=bool(kwargs.get("random_cover", False)),
            miniprogramLink=str(kwargs.get("mini_program_link") or ""),
            miniprogramTitle=str(kwargs.get("mini_program_title") or ""),
            location=str(kwargs.get("location") or ""),
            preview_only=bool(kwargs.get("preview", False)),
            who_can_see=str(kwargs.get("who_can_see") or ""),
            save_permission=str(kwargs.get("save_permission") or ""),
            hotspot=str(kwargs.get("hotspot") or ""),
            collection=str(kwargs.get("collection") or ""),
            cover_orientation=str(kwargs.get("cover_orientation") or "landscape"),
            cover_file=str(kwargs.get("cover_file") or ""),
            miniProgram=({"name": kwargs.get("mini_program_name"), "type": kwargs.get("mini_program_type")} if kwargs.get("mini_program_name") else None),
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
        headless = bool(kwargs.get("headless", True))

        from uploader.douyin_uploader.main_refactored import DOUYIN_PUBLISH_STRATEGY_SCHEDULED, DouYinNote
        app = DouYinNote(
            images, body, tags, schedule, account_file, title=title,
            publish_strategy=DOUYIN_PUBLISH_STRATEGY_SCHEDULED if schedule else "immediate",
            debug=debug, headless=headless,
            bgm=str(kwargs.get("bgm") or ""),
            declaration=(kwargs.get("declaration") or None),
            location=str(kwargs.get("location") or ""),
        )
        await run_main(app)
        return {"success": True, "platform": NAME, "kind": "note", "message": "抖音 图文/笔记发布成功"}

    return handler


def _login_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file = str(kwargs.get("account_file") or "").strip()
        if not account_file:
            raise ValueError("account_file 必填")
        headless = bool(kwargs.get("headless", False))
        from uploader.douyin_uploader.main_refactored import douyin_setup
        result = await douyin_setup(str(account_file), handle=True, return_detail=True, headless=headless)
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
        from uploader.douyin_uploader.main_refactored import cookie_auth
        valid = await cookie_auth(str(account_file))
        return {"success": bool(valid), "account_file": account_file}

    return handler


SPECS = [
    ToolSpec(
        name="publish_video_to_douyin",
        description="发布视频到抖音。account_file 为抖音账号 cookie json 路径，file_path 为本地视频，title 为题；"
                    "支持商品链接、自主声明、位置、随机封面、小程序挂载、谁可以看、保存权限、关联热点、合集、封面朝向等。",
        parameters=_video_params(),
        handler=_video_handler(),
        category="douyin_publish",
        output_summary="向抖音发布单个视频；成功返回 success=True",
    ),
    ToolSpec(
        name="publish_note_to_douyin",
        description="发布图文/笔记到抖音（图片流）。images 为本地图片路径列表，title 为题，note 为正文。",
        parameters=_note_params(),
        handler=_note_handler(),
        category="douyin_publish",
        output_summary="向抖音发布图文/笔记；成功返回 success=True",
    ),
    ToolSpec(
        name="login_to_douyin",
        description="登录抖音账号并写入 account_file（storage_state）。扫码/有头交互。",
        parameters=login_params(),
        handler=_login_handler(),
        category="douyin_login",
        output_summary="登录抖音账号；成功返回 success=True",
    ),
    ToolSpec(
        name="check_account_douyin",
        description="校验抖音账号登录态（account_file 是否有效）。",
        parameters=check_params(),
        handler=_check_handler(),
        category="douyin_login",
        output_summary="返回 抖音 账号登录态是否有效",
    ),
]
