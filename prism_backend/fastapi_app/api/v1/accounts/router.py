"""
账号管理API路由
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, Any, Dict
import asyncio
import subprocess
from datetime import datetime, timezone
import json
from pathlib import Path

from ....schemas.account import (
    AccountResponse,
    AccountListResponse,
    AccountCreate,
    AccountUpdate,
    AccountStatsResponse,
    DeepSyncResponse,
    AccountFilterRequest,
    FrontendAccountSnapshotRequest
)
from ....schemas.common import Response, StatusResponse
from .services import account_service
from ....core.logger import logger
from ....core.exceptions import NotFoundException, BadRequestException
from .tools import router as tools_router
from myUtils.cookie_manager import cookie_manager
from platforms.path_utils import resolve_cookie_file

_PLATFORM_PROFILE_URLS = {
    "douyin": "https://creator.douyin.com/",
    "kuaishou": "https://cp.kuaishou.com/",
    "xiaohongshu": "https://creator.xiaohongshu.com/new/home",
    "tencent": "https://channels.weixin.qq.com/platform",
    "channels": "https://channels.weixin.qq.com/platform",
    "tiktok": "https://www.tiktok.com/tiktokstudio/upload",
    "youtube": "https://studio.youtube.com/",
}


router = APIRouter(tags=["账号管理"])

# 活动浏览器会话注册表（生产版应改为 Redis runtime registry + 并发锁）
_ACTIVE_SESSIONS: Dict[str, Any] = {}

# 包含工具路由
router.include_router(tools_router)


@router.get("", response_model=AccountListResponse, include_in_schema=False)
@router.get("/", response_model=AccountListResponse)
async def list_accounts(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
):
    """
    获取账号列表

    - **platform**: 平台过滤（xiaohongshu/channels/douyin/kuaishou/bilibili/tiktok/youtube）
    - **status**: 状态过滤（valid/expired/error/file_missing）
    - **skip**: 跳过数量
    - **limit**: 限制数量（最大1000）
    """
    try:
        result = await account_service.list_accounts(platform, status, skip, limit)
        return AccountListResponse(
            success=True,
            total=result["total"],
            items=result["items"]
        )
    except Exception as e:
        logger.error(f"获取账号列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{account_id}", response_model=Response[AccountResponse])
async def get_account(account_id: str):
    """
    获取账号详情

    - **account_id**: 账号ID
    """
    try:
        account = await account_service.get_account(account_id)
        return Response(success=True, data=account)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取账号详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{account_id}/creator-center/data", response_model=Response[dict])
async def get_creator_center_data(account_id: str):
    """
    获取打开创作中心所需的数据（URL 和 storage_state），供 Electron 前端自主打开。
    """
    try:
        account = cookie_manager.get_account_by_id(account_id)
        if not account:
            raise NotFoundException(f"账号不存在: {account_id}")

        platform = (account.get("platform") or "").strip().lower()
        cookie_file = account.get("cookie_file") or account.get("cookieFile")
        if not cookie_file:
            raise BadRequestException("该账号缺少 cookie_file")

        cookie_path = resolve_cookie_file(cookie_file)
        p = Path(cookie_path)
        if not p.exists():
            raise BadRequestException(f"Cookie 文件不存在: {cookie_path}")

        raw_state = json.loads(p.read_text(encoding="utf-8"))
        storage_state = raw_state
        if platform == "bilibili" and isinstance(raw_state, dict) and "cookie_info" in raw_state:
            storage_state = _build_storage_state_from_biliup_cookie(raw_state)

        url = _PLATFORM_PROFILE_URLS.get(platform)
        if not url:
            if platform == "bilibili":
                url = "https://member.bilibili.com/platform/home"
            else:
                raise BadRequestException(f"不支持的平台: {platform}")

        return Response(success=True, data={
            "url": url,
            "platform": platform,
            "storage_state": storage_state,
            "account_id": account_id,
            "user_id": account.get("user_id")
        })

    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取创作中心数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/creator-center/open", response_model=Response[dict])
async def open_creator_center(account_id: str):
    """
    打开该账号对应平台的创作中心（使用该账号 cookie 登录态）。

    说明：会在运行 Worker 的机器上打开浏览器窗口（需要 `scripts/launchers/start_worker.bat` 已启动）。
    """
    try:
        account = cookie_manager.get_account_by_id(account_id)
        if not account:
            raise NotFoundException(f"账号不存在: {account_id}")

        platform = (account.get("platform") or "").strip().lower()
        cookie_file = account.get("cookie_file") or account.get("cookieFile")
        if not cookie_file:
            raise BadRequestException("该账号缺少 cookie_file，无法打开创作中心")

        cookie_path = resolve_cookie_file(cookie_file)
        p = Path(cookie_path)
        if not p.exists():
            raise BadRequestException(f"Cookie 文件不存在: {cookie_path}")

        raw_state = json.loads(p.read_text(encoding="utf-8"))
        storage_state = raw_state
        if platform == "bilibili" and isinstance(raw_state, dict) and "cookie_info" in raw_state:
            storage_state = _build_storage_state_from_biliup_cookie(raw_state)

        from automation_worker.client import get_worker_client
        client = get_worker_client()
        try:
            data = await client.open_creator_center(
                platform=platform,
                storage_state=storage_state,
                account_id=account_id,
                apply_fingerprint=True,
                headless=False,
            )
            return Response(success=True, data=data)
        except Exception as e:
            if platform != "bilibili":
                raise
            logger.warning(f"B站打开创作中心失败，尝试 biliup 登录: {e}")
            data = await _open_bilibili_creator_center_with_biliup(account_id, p)
            return Response(success=True, data=data)

    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"打开创作中心失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/sec-uid", response_model=Response[dict])
async def fetch_account_sec_uid(account_id: str):
    """
    Fetch Douyin sec_uid using creator center with stored cookies.
    """
    try:
        account = cookie_manager.get_account_by_id(account_id)
        if not account:
            raise NotFoundException(f"Account not found: {account_id}")

        platform = (account.get("platform") or "").strip().lower()
        if platform != "douyin":
            raise BadRequestException("sec_uid only supported for douyin")

        cookie_file = account.get("cookie_file") or account.get("cookieFile")
        if not cookie_file:
            raise BadRequestException("Missing cookie_file for account")

        cookie_path = resolve_cookie_file(cookie_file)
        p = Path(cookie_path)
        if not p.exists():
            raise BadRequestException(f"Cookie file not found: {cookie_path}")

        raw_state = json.loads(p.read_text(encoding="utf-8"))
        storage_state = raw_state

        from automation_worker.client import get_worker_client
        client = get_worker_client()
        data = await client.fetch_creator_sec_uid(
            platform=platform,
            storage_state=storage_state,
            account_id=account_id,
            headless=True,
        )
        sec_uid = (data or {}).get("sec_uid")

        if sec_uid:
            if not isinstance(raw_state, dict):
                raw_state = {}
            user_info = raw_state.get("user_info")
            if not isinstance(user_info, dict):
                user_info = {}
                raw_state["user_info"] = user_info
            if user_info.get("sec_uid") != sec_uid:
                user_info["sec_uid"] = sec_uid
                p.write_text(json.dumps(raw_state, ensure_ascii=True, indent=2), encoding="utf-8")

        return Response(success=True, data={"sec_uid": sec_uid})

    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Fetch sec_uid failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _build_storage_state_from_biliup_cookie(cookie_data: Dict[str, Any]) -> Dict[str, Any]:
    from uploader.bilibili_uploader.cookie_refresher import to_biliup_cookie_format

    normalized = to_biliup_cookie_format(cookie_data or {})
    cookies_list = (normalized.get("cookie_info") or {}).get("cookies") or []
    if not isinstance(cookies_list, list):
        cookies_list = []
    return {"cookies": cookies_list, "origins": []}


async def _open_bilibili_creator_center_with_biliup(
    account_id: str,
    cookie_path: Path,
) -> Dict[str, Any]:
    biliup_exe = Path(__file__).resolve().parents[4] / "uploader" / "bilibili_uploader" / "biliup.exe"
    if not biliup_exe.exists():
        raise BadRequestException(f"biliup.exe 不存在: {biliup_exe}")

    cookie_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(biliup_exe), "-u", str(cookie_path), "login"]

    # 抑制 biliup.exe 的标准输出，防止日志爆炸
    await asyncio.to_thread(
        subprocess.run,
        cmd,
        check=True,
        cwd=str(biliup_exe.parent),
        stdout=subprocess.DEVNULL,  # 抑制标准输出
        stderr=subprocess.DEVNULL,  # 抑制标准错误
    )

    cookie_data = json.loads(cookie_path.read_text(encoding="utf-8"))
    storage_state = _build_storage_state_from_biliup_cookie(cookie_data)
    if not storage_state.get("cookies"):
        raise BadRequestException("biliup 登录未获取到有效 Cookie")

    try:
        extracted = cookie_manager._extract_user_info_from_cookie("bilibili", cookie_data) or {}
        name = extracted.get("name")
        avatar = extracted.get("avatar")
        user_id = extracted.get("user_id")
        update_kwargs = {
            "status": "valid",
            "last_checked": datetime.now(timezone.utc).isoformat(),
        }
        if user_id:
            update_kwargs["user_id"] = str(user_id)
        if name:
            update_kwargs["name"] = str(name)
        if avatar:
            update_kwargs["avatar"] = str(avatar)
        cookie_manager.update_account(account_id, **update_kwargs)
    except Exception as e:
        logger.warning(f"更新 B站账号信息失败（忽略）: {e}")

    from automation_worker.client import get_worker_client
    client = get_worker_client()
    return await client.open_creator_center(
        platform="bilibili",
        storage_state=storage_state,
        account_id=account_id,
        apply_fingerprint=True,
        headless=False,
    )


@router.post("/{account_id}/creator-center/open-biliup", response_model=Response[dict])
async def open_creator_center_biliup(account_id: str):
    """
    使用 biliup.exe 登录并打开 B站创作者中心（解决 B站账号 cookie 为空/不兼容的问题）。
    """
    try:
        account = cookie_manager.get_account_by_id(account_id)
        if not account:
            raise NotFoundException(f"账号不存在: {account_id}")

        platform = (account.get("platform") or "").strip().lower()
        if platform != "bilibili":
            raise BadRequestException("仅支持 Bilibili 账号")

        cookie_file = account.get("cookie_file") or account.get("cookieFile")
        if not cookie_file:
            raise BadRequestException("该账号缺少 cookie_file，无法打开创作中心")

        cookie_path = resolve_cookie_file(cookie_file)
        p = Path(cookie_path)
        data = await _open_bilibili_creator_center_with_biliup(account_id, p)
        return Response(success=True, data=data)

    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except subprocess.CalledProcessError as e:
        logger.error(f"biliup.exe 登录失败: {e}")
        raise HTTPException(status_code=500, detail="biliup.exe 登录失败")
    except Exception as e:
        logger.error(f"打开创作中心失败(Biliup): {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=StatusResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=StatusResponse, status_code=status.HTTP_201_CREATED)
async def create_account(account_data: AccountCreate):
    """
    创建账号

    需要提供完整的账号信息和Cookie数据
    """
    try:
        result = await account_service.create_account(account_data.dict())
        return StatusResponse(**result)
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建账号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{account_id}", response_model=StatusResponse)
async def update_account(account_id: str, update_data: AccountUpdate):
    """
    更新账号信息

    - **account_id**: 账号ID
    - 可更新字段: name, note, status, avatar, original_name
    """
    try:
        # 只包含非None的字段
        data = update_data.dict(exclude_unset=True)
        result = await account_service.update_account(account_id, data)
        return StatusResponse(**result)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"更新账号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{account_id}", response_model=StatusResponse)
async def delete_account(account_id: str):
    """
    删除账号

    - **account_id**: 账号ID
    - 会同时删除Cookie文件
    """
    try:
        result = await account_service.delete_account(account_id)
        return StatusResponse(**result)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"删除账号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))





# DISABLED: deep-sync 会导致账号数据混乱，已禁用
# @router.post("/deep-sync", response_model=DeepSyncResponse)
# async def deep_sync_accounts():
#     """
#     深度同步账号
#
#     - 备份现有Cookie文件
#     - 扫描磁盘文件，添加未入库的账号
#     - 标记文件丢失的账号
#     - 清理超过7天的备份
#     """
#     try:
#         result = await account_service.deep_sync()
#         return DeepSyncResponse(**result)
#     except Exception as e:
#         logger.error(f"深度同步失败: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


