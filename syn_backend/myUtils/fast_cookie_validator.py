import asyncio
import contextlib
import json
import os
import tempfile
import time
from urllib.parse import urlencode, urlparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx


DEFAULT_UA = os.getenv(
    "FAST_COOKIE_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)


PLATFORM_NAMES: Dict[int, str] = {
    1: "xiaohongshu",
    2: "channels",
    3: "douyin",
    4: "kuaishou",
    5: "bilibili",
}
PLATFORM_CODES: Dict[str, int] = {v: k for k, v in PLATFORM_NAMES.items()}
PLATFORM_ALIASES: Dict[str, str] = {
    "tencent": "channels",
    "wechat": "channels",
    "weixin": "channels",
}


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = str(raw).strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


DEFAULT_FALLBACK = _env_flag("FAST_COOKIE_FALLBACK", False)


def _douyin_params() -> Dict[str, Any]:
    return {
        "aid": 6383,
        "device_platform": "webapp",
        "channel": "channel_pc_web",
        "version_code": 170400,
        "version_name": "17.4.0",
        "platform": "PC",
        "pc_client_type": 1,
        "cookie_enabled": True,
        "browser_language": "zh-CN",
        "browser_platform": "Windows",
        "browser_name": "Chrome",
        "browser_version": "124.0.0.0",
        "browser_online": True,
        "engine_name": "Blink",
        "engine_version": "124.0.0.0",
        "os_name": "Windows",
    }


FAST_CHECKS: Dict[str, Dict[str, Any]] = {
    "xiaohongshu": {
        "method": "GET",
        "url": "https://edith.xiaohongshu.com/api/sns/web/v1/user/selfinfo",
        "domain_filter": "xiaohongshu.com",
        "headers": {
            "Referer": "https://creator.xiaohongshu.com/",
            "Origin": "https://creator.xiaohongshu.com",
        },
        "ok_key": lambda r: r.get("code") == 0,
        "extract": lambda r: (
            str((r.get("data") or {}).get("userId") or (r.get("data") or {}).get("user_id") or ""),
            (r.get("data") or {}).get("nickname") or (r.get("data") or {}).get("name") or "",
            (r.get("data") or {}).get("image") or (r.get("data") or {}).get("avatar") or "",
        ),
    },
    "channels": {
        "method": "GET",
        "url": "https://channels.weixin.qq.com/cgi-bin/mmfinderassistant-bin/auth/auth_data",
        "domain_filter": "channels.weixin.qq.com",
        "headers": {
            "Referer": "https://channels.weixin.qq.com/",
            "Origin": "https://channels.weixin.qq.com",
        },
        "ok_key": lambda r: r.get("ret") == 0,
        "extract": lambda r: (
            str(
                (((r.get("data") or {}).get("finderUser") or {}).get("username"))
                or (((r.get("data") or {}).get("finderUser") or {}).get("finderUsername"))
                or ""
            ),
            (((r.get("data") or {}).get("finderUser") or {}).get("nickname")) or "",
            (((r.get("data") or {}).get("finderUser") or {}).get("headImgUrl")) or "",
        ),
    },
    "douyin": {
        "method": "GET",
        "url": "https://www.douyin.com/aweme/v1/web/user/info/",
        "domain_filter": "douyin.com",
        "headers": {
            "Referer": "https://www.douyin.com/",
            "Origin": "https://www.douyin.com",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        },
        "params": _douyin_params(),
        "ok_key": lambda r: r.get("status_code") == 0,
        "extract": lambda r: (
            str(((r.get("user_info") or {}).get("uid")) or ""),
            ((r.get("user_info") or {}).get("nickname")) or "",
            ((r.get("user_info") or {}).get("avatar_url")) or "",
        ),
    },
    "kuaishou": {
        "method": "POST",
        "url": "https://www.kuaishou.com/graphql",
        "domain_filter": "kuaishou.com",
        "headers": {
            "Referer": "https://www.kuaishou.com/",
            "Origin": "https://www.kuaishou.com",
        },
        "json": {
            "operationName": "visionProfile",
            "variables": {},
            "query": "query visionProfile {visionProfile {userProfile {__typename}}}",
        },
        "ok_key": lambda r: bool(((r.get("data") or {}).get("visionProfile") or {}).get("userProfile") is not None),
        "extract": lambda r: ("", "", ""),
    },
    "bilibili": {
        "method": "GET",
        "url": "https://api.bilibili.com/x/web-interface/nav",
        "domain_filter": "bilibili.com",
        "headers": {
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
        },
        "ok_key": lambda r: r.get("code") == 0 and (r.get("data") or {}).get("isLogin") is True,
        "extract": lambda r: (
            str((r.get("data") or {}).get("mid") or ""),
            (r.get("data") or {}).get("uname") or "",
            (r.get("data") or {}).get("face") or "",
        ),
    },
}


def _normalize_platform(platform: Any) -> str:
    if isinstance(platform, int):
        return PLATFORM_NAMES.get(platform, "")
    name = str(platform or "").strip().lower()
    if name in PLATFORM_ALIASES:
        name = PLATFORM_ALIASES[name]
    return name


def _load_json_file(path: str) -> Optional[Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def _resolve_cookie_path(account_file: str) -> str:
    if not account_file:
        return account_file
    try:
        p = Path(account_file)
        if p.exists():
            return str(p)
    except Exception:
        pass
    try:
        from platforms.path_utils import resolve_cookie_file

        candidate = resolve_cookie_file(account_file)
        if candidate and Path(candidate).exists():
            return candidate
        return candidate
    except Exception:
        return account_file


def _extract_cookies(data: Any) -> List[Dict[str, Any]]:
    cookies: List[Dict[str, Any]] = []
    if isinstance(data, dict):
        cookie_info = data.get("cookie_info")
        if isinstance(cookie_info, dict) and isinstance(cookie_info.get("cookies"), list):
            cookies.extend(cookie_info.get("cookies", []))
        if isinstance(data.get("cookies"), list):
            cookies.extend(data.get("cookies", []))
        if isinstance(data.get("origins"), list):
            for origin in data.get("origins", []):
                if isinstance(origin, dict) and isinstance(origin.get("cookies"), list):
                    cookies.extend(origin.get("cookies", []))
        if isinstance(data.get("cookie"), list):
            cookies.extend(data.get("cookie", []))
    elif isinstance(data, list):
        cookies.extend(data)
    return cookies


def _cookie_header(cookies: List[Dict[str, Any]], domain_filter: Optional[str] = None) -> str:
    pairs: List[str] = []
    for item in cookies:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if not name or value is None:
            continue
        domain = item.get("domain") or ""
        if domain_filter and domain and domain_filter not in str(domain):
            continue
        pairs.append(f"{name}={value}")
    return "; ".join(pairs)


def _cookie_header_from_data(data: Any, domain_filter: Optional[str] = None) -> str:
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, dict):
        for key in ("raw", "cookie", "cookie_str", "cookieString"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    cookies = _extract_cookies(data)
    return _cookie_header(cookies, domain_filter=domain_filter)


def _fallback_user_id(platform: str, cookie_data: Any) -> str:
    cookies = _extract_cookies(cookie_data)
    id_fields = {
        "kuaishou": ["userId", "bUserId", "kuaishou.user.id"],
        "channels": ["wxuin", "uin"],
        "bilibili": ["DedeUserID"],
    }
    for field in id_fields.get(platform, []):
        for item in cookies:
            if isinstance(item, dict) and item.get("name") == field and item.get("value"):
                return str(item.get("value"))

    # LocalStorage fallbacks
    if isinstance(cookie_data, dict) and isinstance(cookie_data.get("origins"), list):
        for origin in cookie_data.get("origins", []):
            local_items = (origin or {}).get("localStorage") or []
            for entry in local_items:
                if not isinstance(entry, dict):
                    continue
                if platform == "channels" and entry.get("name") == "finder_username" and entry.get("value"):
                    return str(entry.get("value"))
                if platform == "xiaohongshu" and entry.get("name") in {"USER_INFO_FOR_BIZ", "USER_INFO"}:
                    try:
                        payload = json.loads(entry.get("value") or "{}")
                        uid = payload.get("userId") or (payload.get("user") or {}).get("value", {}).get("userId")
                        if uid:
                            return str(uid)
                    except Exception:
                        continue
    return ""


def _cookie_pairs_from_string(cookie_str: str) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for part in (cookie_str or "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if name:
            pairs.append((name, value))
    return pairs


def _extract_cookie_value(cookie_data: Any, name: str) -> str:
    target = str(name or "")
    if not target:
        return ""
    if isinstance(cookie_data, str):
        for key, value in _cookie_pairs_from_string(cookie_data):
            if key == target:
                return value
        return ""
    if isinstance(cookie_data, dict):
        for key in ("raw", "cookie", "cookie_str", "cookieString"):
            val = cookie_data.get(key)
            if isinstance(val, str):
                for ck, value in _cookie_pairs_from_string(val):
                    if ck == target:
                        return value
        cookies = _extract_cookies(cookie_data)
    else:
        cookies = _extract_cookies(cookie_data)

    for item in cookies:
        if isinstance(item, dict) and item.get("name") == target and item.get("value"):
            return str(item.get("value"))
    return ""


def _default_domain(platform: str) -> str:
    return {
        "xiaohongshu": ".xiaohongshu.com",
        "channels": ".weixin.qq.com",
        "douyin": ".douyin.com",
        "kuaishou": ".kuaishou.com",
        "bilibili": ".bilibili.com",
    }.get(platform, "")


def _build_storage_state(cookie_data: Any, platform: str, domain_filter: Optional[str]) -> Optional[Dict[str, Any]]:
    if isinstance(cookie_data, dict) and (
        isinstance(cookie_data.get("cookies"), list) or isinstance(cookie_data.get("origins"), list)
    ):
        return cookie_data

    cookies = _extract_cookies(cookie_data)
    if not cookies and isinstance(cookie_data, str):
        cookies = [{"name": k, "value": v} for k, v in _cookie_pairs_from_string(cookie_data)]
    if not cookies:
        return None

    default_domain = domain_filter or _default_domain(platform)
    normalized: List[Dict[str, Any]] = []
    for item in cookies:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if not name or value is None:
            continue
        domain = item.get("domain") or default_domain
        if not domain:
            continue
        path = item.get("path") or "/"
        entry: Dict[str, Any] = {"name": str(name), "value": str(value), "domain": str(domain), "path": str(path)}
        if item.get("expires") is not None:
            entry["expires"] = item.get("expires")
        elif item.get("expirationDate") is not None:
            entry["expires"] = item.get("expirationDate")
        for key in ("httpOnly", "secure", "sameSite"):
            if item.get(key) is not None:
                entry[key] = item.get(key)
        normalized.append(entry)

    if not normalized:
        return None
    return {"cookies": normalized, "origins": []}


def _xhs_sign_path(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return path


def _rc4_crypt(key: bytes, data: bytes) -> bytes:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) & 0xFF
        s[i], s[j] = s[j], s[i]
    i = j = 0
    out = bytearray()
    for byte in data:
        i = (i + 1) & 0xFF
        j = (j + s[i]) & 0xFF
        s[i], s[j] = s[j], s[i]
        k = s[(s[i] + s[j]) & 0xFF]
        out.append(byte ^ k)
    return bytes(out)


def _xbogus_encode(params: str, post_data: str, user_agent: str, timestamp: int) -> str:
    # Ported from https://github.com/smalls0098/xb (Apache-2.0)
    import base64
    import hashlib

    ua_key = bytes([0, 1, 14])
    list_key = bytes([255])
    fixed = 3845494467

    def md5(data: bytes) -> bytes:
        return hashlib.md5(data).digest()

    def md5_twice(data: bytes) -> bytes:
        return md5(md5(data))

    md5_params = md5_twice(params.encode("utf-8"))
    md5_post = md5_twice(post_data.encode("utf-8"))
    ua_rc4 = _rc4_crypt(ua_key, user_agent.encode("utf-8"))
    md5_ua = md5(base64.b64encode(ua_rc4))

    data_list = bytearray()
    data_list.append(64)
    data_list.extend(ua_key)
    data_list.extend(md5_params[14:16])
    data_list.extend(md5_post[14:16])
    data_list.extend(md5_ua[14:16])
    data_list.extend(int(timestamp).to_bytes(4, "big"))
    data_list.extend(int(fixed).to_bytes(4, "big"))
    xor_key = 0
    for b in data_list:
        xor_key ^= b
    data_list.append(xor_key)

    enc = bytearray()
    enc.append(2)
    enc.extend(list_key)
    enc.extend(_rc4_crypt(list_key, bytes(data_list)))

    std_b64 = base64.b64encode(bytes(enc)).decode("ascii")
    std_alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    custom_alphabet = "Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe"
    trans = str.maketrans(std_alphabet, custom_alphabet)
    return std_b64.translate(trans)


def _encode_query(params: Optional[Dict[str, Any]]) -> str:
    if not params:
        return ""
    pairs = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        pairs.append((str(key), str(value)))
    return urlencode(pairs, doseq=True)


async def _sign_xhs(url: str, data: Any, cookie_data: Any, timeout: float = 8.0) -> Optional[Dict[str, str]]:
    a1 = _extract_cookie_value(cookie_data, "a1")
    web_session = _extract_cookie_value(cookie_data, "web_session")
    if not a1:
        return None

    signer_url = os.getenv("XHS_SIGNER_URL")
    if not signer_url:
        try:
            from config.conf import XHS_SERVER

            signer_url = XHS_SERVER
        except Exception:
            signer_url = ""

    path = _xhs_sign_path(url)
    if signer_url:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    signer_url.rstrip("/") + "/sign",
                    json={"uri": path, "data": data, "a1": a1, "web_session": web_session},
                )
            if resp.status_code < 400:
                payload = resp.json()
                if payload.get("x-s") and payload.get("x-t"):
                    return {"x-s": str(payload["x-s"]), "x-t": str(payload["x-t"])}
        except Exception:
            pass

    try:
        from uploader.xhs_uploader.main import sign_local

        signed = await asyncio.to_thread(sign_local, path, data, a1, web_session)
        if signed and signed.get("x-s") and signed.get("x-t"):
            return {"x-s": str(signed["x-s"]), "x-t": str(signed["x-t"])}
    except Exception:
        return None
    return None


async def _sign_douyin(url: str, params: Dict[str, Any], ua: str, timeout: float = 8.0) -> Optional[Dict[str, Any]]:
    signer_url = os.getenv("DOUYIN_SIGNER_URL") or os.getenv("DOUYIN_SIGN_URL")
    if not signer_url:
        query = _encode_query(params)
        if not query:
            return None
        x_bogus = _xbogus_encode(query, "", ua, int(time.time()))
        return {"x_bogus": x_bogus, "params": params}
    payload = {"url": url, "params": params, "user_agent": ua}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(signer_url, json=payload)
        if resp.status_code >= 400:
            return None
        return resp.json()
    except Exception:
        return None


class FastCookieValidator:
    def __init__(self) -> None:
        self._ua = DEFAULT_UA

    async def _fallback_playwright(
        self,
        platform_name: str,
        account_file: Optional[str],
        cookie_data: Any,
        domain_filter: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        try:
            from myUtils import auth
            from myUtils.playwright_helper import run_playwright_task
        except Exception:
            return None

        file_path: Optional[str] = None
        temp_path: Optional[str] = None
        if account_file:
            resolved = _resolve_cookie_path(account_file)
            if resolved and Path(resolved).exists():
                file_path = resolved

        if not file_path and cookie_data is not None:
            storage_state = _build_storage_state(cookie_data, platform_name, domain_filter)
            if storage_state:
                fd, temp_path = tempfile.mkstemp(prefix=f"{platform_name}_cookie_", suffix=".json")
                os.close(fd)
                Path(temp_path).write_text(json.dumps(storage_state), encoding="utf-8")
                file_path = temp_path

        if not file_path:
            return None

        try:
            fn_map = {
                "xiaohongshu": auth.cookie_auth_xhs,
                "channels": auth.cookie_auth_tencent,
                "douyin": auth.cookie_auth_douyin,
                "kuaishou": auth.cookie_auth_ks,
                "bilibili": auth.cookie_auth_bilibili,
            }
            handler = fn_map.get(platform_name)
            if not handler:
                return None
            result = await run_playwright_task(handler(file_path))
            if isinstance(result, dict):
                return result
            return None
        finally:
            if temp_path:
                with contextlib.suppress(Exception):
                    Path(temp_path).unlink()

    async def validate_cookie_fast(
        self,
        platform: Any,
        account_file: Optional[str] = None,
        cookie_data: Any = None,
        *,
        timeout: float = 3.0,
        include_raw: bool = False,
        fallback: Optional[bool] = None,
    ) -> Dict[str, Any]:
        platform_name = _normalize_platform(platform)
        if not platform_name or platform_name not in FAST_CHECKS:
            return {"status": "error", "error": f"Unsupported platform: {platform}"}

        conf = FAST_CHECKS[platform_name]
        domain_filter = conf.get("domain_filter")

        if cookie_data is None and account_file:
            path = _resolve_cookie_path(account_file)
            cookie_data = _load_json_file(path)
            if cookie_data is None:
                return {"status": "error", "error": f"Cookie file not found or invalid: {account_file}"}

        cookie_header = _cookie_header_from_data(cookie_data, domain_filter=domain_filter)
        if not cookie_header:
            return {"status": "error", "error": "Cookie header is empty"}

        headers = {
            "User-Agent": self._ua,
            "Accept": "application/json, text/plain, */*",
            "Cookie": cookie_header,
        }
        headers.update(conf.get("headers") or {})

        use_fallback = DEFAULT_FALLBACK if fallback is None else bool(fallback)
        method = str(conf.get("method") or "GET").upper()
        url = conf.get("url")
        params = conf.get("params")
        json_body = conf.get("json")
        note: Optional[str] = None
        source = "http"

        def _preview(response: httpx.Response) -> str:
            try:
                return (response.text or "").strip()[:200]
            except Exception:
                return ""

        async def _send(
            client: httpx.AsyncClient,
            req_headers: Dict[str, str],
            *,
            params_override: Optional[Dict[str, Any]] = None,
            url_override: Optional[str] = None,
        ) -> httpx.Response:
            req_url = url_override or url
            req_params = params if params_override is None else params_override
            if method == "POST":
                return await client.post(req_url, json=json_body, params=req_params, headers=req_headers)
            return await client.get(req_url, params=req_params, headers=req_headers)

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await _send(client, headers)
                text_preview = _preview(resp)

                if resp.status_code >= 400:
                    if platform_name == "xiaohongshu" and resp.status_code == 406:
                        signed = await _sign_xhs(url, json_body, cookie_data)
                        if signed:
                            resp = await _send(client, {**headers, **signed})
                            text_preview = _preview(resp)
                            note = "xhs_signed"
                            source = "http_signed"
                    elif platform_name == "douyin" and (
                        "Janus" in text_preview or resp.status_code in {403, 418}
                    ):
                        ua_for_sign = headers.get("User-Agent", self._ua)
                        signed = await _sign_douyin(url, params or {}, ua_for_sign)
                        if signed:
                            new_params = dict(params or {})
                            if isinstance(signed.get("params"), dict):
                                new_params.update(signed["params"])
                            x_bogus = signed.get("x_bogus") or signed.get("X-Bogus") or signed.get("X_Bogus")
                            if x_bogus:
                                new_params["X-Bogus"] = x_bogus
                            signed_url = signed.get("signed_url") or signed.get("url")
                            resp = await _send(client, headers, params_override=new_params, url_override=signed_url)
                            text_preview = _preview(resp)
                            note = "douyin_signed"
                            source = "http_signed"
        except httpx.HTTPError as exc:
            return {"status": "network_error", "error": str(exc)}

        elapsed_ms = int((time.monotonic() - start) * 1000)

        def _wrap_fallback_result(result: Dict[str, Any]) -> Dict[str, Any]:
            status = result.get("status") or "error"
            ok = status == "valid"
            payload: Dict[str, Any] = {
                "status": status,
                "ok": ok,
                "platform": platform_name,
                "user_id": result.get("user_id") or None,
                "name": result.get("name") or None,
                "avatar": result.get("avatar") or None,
                "elapsed_ms": elapsed_ms,
                "http_status": None,
                "source": "playwright",
                "note": "fallback",
            }
            if result.get("error"):
                payload["error"] = result.get("error")
            return payload

        if resp.status_code >= 400:
            if use_fallback:
                fallback_result = await self._fallback_playwright(
                    platform_name, account_file, cookie_data, domain_filter
                )
                if fallback_result:
                    return _wrap_fallback_result(fallback_result)

            if platform_name == "xiaohongshu" and resp.status_code == 406:
                error_msg = "XHS requires signed headers (x-s/x-t)."
                if note == "xhs_signed":
                    error_msg = "XHS signed request failed (x-s/x-t)."
                return {
                    "status": "error",
                    "error": error_msg,
                    "http_status": resp.status_code,
                    "elapsed_ms": elapsed_ms,
                    "note": note,
                    "source": source,
                }
            if platform_name == "douyin" and ("Janus" in text_preview or resp.status_code in {403, 418}):
                error_msg = "Douyin blocked (Janus); requires signed params (X-Bogus)."
                if note == "douyin_signed":
                    error_msg = "Douyin signed request failed (X-Bogus)."
                return {
                    "status": "error",
                    "error": error_msg,
                    "http_status": resp.status_code,
                    "elapsed_ms": elapsed_ms,
                    "note": note,
                    "source": source,
                }
            return {
                "status": "error",
                "error": f"HTTP {resp.status_code}",
                "http_status": resp.status_code,
                "elapsed_ms": elapsed_ms,
                "note": note,
                "source": source,
            }

        if text_preview.startswith("<!DOCTYPE") or text_preview.startswith("<html"):
            payload = {
                "status": "expired",
                "ok": False,
                "platform": platform_name,
                "user_id": None,
                "name": None,
                "avatar": None,
                "elapsed_ms": elapsed_ms,
                "http_status": resp.status_code,
                "note": "HTML response (likely not logged in)",
            }
            if source:
                payload["source"] = source
            if note:
                payload["sign_note"] = note
            return payload
        try:
            data = resp.json()
        except Exception:
            return {
                "status": "error",
                "error": f"Invalid JSON response: {resp.status_code}",
                "http_status": resp.status_code,
                "elapsed_ms": elapsed_ms,
                "note": note,
                "source": source,
            }

        ok = False
        try:
            ok = bool(conf["ok_key"](data))
        except Exception:
            ok = False

        user_id = ""
        name = ""
        avatar = ""
        try:
            extract_fn = conf.get("extract")
            if extract_fn:
                user_id, name, avatar = extract_fn(data)
        except Exception:
            user_id = ""
            name = ""
            avatar = ""
        if not user_id:
            user_id = _fallback_user_id(platform_name, cookie_data)

        payload: Dict[str, Any] = {
            "status": "valid" if ok else "expired",
            "ok": ok,
            "platform": platform_name,
            "user_id": user_id or None,
            "name": name or None,
            "avatar": avatar or None,
            "elapsed_ms": elapsed_ms,
            "http_status": resp.status_code,
        }
        if note:
            payload["note"] = note
        if source:
            payload["source"] = source
        if include_raw:
            payload["data"] = data
        return payload


__all__ = ["FastCookieValidator", "PLATFORM_NAMES", "PLATFORM_CODES"]
