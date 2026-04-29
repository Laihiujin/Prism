"""
Playwright Worker 独立进程
专门处理浏览器自动化任务，与 FastAPI 解耦

架构优势：
1. 独立的事件循环，不受 uvicorn reload 影响
2. 稳定的 Playwright 运行环境
3. 支持长时间运行的浏览器会话
4. 可独立重启，不影响 API 服务
"""
import sys
import asyncio
import os
import platform
import contextlib
import glob
import traceback
import json
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from typing import Dict, Any
from loguru import logger
from fastapi import FastAPI
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
import uvicorn
from dotenv import load_dotenv
import uuid


def _is_drive_root(path: Path) -> bool:
    try:
        return len(path.parts) <= 1
    except Exception:
        return False


def _looks_like_app_root(path: Path) -> bool:
    if (path / "syn_backend").exists() or (path / "backend").exists():
        return True
    if (path / "synenv").exists() and (path / "browsers").exists():
        return True
    return False


def _search_app_root(start: Path) -> Path | None:
    for candidate in [start, *start.parents]:
        if _is_drive_root(candidate):
            continue
        name = candidate.name.lower()
        if name in {"syn_backend", "backend"}:
            return candidate.parent
        if _looks_like_app_root(candidate):
            return candidate
    return None


def _resolve_app_root() -> Path:
    env_root = os.getenv("SYNAPSE_APP_ROOT") or os.getenv("SYNAPSE_RESOURCES_PATH")
    if env_root:
        return Path(env_root).resolve()
    if getattr(sys, "frozen", False):
        frozen_root = _search_app_root(Path(sys.executable).resolve().parent)
        if frozen_root:
            return frozen_root
    repo_root = _search_app_root(Path(__file__).resolve().parents[1].parent)
    if repo_root:
        return repo_root
    return Path(__file__).resolve().parents[1].parent


_APP_ROOT = _resolve_app_root()


