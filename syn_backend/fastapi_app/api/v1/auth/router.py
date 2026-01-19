"""
登录认证路由
提供各平台的登录API
"""
import asyncio
import uuid
import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from fastapi import APIRouter, HTTPException, Query, Body
from fastapi_app.core.config import settings
from fastapi.responses import StreamingResponse
import time
from queue import Queue as ThreadQueue
from loguru import logger
import sqlite3
from typing import Any
from datetime import datetime, timezone

from .schemas import (
    PlatformType,
    LoginMethod,
    QRCodeResponse,
    LoginStatusResponse,
    LoginRequest,
    VerificationCodeRequest,
    LoginResult,
    CookieInfo
)
from .services import (
    get_login_service as get_login_service_v1,
    BilibiliLoginService,
    XiaohongshuLoginService,
    DouyinLoginService,
    KuaishouLoginService,
    TencentLoginService
)
from .services_v2 import get_login_service_v2
from .version_switch import should_use_v2_service


def get_login_service(platform: PlatformType):
    """
    获取登录服务 (支持版本切换)

    根据 version_switch.py 配置决定使用V1或V2
    """
    platform_name = platform.value.lower()

    if should_use_v2_service(platform_name):
        logger.info(f"[Login] Using V2 service for {platform_name}")
        return get_login_service_v2(platform)
    else:
        logger.info(f"[Login] Using V1 service for {platform_name}")
        return get_login_service_v1(platform)


router = APIRouter(prefix="/auth", tags=["登录认证"])


# 全局会话存储
login_sessions: Dict[str, dict] = {}


def _fill_user_info_from_cookie(platform: str, cookie_data: dict, user_info: dict) -> dict:
    """从 cookie 补全 user_id/name/avatar，避免 user_id 为空造成重复账号。"""
    try:
        from myUtils.cookie_manager import cookie_manager
        extracted = cookie_manager._extract_user_info_from_cookie(platform, cookie_data) or {}
        if extracted.get("user_id") and not user_info.get("user_id"):
            user_info["user_id"] = extracted["user_id"]
        if extracted.get("name") and (not user_info.get("name") or user_info.get("name") == "-"):
            user_info["name"] = extracted["name"]
        if extracted.get("avatar") and not user_info.get("avatar"):
            user_info["avatar"] = extracted["avatar"]
    except Exception as e:
        logger.warning(f"[Login] fill_user_info_from_cookie failed: {e}")
    return user_info


def _lookup_name_by_user_id(user_id: str, platform: str) -> Optional[str]:
    """从 cookie_accounts 查询已有名称，用于重复 user_id 时回填名称。"""
    try:
        db_path = Path(BASE_DIR) / "db" / "cookie_store.db"
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT name FROM cookie_accounts WHERE platform = ? AND user_id = ?",
                (platform, user_id)
            )
            row = cur.fetchone()
            if row and row["name"]:
                return row["name"]
    except Exception as e:
        logger.warning(f"_lookup_name_by_user_id failed: {e}")
    return None


def _choose_name(user_info: Dict[str, Any], platform: str, account_id: str) -> str:
    """根据已知字段和历史记录选一个最合适的名称（不再使用nickname占位）。"""
    name_fields = ["name", "username", "finder_username", "finderUsername", "finderId", "user_id"]
    for field in name_fields:
        val = user_info.get(field)
        if val:
            return str(val)
    if user_info.get("user_id"):
        return str(user_info["user_id"])
    existing = _lookup_name_by_user_id(user_info.get("user_id", ""), platform) if user_info.get("user_id") else None
    if existing:
        return existing
    return account_id


def _merge_from_cookie_file(account_details: Dict[str, Any], file_path: Path, platform: str):
    """
    用 cookie 文件中的字段填充 name/user_id/avatar（无需再走校验器，纯解析 JSON）
    """
    try:
        from myUtils.cookie_manager import cookie_manager as _cm
        data = json.load(open(file_path, "r", encoding="utf-8"))
        extracted = _cm._extract_user_info_from_cookie(platform, data)
        if extracted.get("user_id") and not account_details.get("user_id"):
            account_details["user_id"] = extracted["user_id"]
        if extracted.get("avatar") and not account_details.get("avatar"):
            account_details["avatar"] = extracted["avatar"]
        if extracted.get("name") and (not account_details.get("name") or account_details.get("name") == "-"):
            account_details["name"] = extracted["name"]
    except Exception as e:
        logger.warning(f"[Login] merge_from_cookie_file failed for {file_path}: {e}")


