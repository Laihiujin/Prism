"""
推特(Twitter/X)发布适配器 —— 走 xurl 官方 CLI。

与其它平台不同：推特没有网页 cookie，登录通过 `xurl auth`（OAuth 2.0 PKCE）
在本机 ~/.xurl 手动绑定。因此 `account_file` 参数其实是 xurl 的 app 名
（或 `app@handle`），而不是一个 json 文件路径。发布时用 `xurl post` + `xurl media upload`。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from ..base import BasePlatform
from ..twitter import xurl_client


class TwitterUpload(BasePlatform):
    def __init__(self) -> None:
        super().__init__(platform_code=9, platform_name="推特")

    async def login(self, account_id: str, **kwargs: Any) -> Dict[str, Any]:
        """推特登录 = 校验 xurl 本机是否已认证。真正绑定需用户在终端手动
        运行 `xurl auth oauth2 --app <app>`（本方法不代填任何密钥）。"""
        if not xurl_client.xurl_available():
            return {
                "success": False,
                "message": "未找到 `xurl` 命令，请先安装并运行 `xurl auth oauth2 --app <app>` 登录。",
            }
        try:
            await xurl_client.auth_status()
            handle = await xurl_client.whoami(app=account_id or None)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "message": f"xurl 未登录或默认 app 无 token：{exc}"}
        return {"success": True, "message": f"xurl 已就绪（@{handle}）", "handle": handle}

    async def upload(
        self,
        account_file: str,
        title: str,
        file_path: str,
        tags: list,
        publish_date: Optional[Any] = None,
        description: str = "",
        thumbnail_path: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        text = xurl_client.compose_text(title, description, tags)

        media_ids: list[str] = []
        if file_path:
            resolved = _resolve_file(file_path)
            if resolved and Path(resolved).is_file():
                media_ids.append(await xurl_client.upload_media(resolved, account_ref=account_file))
            else:
                raise FileNotFoundError(f"媒体文件不存在: {file_path}")

        result = await xurl_client.post(text, media_ids=media_ids, account_ref=account_file)
        return {
            "success": True,
            "platform": "twitter",
            "kind": "post",
            "tweet_id": result.get("id"),
            "video_url": result.get("url") or (f"https://x.com/status/{result.get('id')}" if result.get("id") else None),
            "message": "推特发布成功",
        }


def _resolve_file(file_path: str) -> str:
    """尽量把 videoPath 规范化成真实存在的路径（兼容绝对/相对/videoFile 前缀）。"""
    try:
        from ..path_utils import resolve_video_file

        return resolve_video_file(str(file_path))
    except Exception:  # noqa: BLE001
        return str(file_path)


twitter_upload = TwitterUpload()
