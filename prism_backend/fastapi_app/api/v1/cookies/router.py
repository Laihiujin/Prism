"""
Fast cookie validation routes (no browser).
"""
import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from myUtils.cookie_manager import cookie_manager
from myUtils.fast_cookie_validator import FastCookieValidator


router = APIRouter(prefix="/cookies", tags=["Cookie验证"])


class FastCookieVerifyRequest(BaseModel):
    platform: str = Field(..., description="平台名称 (douyin/xiaohongshu/bilibili/kuaishou/channels/tencent)")
    account_id: Optional[str] = Field(None, description="可选：账号ID，从账号库读取 cookie")
    account_file: Optional[str] = Field(None, description="可选：cookie 文件路径或文件名")
    cookie_data: Optional[Any] = Field(None, description="可选：直接传 cookie JSON 或字符串")
    timeout: float = Field(default=3.0, description="请求超时(秒)")
    include_raw: bool = Field(default=False, description="是否返回原始响应")
    fallback: bool = Field(default=False, description="是否在快速验证失败时启用 Playwright 备用")


class FastCookieVerifyItem(BaseModel):
    platform: str
    account_id: Optional[str] = None
    account_file: Optional[str] = None
    cookie_data: Optional[Any] = None


class FastCookieVerifyBatchRequest(BaseModel):
    items: List[FastCookieVerifyItem]
    timeout: float = Field(default=3.0, description="请求超时(秒)")
    include_raw: bool = Field(default=False, description="是否返回原始响应")
    fallback: bool = Field(default=False, description="是否在快速验证失败时启用 Playwright 备用")
    concurrency: int = Field(default=10, description="并发数")


def _resolve_cookie_payload(item: FastCookieVerifyItem) -> Dict[str, Any]:
    if item.cookie_data is not None:
        return {"cookie_data": item.cookie_data, "account_file": None}
    if item.account_file:
        return {"cookie_data": None, "account_file": item.account_file}
    if item.account_id:
        account = cookie_manager.get_account_by_id(item.account_id)
        if not account:
            raise HTTPException(status_code=404, detail=f"账号不存在: {item.account_id}")
        cookie_data = account.get("cookie")
        if cookie_data:
            return {"cookie_data": cookie_data, "account_file": None}
        cookie_file = account.get("cookie_file") or account.get("cookieFile")
        if not cookie_file:
            raise HTTPException(status_code=400, detail=f"账号缺少 cookie_file: {item.account_id}")
        return {"cookie_data": None, "account_file": cookie_file}
    raise HTTPException(status_code=400, detail="需要提供 account_id/account_file/cookie_data 之一")


@router.post("/fast-verify", summary="极速 Cookie 校验（官方 JSON 接口）")
async def fast_verify_cookie(payload: FastCookieVerifyRequest):
    validator = FastCookieValidator()
    resolved = _resolve_cookie_payload(
        FastCookieVerifyItem(
            platform=payload.platform,
            account_id=payload.account_id,
            account_file=payload.account_file,
            cookie_data=payload.cookie_data,
        )
    )
    result = await validator.validate_cookie_fast(
        payload.platform,
        account_file=resolved.get("account_file"),
        cookie_data=resolved.get("cookie_data"),
        timeout=payload.timeout,
        include_raw=payload.include_raw,
        fallback=payload.fallback,
    )
    is_valid = result.get("status") == "valid"
    if result.get("status") in ("error", "network_error"):
        return {"success": False, "data": result, "message": result.get("error", "Cookie验证失败")}
    return {
        "success": True,
        "data": {"is_valid": is_valid, **result},
        "message": "Cookie有效" if is_valid else "Cookie已失效",
    }


@router.post("/fast-verify/batch", summary="批量极速 Cookie 校验")
async def fast_verify_cookie_batch(payload: FastCookieVerifyBatchRequest):
    if not payload.items:
        return {"success": True, "data": [], "message": "空列表"}

    validator = FastCookieValidator()
    sem = asyncio.Semaphore(max(1, int(payload.concurrency or 10)))

    async def _run(item: FastCookieVerifyItem):
        async with sem:
            try:
                resolved = _resolve_cookie_payload(item)
            except HTTPException as exc:
                return {
                    "platform": item.platform,
                    "account_id": item.account_id,
                    "account_file": item.account_file,
                    "is_valid": False,
                    "status": "error",
                    "error": exc.detail,
                }
            result = await validator.validate_cookie_fast(
                item.platform,
                account_file=resolved.get("account_file"),
                cookie_data=resolved.get("cookie_data"),
                timeout=payload.timeout,
                include_raw=payload.include_raw,
                fallback=payload.fallback,
            )
            is_valid = result.get("status") == "valid"
            return {
                "platform": item.platform,
                "account_id": item.account_id,
                "account_file": item.account_file,
                "is_valid": is_valid,
                **result,
            }

    results = await asyncio.gather(*[_run(item) for item in payload.items], return_exceptions=False)
    return {"success": True, "data": results, "message": "OK"}
