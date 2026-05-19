"""Config endpoints for the project-local Hermes Agent runtime."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ....agent.hermes_agent import (
    get_hermes_runtime_status,
    reset_hermes_agent,
    run_hermes_goal,
    start_hermes_dashboard,
    start_hermes_interfaces,
    stop_hermes_dashboard,
)
from ....agent.hermes_config import (
    delete_agent_config,
    get_config_path,
    read_agent_config,
    write_agent_config,
)
from ....core.logger import logger
from ....schemas.common import Response


router = APIRouter(prefix="/config", tags=["Agent Config"])


class AgentLLMConfig(BaseModel):
    provider: str = Field(default="custom", min_length=1)
    api_key: str = ""
    base_url: Optional[str] = None
    model: str = Field(..., min_length=1)


class AgentRuntimeConfig(BaseModel):
    max_turns: int = Field(default=12, ge=1, le=90)


class AgentFullConfig(BaseModel):
    llm: AgentLLMConfig
    runtime: AgentRuntimeConfig = Field(default_factory=AgentRuntimeConfig)


class AgentConfigResponse(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_turns: int = 12
    is_configured: bool = False
    runtime: Dict[str, Any] = Field(default_factory=dict)


class DashboardStartRequest(BaseModel):
    port: Optional[int] = Field(default=None, ge=1024, le=65535)
    webui_port: Optional[int] = Field(default=None, ge=1024, le=65535)
    backend: Optional[str] = Field(default=None)


async def _build_response(config: Dict[str, Any]) -> AgentConfigResponse:
    llm = config.get("llm") or {}
    runtime = config.get("runtime") or {}
    return AgentConfigResponse(
        provider=llm.get("provider"),
        model=llm.get("model"),
        base_url=llm.get("base_url"),
        api_key=llm.get("api_key"),
        max_turns=int(runtime.get("max_turns") or 12),
        is_configured=bool(llm),
        runtime=await get_hermes_runtime_status(),
    )


@router.get("/hermes", response_model=Response[AgentConfigResponse])
async def get_agent_config():
    config = read_agent_config()
    if not config.get("llm"):
        return Response(
            success=True,
            data=AgentConfigResponse(
                is_configured=False,
                runtime=await get_hermes_runtime_status(),
            ),
        )
    return Response(success=True, data=await _build_response(config))


@router.post("/hermes", response_model=Response[Dict[str, Any]])
async def set_agent_config(config: AgentFullConfig):
    payload: Dict[str, Any] = {
        "llm": {
            "provider": config.llm.provider,
            "model": config.llm.model,
            "api_key": config.llm.api_key,
            "base_url": (config.llm.base_url or "").strip(),
        },
        "runtime": {
            "max_turns": config.runtime.max_turns,
        },
    }

    config_path = write_agent_config(payload)
    await reset_hermes_agent()
    logger.info(f"Saved Hermes Agent config: {config_path}")

    return Response(
        success=True,
        data={
            "message": "Hermes Agent 配置已保存。",
            "config_path": str(config_path),
            "runtime": await get_hermes_runtime_status(),
        },
    )


@router.delete("/hermes")
async def delete_config():
    deleted = delete_agent_config()
    await reset_hermes_agent()
    return Response(
        success=True,
        data={
            "message": "Hermes Agent 配置已删除。" if deleted else "Hermes Agent 配置不存在。",
            "config_path": str(get_config_path()),
            "runtime": await get_hermes_runtime_status(),
        },
    )


@router.post("/hermes/test")
async def test_agent_config():
    config = read_agent_config()
    if not config.get("llm"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hermes Agent 尚未配置。请先保存模型配置。",
        )

    await reset_hermes_agent()

    try:
        result = await run_hermes_goal("Reply with one short sentence confirming Hermes Agent is ready.")
    except Exception as exc:
        logger.error(f"Hermes Agent config test failed: {exc}")
        message = str(exc)
        if "below the minimum 64,000 required by Hermes Agent" in message:
            message = (
                "当前模型上下文窗口不足。Hermes 至少要求 64K 上下文；"
                "当前模型被识别为 4096 tokens。请切换到 64K+ 模型，"
                "或者再单独处理 Hermes 的 context_length 策略。"
            )
        return Response(
            success=False,
            data={
                "status": "error",
                "message": message,
                "runtime": await get_hermes_runtime_status(),
            },
        )

    if result.get("success"):
        return Response(
            success=True,
            data={
                "status": "success",
                "message": "Hermes Agent 连接正常。",
                "provider": config["llm"].get("provider"),
                "model": config["llm"].get("model"),
                "test_result": result.get("result", ""),
                "runtime": await get_hermes_runtime_status(),
            },
        )

    return Response(
        success=False,
        data={
            "status": "error",
            "message": result.get("error", "Unknown error"),
            "runtime": await get_hermes_runtime_status(),
        },
    )


@router.get("/openclaw", response_model=Response[AgentConfigResponse])
async def get_openclaw_config():
    return await get_agent_config()


@router.post("/openclaw", response_model=Response[Dict[str, Any]])
async def set_openclaw_config(config: AgentFullConfig):
    return await set_agent_config(config)


@router.delete("/openclaw")
async def delete_openclaw_config():
    return await delete_config()


@router.post("/openclaw/test")
async def test_openclaw_config():
    return await test_agent_config()


@router.get("/hermes/runtime")
async def get_hermes_runtime():
    return Response(success=True, data=await get_hermes_runtime_status())


@router.post("/hermes/dashboard/start")
async def start_dashboard(request: DashboardStartRequest):
    backend = str(request.backend or "").strip().lower() or None
    if backend in {"official", "webui"}:
        runtime = await start_hermes_dashboard(
            request.port,
            backend_override=backend,
        )
        label = "Hermes WebUI" if backend == "webui" else "Hermes Dashboard"
    else:
        runtime = await start_hermes_interfaces(
            dashboard_port=request.port,
            webui_port=request.webui_port,
        )
        label = "Hermes Dashboard and WebUI"
    return Response(
        success=True,
        data={
            "message": f"{label} 已启动。",
            "runtime": runtime,
        },
    )


@router.post("/hermes/dashboard/stop")
async def stop_dashboard():
    runtime = await stop_hermes_dashboard()
    return Response(
        success=True,
        data={
            "message": "Hermes 可视化界面已停止。",
            "runtime": runtime,
        },
    )