def _normalize_cookie_list(cookies: Any) -> list:
    """Normalize cookies payload into a list of {name, value} dicts."""
    if isinstance(cookies, list):
        return cookies
    if isinstance(cookies, dict):
        return [{"name": name, "value": value} for name, value in cookies.items()]
    return []


def _ensure_account_persisted(platform_name: str, account_id: str, account_details: Dict[str, Any], cookie_file: Path):
    """Ensure login account is persisted to cookie_store.db even if cookie_manager fails."""
    try:
        from myUtils.cookie_manager import cookie_manager
        if cookie_manager.get_account_by_id(account_id):
            return
        user_id = account_details.get("user_id")
        if user_id:
            try:
                with sqlite3.connect(cookie_manager.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    row = conn.execute(
                        "SELECT account_id FROM cookie_accounts WHERE platform = ? AND user_id = ?",
                        (platform_name, user_id),
                    ).fetchone()
                    if row:
                        name = account_details.get("name") or user_id
                        status = account_details.get("status") or "valid"
                        last_checked = account_details.get("last_checked") or datetime.now(timezone.utc).isoformat()
                        avatar = account_details.get("avatar")
                        original_name = account_details.get("original_name")
                        note = account_details.get("note") or "-"
                        conn.execute(
                            """
                            UPDATE cookie_accounts
                            SET name = ?, status = ?, cookie_file = ?, last_checked = ?, avatar = ?, original_name = ?, note = ?, user_id = ?
                            WHERE account_id = ?
                            """,
                            (
                                name,
                                status,
                                cookie_file.name,
                                last_checked,
                                avatar,
                                original_name,
                                note,
                                user_id,
                                row["account_id"],
                            ),
                        )
                        conn.commit()
                        logger.info(f"[Login] Fallback DB update ok: {platform_name} {row['account_id']}")
                        return
            except Exception:
                pass
        platform_code = cookie_manager._resolve_platform(platform_name)
        name = account_details.get("name") or account_details.get("user_id") or account_id
        status = account_details.get("status") or "valid"
        last_checked = account_details.get("last_checked") or datetime.now(timezone.utc).isoformat()
        avatar = account_details.get("avatar")
        original_name = account_details.get("original_name")
        note = account_details.get("note") or "-"

        with sqlite3.connect(cookie_manager.db_path) as conn:
            conn.execute(
                """
                INSERT INTO cookie_accounts (
                    account_id, platform, platform_code, name, status, cookie_file,
                    last_checked, avatar, original_name, note, user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    platform=excluded.platform,
                    platform_code=excluded.platform_code,
                    name=excluded.name,
                    status=excluded.status,
                    cookie_file=excluded.cookie_file,
                    last_checked=excluded.last_checked,
                    avatar=excluded.avatar,
                    original_name=excluded.original_name,
                    note=excluded.note,
                    user_id=excluded.user_id
                """,
                (
                    account_id,
                    platform_name,
                    platform_code,
                    name,
                    status,
                    cookie_file.name,
                    last_checked,
                    avatar,
                    original_name,
                    note,
                    user_id,
                ),
            )
            conn.commit()
            logger.info(f"[Login] Fallback DB insert ok: {platform_name} {account_id}")
    except Exception as e:
        logger.warning(f"[Login] Fallback DB insert failed: {e}")


@router.post("/qrcode/generate", response_model=QRCodeResponse, summary="生成登录二维码")
async def generate_qrcode(
    platform: PlatformType = Query(..., description="平台类型"),
    account_id: str = Query(..., description="账号ID")
):
    """
    生成登录二维码
    所有平台均通过此接口生成二维码。

    **NEW**: 使用 Playwright Worker 独立进程处理，解决事件循环冲突
    """
    try:
        logger.info(f"[Login] QR generation started: platform={platform.value} account={account_id}")

        # 使用 Playwright Worker 客户端
        from playwright_worker.client import get_worker_client
        worker = get_worker_client()
        worker_health = None
        try:
            worker_health = await worker.health_info()
        except Exception as _e:
            worker_health = {"status": "unreachable", "error": str(_e) or type(_e).__name__}

        # 调用 Worker 生成二维码
        from config.conf import PLAYWRIGHT_HEADLESS
        result = await worker.generate_qrcode(
            platform=platform.value.lower(),
            account_id=account_id,
            headless=bool(PLAYWRIGHT_HEADLESS)
        )

        session_id = result["session_id"]

        # 存储会话信息（用于后续保存）
        login_sessions[session_id] = {
            "platform": platform,
            "account_id": account_id,
            "worker_session_id": session_id,  # Worker 的 session ID
            "status": "waiting",
            "created_at": time.time()
        }

        logger.info(f"[Login] QR generated successfully via Worker: platform={platform.value} session={session_id[:8]}")

        return QRCodeResponse(
            success=True,
            message=f"{platform.value} QR code generated",
            qr_id=session_id,
            qr_image=result["qr_image"],
            expires_in=result.get("expires_in", 300)
        )
    except Exception as e:
        import traceback
        err = str(e) or type(e).__name__
        if isinstance(e, NotImplementedError):
            err = f"{type(e).__name__} (message empty) -> 请检查 Playwright Worker 控制台日志与 /health 的 event_loop_policy"
        logger.error(
            f"[Login] QR generation failed: platform={platform.value} account={account_id} error={type(e).__name__}: {err}"
        )
        logger.debug(traceback.format_exc())
        detail = {"error": f"{type(e).__name__}: {err}"}
        try:
            if "worker_health" in locals():
                detail["worker"] = worker_health
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=detail)


