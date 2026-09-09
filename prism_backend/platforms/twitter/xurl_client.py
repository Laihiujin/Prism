"""
xurl 客户端封装 —— 供 Prism 的推特(Twitter/X)平台适配器复用。

xurl 是 X 开发者平台的官方 CLI。它把 OAuth 2.0 PKCE token 存在 ~/.xurl，
Prism 从不接触、也绝不打印该文件（见安全约束）。本模块只用「无内联密钥」的
安全命令，且逐条避免被禁止的 flag（--bearer-token / --consumer-key 等）。

对外暴露：
    parse_account_ref(account_file)      -> (app, username)
    compose_text(title, description, tags) -> str
    media_params(file_path)              -> (mime, category)
    xurl_available()                     -> bool
    auth_status()                        -> dict
    whoami()                             -> str
    upload_media(file_path, account_ref=None) -> media_id
    post(text, media_ids=None, account_ref=None) -> dict(含 tweet id / text)
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class XurlError(RuntimeError):
    """xurl 命令执行失败（非零退出码或返回 X API errors）。"""


def xurl_available() -> bool:
    return shutil.which("xurl") is not None


def _xurl_bin() -> str:
    path = shutil.which("xurl")
    if not path:
        raise XurlError(
            "未找到 `xurl` 命令。请先安装：curl -fsSL "
            "https://raw.githubusercontent.com/xdevplatform/xurl/main/install.sh | bash，"
            "再在终端手动运行 `xurl auth oauth2 --app <app>` 完成登录。"
        )
    return path


def parse_account_ref(account_file: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    把账号标识解析成 (xurl app 名, username)。

    兼容两种写法：
      - "my-app"                -> (app="my-app", user=None)  使用该 app 的默认账号
      - "my-app@myhandle"       -> (app="my-app", user="myhandle")
    如果传入的是一段被 path_utils.resolve_cookie_file 拼过的路径
    （例如 ".../cookiesFile/my-app"），会自动取 basename 恢复 app 名。
    """
    raw = str(account_file or "").strip()
    if not raw:
        return None, None
    # 恢复被 resolve_cookie_file 拼成路径的原始标识
    if os.sep in raw or (os.altsep and os.altsep in raw):
        cand = Path(raw)
        if not cand.is_file() and cand.name:
            raw = cand.name
    app, _, user = raw.partition("@")
    return (app or None), (user or None)


def compose_text(title: Optional[str], description: Optional[str], tags: Optional[List[str]]) -> str:
    """标题 + 描述 + 话题(#tag) 组合成推特正文，超 280 字截断。"""
    parts: List[str] = []
    for part in (title, description):
        text = str(part or "").strip()
        if text:
            parts.append(text)
    hashtags: List[str] = []
    for tag in (tags or []):
        clean = str(tag or "").strip().lstrip("#")
        if clean:
            hashtags.append(f"#{clean}")
    text = "\n\n".join(parts)
    if hashtags:
        text = (text + "\n\n" + " ".join(hashtags)).strip()
    return text[:280]


def media_params(file_path: str) -> Tuple[str, str]:
    """按扩展名/内容类型推断 X 媒体 category 与 media-type。"""
    ext = Path(file_path).suffix.lower()
    mime, _ = mimetypes.guess_type(file_path) or ("application/octet-stream", None)
    mime = mime or "application/octet-stream"
    if ext == ".gif":
        category = "tweet_gif"
    elif mime.startswith("image/"):
        category = "tweet_image"
    else:
        category = "tweet_video"
    return mime, category


async def _run(args: List[str], account_ref: Optional[str] = None, timeout: int = 600) -> Dict[str, Any]:
    cmd: List[str] = [_xurl_bin()]
    app, user = parse_account_ref(account_ref)
    if app and app != "default":
        cmd.extend(["--app", app])
    if user:
        cmd.extend(["-u", user])
    cmd.extend(args)

    proc = await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    stdout = proc.stdout or ""
    payload: Dict[str, Any] = {}
    if stdout.strip():
        try:
            payload = json.loads(stdout)
        except (ValueError, TypeError):
            payload = {"_raw": stdout.strip(), "text": stdout.strip()}

    if proc.returncode != 0 or (isinstance(payload, dict) and payload.get("errors")):
        errors = payload.get("errors") if isinstance(payload, dict) else None
        detail = ""
        if errors:
            try:
                detail = "; ".join(str(e.get("message")) for e in errors if isinstance(e, dict))
            except Exception:
                detail = str(errors)
        if not detail:
            detail = (proc.stderr or stdout or f"exit={proc.returncode}").strip()[:500]
        raise XurlError(f"xurl 执行失败: {detail}")

    if not isinstance(payload, dict):
        payload = {"data": payload}
    return payload


