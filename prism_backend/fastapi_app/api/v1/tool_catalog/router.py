"""
声明式工具注册中心 API —— 每个登记的能力（tool_catalog.ToolSpec）自动暴露为：
- GET  /api/v1/tool-catalog              工具清单
- GET  /api/v1/tool-catalog/{name}       单工具详情（含 inputSchema）
- POST /api/v1/tool-catalog/{name}       调用工具（body 即 kwargs）
"""
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from fastapi_app.agent import tool_catalog
from fastapi_app.core.logger import logger


router = APIRouter(prefix="/tool-catalog", tags=["工具目录"])


def _public_spec(name: str) -> Dict[str, Any]:
    spec = tool_catalog.get(name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"未知工具: {name}")
    return {
        "name": spec.name,
        "description": spec.description,
        "category": spec.category,
        "parameters": spec.parameters,
        "output_summary": spec.output_summary,
    }


@router.get("")
async def list_tools() -> Dict[str, Any]:
    """列出注册中心里所有可调用的工具。"""
    try:
        items = [_public_spec(t.name) for t in tool_catalog.all_tools()]
        return {"status": "success", "result": {"tools": items, "total": len(items)}}
    except Exception as exc:
        logger.error(f"列出工具目录失败: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{name}")
async def tool_detail(name: str) -> Dict[str, Any]:
    """查询单个工具详情（含调用参数 schema）。"""
    return {"status": "success", "result": _public_spec(name)}


@router.post("/{name}")
async def call_tool(name: str, arguments: Dict[str, Any] = Body(default={}, embed=True)):
    """调用指定工具，body 为参数 kwargs。"""
    spec = tool_catalog.get(name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"未知工具: {name}")
    try:
        result = await tool_catalog.invoke(name, **(arguments or {}))
        if isinstance(result, dict) and result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return {"status": "success", "result": result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"调用工具 {name} 失败: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