@router.get("/qrcode/poll", response_model=LoginStatusResponse, summary="轮询登录状态")
async def poll_login_status(session_id: str = Query(..., description="登录会话ID")):
    """
    轮询登录状态

    **NEW**: 通过 Playwright Worker 轮询状态
    """
    if session_id not in login_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = login_sessions[session_id]
    platform = session["platform"]
    worker_session_id = session.get("worker_session_id", session_id)

    try:
        # 使用 Playwright Worker 客户端轮询
        from playwright_worker.client import get_worker_client
        worker = get_worker_client()

        result = await worker.poll_status(worker_session_id)
        status = result["status"]
        session["status"] = status

        if status == "confirmed":
            logger.info(f"[Login] Login confirmed via Worker: platform={platform.value} session={session_id[:8]}")

            # 构造数据结构以兼容原保存逻辑
            data = {
                "cookies": result.get("cookies", {}),
                "user_info": result.get("user_info", {}) or {},
                "full_state": result.get("full_state")
            }

            # ⚠️ 修复2: 优化 enrich_account 调用逻辑，避免不必要的二次浏览器启动
            # 说明：poll_status 中已经在首次浏览器会话中提取了 user_info，
            # 仅当关键字段确实缺失时才需要再次启动浏览器补全
            try:
                from config.conf import PLAYWRIGHT_HEADLESS

                user_info = data["user_info"] or {}
                full_state = data.get("full_state")

                def _is_blank(value: Any) -> bool:
                    if value is None:
                        return True
                    if isinstance(value, str) and not value.strip():
                        return True
                    return False

                def _should_replace_name(current_name: Any, user_id: Any) -> bool:
                    if _is_blank(current_name):
                        return True
                    text = str(current_name).strip()
                    if text in {"-", "null"}:
                        return True
                    if user_id is not None and text == str(user_id).strip():
                        return True
                    if text.startswith("未命名账号"):
                        return True
                    return False

                needs_enrich = bool(full_state) and (
                    _is_blank(user_info.get("user_id"))
                    or _is_blank(user_info.get("avatar"))
                    or _should_replace_name(user_info.get("name"), user_info.get("user_id"))
                )

                if needs_enrich:
                    logger.info(f"[Login] 检测到信息缺失，准备调用enrich_account补全: user_id={user_info.get('user_id')}, name={user_info.get('name')}, avatar={'存在' if user_info.get('avatar') else '缺失'}")
                    enriched = await worker.enrich_account(
                        platform.value.lower(),
                        full_state,
                        headless=bool(PLAYWRIGHT_HEADLESS),
                        account_id=session.get("account_id"),
                    )

                    if enriched.get("user_id") and _is_blank(user_info.get("user_id")):
                        user_info["user_id"] = enriched.get("user_id")
                        logger.info(f"[Login] enrich补全user_id: {enriched.get('user_id')}")

                    if enriched.get("name") and _should_replace_name(user_info.get("name"), user_info.get("user_id")):
                        user_info["name"] = enriched.get("name")
                        logger.info(f"[Login] enrich补全name: {enriched.get('name')}")

                    if enriched.get("avatar") and _is_blank(user_info.get("avatar")):
                        user_info["avatar"] = enriched.get("avatar")
                        logger.info(f"[Login] enrich补全avatar")

                    if enriched.get("extra"):
                        if not user_info.get("extra"):
                            user_info["extra"] = enriched.get("extra")
                        elif isinstance(user_info.get("extra"), dict) and isinstance(enriched.get("extra"), dict):
                            merged = dict(enriched.get("extra") or {})
                            merged.update(user_info.get("extra") or {})
                            user_info["extra"] = merged
                    data["user_info"] = user_info
                else:
                    logger.info(f"[Login] 信息已完整，跳过enrich_account调用: user_id={user_info.get('user_id')}, name={user_info.get('name')}")

                if (
                    _is_blank(user_info.get('user_id'))
                    or _should_replace_name(user_info.get('name'), user_info.get('user_id'))
                    or _is_blank(user_info.get('avatar'))
                ):
                    try:
                        from myUtils.fast_cookie_validator import FastCookieValidator

                        cookie_data = data.get('full_state') or {"cookies": data.get('cookies', []), "user_info": user_info}
                        validator = FastCookieValidator()
                        fast_result = await validator.validate_cookie_fast(
                            platform.value.lower(),
                            cookie_data=cookie_data,
                            fallback=False,
                        )
                        if fast_result.get('status') == 'valid':
                            if _is_blank(user_info.get('user_id')) and fast_result.get('user_id'):
                                user_info['user_id'] = fast_result.get('user_id')
                            if _should_replace_name(user_info.get('name'), user_info.get('user_id')) and fast_result.get('name'):
                                user_info['name'] = fast_result.get('name')
                            if _is_blank(user_info.get('avatar')) and fast_result.get('avatar'):
                                user_info['avatar'] = fast_result.get('avatar')
                            data['user_info'] = user_info
                            logger.info(
                                f"[Login] Fast validator补全: user_id={user_info.get('user_id')}, name={user_info.get('name')}"
                            )
                    except Exception as fast_error:
                        logger.warning(f"[Login] Fast validator enrich failed (ignored): {fast_error}")
            except Exception as e:
                logger.warning(f"[Login] Worker enrich failed (ignored): {e}")
                try:
                    from myUtils.fast_cookie_validator import FastCookieValidator

                    cookie_data = data.get("full_state") or {"cookies": data.get("cookies", []), "user_info": user_info}
                    validator = FastCookieValidator()
                    fast_result = await validator.validate_cookie_fast(
                        platform.value.lower(),
                        cookie_data=cookie_data,
                        fallback=False,
                    )
                    if fast_result.get("status") == "valid":
                        if _is_blank(user_info.get("user_id")) and fast_result.get("user_id"):
                            user_info["user_id"] = fast_result.get("user_id")
                        if _should_replace_name(user_info.get("name"), user_info.get("user_id")) and fast_result.get("name"):
                            user_info["name"] = fast_result.get("name")
                        if _is_blank(user_info.get("avatar")) and fast_result.get("avatar"):
                            user_info["avatar"] = fast_result.get("avatar")
                        data["user_info"] = user_info
                        logger.info(
                            f"[Login] Fast validator??: user_id={user_info.get('user_id')}, name={user_info.get('name')}"
                        )
                except Exception as fast_error:
                    logger.warning(f"[Login] Fast validator enrich failed (ignored): {fast_error}")


            # 保存登录信息
            if platform == PlatformType.BILIBILI:
                await _save_bilibili_login(session, data)
            elif platform == PlatformType.XIAOHONGSHU:
                await _save_xiaohongshu_login(session, data)
            elif platform == PlatformType.DOUYIN:
                await _save_douyin_login(session, data)
            elif platform == PlatformType.KUAISHOU:
                await _save_kuaishou_login(session, data)
            elif platform == PlatformType.TENCENT:
                await _save_tencent_login(session, data)

            del login_sessions[session_id]

        return LoginStatusResponse(
            success=True,
            status=status,
            message=result.get("message", ""),
            data=result if status == "confirmed" else None
        )
    except Exception as e:
        logger.error(f"[Login] Poll failed: platform={platform.value} session={session_id[:8]} error={str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/login/unified", summary="统一登录接口")
