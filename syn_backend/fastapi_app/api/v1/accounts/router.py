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


router = APIRouter(tags=["账号管理"])

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

    - **platform**: 平台过滤（xiaohongshu/channels/douyin/kuaishou/bilibili）
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

        from playwright_worker.worker import _PLATFORM_PROFILE_URL
        url = _PLATFORM_PROFILE_URL.get(platform)
        if not url:
            if platform == "bilibili":
                url = "https://member.bilibili.com/platform/home"
            else:
                raise BadRequestException(f"不支持的平台: {platform}")

        return Response(success=True, data={
            "url": url,
            "platform": platform,
            "storage_state": storage_state
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

        from playwright_worker.client import get_worker_client
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

        from playwright_worker.client import get_worker_client
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

    from playwright_worker.client import get_worker_client
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