def _resolve_executable_path_legacy_unused() -> str | None:
    # 1. 优先从环境变量读取（Electron 打包模式）
    env_path = os.getenv("LOCAL_CHROME_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # 2. 从 config.conf 读取（开发模式）
    try:
        from config.conf import LOCAL_CHROME_PATH, APP_ROOT # type: ignore
        if LOCAL_CHROME_PATH:
            p = Path(str(LOCAL_CHROME_PATH))
            if not p.is_absolute():
                p = Path(APP_ROOT) / p
            if p.exists():
                return str(p)
    except Exception:
        pass

    # 3. 兜底：手动检测 browsers 目录
    # 特别针对用户指定的路径模式
    try:
        common_paths = [
            str(_APP_ROOT / "browsers" / "chromium" / "chromium-1161" / "chrome-win" / "chrome.exe"),
            str(_APP_ROOT / "browsers" / "chrome-for-testing" / "chrome-143.0.7499.169" / "chrome-win64" / "chrome.exe"),
            str(_APP_ROOT / "browsers" / "firefox" / "firefox-1495" / "firefox" / "firefox.exe"),
        ]
        for cp in common_paths:
            if Path(cp).exists():
                return cp
    except Exception:
        pass
        
    return None

# 设置正确的事件循环策略（Windows）
# Playwright 需要 asyncio subprocess 支持（Windows 上由 ProactorEventLoop 提供）。
def _resolve_executable_path() -> str | None:
    def _normalize(raw: str | Path | None) -> Path | None:
        if not raw:
            return None
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = _APP_ROOT / candidate
        return candidate.resolve()

    def _is_legacy_bundled_chrome(candidate: Path) -> bool:
        normalized = str(candidate).replace("/", "\\").lower()
        return (
            "\\browsers\\chromium\\chromium-" in normalized
            or "\\browsers\\chrome-for-testing\\" in normalized
        )

    def _find_matching(patterns: tuple[str, ...]) -> Path | None:
        browser_root = _APP_ROOT / "browsers"
        for pattern in patterns:
            matches = sorted(glob.glob(str(browser_root / pattern)))
            if matches:
                return Path(matches[-1]).resolve()
        return None

    preferred_chrome = _find_matching(("chromium/hibbiki-*/Chrome-bin/chrome.exe",))

    env_path = _normalize(os.getenv("LOCAL_CHROME_PATH"))
    if env_path and env_path.exists():
        if preferred_chrome and _is_legacy_bundled_chrome(env_path):
            return str(preferred_chrome)
        return str(env_path)

    try:
        from config.conf import LOCAL_CHROME_PATH, APP_ROOT  # type: ignore

        if LOCAL_CHROME_PATH:
            configured_path = Path(str(LOCAL_CHROME_PATH))
            if not configured_path.is_absolute():
                configured_path = Path(APP_ROOT) / configured_path
            if configured_path.exists():
                if preferred_chrome and _is_legacy_bundled_chrome(configured_path):
                    return str(preferred_chrome)
                return str(configured_path.resolve())
    except Exception:
        pass

    fallback = _find_matching(
        (
            "chromium/hibbiki-*/Chrome-bin/chrome.exe",
            "chromium/chromium-*/chrome-win64/chrome.exe",
            "chromium/chromium-*/chrome-win/chrome.exe",
            "chrome-for-testing/chrome-*/chrome-win64/chrome.exe",
        )
    )
    return str(fallback) if fallback else None


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    logger.info("[Worker] Set WindowsProactorEventLoopPolicy for Playwright")

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载环境变量（根目录 `.env` 优先，`syn_backend/.env` 作为补充）
_BASE_DIR = Path(__file__).resolve().parent.parent  # syn_backend
_ROOT_ENV = _APP_ROOT / ".env"
if _ROOT_ENV.exists():
    load_dotenv(_ROOT_ENV, override=True)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = raw.strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default

# 导入平台适配器
from app_new.platforms.tencent import TencentAdapter
from app_new.platforms.douyin import DouyinAdapter
from app_new.platforms.kuaishou import KuaishouAdapter
from app_new.platforms.xiaohongshu import XiaohongshuAdapter
from app_new.platforms.bilibili import BilibiliAdapter
from app_new.platforms.base import LoginStatus

# 创建 FastAPI 应用
app = FastAPI(title="Playwright Worker", version="1.0.0")

# Ensure bundled Playwright Chromium exists on worker host.
@app.on_event("startup")
async def _startup_bootstrap_playwright():
    # 如果已经设置了 LOCAL_CHROME_PATH（Electron 打包模式），跳过 Playwright bootstrap
    local_chrome = _resolve_executable_path()
    if local_chrome:
        logger.info(f"[Worker] Using LOCAL_CHROME_PATH: {local_chrome}")
        logger.info(f"[Worker] Skipping Playwright Chromium bootstrap")
        return

    try:
        from utils.playwright_bootstrap import ensure_playwright_chromium_installed

        auto_install = os.getenv("PLAYWRIGHT_AUTO_INSTALL", "1").strip().lower() not in {"0", "false", "no", "off"}
        r = await asyncio.to_thread(ensure_playwright_chromium_installed, auto_install=auto_install)
        logger.info(f"[Worker] PLAYWRIGHT_BROWSERS_PATH={r.browsers_path}")
        if not r.installed:
            logger.warning(f"[Worker] Chromium not ready: {r.error}")
    except Exception as e:
        logger.warning(f"[Worker] Playwright bootstrap failed (ignored): {e}")

# 全局会话存储
sessions: Dict[str, Dict[str, Any]] = {}
sessions_lock = asyncio.Lock()
_cleanup_task: asyncio.Task | None = None

# 平台适配器映射
PLATFORM_ADAPTERS = {
    "tencent": TencentAdapter,
    "channels": TencentAdapter,  # alias for WeChat Channels
    "douyin": DouyinAdapter,
    "kuaishou": KuaishouAdapter,
    "xiaohongshu": XiaohongshuAdapter,
    "bilibili": BilibiliAdapter,
}


class EnrichAccountRequest(BaseModel):
    platform: str = Field(..., description="平台名称 (tencent/douyin/kuaishou/xiaohongshu/bilibili)")
    storage_state: Dict[str, Any] = Field(default_factory=dict, description="Playwright storage_state JSON")
    account_id: str | None = Field(default=None, description="账号ID(用于设备指纹)")
    # None => 使用环境变量 `PLAYWRIGHT_HEADLESS` 的默认值
    headless: bool | None = Field(default=None, description="是否无头模式（None 表示使用 PLAYWRIGHT_HEADLESS）")
    timeout_ms: int = Field(default=30000, description="页面加载超时(ms)")


class OpenCreatorCenterRequest(BaseModel):
    platform: str = Field(..., description="平台名称 (tencent/channels/douyin/kuaishou/xiaohongshu/bilibili)")
    storage_state: Dict[str, Any] = Field(..., description="Playwright storage_state JSON")
    account_id: str | None = Field(default=None, description="账号ID(用于设备指纹)")
    apply_fingerprint: bool = Field(default=True, description="是否应用设备指纹")
    headless: bool | None = Field(default=None, description="是否无头模式（None 表示使用 PLAYWRIGHT_HEADLESS）")
    timeout_ms: int = Field(default=60000, description="页面加载超时(ms)")
    expires_in: int = Field(default=3600, description="会话保留时间(秒)")
    url: str | None = Field(default=None, description="可选，直接打开的 URL")


class CreatorSecUidRequest(BaseModel):
    platform: str = Field(..., description="platform name (douyin only)")
    storage_state: Dict[str, Any] = Field(..., description="Playwright storage_state JSON")
    account_id: str | None = Field(default=None, description="account id (fingerprint)")
    headless: bool | None = Field(default=None, description="headless mode (None => env default)")
    timeout_ms: int = Field(default=30000, description="page load timeout (ms)")
    input_selector: str | None = Field(default=None, description="input selector to trigger sec_uid request")


_PLATFORM_PROFILE_URL = {
    "tencent": "https://channels.weixin.qq.com/platform",
    "channels": "https://channels.weixin.qq.com/platform",
    "douyin": "https://creator.douyin.com/creator-micro/home",
    "kuaishou": "https://cp.kuaishou.com/profile",
    "xiaohongshu": "https://creator.xiaohongshu.com/new/home",
    "bilibili": "https://member.bilibili.com/platform/home",
}


def _append_sec_uid_log(message: str) -> None:
    try:
        log_root = Path(__file__).resolve().parents[1] / "logs"
        log_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat()
        with (log_root / "sec_uid_worker.log").open("a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {message}\n")
    except Exception:
        pass


async def _apply_storage_state(context, storage_state: Dict[str, Any]) -> None:
    if not storage_state:
        return
    cookies = storage_state.get("cookies") or []
    if isinstance(cookies, list) and cookies:
        safe_cookies = [c for c in cookies if isinstance(c, dict)]
        if safe_cookies:
            await context.add_cookies(safe_cookies)

    origins = storage_state.get("origins") or []
    if not isinstance(origins, list) or not origins:
        return
    local_storage_map: Dict[str, Dict[str, str]] = {}
    for origin in origins:
        if not isinstance(origin, dict):
            continue
        origin_url = origin.get("origin")
        if not origin_url:
            continue
        items = {}
        for entry in origin.get("localStorage") or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            value = entry.get("value")
            if not name:
                continue
            items[str(name)] = "" if value is None else str(value)
        if items:
            local_storage_map[str(origin_url)] = items
    if not local_storage_map:
        return
    payload = json.dumps(local_storage_map, ensure_ascii=True)
    script = (
        "(() => {"
        f"const itemsByOrigin = {payload};"
        "try {"
        "  const origin = window.location.origin;"
        "  const items = itemsByOrigin[origin];"
        "  if (!items) return;"
        "  for (const [k, v] of Object.entries(items)) {"
        "    try { localStorage.setItem(k, v); } catch (e) {}"
        "  }"
        "} catch (e) {}"
        "})();"
    )
    await context.add_init_script(script)


@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        loop = asyncio.get_running_loop()
        loop_type = loop.__class__.__name__
    except Exception:
        loop_type = "unknown"

    return {
        "status": "ok",
        "service": "playwright-worker",
        "pid": os.getpid(),
        "python": sys.version.split(" ")[0],
        "platform": platform.platform(),
        "event_loop_policy": asyncio.get_event_loop_policy().__class__.__name__,
        "event_loop": loop_type,
    }


@app.get("/debug/playwright")
async def debug_playwright(headless: bool | None = None):
    """
    调试：尝试启动并关闭一次 Chromium，用于定位 Playwright/浏览器环境问题。
    """
    try:
        if headless is None:
            headless = _env_bool("PLAYWRIGHT_HEADLESS", True)
        from utils.playwright_provider import async_playwright

        pw = await async_playwright().start()
        launch_kwargs: Dict[str, Any] = {"headless": headless}
        executable_path = _resolve_executable_path()
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
        browser = await pw.chromium.launch(**launch_kwargs)
        await browser.close()
        await pw.stop()
        return {"success": True}
    except Exception as e:
        err = str(e) or repr(e) or type(e).__name__
        logger.error(f"[Worker] debug_playwright failed: {err}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "error": err})


@app.post("/creator/open")
async def open_creator_center(req: OpenCreatorCenterRequest):
    """
    打开创作者中心（使用 storage_state 复用登录态）。

    说明：该接口会在运行本服务的机器上打开浏览器窗口（headless=false 时）。
    """
    try:
        platform_code = (req.platform or "").strip().lower()
        profile_url = (req.url or "").strip() or _PLATFORM_PROFILE_URL.get(platform_code)
        if not profile_url:
            return JSONResponse(status_code=400, content={"success": False, "error": f"Unsupported platform: {req.platform}"})

        headless = req.headless
        if headless is None:
            headless = _env_bool("PLAYWRIGHT_HEADLESS", True)

        from utils.playwright_provider import async_playwright
        from myUtils.playwright_context_factory import create_context_with_policy

        # Creator center is more stable in a clean ephemeral context.
        # Reuse storage_state for login, but avoid the per-account persistent profile.
        pw = await async_playwright().start()
        browser = None
        context = None

        # Close stale creator-center sessions for the same account/platform first.
        existing_session_id = None
        if req.account_id:
            async with sessions_lock:
                for sid, sess in sessions.items():
                    if (
                        sess.get("type") == "creator_center"
                        and sess.get("account_id") == req.account_id
                        and sess.get("platform") == platform_code
                    ):
                        existing_session_id = sid
                        break

        if existing_session_id:
            logger.warning(
                f"[Worker] Account {req.account_id} already has session {existing_session_id}, closing old session first"
            )
            try:
                async with sessions_lock:
                    old_sess = sessions.pop(existing_session_id, None)
                if old_sess:
                    with contextlib.suppress(Exception):
                        if old_sess.get("page"):
                            await old_sess["page"].close()
                    with contextlib.suppress(Exception):
                        if old_sess.get("context"):
                            await old_sess["context"].close()
                    with contextlib.suppress(Exception):
                        browser_obj = old_sess.get("browser")
                        if browser_obj:
                            await browser_obj.close()
                    with contextlib.suppress(Exception):
                        if old_sess.get("pw"):
                            await old_sess["pw"].stop()
                    await asyncio.sleep(1)
                    logger.info(f"[Worker] Old session {existing_session_id} closed successfully")
            except Exception as e:
                logger.error(f"[Worker] Failed to close old session: {e}")

        browser, context, _, _ = await create_context_with_policy(
            pw,
            platform=platform_code,
            account_id=None,
            headless=headless,
            storage_state=req.storage_state,
            force_ephemeral=True,
            disable_proxy=True,
            launch_kwargs={"args": ["--no-sandbox"]},
        )

        # 对于持久化上下文，复用已有的页面而不是创建新页面（避免 about:blank）
        pages = context.pages
        if pages:
            page = pages[0]
            logger.info(f"[Worker] Reusing existing page: {page.url}")
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=req.timeout_ms)
        else:
            page = await context.new_page()
            logger.info(f"[Worker] Created new page, navigating to {profile_url}")
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=req.timeout_ms)

        # 🔧 调试：记录最终的页面 URL 和 Cookie 数量
        final_url = page.url
        final_cookies = await context.cookies()
        logger.info(f"[Worker] Page loaded: url={final_url}, cookies={len(final_cookies)}")

        # 🔧 视频号特殊检查：如果跳转到登录页，立即返回错误
        if platform_code in ["channels", "tencent"]:
            # 检查是否在登录页
            if "login" in final_url.lower() or final_url == "https://channels.weixin.qq.com/":
                logger.error(f"[Worker] WeChat Channels redirected to login page, cookies may be invalid")
                # 截图保存（用于调试）
                try:
                    screenshot_path = Path("logs") / f"channels_login_redirect_{req.account_id}.png"
                    screenshot_path.parent.mkdir(exist_ok=True)
                    await page.screenshot(path=str(screenshot_path), full_page=False)
                    logger.info(f"[Worker] Screenshot saved: {screenshot_path}")
                except Exception:
                    pass
                # 清理并返回错误
                with contextlib.suppress(Exception):
                    await page.close()
                with contextlib.suppress(Exception):
                    await context.close()
                with contextlib.suppress(Exception):
                    await browser.close()
                with contextlib.suppress(Exception):
                    await pw.stop()
                return JSONResponse(status_code=401, content={
                    "success": False,
                    "error": "Login required: cookies may be expired or invalid",
                    "detail": f"Redirected to {final_url}"
                })

        if platform_code == "bilibili":
            current_url = (page.url or "").lower()
            if "passport.bilibili.com" in current_url or "passport.bilibili" in current_url:
                with contextlib.suppress(Exception):
                    await page.close()
                with contextlib.suppress(Exception):
                    await context.close()
                with contextlib.suppress(Exception):
                    await browser.close()
                with contextlib.suppress(Exception):
                    await pw.stop()
                return JSONResponse(status_code=401, content={"success": False, "error": "Login required"})

        session_id = f"creator_{uuid.uuid4().hex[:12]}"
        now = asyncio.get_running_loop().time()
        async with sessions_lock:
            sessions[session_id] = {
                "type": "creator_center",
                "created_at": now,
                "expires_in": float(req.expires_in),
                "pw": pw,
                "browser": browser,
                "context": context,
                "page": page,
                "profile_url": profile_url,
                "persistent": False,
                "account_id": req.account_id,
                "platform": platform_code,
            }

        logger.info(f"[Worker] Creator center opened: platform={platform_code} session={session_id}")
        return {"success": True, "data": {"session_id": session_id, "url": profile_url}}

    except Exception as e:
        err = str(e) or type(e).__name__
        logger.error(f"[Worker] Open creator center failed: {err}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "error": err})


@app.post("/creator/sec-uid")
async def fetch_creator_sec_uid(req: CreatorSecUidRequest):
    """Fetch Douyin sec_uid by opening creator center with storage_state."""
    try:
        platform_code = (req.platform or "").strip().lower()
        if platform_code != "douyin":
            return JSONResponse(status_code=400, content={"success": False, "error": "sec_uid only supported for douyin"})

        profile_url = _PLATFORM_PROFILE_URL.get(platform_code)
        if not profile_url:
            return JSONResponse(status_code=400, content={"success": False, "error": "Missing profile url"})

        from utils.playwright_provider import async_playwright
        from myUtils.playwright_context_factory import create_context_with_policy

        headless = req.headless if req.headless is not None else _env_bool("PLAYWRIGHT_HEADLESS", True)
        _append_sec_uid_log(f"start account_id={req.account_id} headless={headless} url={profile_url}")
        pw = await async_playwright().start()
        browser = None
        context = None
        try:
            browser, context, _, _ = await create_context_with_policy(
                pw,
                platform=platform_code,
                account_id=req.account_id,
                headless=headless,
                storage_state=req.storage_state,
                force_ephemeral=bool(req.storage_state),
                launch_kwargs={"args": ["--no-sandbox"]},
            )
            _append_sec_uid_log("context created")
            page = await context.new_page()
            sec_uid_future: asyncio.Future[str | None] = asyncio.get_running_loop().create_future()

            async def _capture_from_response(resp) -> None:
                try:
                    url = resp.url
                    if "/aweme/v1/creator/check/user/" in url:
                        qs = parse_qs(urlparse(url).query)
                        sec_uid_val = (qs.get("sec_uid") or [None])[0]
                        if sec_uid_val and not sec_uid_future.done():
                            sec_uid_future.set_result(sec_uid_val)
                        return
                    if "/passport/user_info/get_sec_ts/" in url:
                        data = await resp.json()
                        if isinstance(data, dict):
                            for key in ("sec_uid", "secUid"):
                                sec_uid_val = data.get(key)
                                if sec_uid_val and not sec_uid_future.done():
                                    sec_uid_future.set_result(str(sec_uid_val))
                                    return
                            user_info = data.get("user_info")
                            if isinstance(user_info, dict):
                                for key in ("sec_uid", "secUid"):
                                    sec_uid_val = user_info.get(key)
                                    if sec_uid_val and not sec_uid_future.done():
                                        sec_uid_future.set_result(str(sec_uid_val))
                                        return
                except Exception:
                    pass

            def _on_response(resp) -> None:
                asyncio.create_task(_capture_from_response(resp))

            page.on("response", _on_response)
            _append_sec_uid_log("response listener attached")

            await page.goto(profile_url, timeout=req.timeout_ms, wait_until="domcontentloaded")
            _append_sec_uid_log(f"page loaded url={page.url}")
            await asyncio.sleep(0.2)

            sec_uid = None
            try:
                sec_uid = await asyncio.wait_for(sec_uid_future, timeout=1.2)
            except Exception:
                sec_uid = None

            _append_sec_uid_log(f"done sec_uid={sec_uid}")
            return {"success": True, "data": {"sec_uid": sec_uid}}
        finally:
            with contextlib.suppress(Exception):
                if context:
                    await context.close()
            with contextlib.suppress(Exception):
                if browser:
                    await browser.close()
            with contextlib.suppress(Exception):
                await pw.stop()
    except Exception as e:
        err = str(e) or type(e).__name__
        _append_sec_uid_log(f"error {err} traceback={traceback.format_exc()}")
        logger.error(f"[Worker] fetch_creator_sec_uid failed: {err}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "error": err})


class CheckLoginStatusRequest(BaseModel):
    """检查账号登录状态请求"""
    account_ids: list[str] | None = Field(default=None, description="账号ID列表(为空则检查下一批)")
    batch_size: int = Field(default=5, ge=1, le=100, description="批量检查数量")


@app.post("/creator/check-login-status")
async def check_login_status_batch(req: CheckLoginStatusRequest):
    """
    批量检查账号登录状态（高并发，直接在Worker内部实现）

    - 如果提供 account_ids，则检查指定账号
    - 如果不提供，则使用轮询策略检查下一批账号
    - 使用高并发 asyncio.gather() 检查
    - 完全在Worker内部实现，无需调用外部 login_status_checker
    """
    try:
        if req.account_ids:
            # 指定账号检查
            logger.info(f"[Worker] 检查指定账号登录状态: {req.account_ids}")
            stats = await _check_specific_accounts_status(req.account_ids)
        else:
            # 轮询策略检查 - 直接在Worker内部实现
            logger.info(f"[Worker] 轮询检查下一批账号登录状态 (batch_size={req.batch_size})")
            stats = await _check_batch_accounts_rotation(batch_size=req.batch_size)

        return {
            "success": True,
            "logged_in": stats["logged_in"],
            "session_expired": stats["session_expired"],
            "errors": stats["errors"],
            "details": stats["details"],
        }

    except Exception as e:
        err = str(e) or type(e).__name__
        logger.error(f"[Worker] check_login_status_batch failed: {err}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "error": err})


async def _check_batch_accounts_rotation(batch_size: int = 5) -> dict:
    """轮询检查下一批账号（直接在Worker内部实现）"""
    from myUtils.cookie_manager import cookie_manager
    from myUtils.login_status_checker import login_status_checker

    # 使用 login_status_checker 的轮询索引
    batch = login_status_checker.get_next_batch_accounts(batch_size)

    if not batch:
        return {
            "checked": 0,
            "logged_in": 0,
            "session_expired": 0,
            "errors": 0,
            "skipped": 0,
            "details": [],
        }

    logger.info(f"[Worker] 开始轮询检查 {len(batch)} 个账号 (直接在Worker内部)")

    # 高并发检查 - 直接调用 Worker 内部方法
    tasks = [
        _check_single_account_login_worker(
            account_id=acc.get("account_id"),
            platform=acc.get("platform"),
            cookie_file=acc.get("cookie_file"),
        )
        for acc in batch
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理结果
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            account = batch[i]
            processed_results.append({
                "account_id": account.get("account_id"),
                "platform": account.get("platform"),
                "login_status": "error",
                "error": str(result),
            })
            logger.error(f"[Worker] 检查异常: {account.get('account_id')} - {result}")
        else:
            processed_results.append(result)

    # 统计结果
    stats = {
        "checked": len(processed_results),
        "logged_in": sum(1 for r in processed_results if r["login_status"] == "logged_in"),
        "session_expired": sum(1 for r in processed_results if r["login_status"] == "session_expired"),
        "errors": sum(1 for r in processed_results if r["login_status"] == "error"),
        "skipped": sum(1 for r in processed_results if r["login_status"] == "skipped"),
        "details": processed_results,
    }

    logger.info(
        f"[Worker] 轮询检查完成: "
        f"总数={stats['checked']}, 在线={stats['logged_in']}, "
        f"掉线={stats['session_expired']}, 错误={stats['errors']}, 跳过={stats['skipped']}"
    )

    return stats


async def _check_single_account_login_worker(account_id: str, platform: str, cookie_file: str) -> dict:
    """在 Worker 内部直接检查单个账号登录状态"""
    import json
    import random
    from pathlib import Path
    from myUtils.cookie_manager import cookie_manager

    result = {
        "account_id": account_id,
        "platform": platform,
        "login_status": "unknown",
        "error": None,
    }

    # 跳过B站账号
    if platform == "bilibili":
        result["login_status"] = "skipped"
        result["error"] = "B站账号跳过检查"
        return result

    # 平台创作者中心URL
    PLATFORM_CREATOR_URLS = {
        "douyin": "https://creator.douyin.com/creator-micro/home",
        "xiaohongshu": "https://creator.xiaohongshu.com/new/home",
        "kuaishou": "https://cp.kuaishou.com/profile",
        "channels": "https://channels.weixin.qq.com/platform/home",
    }

    creator_url = PLATFORM_CREATOR_URLS.get(platform)
    if not creator_url:
        result["login_status"] = "error"
        result["error"] = f"不支持的平台: {platform}"
        return result

    # 读取 cookie 文件
    cookie_file_path = cookie_manager._resolve_cookie_path(cookie_file)
    if not cookie_file_path.exists():
        result["login_status"] = "error"
        result["error"] = "Cookie文件不存在"
        return result

    try:
        with open(cookie_file_path, 'r', encoding='utf-8') as f:
            storage_state = json.load(f)
    except Exception as e:
        result["login_status"] = "error"
        result["error"] = f"读取Cookie文件失败: {str(e)}"
        return result

    # 直接在 Worker 内部启动浏览器检查
    browser = None
    context = None
    page = None
    try:
        from utils.playwright_provider import async_playwright
        from myUtils.playwright_context_factory import create_context_with_policy

        pw = await async_playwright().start()

        # 使用 create_context_with_policy 创建浏览器上下文
        browser, context, fingerprint, policy = await create_context_with_policy(
            pw,
            platform=platform,
            account_id=account_id,
            headless=True,
            storage_state=storage_state,
        )

        page = await context.new_page()

        # 访问创作者中心
        logger.info(f"[Worker] 直接检查 {platform} 账号: {account_id}")
        response = await page.goto(creator_url, wait_until="domcontentloaded", timeout=30000)

        # 等待1-2秒让页面加载/重定向
        wait_time = random.uniform(1, 2)
        await asyncio.sleep(wait_time)

        final_url = page.url

        # 判断登录状态: 如果URL包含login则表示掉线
        if "login" in final_url.lower():
            result["login_status"] = "session_expired"
            result["final_url"] = final_url
            logger.warning(f"[Worker] 账号 {account_id} ({platform}) 已掉线 - URL: {final_url}")
        else:
            result["login_status"] = "logged_in"
            result["final_url"] = final_url
            logger.info(f"[Worker] 账号 {account_id} ({platform}) 在线")

        # 更新数据库（使用 login_status_checker 而不是 cookie_manager）
        from myUtils.login_status_checker import login_status_checker
        login_status_checker.update_login_status(account_id, platform, result["login_status"])

    except Exception as e:
        result["login_status"] = "error"
        result["error"] = str(e)
        logger.error(f"[Worker] {account_id} 检查失败: {e}")
    finally:
        # 清理资源
        try:
            if page:
                await page.close()
            if context:
                await context.close()
            if browser:
                await browser.close()
        except Exception as e:
            logger.warning(f"[Worker] 清理资源失败: {e}")

    return result


async def _check_specific_accounts_status(account_ids: list[str]) -> dict:
    """检查指定账号的登录状态(高并发，直接在Worker内部实现)"""
    from myUtils.cookie_manager import cookie_manager

    # 获取指定账号信息
    all_accounts = cookie_manager.list_flat_accounts()
    target_accounts = [
        acc for acc in all_accounts
        if acc.get("account_id") in account_ids and acc.get("platform") != "bilibili"
    ]

    if not target_accounts:
        return {
            "checked": 0,
            "logged_in": 0,
            "session_expired": 0,
            "errors": 0,
            "skipped": 0,
            "details": [],
        }

    count_text = f"{len(target_accounts)} 个账号" if len(target_accounts) > 1 else "账号"
    logger.info(f"[Worker] 开始检查指定的 {count_text}: {[a.get('account_id') for a in target_accounts]}")

    # 并发检查（多个账号时才并发）
    tasks = [
        _check_single_account_login_worker(
            account_id=acc.get("account_id"),
            platform=acc.get("platform"),
            cookie_file=acc.get("cookie_file"),
        )
        for acc in target_accounts
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理结果
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            account = target_accounts[i]
            processed_results.append({
                "account_id": account.get("account_id"),
                "platform": account.get("platform"),
                "login_status": "error",
                "error": str(result),
            })
            logger.error(f"[Worker] 检查异常: {account.get('account_id')} - {result}")
        else:
            processed_results.append(result)

    # 统计结果
    stats = {
        "checked": len(processed_results),
        "logged_in": sum(1 for r in processed_results if r["login_status"] == "logged_in"),
        "session_expired": sum(1 for r in processed_results if r["login_status"] == "session_expired"),
        "errors": sum(1 for r in processed_results if r["login_status"] == "error"),
        "skipped": sum(1 for r in processed_results if r["login_status"] == "skipped"),
        "details": processed_results,
    }

    logger.info(
        f"[Worker] 指定账号检查完成: "
        f"总数={stats['checked']}, 在线={stats['logged_in']}, "
        f"掉线={stats['session_expired']}, 错误={stats['errors']}, 跳过={stats['skipped']}"
    )

    return stats


@app.delete("/creator/close/{session_id}")
async def close_creator_center(session_id: str):
    try:
        async with sessions_lock:
            s = sessions.get(session_id)
        if not s:
            return JSONResponse(status_code=404, content={"success": False, "error": "Session not found"})

        await _cleanup_session(session_id, s)
        async with sessions_lock:
            sessions.pop(session_id, None)
        return {"success": True}
    except Exception as e:
        err = str(e) or type(e).__name__
        logger.error(f"[Worker] Close creator center failed: {err}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "error": err})


async def _cleanup_session(session_id: str, session: Dict[str, Any]) -> None:
    # Creator-center sessions own their Playwright lifecycle.
    if session.get("type") == "creator_center":
        page = session.get("page")
        context = session.get("context")
        browser = session.get("browser")
        pw = session.get("pw")
        with contextlib.suppress(Exception):
            if page:
                await page.close()
        with contextlib.suppress(Exception):
            if context:
                await context.close()
        with contextlib.suppress(Exception):
            if browser:
                await browser.close()
        with contextlib.suppress(Exception):
            if pw:
                await pw.stop()
        logger.info(f"[Worker] Creator center session cleaned: {session_id}")
        return

    adapter = session.get("adapter")
    if adapter:
        await adapter.cleanup_session(session_id)


@app.post("/account/enrich")
async def enrich_account(req: EnrichAccountRequest):
    """
    使用 storage_state 重新打开平台页面，提取 user_id/name/avatar 等信息。
    用于“登录成功后信息补全”（DOM + Cookie），避免在 API 进程内运行 Playwright。
    """
    try:
        platform_code = (req.platform or "").lower()
        adapter_class = PLATFORM_ADAPTERS.get(platform_code)
        if not adapter_class:
            return JSONResponse(status_code=400, content={"success": False, "error": f"Unsupported platform: {req.platform}"})

        profile_url = _PLATFORM_PROFILE_URL.get(platform_code)
        if not profile_url:
            return JSONResponse(status_code=400, content={"success": False, "error": f"No profile url for platform: {req.platform}"})

        from utils.playwright_provider import async_playwright
        from myUtils.playwright_context_factory import create_context_with_policy
        import inspect

        headless = req.headless if req.headless is not None else _env_bool("PLAYWRIGHT_HEADLESS", True)
        adapter = adapter_class(config={"headless": headless, "account_id": req.account_id})

        pw = await async_playwright().start()
        browser = None
        context = None
        try:
            browser, context, _, _ = await create_context_with_policy(
                pw,
                platform=platform_code,
                account_id=req.account_id,
                headless=headless,
                storage_state=req.storage_state,
                force_ephemeral=bool(req.storage_state),
                launch_kwargs={"args": ["--no-sandbox"]},
            )
            page = await context.new_page()
            await page.goto(profile_url, timeout=req.timeout_ms, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            cookies_list = await context.cookies()

            user_info = None
            extract_fn = getattr(adapter, "_extract_user_info", None)
            if extract_fn:
                try:
                    sig = inspect.signature(extract_fn)
                    if len(sig.parameters) >= 4:
                        user_info = await extract_fn(page, cookies_list, req.storage_state)
                    else:
                        user_info = await extract_fn(page, cookies_list)
                except TypeError:
                    user_info = await extract_fn(page, cookies_list)
            else:
                user_info = None

            if not user_info:
                return {"success": True, "data": {"user_id": None, "name": None, "avatar": None, "extra": None}}

            return {
                "success": True,
                "data": {
                    "user_id": user_info.user_id,
                    "name": user_info.name,
                    "avatar": user_info.avatar,
                    "extra": user_info.extra,
                },
            }
        finally:
            with contextlib.suppress(Exception):
                if context:
                    await context.close()
            with contextlib.suppress(Exception):
                if browser:
                    await browser.close()
            with contextlib.suppress(Exception):
                await pw.stop()

    except Exception as e:
        err = str(e) or repr(e) or type(e).__name__
        logger.error(f"[Worker] enrich_account failed: {err}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "error": err})


@app.post("/qrcode/generate")
async def generate_qrcode(platform: str, account_id: str, headless: bool | None = None):
    """
    生成登录二维码

    Args:
        platform: 平台名称 (tencent/douyin/kuaishou/xiaohongshu/bilibili)
        account_id: 账号ID
        headless: 是否无头模式
    """
    try:
        logger.info(f"[Worker] Generate QR: platform={platform} account={account_id}")

        # 获取平台适配器
        adapter_class = PLATFORM_ADAPTERS.get(platform)
        if not adapter_class:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"Unsupported platform: {platform}"}
            )

        if headless is None:
            headless = _env_bool("PLAYWRIGHT_HEADLESS", True)

        # 创建适配器实例
        adapter = adapter_class(config={"headless": headless, "account_id": account_id})

        # 生成二维码
        qr_data = await adapter.get_qrcode()

        # 存储会话信息
        async with sessions_lock:
            sessions[qr_data.session_id] = {
                "platform": platform,
                "account_id": account_id,
                "adapter": adapter,
                "qr_data": qr_data,
                "created_at": asyncio.get_running_loop().time(),
                "expires_in": int(qr_data.expires_in or 300),
            }

        logger.info(f"[Worker] QR generated: session={qr_data.session_id[:8]}")

        return {
            "success": True,
            "data": {
                "session_id": qr_data.session_id,
                "qr_url": qr_data.qr_url,
                "qr_image": qr_data.qr_image,
                "expires_in": qr_data.expires_in,
            }
        }

    except Exception as e:
        err = str(e) or type(e).__name__
        if isinstance(e, NotImplementedError) and sys.platform == "win32":
            err = (
                f"{err} (Windows asyncio subprocess 未启用；"
                f"policy={asyncio.get_event_loop_policy().__class__.__name__}；"
                "请使用 start_worker.bat 启动 Worker，勿用 reload)"
            )
        logger.error(f"[Worker] QR generation failed: {err}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": err}
        )


@app.get("/qrcode/status/{session_id}")
async def poll_qrcode_status(session_id: str):
    """
    轮询登录状态

    Args:
        session_id: 会话ID
    """
    try:
        # 检查会话是否存在
        async with sessions_lock:
            session = sessions.get(session_id)
        if not session:
            return JSONResponse(status_code=404, content={"success": False, "error": "Session not found or expired"})

        adapter = session["adapter"]

        # 轮询状态
        result = await adapter.poll_status(session_id)

        # 如果登录成功或失败，清理会话
        if result.status in (LoginStatus.CONFIRMED, LoginStatus.FAILED, LoginStatus.EXPIRED):
            try:
                await adapter.cleanup_session(session_id)
            finally:
                async with sessions_lock:
                    sessions.pop(session_id, None)
            logger.info(f"[Worker] Session cleaned: {session_id[:8]} status={result.status.value}")

        return {
            "success": True,
            "data": {
                "status": result.status.value,
                "message": result.message,
                "cookies": result.cookies,
                "user_info": {
                    "user_id": result.user_info.user_id if result.user_info else None,
                    "name": result.user_info.name if result.user_info else None,
                    "avatar": result.user_info.avatar if result.user_info else None,
                    "extra": result.user_info.extra if result.user_info else None,
                } if result.user_info else None,
                "full_state": result.full_state,
            }
        }

    except Exception as e:
        err = str(e) or type(e).__name__
        if isinstance(e, NotImplementedError) and sys.platform == "win32":
            err = (
                f"{err} (Windows asyncio subprocess 未启用；"
                f"policy={asyncio.get_event_loop_policy().__class__.__name__}；"
                "请使用 start_worker.bat 启动 Worker，勿用 reload)"
            )
        logger.error(f"[Worker] Poll status failed: {err}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": err}
        )


@app.delete("/qrcode/cancel/{session_id}")
async def cancel_qrcode(session_id: str):
    """
    取消登录会话

    Args:
        session_id: 会话ID
    """
    try:
        async with sessions_lock:
            session = sessions.get(session_id)
        if not session:
            return JSONResponse(status_code=404, content={"success": False, "error": "Session not found"})

        await _cleanup_session(session_id, session)
        async with sessions_lock:
            sessions.pop(session_id, None)

        logger.info(f"[Worker] Session cancelled: {session_id[:8]}")

        return {"success": True, "message": "Session cancelled"}

    except Exception as e:
        err = str(e) or type(e).__name__
        if isinstance(e, NotImplementedError) and sys.platform == "win32":
            err = (
                f"{err} (Windows asyncio subprocess 未启用；"
                f"policy={asyncio.get_event_loop_policy().__class__.__name__}；"
                "请使用 start_worker.bat 启动 Worker，勿用 reload)"
            )
        logger.error(f"[Worker] Cancel session failed: {err}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": err}
        )


@app.on_event("startup")
async def startup_event():
    """启动事件"""
    logger.info("=" * 60)
    logger.info("Playwright Worker Started")
    logger.info("=" * 60)
    logger.info(f"Event Loop Policy: {asyncio.get_event_loop_policy().__class__.__name__}")
    logger.info(f"Supported Platforms: {list(PLATFORM_ADAPTERS.keys())}")
    logger.info("=" * 60)

    async def _periodic_cleanup():
        while True:
            try:
                now = asyncio.get_running_loop().time()
                async with sessions_lock:
                    expired = [
                        (sid, s)
                        for sid, s in sessions.items()
                        if now - float(s.get("created_at", now)) > float(s.get("expires_in", 300))
                    ]
                for sid, s in expired:
                    try:
                        await _cleanup_session(sid, s)
                    except Exception as e:
                        logger.warning(f"[Worker] Periodic cleanup failed: {sid[:8]} {e}")
                    finally:
                        async with sessions_lock:
                            sessions.pop(sid, None)
                await asyncio.sleep(15)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[Worker] Periodic cleanup loop error: {e}")
                await asyncio.sleep(5)

    global _cleanup_task
    _cleanup_task = asyncio.create_task(_periodic_cleanup())


@app.on_event("shutdown")
async def shutdown_event():
    """关闭事件 - 清理所有会话"""
    logger.info("[Worker] Shutting down, cleaning up sessions...")

    global _cleanup_task
    if _cleanup_task:
        _cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _cleanup_task
        _cleanup_task = None

    async with sessions_lock:
        items = list(sessions.items())

    for session_id, session in items:
        try:
            await _cleanup_session(session_id, session)
        except Exception as e:
            logger.error(f"[Worker] Cleanup failed for {session_id[:8]}: {e}")

    async with sessions_lock:
        sessions.clear()
    logger.info("[Worker] All sessions cleaned")


if __name__ == "__main__":
    # 配置
    HOST = "127.0.0.1"
    PORT = 7001  # 使用不同的端口，避免与 API 服务冲突

    logger.info(f"Starting Playwright Worker on http://{HOST}:{PORT}")

    # 启动服务（不使用 reload）
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        loop="asyncio"  # 使用我们设置的事件循环策略
    )