async def unified_login(
    platform: PlatformType = Query(..., description="平台类型"),
    account_id: str = Query(..., description="账号ID")
):
    """统一登录接口 (强制API模式)"""
    return {
        "success": True, 
        "method": "api", 
        "platform": platform, 
        "instructions": {
            "step1": {
                "method": "POST", 
                "url": f"/api/v1/auth/qrcode/generate?platform={platform.value}&account_id={account_id}", 
                "description": "生成二维码"
            },
            "step2": {
                "method": "GET", 
                "url": "/api/v1/auth/qrcode/poll?session_id={session_id}", 
                "description": "轮询状态"
            }
        }
    }


async def _save_bilibili_login(session: dict, login_data: dict):
    """Save Bilibili login data."""
    try:
        account_id = session["account_id"]
        cookies_list = _normalize_cookie_list(login_data.get("cookies"))
        user_info = login_data.get("user_info", {}) or {}

        cookie_data = {
            "cookie_info": {
                "cookies": cookies_list
            },
            "token_info": {
                "user_id": user_info.get("user_id", "")
            },
            "user_info": {
                "user_id": user_info.get("user_id", ""),
                "username": user_info.get("username", ""),
                "avatar": user_info.get("avatar", "")
            }
        }

        user_info = _fill_user_info_from_cookie("bilibili", cookie_data, user_info)

        cookies_dir = Path(settings.COOKIE_FILES_DIR)
        cookies_dir.mkdir(parents=True, exist_ok=True)
        account_file = cookies_dir / f"bilibili_{account_id}.json"

        final_user_id = user_info.get("user_id") or ""
        if final_user_id:
            final_file = cookies_dir / f"bilibili_{final_user_id}.json"
        else:
            final_file = account_file

        with open(account_file, 'w', encoding='utf-8') as f:
            json.dump(cookie_data, f, ensure_ascii=False, indent=2)

        if final_file != account_file:
            try:
                if final_file.exists():
                    final_file.unlink()
                account_file.replace(final_file)
            except Exception:
                pass
            account_file = final_file

        logger.info(f"[Login] Bilibili login saved: account={account_id} file={account_file.name}")

        account_details = {
            'id': account_id,
            'name': _choose_name(user_info, "bilibili", account_id),
            'status': 'valid',
            'cookie': cookie_data,
            'user_id': user_info.get("user_id", ""),
            'avatar': user_info.get("avatar", ""),
            'note': '-'
        }
        _merge_from_cookie_file(account_details, account_file, "bilibili")

        try:
            from myUtils.cookie_manager import cookie_manager
            cookie_manager.add_account(platform_name='bilibili', account_details=account_details)
        except Exception as e:
            logger.warning(f"[Login] Cookie manager update failed: {e}")
        _ensure_account_persisted("bilibili", account_id, account_details, account_file)

    except Exception as e:
        logger.error(f"[Login] Save Bilibili login failed: account={session.get('account_id')} error={str(e)}")
        raise

