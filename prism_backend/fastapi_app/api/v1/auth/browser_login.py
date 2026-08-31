"""
TikTok / YouTube 交互式浏览器登录（方案 C：本机非 headless 弹出浏览器）。

背景：
- 抖音/快手/视频号/小红书/B站 走网页内扫码（/auth/qrcode/*）。
- TikTok / YouTube 无官方网页扫码，需要真实浏览器人工登录（验证码 / Google 2FA）。
  本模块直接在本机调用 CLI 同款登录函数（tiktok_setup / youtube_setup），
  它会弹出一个真实的浏览器窗口让用户完成登录，登录成功后把 cookie
  写入账号 cookie 文件，再由 deep_sync 把账号注册进账号库。

适用：后端/登录在「本机（带桌面/显示器）」运行时，浏览器窗口可见。
（若在无头 Docker 容器内运行，浏览器无法弹出，登录无法人工完成。）
"""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from fastapi_app.core.config import settings

router = APIRouter(prefix="/auth/login/browser", tags=["浏览器登录"])

# 内存中的登录任务: login_id -> 记录
_tasks: Dict[str, Dict[str, Any]] = {}
_tasks_lock = asyncio.Lock()

# 允许的浏览器登录平台
_BROWSER_LOGIN_PLATFORMS = {"tiktok", "youtube"}


def _cookie_file_path(platform: str, account: str) -> Path:
    base = Path(settings.COOKIE_FILES_DIR)
    return base / f"{platform}_{account}.json"


