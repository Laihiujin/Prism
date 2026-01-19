import argparse
import asyncio
import json
import os
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
import httpx
from playwright.async_api import async_playwright


def _media_root() -> Path:
    return Path(__file__).resolve().parents[1] / "MediaCrawler"

def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]

def _ensure_mediacrawler_on_path() -> Path:
    root = _media_root()
    os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
    project_root = _project_root()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(root))
    try:
        os.chdir(root)
    except Exception:
        pass
    if "jieba" not in sys.modules:
        sys.modules["jieba"] = types.SimpleNamespace(
            lcut=lambda text: [],
            add_word=lambda word: None,
        )
    if "matplotlib" not in sys.modules:
        mpl = types.ModuleType("matplotlib")
        mpl.pyplot = types.ModuleType("matplotlib.pyplot")
        sys.modules["matplotlib"] = mpl
        sys.modules["matplotlib.pyplot"] = mpl.pyplot
    if "wordcloud" not in sys.modules:
        wordcloud = types.ModuleType("wordcloud")
        wordcloud.WordCloud = object
        sys.modules["wordcloud"] = wordcloud
    if "motor" not in sys.modules:
        motor = types.ModuleType("motor")
        motor_asyncio = types.ModuleType("motor.motor_asyncio")

        class _AsyncIOMotorClient:
            def __init__(self, *args, **kwargs):
                pass

            async def server_info(self):
                return {}

            def __getitem__(self, name):
                return {}

            def close(self):
                return None

        motor_asyncio.AsyncIOMotorClient = _AsyncIOMotorClient
        motor_asyncio.AsyncIOMotorDatabase = object
        motor_asyncio.AsyncIOMotorCollection = object
        motor.motor_asyncio = motor_asyncio
        sys.modules["motor"] = motor
        sys.modules["motor.motor_asyncio"] = motor_asyncio
    if "humps" not in sys.modules:
        humps = types.ModuleType("humps")
        humps.decamelize = lambda value: value
        sys.modules["humps"] = humps
    return root