async def _save_xiaohongshu_login(session: dict, login_data: dict):
    """保存小红书登录信息"""
    try:

        account_id = session["account_id"]
        cookie_str = login_data.get("cookie", "")
        # ⚠️ 修复1: 统一使用 user_info（而不是login_info），与poll_status保持一致
        user_info = login_data.get("user_info", {}) or {}
        full_state = login_data.get("full_state")

        # 保存到文件
        cookies_dir = Path(settings.COOKIE_FILES_DIR)
        cookies_dir.mkdir(parents=True, exist_ok=True)
        account_file = cookies_dir / f"xiaohongshu_{account_id}.json"

        if full_state:
            cookie_data = full_state
            # ⚠️ 关键修复: Playwright的storage_state没有user_info，需要手动注入
            cookie_data["user_info"] = user_info
        else:
            cookie_data = {
                "cookie": cookie_str,
                "user_info": user_info
            }

        user_info = _fill_user_info_from_cookie("xiaohongshu", cookie_data, user_info)

        # Use user_id filename when available to avoid duplicate account_id cookies
        final_user_id = user_info.get("user_id") or ""
        if final_user_id:
            final_file = cookies_dir / f"xiaohongshu_{final_user_id}.json"
        else:
            final_file = account_file

        with open(account_file, 'w', encoding='utf-8') as f:
            json.dump(cookie_data, f, ensure_ascii=False, indent=2)

        if final_file != account_file:
            try:
                if final_file.exists():
                    final_file.unlink()
                account_file.replace(final_file)
            except Exception:
                pass
            account_file = final_file

        logger.info(f"小红书登录成功，Cookie已保存: {account_file}")

        account_details = {
            'id': account_id,
            'name': _choose_name(user_info, "xiaohongshu", account_id),
            'status': 'valid',
            'cookie': cookie_data,
            'user_id': user_info.get("user_id", ""),
            'avatar': user_info.get("avatar", ""),
            'note': '-'
        }
        _merge_from_cookie_file(account_details, account_file, "xiaohongshu")

        logger.info(f"[Login] 小红书账号详情: name={account_details['name']}, user_id={account_details['user_id']}")

        # 更新到cookie管理器
        try:
            from myUtils.cookie_manager import cookie_manager
            cookie_manager.add_account(platform_name='xiaohongshu', account_details=account_details)
        except Exception as e:
            logger.warning(f"更新cookie管理器失败: {e}")
        _ensure_account_persisted("xiaohongshu", account_id, account_details, account_file)

    except Exception as e:
        logger.error(f"保存小红书登录信息失败: {e}")
        raise


