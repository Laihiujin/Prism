"""
Prism 后端 HTTP 客户端 —— 供 tool_catalog / mcp_server 复用。

避免在多处重复「调用本机 FastAPI 后端」的代码：
- tool_catalog 登记的能力（`prism tool list` / `prism tool invoke`）
- MCP 服务（`prism mcp`，mcp_server.py）
- 未来任何需要调用后端 HTTP 的地方

所有函数返回统一信封 dict：
    {"ok": bool, "message": str, "data": ...}
失败时 ok=False，message 带错误说明。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from fastapi_app.core.runtime import get_backend_url

BACKEND_URL = get_backend_url()


def _short(value: Any, limit: int = 500) -> Any:
    """截断过长的字符串（如错误堆栈），避免返回体积过大。"""
    if not isinstance(value, str):
        return value
    if len(value) <= limit:
        return value
    return value[:limit] + "…(截断)"


def _ok(data: Any, message: str = "") -> Dict[str, Any]:
    return {"ok": True, "message": message, "data": data}


def _err(message: str) -> Dict[str, Any]:
    return {"ok": False, "message": message, "data": None}


async def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=60.0) as client:
        resp = await client.get(path, params=params or {})
        resp.raise_for_status()
        return resp.json()


async def _post(path: str, json_body: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=300.0) as client:
        resp = await client.post(path, json=json_body)
        resp.raise_for_status()
        return resp.json()


async def fetch_accounts(count: int = 100) -> Dict[str, Any]:
    """列出所有平台账号（id / 名称 / 平台 / 状态）。"""
    try:
        body = await _get("/api/v1/accounts/")
        items = body.get("items") or []
        slim = [
            {
                "id": a.get("id") or a.get("account_id") or a.get("accountId"),
                "name": a.get("name") or a.get("nickname") or a.get("original_name"),
                "platform": a.get("platform"),
                "platform_name": a.get("platform_name") or a.get("platformName"),
                "status": a.get("status"),
            }
            for a in items[:count]
        ]
        return _ok({"total": body.get("total", len(slim)), "accounts": slim})
    except Exception as exc:  # noqa: BLE001
        return _err(f"accounts 失败（后端需运行在 {BACKEND_URL}）: {exc}")


async def fetch_history(
    platform: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """查询发布历史（可筛选）。"""
    try:
        params: Dict[str, Any] = {"limit": limit}
        if platform is not None:
            params["platform"] = platform
        if status:
            params["status"] = status
        body = await _get("/api/v1/publish/history", params=params)
        data = body.get("data") or []
        for item in data:
            if isinstance(item, dict) and item.get("error_message"):
                item["error_message"] = _short(item["error_message"])
        return _ok({"total": len(data), "history": data}, body.get("message", ""))
    except Exception as exc:  # noqa: BLE001
        return _err(f"history 失败（后端需运行在 {BACKEND_URL}）: {exc}")


async def publish_batch(
    file_ids: List[int],
    accounts: List[str],
    title: str,
    platform: Optional[int] = None,
    description: Optional[str] = None,
    topics: Optional[List[str]] = None,
    scheduled_time: Optional[str] = None,
) -> Dict[str, Any]:
    """把素材批量发布到账号（Celery + 浏览器模式，不走 HTTP 逆向登录）。"""
    try:
        body: Dict[str, Any] = {
            "file_ids": file_ids,
            "accounts": accounts,
            "title": title,
            "platform": platform,
            "description": description or "",
            "topics": topics or [],
        }
        if scheduled_time:
            body["scheduled_time"] = scheduled_time
        result = await _post("/api/v1/publish/batch", body)
        data = result.get("data") or result
        return _ok({"publish": data}, result.get("message", ""))
    except Exception as exc:  # noqa: BLE001
        return _err(f"publish 失败（后端需运行在 {BACKEND_URL}）: {exc}")