async def _import_from_chrome_profile(platform: str, account: str, cookie_path: Path) -> bool:
    """从本机 Chrome 已登录会话导入：复制 Chrome 的 Cookies/Local State 到
    一个 Prism 专用 profile 目录（非无痕），用其起 Chrome，若平台已登录则
    读取登录态写入 cookie 文件。Chrome 正在运行时也不冲突（用的是副本）。
    """
    import shutil
    from pathlib import Path as _P

    home = _P.home()
    chrome_root = home / "Library" / "Application Support" / "Google" / "Chrome"
    default_dir = chrome_root / "Default"
    cookies_src = default_dir / "Cookies"
    local_state_src = chrome_root / "Local State"
    if not default_dir.is_dir():
        logger.warning(f"[BrowserLogin] 未找到本机 Chrome profile: {default_dir}")
        return False

    def _ignore_cache_dirs(dir: str, names: list) -> set:
        ignored = {
            "Cache", "Code Cache", "GPUCache", "GpuCache", "Service Worker",
            "CacheStorage", "DawnCache", "DawnGraphiteCache", "DawnWebGPUCache",
            "GrShaderCache", "ShaderCache", "component_crx_cache", "Crashpad",
            "File System", "OptimizationGuidePredictionModels", "Storage",
        }
        return {n for n in names if n in ignored}

    from fastapi_app.core.config import settings
    profile_dir = _P(settings.BROWSER_PROFILES_DIR) / f"chrome-import-{platform}-{account}"
    if profile_dir.exists():
        shutil.rmtree(profile_dir, ignore_errors=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    # 复制整个 Default profile（排除缓存），保证 Chrome 读到完整登录态
    shutil.copytree(
        str(default_dir), str(profile_dir / "Default"),
        ignore=_ignore_cache_dirs, dirs_exist_ok=True,
    )
    if local_state_src.exists():
        shutil.copy2(str(local_state_src), str(profile_dir / "Local State"))

    from utils.automation_provider import async_playwright
    from config.conf import LOCAL_CHROME_PATH

    ok = False
    async with async_playwright() as p:
        launch: Dict[str, Any] = {
            "headless": False,
            "user_data_dir": str(profile_dir),
            # patchright 在 chromiumSandbox!==true 时会自动加 --no-sandbox，
            # 显式开启沙箱以避免「不支持的命令行标记」被平台拦截
        }
        if LOCAL_CHROME_PATH:
            launch["executable_path"] = LOCAL_CHROME_PATH
        context = await p.chromium.launch_persistent_context(**launch)
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            url = (
                "https://studio.youtube.com"
                if platform == "youtube"
                else "https://www.tiktok.com/tiktokstudio/upload?lang=en"
            )
            await page.goto(url, wait_until="domcontentloaded")
            logger.info(f"[BrowserLogin] 已用本机 Chrome profile 打开 {platform}，检测登录态...")
            for _ in range(600):  # 最多 10 分钟
                cur = page.url.lower()
                if platform == "youtube" and "/channel/" in cur:
                    await page.wait_for_timeout(2000)
                    ok = True
                    break
                # tiktok：要求进入创作者后台 tiktokstudio，避免首页误判
                if platform == "tiktok" and "tiktokstudio" in cur and "login" not in cur:
                    await page.wait_for_timeout(1000)
                    ok = True
                    break
                await asyncio.sleep(1)
            if ok:
                cookie_path.parent.mkdir(parents=True, exist_ok=True)
                await context.storage_state(path=str(cookie_path))
                logger.info(f"[BrowserLogin] 已从本机 Chrome 导入 {platform} 登录态: {cookie_path}")
        finally:
            try:
                await context.close()
            except Exception:
                pass
    return ok


async def _persona_login(platform: str, account: str, cookie_path: Path, headless: bool = False) -> Dict[str, Any]:
    """通过 PersonaBackend 起 persona profile 浏览器做交互式登录（tiktok/youtube）。

    若该账号已有有效 cookie 文件，则直接复用（不重新登录），返回 success=True
    （上层 browser_login_status 会用 add_account 把它加入账号库）。
    """
    # 已有有效登录态？直接入库，避免强制重新登录
    if cookie_path.exists():
        try:
            if platform == "youtube":
                from uploader.youtube_uploader.main_refactored import cookie_auth as _yt_auth
                _valid = await _yt_auth(str(cookie_path))
            else:
                from uploader.tk_uploader.main_chrome import cookie_auth as _tt_auth
                _valid = await _tt_auth(str(cookie_path))
            if _valid:
                logger.info(f"[BrowserLogin] {platform} 已有有效登录态，直接复用入库: {cookie_path}")
                return {
                    "success": True,
                    "platform": platform,
                    "account": account,
                    "account_file": str(cookie_path),
                    "reused": True,
                }
        except Exception as exc:
            logger.warning(f"[BrowserLogin] cookie 校验异常，进入登录流程: {exc}")

    from fastapi_app.services.browser_backend import get_browser_backend

    persona_profile_id = f"{platform}_{account}"
    backend = get_browser_backend("persona")
    session = None
    try:
        session = await backend.start(
            account,
            profile={"persona_profile_id": persona_profile_id},
            headless=headless,
        )
        page = session.page
        if platform == "youtube":
            url = "https://studio.youtube.com"
        else:  # tiktok
            url = "https://www.tiktok.com/login?lang=en"
        await page.goto(url, wait_until="domcontentloaded")
        logger.info(f"[BrowserLogin] {platform} 已在 Persona 浏览器打开登录页，等待用户登录...")

        ok = False
        for _ in range(600):  # 最多 10 分钟
            current = page.url.lower()
            if platform == "youtube":
                if "/channel/" in current:
                    await page.wait_for_timeout(2000)
                    ok = True
                    break
            else:  # tiktok
                if "login" not in current and "tiktok.com" in current:
                    await page.wait_for_timeout(1000)
                    ok = True
                    break
            await asyncio.sleep(1)

        if ok:
            cookie_path.parent.mkdir(parents=True, exist_ok=True)
            await session.context.storage_state(path=str(cookie_path))
            logger.info(f"[BrowserLogin] {platform} 登录态已保存: {cookie_path}")
        else:
            logger.warning(f"[BrowserLogin] {platform} 等待登录超时")
        return {
            "success": ok,
            "platform": platform,
            "account": account,
            "account_file": str(cookie_path),
            "persona_profile_id": persona_profile_id,
        }
    except Exception as exc:
        logger.error(f"[BrowserLogin] persona 登录失败 {platform}/{account}: {exc}", exc_info=True)
        return {"success": False, "platform": platform, "account": account, "account_file": str(cookie_path)}
    finally:
        if session is not None:
            try:
                await backend.stop(session)
            except Exception:
                pass


async def _run_login(platform: str, account: str, cookie_path: Path) -> Dict[str, Any]:
    """在后台任务中运行平台登录；本机运行时会弹出真实浏览器窗口。"""
    if platform == "tiktok":
        from uploader.tk_uploader.main_chrome import tiktok_setup
        result = await tiktok_setup(str(cookie_path), handle=True)
        return {"success": bool(result), "platform": platform, "account": account, "account_file": str(cookie_path)}
    if platform == "youtube":
        from uploader.youtube_uploader.main_refactored import youtube_setup
        result = await youtube_setup(str(cookie_path), handle=True, return_detail=True, headless=False)
        if isinstance(result, dict):
            ok = bool(result.get("success"))
        else:
            ok = bool(result)
        return {"success": ok, "platform": platform, "account": account, "account_file": str(cookie_path)}
    raise ValueError(f"不支持的浏览器登录平台: {platform}")


@router.post("/start", summary="启动 TikTok/YouTube 浏览器登录")
async def browser_login_start(
    platform: str = Query(..., description="平台: tiktok / youtube"),
    account_id: str = Query(..., description="账号ID"),
):
    platform = (platform or "").lower()
    if platform not in _BROWSER_LOGIN_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"平台 {platform} 不支持浏览器登录")

    cookie_path = _cookie_file_path(platform, account_id)
    cookie_path.parent.mkdir(parents=True, exist_ok=True)

    login_id = str(uuid.uuid4())
    task = asyncio.create_task(_run_login(platform, account_id, cookie_path))

    async with _tasks_lock:
        _tasks[login_id] = {
            "platform": platform,
            "account_id": account_id,
            "cookie_file": str(cookie_path),
            "task": task,
            "status": "running",
            "result": None,
            "error": None,
        }

    logger.info(f"[BrowserLogin] started platform={platform} account={account_id} login_id={login_id[:8]}")

    return {
        "success": True,
        "login_id": login_id,
        "message": "已启动浏览器登录，请在本机弹出的浏览器窗口中完成登录",
        "account_file": str(cookie_path),
    }