async def _save_douyin_login(session: dict, login_data: dict):
    """Save Douyin login data."""
    try:

        account_id = session["account_id"]
        cookies_list = _normalize_cookie_list(login_data.get("cookies"))
        user_info = login_data.get("user_info", {}) or {}
        full_state = login_data.get("full_state")

        cookies_dir = Path(settings.COOKIE_FILES_DIR)
        cookies_dir.mkdir(parents=True, exist_ok=True)
        account_file = cookies_dir / f"douyin_{account_id}.json"

        if full_state:
            cookie_data = full_state
            # Inject user_info into storage_state when missing.
            cookie_data["user_info"] = user_info
        else:
            cookie_data = {
                "cookies": cookies_list,
                "user_info": user_info
            }

        user_info = _fill_user_info_from_cookie("douyin", cookie_data, user_info)

        final_user_id = user_info.get("user_id") or ""
        if final_user_id:
            final_file = cookies_dir / f"douyin_{final_user_id}.json"
        else:
            final_file = account_file

        with open(account_file, 'w', encoding='utf-8') as f:
            json.dump(cookie_data, f, ensure_ascii=False, indent=2)

        if final_file != account_file:
            try:
                if final_file.exists():
                    final_file.unlink()
                account_file.replace(final_file)
            except Exception:
                pass
            account_file = final_file

        logger.info(f"[Login] Douyin login saved: {account_file}")

        account_details = {
            'id': account_id,
            'name': _choose_name(user_info, "douyin", account_id),
            'status': 'valid',
            'cookie': cookie_data,
            'user_id': user_info.get("user_id", ""),
            'avatar': user_info.get("avatar", ""),
            'note': '-'
        }
        _merge_from_cookie_file(account_details, account_file, "douyin")

        # Update cookie manager.
        try:
            from myUtils.cookie_manager import cookie_manager
            cookie_manager.add_account(platform_name='douyin', account_details=account_details)
        except Exception as e:
            logger.warning(f"[Login] Cookie manager update failed: {e}")
        _ensure_account_persisted("douyin", account_id, account_details, account_file)

    except Exception as e:
        logger.error(f"[Login] Save Douyin login failed: {e}")
        raise

