"""
开发者工具管理 API（插件/MCP 工具一键安装）。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, Dict
import asyncio

from fastapi_app.services.tool_registry import get_tool_registry
from fastapi_app.core.logger import logger


router = APIRouter(prefix="/tools", tags=["开发者工具"])


@router.get("")
async def list_tools():
    """列出可一键安装的开发工具及其状态。"""
    try:
        tools = get_tool_registry().list()
        return {"status": "success", "result": {"tools": tools, "total": len(tools)}}
    except Exception as e:
        logger.error(f"列出工具失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tool_id}/status")
async def tool_status(tool_id: str):
    """查询单个工具安装状态。"""
    status = get_tool_registry().status(tool_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"未知工具: {tool_id}")
    return {"status": "success", "result": status}


@router.post("/{tool_id}/install")
async def install_tool(tool_id: str):
    """一键安装指定工具（克隆 + 构建）。"""
    try:
        result = await asyncio.to_thread(
            get_tool_registry().install, tool_id
        )
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        logger.error(f"安装 {tool_id} 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"安装 {tool_id} 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tool_id}/uninstall")
async def uninstall_tool(tool_id: str):
    """卸载指定工具。"""
    try:
        result = await asyncio.to_thread(
            get_tool_registry().uninstall, tool_id
        )
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"卸载 {tool_id} 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
