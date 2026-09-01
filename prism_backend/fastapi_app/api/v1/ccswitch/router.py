"""cc-switch 桥接 API：读取本机 CC Switch 的 provider 档案并应用到项目内的 agent。

只读 cc-switch；应用目标仅限项目内配置（Hermes: hermes_agent.toml + hermes-home/config.yaml）。
app_type 支持 cc-switch 全部类型：claude / claude-desktop / codex / gemini /
grokbuild / opencode / openclaw / hermes / pi。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from ....agent.ccswitch_bridge import (
    APP_TYPES,
    apply_provider_to_hermes,
    ccswitch_available,
    fetch_provider_models,
    get_current_provider,
    get_provider,
    get_status,
    list_providers,
    test_provider,
)
from ....schemas.common import Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ccswitch", tags=["CC Switch 桥接"])


def _validate_app_type(app_type: str) -> str:
    at = (app_type or "").strip().lower()
    if at not in APP_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"app_type 必须是 {'/'.join(APP_TYPES)} 之一，收到：{app_type!r}",
        )
    return at


class ApplyRequest(BaseModel):
    app_type: str = Field(default="hermes", description=f"agent 类型：{'/'.join(APP_TYPES)}")
    provider_id: Optional[str] = Field(default=None, description="cc-switch provider id；缺省用当前选中")
    model: Optional[str] = Field(default=None, description="覆盖模型（缺省用 provider 第一个模型）")
    max_turns: int = Field(default=12, ge=1, le=90)


class ModelsRequest(BaseModel):
    app_type: str = Field(default="hermes", description=f"agent 类型：{'/'.join(APP_TYPES)}")
    provider_id: Optional[str] = Field(default=None, description="cc-switch provider id；缺省用当前选中")


class TestRequest(BaseModel):
    app_type: str = Field(default="hermes", description=f"agent 类型：{'/'.join(APP_TYPES)}")
    provider_id: Optional[str] = Field(default=None, description="cc-switch provider id；缺省用当前选中")
    model: Optional[str] = Field(default=None, description="要测试的模型（可选，缺省只测连接/鉴权）")


_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "api-key",
    "token",
    "secret",
    "auth_token",
    "auth",
    "openai_api_key",
    "anthropic_auth_token",
    "anthropic_api_key",
    "gemini_api_key",
    "google_api_key",
    "openrouter_api_key",
}


def _mask(provider: Dict[str, Any]) -> Dict[str, Any]:
    """API 返回时掩码 api_key（含 settings_config 嵌套 env/auth），避免明文回传。"""
    out = dict(provider)
    if out.get("api_key"):
        out["api_key"] = "***"
    settings = out.get("settings_config") or {}
    if isinstance(settings, dict):
        masked = _mask_settings(settings)
        out["settings_config"] = masked
    return out


def _mask_settings(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("***" if str(k).lower() in _SENSITIVE_KEYS and v not in (None, "") else _mask_settings(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_mask_settings(v) for v in obj]
    return obj


@router.get("/status", summary="cc-switch 桥接状态")
async def status():
    if not ccswitch_available():
        return Response(success=False, message="未检测到 cc-switch 数据库", data=get_status())
    return Response(success=True, message="cc-switch 可用", data=get_status())


@router.get("/providers", summary="列出 cc-switch provider 档案")
async def providers(app_type: Optional[str] = Query(default=None, description="按 app_type 过滤；缺省返回全部类型")):
    if not ccswitch_available():
        raise HTTPException(status_code=404, detail="未检测到 cc-switch 数据库（~/.cc-switch/cc-switch.db）")
    at = _validate_app_type(app_type) if app_type else None
    items = list_providers(at)
    return Response(
        success=True,
        data={"providers": [_mask(p) for p in items]},
        message=f"共 {len(items)} 个 provider",
    )


@router.get("/current", summary="cc-switch 当前选中的 provider")
async def current(app_type: str = Query(default="hermes")):
    if not ccswitch_available():
        raise HTTPException(status_code=404, detail="未检测到 cc-switch 数据库（~/.cc-switch/cc-switch.db）")
    at = _validate_app_type(app_type)
    item = get_current_provider(at)
    if not item:
        return Response(success=True, data=None, message=f"{at} 当前未选中 provider")
    return Response(success=True, data=_mask(item))


@router.post("/models", summary="抓取 provider 的全部可用模型（/v1/models）")
async def models(request: ModelsRequest):
    """调用该 provider 的 {base_url}/v1/models 抓取全部可用模型（只读，不改 cc-switch 数据）。"""
    app_type = _validate_app_type(request.app_type)
    try:
        result = await fetch_provider_models(
            app_type=app_type, provider_id=request.provider_id
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(
        success=True,
        message=f"从 {result['provider']['name']} 抓取到 {len(result['models'])} 个模型",
        data=result,
    )


@router.post("/test", summary="测试 provider/模型连接")
async def test(request: TestRequest):
    """先探 /v1/models 验证连接与鉴权；传了 model 再发最小对话验证模型可用。"""
    app_type = _validate_app_type(request.app_type)
    try:
        result = await test_provider(
            app_type=app_type,
            provider_id=request.provider_id,
            model=request.model,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(success=True, data=result)


@router.post("/apply", summary="把 cc-switch provider 应用到项目内的 agent")
async def apply(request: ApplyRequest):
    app_type = _validate_app_type(request.app_type)
    try:
        result = await apply_provider_to_hermes(
            app_type=app_type,
            provider_id=request.provider_id,
            model=request.model,
            max_turns=request.max_turns,
        )
        # 返回给前端时掩码 key
        result["provider"] = _mask(result["provider"])
        llm = result.get("llm") or {}
        if llm.get("api_key"):
            result["llm"] = {**llm, "api_key": "***"}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(success=True, message=result["message"], data=result)