async def _save_kuaishou_login(session: dict, login_data: dict):
    """Save Kuaishou login data."""
    try:
        account_id = session["account_id"]
        cookies_list = _normalize_cookie_list(login_data.get("cookies"))
        user_info = login_data.get("user_info", {}) or {}
        full_state = login_data.get("full_state")

        cookies_dir = Path(settings.COOKIE_FILES_DIR)
        cookies_dir.mkdir(parents=True, exist_ok=True)
        account_file = cookies_dir / f"kuaishou_{account_id}.json"

        if full_state:
            cookie_data = full_state
            # Inject user_info into storage_state when missing.
            cookie_data["user_info"] = user_info
        else:
            cookie_data = {
                "cookies": cookies_list,
                "user_info": user_info
            }

        user_info = _fill_user_info_from_cookie("kuaishou", cookie_data, user_info)

        final_user_id = user_info.get("user_id") or ""
        if final_user_id:
            final_file = cookies_dir / f"kuaishou_{final_user_id}.json"
        else:
            final_file = account_file

        with open(account_file, 'w', encoding='utf-8') as f:
            json.dump(cookie_data, f, ensure_ascii=False, indent=2)

        if final_file != account_file:
            try:
                if final_file.exists():
                    final_file.unlink()
                account_file.replace(final_file)
            except Exception:
                pass
            account_file = final_file

        account_details = {
            'id': account_id,
            'name': _choose_name(user_info, "kuaishou", account_id),
            'status': 'valid',
            'cookie': cookie_data,
            'user_id': user_info.get("user_id", ""),
            'avatar': user_info.get("avatar", ""),
            'note': '-'
        }
        _merge_from_cookie_file(account_details, account_file, "kuaishou")

        # Update cookie manager.
        try:
            from myUtils.cookie_manager import cookie_manager
            cookie_manager.add_account(platform_name='kuaishou', account_details=account_details)
        except Exception as e:
            logger.warning(f"[Login] Cookie manager update failed: {e}")
        _ensure_account_persisted("kuaishou", account_id, account_details, account_file)

    except Exception as e:
        logger.error(f"[Login] Save Kuaishou login failed: {e}")
        raise

async def _save_tencent_login(session: dict, login_data: dict):
    """保存视频号登录信息"""
    try:
        account_id = session["account_id"]
        cookies_list = _normalize_cookie_list(login_data.get("cookies"))
        user_info = login_data.get("user_info", {}) or {}
        full_state = login_data.get("full_state")

        # 保存到文件（优先用 user_id 命名，避免生成 tencent_account_* 临时文件）
        cookies_dir = Path(settings.COOKIE_FILES_DIR)
        cookies_dir.mkdir(parents=True, exist_ok=True)

        if full_state:
            cookie_data = full_state
            # ⚠️ 关键修复: Playwright的storage_state没有user_info，需要手动注入
            cookie_data["user_info"] = user_info
        else:
            cookie_data = {
                "cookies": cookies_list,
                "user_info": user_info
            }

        user_info = _fill_user_info_from_cookie("channels", cookie_data, user_info)
        final_user_id = user_info.get("finder_username") or user_info.get("user_id") or ""
        temp_file = cookies_dir / f"tencent_{account_id}.json"
        if final_user_id:
            account_file = cookies_dir / f"channels_{final_user_id}.json"
        else:
            account_file = temp_file

        with open(account_file, 'w', encoding='utf-8') as f:
            json.dump(cookie_data, f, ensure_ascii=False, indent=2)
        if final_user_id and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass
            
        account_details = {
            'id': account_id,
            'name': _choose_name(user_info, "channels", account_id),
            'status': 'valid',
            'cookie': cookie_data,
            'user_id': user_info.get("finder_username", "") or user_info.get("user_id", ""),
            'avatar': user_info.get("avatar", ""),
            'note': '-'
        }
        _merge_from_cookie_file(account_details, account_file, "channels")

        # 更新Cookie管理器
        try:
            from myUtils.cookie_manager import cookie_manager
            cookie_manager.add_account(platform_name='channels', account_details=account_details)
            cookie_manager.cleanup_duplicate_accounts()
            cookie_manager.cleanup_orphan_cookie_files()
        except Exception as e:
            logger.warning(f"更新cookie管理器失败: {e}")
        _ensure_account_persisted("channels", account_id, account_details, account_file)

    except Exception as e:
        logger.error(f"保存视频号登录信息失败: {e}")
        raise


@router.delete("/sessions/{session_id}", summary="删除登录会话")
async def delete_session(session_id: str):
    """删除登录会话（清理过期会话）"""
    if session_id in login_sessions:
        del login_sessions[session_id]
        return {"success": True, "message": "会话已删除"}

    raise HTTPException(status_code=404, detail="会话不存在")


@router.get("/sessions/cleanup", summary="清理过期会话")
async def cleanup_sessions(max_age: int = Query(default=600, description="最大存活时间（秒）")):
    """清理超过指定时间的登录会话"""
    current_time = time.time()
    expired_sessions = [
        session_id
        for session_id, session in login_sessions.items()
        if current_time - session.get("created_at", 0) > max_age
    ]

    for session_id in expired_sessions:
        del login_sessions[session_id]

    return {
        "success": True,
        "message": f"已清理 {len(expired_sessions)} 个过期会话",
        "cleaned": len(expired_sessions)
    }