def _pick(payload: Dict[str, Any], keys: List[str]) -> Optional[str]:
    """在嵌套 dict/list 里按优先级取第一个「叶子标量」值。

    与简单遍历不同：优先命中 keys 里的名称，但只有当值是标量（str/int/float）
    时才返回；若命中的是嵌套 dict/list 则继续下钻，避免把容器 str() 出来。
    """
    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            # 第一遍：按优先级找标量叶子
            for key in keys:
                if key in node:
                    val = node[key]
                    if isinstance(val, (dict, list)):
                        found = walk(val)
                        if found not in (None, ""):
                            return found
                    elif val not in (None, ""):
                        return val
            # 第二遍：任意标量叶子兜底
            for val in node.values():
                found = walk(val)
                if found not in (None, ""):
                    return found
        elif isinstance(node, list):
            for item in node:
                found = walk(item)
                if found not in (None, ""):
                    return found
        elif isinstance(node, (str, int, float)) and str(node).strip():
            return str(node)
        return None

    found = walk(payload)
    return str(found) if found not in (None, "") else None


async def auth_status() -> Dict[str, Any]:
    """`xurl auth status` —— 校验是本机是否已注册 app 且默认 app 有 token。"""
    payload = await _run(["auth", "status"], timeout=60)
    # auth status 可能返回非 JSON（表格/文本），此时以 raw 兜底
    return payload


async def whoami(app: Optional[str] = None, username: Optional[str] = None) -> str:
    """返回当前账号 handle（可带 @）。"""
    payload = await _run(["whoami"], account_ref=_account_ref(app, username), timeout=60)
    raw = payload.get("_raw") or payload.get("text") or ""
    if raw:
        return raw.strip().lstrip("@")
    handle = _pick(payload, ["username", "handle", "user_name", "data", "id"])
    return (handle or "").strip().lstrip("@")


def _account_ref(app: Optional[str], username: Optional[str]) -> Optional[str]:
    if app and username:
        return f"{app}@{username}"
    if app:
        return app
    return username


async def upload_media(file_path: str, account_ref: Optional[str] = None) -> str:
    """上传一张图片/一段视频，返回 media_id。视频会等待服务端处理完成。"""
    mime, category = media_params(file_path)
    payload = await _run(
        ["media", "upload", "--media-type", mime, "--category", category, file_path],
        account_ref=account_ref,
        timeout=600,
    )
    media_id = _pick(payload, ["media_id_string", "media_id", "id", "media_key"])
    if not media_id:
        raise XurlError("xurl media upload 未返回 media_id")
    if category in ("tweet_video", "tweet_gif"):
        await _run(["media", "status", "--wait", media_id], account_ref=account_ref, timeout=900)
    return media_id


def start_oauth_browser(app: Optional[str] = None) -> bool:
    """在运行后端的机器上启动 `xurl auth oauth2 --app <app>`，弹出浏览器授权。

    不接收任何密钥（client-id/secret 已在 ~/.xurl），不等待授权完成——前端轮询
    /api/v1/accounts/twitter/whoami 确认 token 就绪后再绑定。后台进程 detach，避免阻塞请求。
    """
    cmd: List[str] = [_xurl_bin()]
    if app and app != "default":
        cmd.extend(["--app", app])
    cmd.extend(["auth", "oauth2"])
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True


async def post(text: str, media_ids: Optional[List[str]] = None, account_ref: Optional[str] = None) -> Dict[str, Any]:
    """发布一条推文，返回 {id, text, url}。"""
    if not text.strip():
        raise XurlError("推文正文为空")
    app, user = parse_account_ref(account_ref)
    args: List[str] = ["post", text]
    for media_id in (media_ids or []):
        args.extend(["--media-id", str(media_id)])
    payload = await _run(args, account_ref=account_ref, timeout=120)
    tweet_id = _pick(payload, ["id", "data", "tweet_id"])
    handle = await whoami(app=app, username=user) if user else await whoami(app=app)
    url = f"https://x.com/{handle}/status/{tweet_id}" if handle and tweet_id else None
    return {
        "id": tweet_id,
        "text": payload.get("data", {}).get("text") if isinstance(payload.get("data"), dict) else text,
        "url": url,
    }