@router.delete("/invalid", response_model=StatusResponse)
async def delete_invalid_accounts():
    """
    删除所有失效账号

    - 删除状态不为'valid'的账号
    - 同时删除对应的Cookie文件
    """
    try:
        result = await account_service.delete_invalid_accounts()
        return StatusResponse(**result)
    except Exception as e:
        logger.error(f"删除失效账号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary", response_model=Response[AccountStatsResponse])
async def get_account_stats():
    """
    获取账号统计信息

    - 总数、各状态数量
    - 按平台分组统计
    """
    try:
        stats = await account_service.get_stats()
        return Response(success=True, data=stats)
    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/filter", response_model=AccountListResponse)
async def filter_accounts(filter_req: AccountFilterRequest):
    """
    高级筛选账号

    - 支持多条件组合筛选
    - 支持分页
    """
    try:
        result = await account_service.list_accounts(
            platform=filter_req.platform,
            status=filter_req.status,
            skip=filter_req.skip,
            limit=filter_req.limit
        )
        return AccountListResponse(
            success=True,
            total=result["total"],
            items=result["items"]
        )
    except Exception as e:
        logger.error(f"筛选账号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prune-by-frontend", response_model=Response[dict])
async def prune_by_frontend_snapshot(request: FrontendAccountSnapshotRequest):
    """
    Delete backend accounts/cookies that are not present in frontend list.
    """
    try:
        snapshot = [{"account_id": acc.account_id, "platform": acc.platform, "user_id": acc.user_id} for acc in request.accounts]
        cookie_manager.save_frontend_snapshot(snapshot)
        result = cookie_manager.prune_accounts_not_in_frontend(snapshot)
        return Response(success=True, data=result)
    except Exception as e:
        logger.error(f"Prune by frontend failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# DISABLED: sync-user-info 功能暂时关闭（等待优化）
# @router.post("/sync-user-info", response_model=Response[dict])
# async def sync_user_info():
#     """
#     同步所有账号的用户信息
#
#     - 通过访问平台页面抓取最新的用户名、头像、ID
#     - 更新cookie文件和数据库
#     - 支持平台: 快手、抖音、视频号、小红书、B站
#     """
#     try:
#         result = await account_service.sync_user_info()
#         return Response(success=True, data=result)
#     except Exception as e:
#         logger.error(f"同步用户信息失败: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 账号环境 / 固定身份绑定（Proxy Manager + Persona Studio）
# ============================================================

from ....schemas.common import StatusResponse as _StatusResponse  # noqa: E402
from pydantic import BaseModel as _BaseModel  # noqa: E402


class _BindProxyRequest(_BaseModel):
    proxy_id: str


class _RebindProxyRequest(_BaseModel):
    proxy_id: str


class _BrowserActionRequest(_BaseModel):
    headless: bool = True


def _proxy_service():
    from fastapi_app.services.ip_pool_service import get_ip_pool_service
    return get_ip_pool_service()


@router.get("/{account_id}/environment")
async def get_account_environment(account_id: str):
    """
    账号环境视图：展示固定身份绑定关系。
    Account → Browser Profile(Persona) → Sticky Proxy → Patchright。
    """
    try:
        account = cookie_manager.get_account_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")

        binding = cookie_manager.get_account_binding(account_id) or {}
        proxy_id = binding.get("proxy_id")
        proxy = None
        proxy_service = None
        try:
            proxy_service = _proxy_service()
            if proxy_id:
                proxy = proxy_service.get_ip(proxy_id)
        except Exception as e:
            logger.warning(f"读取代理服务失败: {e}")

        # Persona serve 在线状态
        persona_online = False
        try:
            from fastapi_app.services.persona_client import get_persona_client
            persona_online = await get_persona_client().health()
        except Exception:
            persona_online = False

        # Runtime 锁状态（安全信息，不含敏感数据）
        runtime_status = {"locked": False}
        try:
            from fastapi_app.services.runtime_lock_service import get_runtime_lock_service
            runtime_status = get_runtime_lock_service().status(account_id)
        except Exception:
            pass

        env = {
            "account": {
                "account_id": account.get("account_id"),
                "platform": account.get("platform"),
                "name": account.get("name"),
                "user_id": account.get("user_id"),
            },
            "browser": {
                "backend": binding.get("browser_backend") or "patchright",
                "persona_profile_id": binding.get("persona_profile_id"),
                "persona_online": persona_online,
                "engine": "patchright",
            },
            "runtime": runtime_status,
            "proxy": {
                "proxy_id": proxy_id,
                "name": proxy.name if proxy else None,
                "host": proxy.ip if proxy else None,
                "port": proxy.port if proxy else None,
                "protocol": proxy.protocol if proxy else None,
                "exit_ip": proxy.exit_ip if proxy else None,
                "asn": proxy.asn if proxy else None,
                "isp": proxy.isp if proxy else None,
                "country": proxy.country if proxy else None,
                "region": proxy.region if proxy else None,
                "city": proxy.city if proxy else None,
                "latency_ms": proxy.latency_ms if proxy else None,
                "status": proxy.status if proxy else None,
                "last_check_at": proxy.last_check_at if proxy else None,
            },
            "identity": {
                "stable": bool(proxy_id),
                "relationship": "Account → Persona Profile → Sticky Proxy → Patchright → Platform Adapter",
            },
        }
        return {"status": "success", "result": env}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取账号环境失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{account_id}/runtime")
async def get_account_runtime(account_id: str):
    """查询账号 Browser Runtime 状态（锁 + 浏览器后端）。"""
    try:
        from fastapi_app.services.runtime_lock_service import get_runtime_lock_service
        lock_service = get_runtime_lock_service()
        lock_status = lock_service.status(account_id)
        binding = cookie_manager.get_account_binding(account_id) or {}
        active_local = account_id in _ACTIVE_SESSIONS
        return {
            "status": "success",
            "result": {
                "account_id": account_id,
                "locked": lock_status.get("locked", False),
                "operation": lock_status.get("operation"),
                "task_id": lock_status.get("task_id"),
                "worker_id": lock_status.get("worker_id"),
                "acquired_at": lock_status.get("acquired_at"),
                "expires_at": lock_status.get("expires_at"),
                "ttl_remaining": lock_status.get("ttl_remaining"),
                "browser_backend": binding.get("browser_backend") or "patchright",
                "active_local": active_local,
            },
        }
    except Exception as e:
        logger.error(f"查询账号 Runtime 状态失败 {account_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/proxy/bind")
async def bind_account_proxy(account_id: str, request: _BindProxyRequest):
    """固定绑定账号到代理（sticky，登录/发布/数据回收复用同一代理）。"""
    try:
        service = _proxy_service()
        success = service.bind_account_to_ip(request.proxy_id, account_id)
        return {"status": "success", "result": {"success": success, "message": "账号已固定绑定到代理"}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"绑定代理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/proxy/unbind")
async def unbind_account_proxy(account_id: str):
    """解除账号固定代理绑定。"""
    try:
        service = _proxy_service()
        success = service.unbind_account(account_id)
        return {"status": "success", "result": {"success": success, "message": "已解除代理绑定" if success else "账号无绑定"}}
    except Exception as e:
        logger.error(f"解绑代理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/proxy/rebind")
async def rebind_account_proxy(account_id: str, request: _RebindProxyRequest):
    """换绑：解绑原代理并绑定到新代理。"""
    try:
        service = _proxy_service()
        service.unbind_account(account_id)
        success = service.bind_account_to_ip(request.proxy_id, account_id)
        return {"status": "success", "result": {"success": success, "message": "账号已换绑到新代理"}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"换绑代理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/browser/start")
async def start_account_browser(account_id: str, request: _BrowserActionRequest):
    """
    启动账号浏览器环境（统一 BrowserBackend）。

    链路：AccountRuntimeLock → 读取绑定 → 选择 backend → 注入固定 Proxy → 启动。
    同一账号同时只允许一个活跃 Runtime；冲突返回 409 ACCOUNT_RUNTIME_BUSY。
    """
    from fastapi_app.services.runtime_lock_service import (
        get_runtime_lock_service, RuntimeLockConflict, RuntimeLockUnavailable,
        LockHeartbeat,
    )

    lock_service = get_runtime_lock_service()
    import uuid as _uuid
    task_id = f"api-start-{_uuid.uuid4().hex[:8]}"

    # 1. 获取锁（非阻塞；冲突 → 409）
    lock = None
    try:
        lock = lock_service.acquire_or_raise(
            account_id, operation="browser_start", task_id=task_id
        )
    except RuntimeLockConflict as e:
        return {
            "status": "error",
            "code": "ACCOUNT_RUNTIME_BUSY",
            "detail": str(e),
            "runtime": e.status,
        }
    except RuntimeLockUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))

    # 2. 启动浏览器（锁保持持有，heartbeat 续期）
    heartbeat = None
    try:
        binding = cookie_manager.get_account_binding(account_id) or {}
        proxy_id = binding.get("proxy_id")
        backend_name = binding.get("browser_backend") or "patchright"

        from fastapi_app.services.browser_backend import get_browser_backend
        from fastapi_app.services.ip_pool_service import get_ip_pool_service

        backend = get_browser_backend(backend_name)
        proxy_config = None
        proxy_meta = None
        if proxy_id:
            proxy_service = get_ip_pool_service()
            proxy_obj = proxy_service.get_ip(proxy_id)
            if proxy_obj:
                url = proxy_obj.to_proxy_url()
                if url:
                    proxy_config = {"server": url}
                proxy_meta = {
                    "proxy_id": proxy_id,
                    "name": proxy_obj.name,
                    "host": proxy_obj.ip,
                    "port": proxy_obj.port,
                    "exit_ip": proxy_obj.exit_ip,
                    "status": proxy_obj.status,
                }

        profile = {
            "persona_profile_id": binding.get("persona_profile_id") or account_id,
        }
        # Persona Proxy 需带 country 用于指纹 locale/timezone 对齐
        if proxy_config and proxy_obj and proxy_obj.country:
            proxy_config["country"] = proxy_obj.country
        session = await backend.start(
            account_id,
            profile=profile,
            proxy=proxy_config,
            headless=request.headless,
        )
        # 会话句柄 + 锁 + 心跳暂存（Runtime 保持存活期间持续持有锁）
        heartbeat = LockHeartbeat(lock_service, account_id, lock["token"])
        heartbeat.start()
        _ACTIVE_SESSIONS[account_id] = {
            "session": session,
            "lock": lock,
            "heartbeat": heartbeat,
        }
        return {
            "status": "success",
            "result": {
                "success": True,
                "backend": backend_name,
                "account_id": account_id,
                "proxy": proxy_meta,
                "persona_profile_id": binding.get("persona_profile_id"),
                "runtime": {
                    "locked": True,
                    "operation": lock["operation"],
                    "task_id": lock["task_id"],
                    "acquired_at": lock["acquired_at"],
                },
                "message": "浏览器环境已启动",
            },
        }
    except NotImplementedError as e:
        # 启动失败：释放锁
        if lock:
            lock_service.release(account_id, lock["token"])
        return {"status": "success", "result": {"success": False, "message": str(e)}}
    except Exception as e:
        if lock:
            lock_service.release(account_id, lock["token"])
        logger.error(f"启动账号浏览器失败 {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"启动浏览器失败: {e}")


@router.post("/{account_id}/browser/stop")
async def stop_account_browser(account_id: str, force: bool = False):
    """
    停止账号浏览器进程（Profile 数据永久保留，仅关闭进程）。

    默认只能停止当前调用方持有的 Runtime（token 校验）；
    force=true 为管理员强制停止（显式操作，不默认启用）。
    """
    from fastapi_app.services.runtime_lock_service import get_runtime_lock_service
    lock_service = get_runtime_lock_service()

    entry = _ACTIVE_SESSIONS.get(account_id)
    if entry is None:
        return {"status": "success", "result": {"success": True, "message": "无活动浏览器会话"}}
    session = entry["session"]
    lock = entry["lock"]
    heartbeat = entry.get("heartbeat")

    # token 校验：默认只允许持有者释放
    if not force:
        current = lock_service.status(account_id)
        if not current.get("locked"):
            pass  # 锁已过期，允许清理本地会话
        elif current.get("task_id") != lock.get("task_id") or current.get("worker_id") != lock.get("worker_id"):
            raise HTTPException(
                status_code=409,
                detail="Runtime 由其他调用方持有（task_id 不匹配）；如需强制停止请传 force=true",
            )

    try:
        # 停止心跳 → 关闭浏览器 → 释放锁（try/finally）
        try:
            if heartbeat:
                heartbeat.stop()
            from fastapi_app.services.browser_backend import get_browser_backend
            backend = get_browser_backend(session.backend)
            await backend.stop(session)
        finally:
            _ACTIVE_SESSIONS.pop(account_id, None)
            lock_service.release(account_id, lock["token"])
        return {"status": "success", "result": {"success": True, "message": "浏览器已关闭，Profile 已保留"}}
    except Exception as e:
        logger.error(f"停止账号浏览器失败 {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"停止浏览器失败: {e}")