def _load_cookie_data(cookie_path: Path) -> Dict[str, Any]:
    if not cookie_path.exists():
        return {}
    try:
        return json.loads(cookie_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _extract_cookie_list(cookie_data: Any) -> List[Dict[str, Any]]:
    if isinstance(cookie_data, dict):
        if isinstance(cookie_data.get("cookies"), list):
            return cookie_data.get("cookies") or []
        if isinstance(cookie_data.get("origins"), list):
            cookies: List[Dict[str, Any]] = []
            for origin in cookie_data.get("origins") or []:
                cookies.extend(origin.get("cookies") or [])
            return cookies
    if isinstance(cookie_data, list):
        return [c for c in cookie_data if isinstance(c, dict)]
    return []

def _parse_cookie_string(raw: str, domain: str) -> List[Dict[str, Any]]:
    cookies: List[Dict[str, Any]] = []
    if not raw:
        return cookies
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    for part in parts:
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies.append(
            {
                "name": name.strip(),
                "value": value.strip(),
                "domain": domain,
                "path": "/",
                "httpOnly": False,
                "secure": True,
                "sameSite": "Lax",
            }
        )
    return cookies


def _extract_kuaishou_user_id(cookies: List[Dict[str, Any]]) -> Optional[str]:
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        if cookie.get("name") == "userId":
            value = cookie.get("value")
            if value:
                return str(value)
    return None


def _extract_xhs_user_id(cookie_data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(cookie_data, dict):
        return None
    origins = cookie_data.get("origins") or []
    for origin in origins:
        if not isinstance(origin, dict):
            continue
        local_storage = origin.get("localStorage") or []
        for item in local_storage:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            value = item.get("value")
            if name == "snsWebPublishCurrentUser" and value:
                return str(value)
            if name == "USER_INFO_FOR_BIZ" and value:
                try:
                    parsed = json.loads(value)
                    user_id = parsed.get("userId")
                    if user_id:
                        return str(user_id)
                except Exception:
                    continue
            if name == "USER_INFO" and value:
                try:
                    parsed = json.loads(value)
                    user_id = (parsed.get("user") or {}).get("value", {}).get("userId")
                    if user_id:
                        return str(user_id)
                except Exception:
                    continue
    return None


def _build_launch_args() -> Dict[str, Any]:
    args: Dict[str, Any] = {
        "headless": True,
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    local_path = os.getenv("LOCAL_CHROME_PATH")
    if local_path:
        candidate = Path(local_path)
        if not candidate.is_absolute():
            candidate = (Path(__file__).resolve().parents[1] / candidate).resolve()
        if candidate.exists():
            args["executable_path"] = str(candidate)
            return args
    base_dir = Path(__file__).resolve().parents[1]
    fallback = base_dir / "browsers" / "chromium" / "chromium-1161" / "chrome-win" / "chrome.exe"
    if fallback.exists():
        args["executable_path"] = str(fallback)
    return args


def _extract_xhs_xsec_from_html(html: str) -> Dict[str, str]:
    token = ""
    source = ""
    for match in ("xsec_token=", "xsecSource:", "xsec_source="):
        if match in html:
            break
    import re
    token_match = re.search(r"xsec_token=([A-Za-z0-9_-]+)", html)
    if token_match:
        token = token_match.group(1)
    source_match = re.search(r"xsec_source=([A-Za-z0-9_-]+)", html)
    if source_match:
        source = source_match.group(1)
    return {"xsec_token": token, "xsec_source": source}


async def _collect_xhs(cookie_path: Path, user_id: str, account_id: Optional[str]) -> Dict[str, Any]:
    _ensure_mediacrawler_on_path()
    from tools.crawler_util import convert_cookies
    from media_platform.xhs.client import XiaoHongShuClient
    from myUtils.browser_context import persistent_browser_manager

    cookie_data = _load_cookie_data(cookie_path)
    cookie_list = _extract_cookie_list(cookie_data)
    cookie_str, cookie_dict = convert_cookies(cookie_list)

    async with async_playwright() as p:
        browser = None
        launch_args = _build_launch_args()
        if account_id and user_id:
            user_dir = persistent_browser_manager.get_user_data_dir(account_id, "xiaohongshu", user_id=user_id)
            context = await p.chromium.launch_persistent_context(str(user_dir), **launch_args)
        else:
            browser = await p.chromium.launch(**launch_args)
            context = await browser.new_context()
        if cookie_list:
            await context.add_cookies(cookie_list)
        page = await context.new_page()
        # Touch www + creator to let cookies settle into the profile
        await page.goto("https://www.xiaohongshu.com", timeout=30000)
        try:
            await page.goto("https://creator.xiaohongshu.com/new/home", timeout=30000)
        except Exception:
            pass
        try:
            await page.wait_for_function("typeof window.mnsv2 === 'function'", timeout=8000)
        except Exception:
            pass

        if account_id:
            runtime_cookies = await context.cookies()
            cookie_str, cookie_dict = convert_cookies(runtime_cookies)
            try:
                storage_state = await context.storage_state()
                state_user_id = _extract_xhs_user_id(storage_state) or ""
                if state_user_id:
                    user_id = state_user_id
            except Exception:
                pass
            # Warn if web_session is missing (www domain not logged in)
            if not any(c.get("name") == "web_session" for c in runtime_cookies):
                logger.warning("[MediaCrawler] XHS profile missing web_session; www login may be required.")
        if not user_id:
            await context.close()
            if browser:
                await browser.close()
            raise RuntimeError("missing user_id for xiaohongshu")

        client = XiaoHongShuClient(
            headers={
                "accept": "application/json, text/plain, */*",
                "accept-language": "zh-CN,zh;q=0.9",
                "cache-control": "no-cache",
                "content-type": "application/json;charset=UTF-8",
                "origin": "https://www.xiaohongshu.com",
                "pragma": "no-cache",
                "referer": "https://www.xiaohongshu.com/",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Cookie": cookie_str,
            },
            playwright_page=page,
            cookie_dict=cookie_dict,
        )

        profile_url = f"https://www.xiaohongshu.com/user/profile/{user_id}"
        captured = {"xsec_token": "", "xsec_source": ""}

        def _capture_request(request):
            url = request.url
            if "xsec_token=" in url and not captured["xsec_token"]:
                parsed = _extract_xhs_xsec_from_html(url)
                if parsed.get("xsec_token"):
                    captured["xsec_token"] = parsed.get("xsec_token", "")
                    captured["xsec_source"] = parsed.get("xsec_source", "pc_feed")

        page.on("request", _capture_request)
        await page.goto(profile_url, timeout=30000)
        try:
            req = await page.wait_for_request(
                lambda req: "user_posted" in req.url and "xsec_token=" in req.url,
                timeout=8000,
            )
            parsed = _extract_xhs_xsec_from_html(req.url)
            if parsed.get("xsec_token"):
                captured["xsec_token"] = parsed.get("xsec_token", "")
                captured["xsec_source"] = parsed.get("xsec_source", "pc_feed")
        except Exception:
            pass
        await page.wait_for_timeout(3000)
        html = await page.content()
        xsec = _extract_xhs_xsec_from_html(html)
        if captured["xsec_token"]:
            xsec = captured

        notes = await asyncio.wait_for(
            client.get_all_notes_by_creator(
                user_id=user_id,
                crawl_interval=0,
                xsec_token=xsec.get("xsec_token", ""),
                xsec_source=xsec.get("xsec_source", "pc_feed"),
            ),
            timeout=60,
        )
        await context.close()
        if browser:
            await browser.close()

    return {"success": True, "items": notes}


async def _collect_kuaishou(cookie_path: Path, user_id: str, account_id: Optional[str]) -> Dict[str, Any]:
    _ensure_mediacrawler_on_path()
    from tools.crawler_util import convert_cookies
    from media_platform.kuaishou.client import KuaiShouClient
    from myUtils.browser_context import persistent_browser_manager

    cookie_data = _load_cookie_data(cookie_path)
    cookie_list = _extract_cookie_list(cookie_data)
    env_cookie = os.getenv("KUAISHOU_COOKIE", "").strip()
    if env_cookie:
        cookie_list = _parse_cookie_string(env_cookie, ".kuaishou.com")
    cookie_str, cookie_dict = convert_cookies(cookie_list)
    if not user_id:
        user_id = _extract_kuaishou_user_id(cookie_list) or ""

    async with async_playwright() as p:
        browser = None
        launch_args = _build_launch_args()
        if account_id and user_id:
            user_dir = persistent_browser_manager.get_user_data_dir(account_id, "kuaishou", user_id=user_id)
            context = await p.chromium.launch_persistent_context(str(user_dir), **launch_args)
        else:
            browser = await p.chromium.launch(**launch_args)
            context = await browser.new_context()
        if not account_id and cookie_list:
            await context.add_cookies(cookie_list)
        page = await context.new_page()
        await page.goto("https://www.kuaishou.com", timeout=30000)

        if account_id:
            runtime_cookies = await context.cookies()
            cookie_str, cookie_dict = convert_cookies(runtime_cookies)
            if not user_id:
                user_id = _extract_kuaishou_user_id(runtime_cookies) or ""
        if not user_id:
            await context.close()
            if browser:
                await browser.close()
            raise RuntimeError("missing user_id for kuaishou")

        profile_url = f"https://www.kuaishou.com/profile/{user_id}"
        captured_headers: Dict[str, str] = {}
        captured_payload: Dict[str, Any] | None = None
        captured_response: Dict[str, Any] | None = None

        def _capture_request(req) -> None:
            if "kuaishou.com/graphql" not in req.url:
                return
            headers = req.headers or {}
            for k, v in headers.items():
                if k.lower() == "cookie":
                    continue
                captured_headers[k] = v
            post_data = req.post_data or ""
            if "visionProfilePhotoList" in post_data:
                try:
                    data = json.loads(post_data)
                except Exception:
                    data = {}
                if isinstance(data, dict) and data.get("operationName") == "visionProfilePhotoList":
                    nonlocal captured_payload
                    captured_payload = data

        page.on("request", _capture_request)
        try:
            await page.goto(profile_url, timeout=30000)
            try:
                resp = await page.wait_for_response(
                    lambda r: "kuaishou.com/graphql" in r.url
                    and r.request.post_data
                    and "visionProfilePhotoList" in r.request.post_data,
                    timeout=8000,
                )
                try:
                    payload = await resp.json()
                except Exception:
                    payload = {}
                if isinstance(payload, dict) and payload.get("data"):
                    captured_response = payload.get("data")
            except Exception:
                pass
            await page.wait_for_timeout(1500)
        except Exception:
            pass

        base_headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://www.kuaishou.com",
            "referer": profile_url,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Cookie": cookie_str,
        }
        base_headers.update(captured_headers)

        async def _fetch_profile_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
            videos: List[Dict[str, Any]] = []
            pcursor = ""
            async with httpx.AsyncClient(timeout=15) as client:
                while pcursor != "no_more":
                    payload_vars = payload.get("variables") if isinstance(payload.get("variables"), dict) else {}
                    payload_vars = dict(payload_vars)
                    payload_vars["pcursor"] = pcursor
                    payload_vars["userId"] = user_id
                    payload["variables"] = payload_vars
                    res = await client.post(
                        "https://www.kuaishou.com/graphql",
                        headers=base_headers,
                        data=json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
                    )
                    data = res.json().get("data", {}) if res.content else {}
                    profile_list = data.get("visionProfilePhotoList", {}) if isinstance(data, dict) else {}
                    feeds = profile_list.get("feeds") or []
                    pcursor = profile_list.get("pcursor") or "no_more"
                    videos.extend(feeds)
                    if not feeds:
                        break
            return videos

        if captured_response and isinstance(captured_response, dict):
            profile_list = captured_response.get("visionProfilePhotoList", {})
            if isinstance(profile_list, dict):
                feeds = profile_list.get("feeds") or []
                pcursor = profile_list.get("pcursor") or "no_more"
                if feeds:
                    if captured_payload:
                        more = await _fetch_profile_list(captured_payload)
                        feeds.extend(more)
                    await context.close()
                    if browser:
                        await browser.close()
                    return {"success": True, "items": feeds}
                if pcursor != "no_more" and captured_payload:
                    feeds = await _fetch_profile_list(captured_payload)
                    await context.close()
                    if browser:
                        await browser.close()
                    return {"success": True, "items": feeds}

        client = KuaiShouClient(
            headers=base_headers,
            playwright_page=page,
            cookie_dict=cookie_dict,
        )

        videos = await asyncio.wait_for(
            client.get_all_videos_by_creator(user_id=user_id, crawl_interval=0),
            timeout=60,
        )
        await context.close()
        if browser:
            await browser.close()

    return {"success": True, "items": videos}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=["xiaohongshu", "kuaishou"])
    parser.add_argument("--cookie-file", required=True)
    parser.add_argument("--user-id", required=False, default="")
    parser.add_argument("--account-id", required=False, default="")
    args = parser.parse_args()

    cookie_path = Path(args.cookie_file).expanduser().resolve()
    if not cookie_path.exists():
        print(json.dumps({"success": False, "error": "cookie file not found"}))
        return 1

    user_id = args.user_id.strip()
    account_id = args.account_id.strip() or None
    if args.platform == "xiaohongshu" and not user_id:
        cookie_data = _load_cookie_data(cookie_path)
        user_id = _extract_xhs_user_id(cookie_data) or ""
    if args.platform == "kuaishou" and not user_id:
        cookie_data = _load_cookie_data(cookie_path)
        cookies = _extract_cookie_list(cookie_data)
        env_cookie = os.getenv("KUAISHOU_COOKIE", "").strip()
        if env_cookie:
            cookies = _parse_cookie_string(env_cookie, ".kuaishou.com")
        user_id = _extract_kuaishou_user_id(cookies) or ""
    if not user_id and not account_id:
        print(json.dumps({"success": False, "error": "missing user_id"}))
        return 2

    try:
        if args.platform == "xiaohongshu":
            result = asyncio.run(_collect_xhs(cookie_path, user_id, account_id))
        else:
            result = asyncio.run(_collect_kuaishou(cookie_path, user_id, account_id))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        try:
            from tenacity import RetryError
        except Exception:
            RetryError = None
        if RetryError and isinstance(exc, RetryError):
            last = exc.last_attempt.exception()
            if last:
                print(json.dumps({"success": False, "error": str(last)}))
                return 3
        print(json.dumps({"success": False, "error": str(exc)}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