@router.post("/import-chrome", summary="从本机 Chrome 导入已登录账号")
async def browser_login_import_chrome(
    platform: str = Query(..., description="平台: tiktok / youtube"),
    account_id: str = Query(..., description="账号ID"),
):
    """复制本机 Chrome 的 Cookies/Local State 到 Prism 专用 profile，起浏览器
    读取已登录会话并入库（非无痕，不需要 Chrome 关闭）。"""
    platform = (platform or "").lower()
    if platform not in _BROWSER_LOGIN_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"平台 {platform} 不支持从 Chrome 导入")

    cookie_path = _cookie_file_path(platform, account_id)
    cookie_path.parent.mkdir(parents=True, exist_ok=True)

    async def _run():
        ok = await _import_from_chrome_profile(platform, account_id, cookie_path)
        return {"success": ok, "platform": platform, "account": account_id, "account_file": str(cookie_path)}

    task = asyncio.create_task(_run())
    login_id = str(uuid.uuid4())
    async with _tasks_lock:
        _tasks[login_id] = {
            "platform": platform,
            "account_id": account_id,
            "cookie_file": str(cookie_path),
            "task": task,
            "status": "running",
            "result": None,
            "error": None,
        }
    logger.info(f"[BrowserLogin] 从本机 Chrome 导入: platform={platform} account={account_id} login_id={login_id[:8]}")
    return {
        "success": True,
        "login_id": login_id,
        "message": "正在从本机 Chrome 导入，请稍候（会自动检测平台登录态）",
        "account_file": str(cookie_path),
    }


@router.get("/status", summary="查询浏览器登录状态")
async def browser_login_status(login_id: str = Query(..., description="登录会话ID")):
    async with _tasks_lock:
        rec = _tasks.get(login_id)
    if not rec:
        raise HTTPException(status_code=404, detail="登录会话不存在或已过期")

    task: asyncio.Task = rec["task"]

    if not task.done():
        return {"success": True, "status": "running", "message": "请在本机弹出的浏览器窗口中完成登录，等待确认..."}

    # 任务已完成
    if rec["status"] == "running":
        try:
            rec["result"] = task.result()
            rec["status"] = "success" if (rec["result"] or {}).get("success") else "failed"
            if rec["status"] == "success":
                # 登录成功：显式把新 cookie 文件注册为账号，再 deep_sync 补全信息。
                # 注意：deep_sync_accounts 已关闭「自动添加磁盘新文件」，
                # 所以这里必须用 add_account 显式入库，否则账号不会出现（未回收）。
                try:
                    from myUtils.cookie_manager import cookie_manager
                    cookie_file = rec["cookie_file"]
                    if cookie_file and Path(cookie_file).exists():
                        try:
                            import json as _json
                            data = _json.load(open(cookie_file, "r", encoding="utf-8"))
                            details = {
                                "account_id": rec["account_id"],
                                "cookie": data if isinstance(data, dict) else {},
                                "note": rec["account_id"],
                            }
                            # 提取 user_id；提取不到时用兜底 ID（先入库，后续可补全）
                            try:
                                uid = cookie_manager._extract_user_id_from_cookie(rec["platform"], data)
                            except Exception:
                                uid = None
                            if not uid:
                                uid = f"{rec['platform']}_{rec['account_id']}"
                            details["user_id"] = uid
                            cookie_manager.add_account(rec["platform"], details)
                            logger.info(f"[BrowserLogin] 已注册账号: platform={rec['platform']} user_id={uid} file={cookie_file}")
                        except Exception as exc:
                            logger.warning(f"[BrowserLogin] add_account 失败: {exc}")
                    await asyncio.to_thread(cookie_manager.deep_sync_accounts)
                except Exception as exc:
                    logger.warning(f"[BrowserLogin] deep_sync failed: {exc}")
        except Exception as exc:
            rec["status"] = "failed"
            rec["error"] = str(exc) or type(exc).__name__
            logger.error(f"[BrowserLogin] login task error: {rec['error']}", exc_info=True)

    if rec["status"] == "success":
        return {
            "success": True,
            "status": "success",
            "message": "登录成功",
            "account_file": rec["cookie_file"],
            "result": rec["result"],
        }

    if rec["status"] == "failed":
        return {
            "success": False,
            "status": "failed",
            "message": rec["error"] or "登录失败",
            "account_file": rec["cookie_file"],
        }

    return {"success": True, "status": "running", "message": "登录中..."}


@router.delete("/cancel/{login_id}", summary="取消浏览器登录")
async def browser_login_cancel(login_id: str):
    async with _tasks_lock:
        rec = _tasks.pop(login_id, None)
    if not rec:
        raise HTTPException(status_code=404, detail="登录会话不存在")
    task: asyncio.Task = rec["task"]
    if not task.done():
        task.cancel()
    return {"success": True, "message": "登录会话已取消"}
