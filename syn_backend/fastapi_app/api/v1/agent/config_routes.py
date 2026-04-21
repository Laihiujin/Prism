"""Config endpoints for the OpenClaw/Hermes agent runtime."""

from __future__ import annotations

from typing import Dict, Literal, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ....core.logger import logger
from ....schemas.common import Response
from ....agent.hermes_config import delete_agent_config, get_config_path, read_agent_config, write_agent_config
from ....agent.hermes_agent import reset_hermes_agent, run_hermes_goal


router = APIRouter(prefix="/config", tags=["Agent Config"])

PROVIDER_BASE_URLS = {
    "siliconflow": "https://api.siliconflow.cn/v1",
    "volcanoengine": "https://api.volcanoengine.com/v1",
    "tongyi": "https://dashscope.aliyuncs.com/api/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
}

PROVIDER_MODELS = {
    "siliconflow": {
        "name": "SiliconFlow",
        "models": [
            {"id": "Qwen/QwQ-32B", "name": "Qwen QwQ-32B"},
            {"id": "deepseek-ai/DeepSeek-V3", "name": "DeepSeek V3"},
            {"id": "Qwen/Qwen2.5-72B-Instruct", "name": "Qwen 2.5 72B"},
        ],
        "vision_models": [{"id": "Qwen/Qwen2-VL-72B-Instruct", "name": "Qwen2-VL 72B"}],
    },
    "volcanoengine": {
        "name": "Volcano Engine",
        "models": [
            {"id": "doubao-pro", "name": "Doubao Pro"},
            {"id": "doubao-lite", "name": "Doubao Lite"},
        ],
        "vision_models": [],
    },
    "tongyi": {
        "name": "Tongyi",
        "models": [
            {"id": "qwen-max", "name": "Qwen Max"},
            {"id": "qwen-plus", "name": "Qwen Plus"},
            {"id": "qwen-turbo", "name": "Qwen Turbo"},
        ],
        "vision_models": [{"id": "qwen-vl-max", "name": "Qwen VL Max"}],
    },
    "openai": {
        "name": "OpenAI",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o"},
            {"id": "gpt-4.1", "name": "GPT-4.1"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
        ],
        "vision_models": [{"id": "gpt-4o", "name": "GPT-4o"}],
    },
    "anthropic": {
        "name": "Anthropic",
        "models": [
            {"id": "claude-3-5-sonnet-latest", "name": "Claude 3.5 Sonnet"},
            {"id": "claude-3-7-sonnet-latest", "name": "Claude 3.7 Sonnet"},
            {"id": "claude-3-5-haiku-latest", "name": "Claude 3.5 Haiku"},
        ],
        "vision_models": [],
    },
}


class AgentLLMConfig(BaseModel):
    provider: Literal["siliconflow", "volcanoengine", "tongyi", "openai", "anthropic"]
    api_key: str = Field(..., min_length=10)
    base_url: Optional[str] = None
    model: str = Field(..., min_length=1)
    max_tokens: int = Field(16384, ge=1024, le=32768)
    temperature: float = Field(0.6, ge=0.0, le=2.0)


class AgentVisionConfig(BaseModel):
    model: str = Field(..., min_length=1)
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class AgentFullConfig(BaseModel):
    llm: AgentLLMConfig
    vision: Optional[AgentVisionConfig] = None


class AgentConfigResponse(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 16384
    temperature: float = 0.6
    vision_model: Optional[str] = None
    vision_base_url: Optional[str] = None
    is_configured: bool = False


def _build_response(config: Dict) -> AgentConfigResponse:
    llm = config.get("llm") or {}
    vision = llm.get("vision") or {}
    return AgentConfigResponse(
        provider=llm.get("provider"),
        model=llm.get("model"),
        base_url=llm.get("base_url"),
        max_tokens=llm.get("max_tokens", 16384),
        temperature=llm.get("temperature", 0.6),
        vision_model=vision.get("model"),
        vision_base_url=vision.get("base_url"),
        is_configured=bool(llm),
    )


@router.get("/providers")
async def get_supported_providers():
    return Response(
        success=True,
        data={
            "providers": {
                provider_id: {
                    "id": provider_id,
                    "name": provider["name"],
                    "base_url": PROVIDER_BASE_URLS.get(provider_id, ""),
                    "models": provider["models"],
                    "vision_models": provider["vision_models"],
                }
                for provider_id, provider in PROVIDER_MODELS.items()
            },
            "total": len(PROVIDER_MODELS),
        },
    )


@router.get("/openclaw", response_model=Response[AgentConfigResponse])
async def get_agent_config():
    config = read_agent_config()
    if not config.get("llm"):
        return Response(success=True, data=AgentConfigResponse(is_configured=False))
    return Response(success=True, data=_build_response(config))


@router.post("/openclaw", response_model=Response[Dict])
async def set_agent_config(config: AgentFullConfig):
    payload: Dict[str, Dict] = {
        "llm": {
            "provider": config.llm.provider,
            "model": config.llm.model,
            "api_key": config.llm.api_key,
            "base_url": config.llm.base_url or PROVIDER_BASE_URLS.get(config.llm.provider, ""),
            "max_tokens": config.llm.max_tokens,
            "temperature": config.llm.temperature,
        }
    }

    if config.vision:
        payload["llm"]["vision"] = {
            "model": config.vision.model,
            "base_url": config.vision.base_url or payload["llm"]["base_url"],
            "api_key": config.vision.api_key or config.llm.api_key,
        }

    config_path = write_agent_config(payload)
    await reset_hermes_agent()
    logger.info(f"Saved Hermes/OpenClaw config: {config_path}")

    return Response(
        success=True,
        data={
            "message": "Agent config saved.",
            "provider": config.llm.provider,
            "model": config.llm.model,
            "config_path": str(config_path),
        },
    )


@router.delete("/openclaw")
async def delete_config():
    deleted = delete_agent_config()
    await reset_hermes_agent()
    return Response(
        success=True,
        data={
            "message": "Agent config deleted." if deleted else "Agent config not found.",
            "config_path": str(get_config_path()),
        },
    )


@router.post("/openclaw/test")
async def test_agent_config():
    config = read_agent_config()
    if not config.get("llm"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent config not found. Save config first.",
        )

    await reset_hermes_agent()
    result = await run_hermes_goal("Reply with a short sentence confirming the agent is ready.")

    if result.get("success"):
        return Response(
            success=True,
            data={
                "status": "success",
                "message": "Agent config is valid.",
                "provider": config["llm"].get("provider"),
                "model": config["llm"].get("model"),
                "test_result": result.get("result", ""),
            },
        )

    logger.error(f"Agent config test failed: {result.get('error')}")
    return Response(
        success=False,
        data={
            "status": "error",
            "message": result.get("error", "Unknown error"),
        },
    )
