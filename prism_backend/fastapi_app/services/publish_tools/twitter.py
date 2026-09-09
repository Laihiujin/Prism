"""推特发布工具 —— 走 xurl 官方 CLI（独立模块：改这里只影响推特）。

推特是「文字 + 可选媒体」的图文/视频一体平台，与其它视频平台不同：
- 无网页 cookie，账号标识 = xurl 的 app 名（或 `app@handle`）
- 发布 = `xurl media upload`（可选）+ `xurl post`
- 正文 = title + description + 话题(#tag)，超 280 字由客户端截断
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from ._base import (
    ToolSpec, check_params, clean_tags, display_name, login_params,
)


NAME = "twitter"
DISPLAY = display_name(NAME)


def _publish_params() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "account_file": {"type": "string", "description": "xurl app 名（或 app@handle）；需先在终端 `xurl auth oauth2 --app <app>` 登录"},
            "title": {"type": "string", "description": "推文正文/标题", "default": ""},
            "description": {"type": "string", "description": "推文正文补充（与 title 拼接）", "default": ""},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "话题标签列表（自动加 #）", "default": []},
            "file_path": {"type": "string", "description": "本地媒体文件绝对路径（图片/视频/GIF，可选；不填则纯文字推文）", "default": ""},
        },
        "required": ["account_file", "title"],
    }


def _publish_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file = str(kwargs.get("account_file") or "").strip()
        if not account_file:
            raise ValueError("account_file 必填（xurl app 名）")
        title = str(kwargs.get("title") or "").strip()
        if not title:
            raise ValueError("title 必填")
        description = str(kwargs.get("description") or "")
        tags = clean_tags(kwargs.get("tags"))
        file_path = str(kwargs.get("file_path") or "").strip()

        from platforms.twitter.upload import twitter_upload

        result = await twitter_upload.upload(
            account_file=account_file,
            title=title,
            description=description,
            tags=tags,
            file_path=file_path or "",
        )
        return result

    return handler


def _login_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file = str(kwargs.get("account_file") or "").strip()
        from platforms.twitter.upload import twitter_upload

        result = await twitter_upload.login(account_file)
        return {
            "success": bool(result.get("success")),
            "account_file": account_file,
            "message": result.get("message", ""),
            "handle": result.get("handle"),
        }

    return handler


def _check_handler() -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> Dict[str, Any]:
        account_file = str(kwargs.get("account_file") or "").strip()
        if not account_file:
            raise ValueError("account_file 必填")
        from platforms.twitter import xurl_client

        available = xurl_client.xurl_available()
        if not available:
            return {"success": False, "account_file": account_file, "message": "未找到 xurl 命令"}
        try:
            await xurl_client.auth_status()
            handle = await xurl_client.whoami(app=account_file or None)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "account_file": account_file, "message": str(exc)}
        return {"success": True, "account_file": account_file, "handle": handle}

    return handler


SPECS = [
    ToolSpec(name="publish_to_twitter", description="发布一条推文到推特(X)。account_file 为 xurl app 名（或 app@handle），正文由 title+description+tags 拼接；file_path 为可选媒体（图片/视频/GIF）。",
             parameters=_publish_params(), handler=_publish_handler(), category="twitter_publish",
             output_summary="向推特发布一条推文（可带媒体）；成功返回 success=True 与 tweet 链接"),
    ToolSpec(name="login_to_twitter", description="校验推特发布账号是否已在本机完成 xurl 认证（需用户先手动 `xurl auth oauth2`）。",
             parameters=login_params(), handler=_login_handler(), category="twitter_login",
             output_summary="返回推特账号是否已通过 xurl 认证"),
    ToolSpec(name="check_account_twitter", description="校验推特账号登录态（本机 xurl 是否可用且默认 app 有 token）。",
             parameters=check_params(), handler=_check_handler(), category="twitter_login",
             output_summary="返回推特账号登录态是否有效"),
]
