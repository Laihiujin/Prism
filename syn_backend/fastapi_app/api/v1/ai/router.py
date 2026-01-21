from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
import json
import os
import re
import yaml
from fastapi.responses import StreamingResponse
from fastapi_app.core.config import settings
from fastapi_app.db.runtime import mysql_enabled, sa_connection
from sqlalchemy import text

router = APIRouter(prefix="/ai", tags=["ai"])

# Global AI client reference
_ai_client = None


def _normalize_images_base_url(value: Optional[str]) -> Optional[str]:
    """
    Accept either:
    - https://api.siliconflow.cn/v1
    - https://api.siliconflow.cn/v1/images/generations

    and normalize to the base host root (without `/images/generations`) since we append it later.
    """
    if not value:
        return value
    s = str(value).strip().rstrip("/")
    if s.endswith("/images/generations"):
        s = s[: -len("/images/generations")].rstrip("/")
    return s


def set_ai_client(ai_client):
    """Set global AI client"""
    global _ai_client
    _ai_client = ai_client


def get_ai_client():
    """Get AI client or raise error"""
    if not _ai_client:
        raise HTTPException(status_code=400, detail="AI client not configured")
    return _ai_client


def _refresh_ai_model_manager() -> None:
    try:
        from ai_service.model_manager import get_model_manager

        get_model_manager().reload()
    except Exception:
        pass
    try:
        if _ai_client and hasattr(_ai_client, "model_manager"):
            _ai_client.model_manager.reload()
    except Exception:
        pass


def get_ai_config(service_type: str) -> Optional[Dict[str, Any]]:
    """从数据库读取AI配置；若未配置则从环境变量回退（仅 chat）。"""
    import json

    try:
        if mysql_enabled():
            with sa_connection() as conn:
                row = conn.execute(
                    text("SELECT * FROM ai_model_configs WHERE service_type = :t AND is_active = 1"),
                    {"t": service_type},
                ).mappings().first()
        else:
            import sqlite3
            conn = sqlite3.connect(settings.DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM ai_model_configs WHERE service_type = ? AND is_active = 1",
                (service_type,),
            )
            row = cursor.fetchone()
            conn.close()
            row = dict(row) if row else None

        if not row:
            if service_type == "chat":
                api_key = (settings.AI_API_KEY or settings.SILICONFLOW_API_KEY or "").strip()
                base_url = (settings.AI_BASE_URL or settings.SILICONFLOW_BASE_URL or "").strip() or "https://api.siliconflow.cn/v1"
                model_name = (settings.AI_MODEL or "").strip() or "deepseek-ai/DeepSeek-V3"
                if api_key:
                    return {
                        "service_type": "chat",
                        "provider": "openai_compatible",
                        "api_key": api_key,
                        "base_url": base_url,
                        "model_name": model_name,
                        "extra_config": {},
                        "is_active": 1,
                    }
            if service_type == "cover_generation":
                api_key = (settings.SILICONFLOW_API_KEY or settings.AI_API_KEY or "").strip()
                base_url = (settings.SILICONFLOW_BASE_URL or settings.AI_BASE_URL or "").strip() or "https://api.siliconflow.cn/v1"
                model_name = (settings.SILICONFLOW_IMAGE_MODEL or "").strip() or "Pro/jimeng-4.0/text2image"
                if api_key:
                    return {
                        "service_type": "cover_generation",
                        "provider": "siliconflow",
                        "api_key": api_key,
                        "base_url": base_url,
                        "model_name": model_name,
                        "extra_config": {},
                        "is_active": 1,
                    }
            return None

        config = dict(row)
        provider = (config.get("provider") or "").strip().lower()
        if provider in {"custom", "openai", "openai-compatible", "openai_compatible"}:
            config["provider"] = "openai_compatible"
        if config.get("extra_config"):
            try:
                config["extra_config"] = json.loads(config["extra_config"])
            except Exception:
                config["extra_config"] = {}
        return config
    except Exception as e:
        print(f"读取AI配置失败: {e}")
        return None


_PROMPTS_CACHE: Dict[str, Any] = {"mtime": None, "data": None}


def _load_ai_prompts_config() -> Dict[str, Any]:
    config_path = settings.BASE_DIR / "config" / "ai_prompts.yaml"
    if not config_path.exists():
        return {}
    try:
        mtime = config_path.stat().st_mtime
        cached = _PROMPTS_CACHE.get("data")
        if cached is not None and _PROMPTS_CACHE.get("mtime") == mtime:
            return cached
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _PROMPTS_CACHE["data"] = data
        _PROMPTS_CACHE["mtime"] = mtime
        return data
    except Exception as e:
        print(f"[AI Router] Failed to load prompts config: {e}")
        return {}


def _extract_user_text(messages: List[Dict[str, Any]], fallback: Optional[str]) -> str:
    if fallback:
        text = str(fallback).strip()
        if text:
            return text
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            if content:
                return str(content)
    return ""


def _safe_regex_search(pattern: str, text: str) -> bool:
    try:
        return re.search(pattern, text, re.I) is not None
    except re.error:
        return False


def _match_any_regex(patterns: List[str], text: str) -> bool:
    for pattern in patterns:
        if pattern and _safe_regex_search(pattern, text):
            return True
    return False


def _resolve_intent_hard_rules(user_text: str, routing_config: Dict[str, Any]) -> Optional[str]:
    hard_rules = routing_config.get("hard_rules") or {}
    intent_by_regex = hard_rules.get("intent_by_regex") or []
    anti_generate_regex = hard_rules.get("anti_generate_regex") or []

    generate_regexes = []
    for rule in intent_by_regex:
        intent = (rule.get("intent") or "").strip()
        regex = rule.get("regex")
        if intent.startswith("generate_") and regex:
            generate_regexes.append(regex)

    if _match_any_regex(anti_generate_regex, user_text) and not _match_any_regex(generate_regexes, user_text):
        return "chat"

    for rule in intent_by_regex:
        regex = rule.get("regex")
        if regex and _safe_regex_search(regex, user_text):
            intent = rule.get("intent")
            if intent:
                return intent
    return None


def _parse_intent_json(content: str) -> Optional[Dict[str, Any]]:
    if not content:
        return None
    try:
        return json.loads(content)
    except Exception:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start : end + 1])
            except Exception:
                return None
    return None


async def _resolve_intent_by_llm(
    client,
    model_name: str,
    routing_prompt: str,
    user_text: str,
    allowed_intents: set,
    default_intent: str,
) -> str:
    if not routing_prompt or not user_text:
        return default_intent
    response = await client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": routing_prompt},
            {"role": "user", "content": user_text},
        ],
        stream=False,
        temperature=0,
        max_tokens=200,
    )
    content = response.choices[0].message.content or ""
    data = _parse_intent_json(content)
    intent = (data or {}).get("intent")
    if intent in allowed_intents:
        return intent
    return default_intent


def _get_system_prompt_for_intent(config: Dict[str, Any], intent: str) -> str:
    key_map = {
        "chat": "chat_assistant",
        "generate_title": "title_generation",
        "generate_description": "description_generation",
        "generate_tags": "tags_generation",
        "generate_cover": "cover_generation",
        "troubleshoot": "chat_assistant",
        "plan": "chat_assistant",
    }
    section_key = key_map.get(intent, "chat_assistant")
    section = config.get(section_key, {}) if isinstance(config, dict) else {}
    return section.get("system_prompt", "")


def _apply_system_prompt(messages: List[Dict[str, Any]], system_prompt: str) -> List[Dict[str, Any]]:
    if not system_prompt:
        return messages
    cleaned = [msg for msg in messages if msg.get("role") != "system"]
    return [{"role": "system", "content": system_prompt}] + cleaned


class ChatRequest(BaseModel):
    messages: Optional[List[Dict[str, Any]]] = Field(default=None)
    model: Optional[str] = Field(default=None)
    stream: Optional[bool] = Field(default=True)
    # Legacy fields support
    message: Optional[str] = Field(default=None)
    context: Optional[List[Dict[str, Any]]] = Field(default=None)
    role: Optional[str] = Field(default="default")
    max_iterations: Optional[int] = Field(default=None)



class SwitchProviderRequest(BaseModel):
    provider: str


class SwitchModelRequest(BaseModel):
    model: str


class AddProviderRequest(BaseModel):
    provider: str
    api_key: str
    base_url: Optional[str] = None


class FetchModelsRequest(BaseModel):
    provider: str
    api_key: str
    base_url: Optional[str] = None
    type: Optional[str] = None
    sub_type: Optional[str] = None


class RemoveProviderRequest(BaseModel):
    provider: str


class GenerateCoverRequest(BaseModel):
    prompt: str
    aspect_ratio: Optional[str] = "3:4"
    model: Optional[str] = "jimeng-4.0"


@router.get("/status")
async def get_status(ai_client=Depends(get_ai_client)):
    """Get AI status"""
    current_status = ai_client.model_manager.get_status()
    
    # Check if any provider is configured
    current_provider_name = current_status.get("current_provider")
    is_connected = False
    connection_error = None
    
    if current_provider_name:
        provider = ai_client.model_manager.get_current_provider()
        if provider:
            # We report "connected" if a provider is configured, 
            # so the input box stays enabled and UI looks alive.
            is_connected = True
            
            # STILL try a quick connection test but don't let it block "online" status entirely
            try:
                # Set a very short timeout for test
                test_result = await asyncio.wait_for(provider.test_connection(), timeout=5.0)
                if test_result.get("status") != "success":
                    connection_error = test_result.get("error", "Unknown connection error")
                    # Optionally we could set is_connected = False here if we want strict mode,
                    # but we keep it True to satisfy the requirement of fixing "Offline" block.
            except asyncio.TimeoutError:
                connection_error = "Connection test timed out"
            except Exception as e:
                connection_error = str(e)
    
    return {
        "status": "success",
        "connected": is_connected,
        "current_status": current_status,
        "connection_error": connection_error,
        "statistics": ai_client.get_statistics(),
        "health": ai_client.get_health_status(),
    }


@router.get("/models")
async def get_models(ai_client=Depends(get_ai_client)):
    """Get available models"""
    providers = {}
    for provider_name, provider in ai_client.model_manager.get_all_providers().items():
        models = []
        for model in provider.models.values():
            models.append(model.to_dict())
        providers[provider_name] = {
            "name": provider.provider_name,
            "models": models
        }

    return {
        "status": "success",
        "providers": providers,
        "current_provider": ai_client.model_manager.current_provider,
        "current_model": ai_client.model_manager.current_model,
    }


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    纯聊天模式 - 使用配置的 chat 模型进行对话
    不支持工具调用，只是简单的AI对话
    """
    try:
        # 从数据库读取 chat 服务配置
        config = get_ai_config("chat")
        if not config:
            raise HTTPException(
                status_code=400,
                detail="Chat 服务未配置，请在 AI 模型配置页面添加 'chat' 类型的配置"
            )

        # 使用 OpenAI 兼容客户端
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=config['api_key'],
            base_url=config.get('base_url', 'https://api.siliconflow.cn/v1')
        )
        model_name = config.get('model_name', 'deepseek-ai/DeepSeek-V3')

        # 构建消息列表（优先使用 messages，其次使用 context + message）
        messages = []

        if request.messages:
            # 如果提供了 messages，使用它
            messages = request.messages
        else:
            # 否则使用 context + message 模式
            if request.context:
                messages.extend(request.context)
            if request.message:
                messages.append({"role": "user", "content": request.message})

        if not messages:
            raise HTTPException(status_code=400, detail="Message content is required")

        prompts_config = _load_ai_prompts_config()
        routing_config = prompts_config.get("routing", {}) if prompts_config else {}
        hard_rules = routing_config.get("hard_rules") or {}
        default_intent = hard_rules.get("default_intent", "chat")
        user_text = _extract_user_text(messages, request.message)

        intent = None
        if user_text:
            intent = _resolve_intent_hard_rules(user_text, routing_config)

        if not intent:
            intent_by_regex = hard_rules.get("intent_by_regex") or []
            allowed_intents = {rule.get("intent") for rule in intent_by_regex if rule.get("intent")}
            allowed_intents.add(default_intent)
            allowed_intents.add("chat")
            routing_prompt = routing_config.get("intent_router_prompt", "")
            intent = await _resolve_intent_by_llm(
                client,
                model_name,
                routing_prompt,
                user_text,
                allowed_intents,
                default_intent,
            )

        if not intent:
            intent = default_intent

        system_prompt = _get_system_prompt_for_intent(prompts_config, intent)
        messages = _apply_system_prompt(messages, system_prompt)

        # 调用模型
        if not request.stream:
            # 非流式响应
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=False
            )

            return {
                "status": "success",
                "content": response.choices[0].message.content,
                "role": "assistant"
            }
        else:
            # 流式响应
            async def generate():
                try:
                    stream = await client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        stream=True
                    )

                    async for chunk in stream:
                        if chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content

                except Exception as e:
                    yield f"[ERROR] {str(e)}"

            return StreamingResponse(generate(), media_type="text/plain")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat 失败: {str(e)}")


@router.post("/agent-chat")
async def agent_chat(request: ChatRequest):
    """
    Agent 模式 - 使用 Function Calling 模型
    支持工具调用和任务执行
    """
    try:
        from ai_service.function_calling_service import get_function_calling_service
        from ai_service.function_calling_tools import ALL_TOOLS

        # 获取 Function Calling 服务实例
        service = await get_function_calling_service()
        if not service:
            raise HTTPException(
                status_code=400,
                detail="Function Calling 服务未配置，请在 AI 模型配置中添加 'function_calling' 类型的配置"
            )

        # 注册工具
        service.register_tools(ALL_TOOLS)

        # 构建消息列表
        messages = request.messages if request.messages else []
        if request.message and not messages:
            messages = [{"role": "user", "content": request.message}]

        # 添加上下文
        if request.context:
            messages = request.context + messages

        if not messages:
            raise HTTPException(status_code=400, detail="Message content is required")

        # 执行 Function Calling
        result = await service.call(
            messages=messages,
            max_iterations=request.max_iterations or int(os.getenv("FUNCTION_CALLING_MAX_ITERATIONS", "8")),
            auto_execute=True
        )

        return {
            "status": "success",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 执行失败: {str(e)}")


@router.post("/switch-provider")
async def switch_provider(request: SwitchProviderRequest, ai_client=Depends(get_ai_client)):
    """Switch provider"""
    success = ai_client.model_manager.switch_provider(request.provider)
    if success:
        status = ai_client.model_manager.get_status()
        return {
            "status": "success",
            "message": f"Switched to {request.provider}",
            "current_status": status
        }
    else:
        raise HTTPException(status_code=400, detail=f"Provider {request.provider} not found")


@router.post("/switch-model")
async def switch_model(request: SwitchModelRequest, ai_client=Depends(get_ai_client)):
    """Switch model"""
    success = ai_client.model_manager.switch_model(request.model)
    if success:
        status = ai_client.model_manager.get_status()
        return {
            "status": "success",
            "message": f"Switched to model {request.model}",
            "current_status": status
        }
    else:
        raise HTTPException(status_code=400, detail=f"Model {request.model} not found")


@router.post("/add-provider")
async def add_provider(request: AddProviderRequest, ai_client=Depends(get_ai_client)):
    """Add provider"""
    success = ai_client.model_manager.add_provider(
        request.provider, 
        request.api_key,
        request.base_url
    )
    if success:
        status = ai_client.model_manager.get_status()
        return {
            "status": "success",
            "message": f"Added provider {request.provider}",
            "current_status": status
        }
    else:
        raise HTTPException(status_code=400, detail=f"Failed to add provider {request.provider}")


@router.post("/fetch-models")
async def fetch_models(request: FetchModelsRequest):
    """Fetch models from provider without saving config"""
    try:
        from ai_service.providers import OpenAICompatibleProvider, SiliconFlowProvider, VolcanoEngineProvider, TongyiProvider
        
        provider = None
        if request.provider == "openai_compatible":
            if not request.base_url:
                raise HTTPException(status_code=400, detail="Base URL is required for OpenAI Compatible provider")
            provider = OpenAICompatibleProvider(request.api_key, request.base_url)
        elif request.provider == "siliconflow":
            provider = SiliconFlowProvider(request.api_key)
        elif request.provider == "volcanoengine":
            provider = VolcanoEngineProvider(request.api_key)
        elif request.provider == "tongyi":
            provider = TongyiProvider(request.api_key)
            
        if not provider:
            raise HTTPException(status_code=400, detail=f"Unknown provider {request.provider}")
            
        result = await provider.test_connection()
        
        if result.get("status") == "success":
            # 如果是 openai_compatible，我们显式调用 get_available_models 以支持筛选
            if request.provider == "openai_compatible":
                models = await provider.get_available_models(type=request.type, sub_type=request.sub_type)
                result["models"] = [m.to_dict() for m in models]
            elif "models" not in result:
                 models = await provider.get_available_models()
                 result["models"] = [m.to_dict() for m in models]
            return result
        else:
             raise HTTPException(status_code=400, detail=result.get("error", "Connection failed"))
             
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/remove-provider")
async def remove_provider(request: RemoveProviderRequest, ai_client=Depends(get_ai_client)):
    """Remove provider"""
    success = ai_client.model_manager.remove_provider(request.provider)
    if success:
        status = ai_client.model_manager.get_status()
        return {
            "status": "success",
            "message": f"Removed provider {request.provider}",
            "current_status": status
        }
    else:
        raise HTTPException(status_code=400, detail=f"Provider {request.provider} not found")


@router.post("/health-check")
async def health_check(ai_client=Depends(get_ai_client)):
    """Execute health check"""
    results = await ai_client.health_check()
    return {
        "status": "success",
        "health_check_results": results
    }


@router.get("/statistics")
async def get_statistics(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    hours: int = Query(24),
    ai_client=Depends(get_ai_client)
):
    """Get statistics"""
    stats = ai_client.logger.get_statistics(
        provider=provider,
        model_id=model,
        hours=hours
    )

    return {
        "status": "success",
        "statistics": stats
    }


@router.get("/recent-calls")
async def get_recent_calls(
    limit: int = Query(20),
    ai_client=Depends(get_ai_client)
):
    """Get recent call records"""
    calls = ai_client.logger.get_recent_calls(limit=limit)

    return {
        "status": "success",
        "recent_calls": calls
    }


# ============================================
# 脚本管理功能
# ============================================

class ScriptRunRequest(BaseModel):
    """脚本执行请求"""
    name: str
    args: Optional[List[str]] = []


@router.get("/scripts/list", summary="列出可用脚本")
async def list_scripts():
    """
    列出 syn_backend/scripts/ 目录下的所有 Python 脚本
    """
    try:
        from pathlib import Path
        from fastapi_app.core.config import settings
        
        scripts_dir = settings.BASE_DIR / "scripts"
        scripts = []
        
        if scripts_dir.exists():
            for script_file in scripts_dir.rglob("*.py"):
                # 跳过 __init__.py 和私有文件
                if script_file.name.startswith("_"):
                    continue
                
                # 读取脚本的 docstring 作为描述
                description = ""
                try:
                    with open(script_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 简单提取第一行注释或 docstring
                        lines = content.split('\n')
                        for line in lines[:10]:
                            if line.strip().startswith('"""') or line.strip().startswith("'''"):
                                description = line.strip().strip('"""').strip("'''")
                                break
                            elif line.strip().startswith('#'):
                                description = line.strip('#').strip()
                                break
                except Exception:
                    pass
                
                scripts.append({
                    "name": script_file.name,
                    "path": str(script_file.relative_to(settings.BASE_DIR)),
                    "description": description or "无描述",
                    "category": script_file.parent.name
                })
        
        return {
            "status": "success",
            "scripts": scripts,
            "total": len(scripts)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"列出脚本失败: {str(e)}")


@router.post("/scripts/run", summary="运行脚本")
async def run_script(request: ScriptRunRequest):
    """
    运行指定的 Python 脚本
    
    **安全提示**: 此接口会执行任意脚本，生产环境应添加权限控制
    """
    try:
        import subprocess
        import time
        from pathlib import Path
        from fastapi_app.core.config import settings
        
        # 查找脚本文件
        scripts_dir = settings.BASE_DIR / "scripts"
        script_path = None
        
        for script_file in scripts_dir.rglob(request.name):
            if script_file.is_file():
                script_path = script_file
                break
        
        if not script_path:
            raise HTTPException(
                status_code=404,
                detail=f"脚本 '{request.name}' 不存在"
            )
        
        # 执行脚本
        start_time = time.time()
        
        result = subprocess.run(
            ["python", str(script_path)] + request.args,
            capture_output=True,
            text=True,
            timeout=300,  # 5分钟超时
            cwd=str(settings.BASE_DIR)
        )
        
        duration = time.time() - start_time
        
        return {
            "status": "success",
            "result": {
                "script": request.name,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration": round(duration, 2),
                "args": request.args
            }
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="脚本执行超时（5分钟）")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"脚本执行失败: {str(e)}")


@router.get("/scripts/info/{script_name}", summary="获取脚本信息")
async def get_script_info(script_name: str):
    """
    获取指定脚本的详细信息
    """
    try:
        from pathlib import Path
        from fastapi_app.core.config import settings
        
        scripts_dir = settings.BASE_DIR / "scripts"
        script_path = None
        
        for script_file in scripts_dir.rglob(script_name):
            if script_file.is_file():
                script_path = script_file
                break
        
        if not script_path:
            raise HTTPException(status_code=404, detail=f"脚本 '{script_name}' 不存在")
        
        # 读取脚本内容
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取 docstring
        docstring = ""
        if '"""' in content:
            start = content.find('"""') + 3
            end = content.find('"""', start)
            if end > start:
                docstring = content[start:end].strip()
        
        # 获取文件信息
        stat = script_path.stat()
        
        return {
            "status": "success",
            "script": {
                "name": script_name,
                "path": str(script_path.relative_to(settings.BASE_DIR)),
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "description": docstring or "无描述",
                "category": script_path.parent.name,
                "lines": len(content.split('\n'))
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取脚本信息失败: {str(e)}")


@router.post("/generate-cover", summary="生成视频封面")
async def generate_cover(request: GenerateCoverRequest):
    """
    使用 AI 绘图模型生成视频封面

    支持的提供商:
    - volcengine: 火山引擎（即梦 4.0）
    - siliconflow: 硅基流动
    - tongyi: 通义千问 (Qwen/Qwen-Image-Edit-2509等)
    - openai_compatible: OpenAI兼容接口

    支持的比例:
    - 3:4 (默认，适合短视频)
    - 16:9 (横屏)
    - 1:1 (方形)
    """
    try:
        import httpx
        
        # 从数据库读取配置
        config = get_ai_config("cover_generation")
        
        if not config:
            raise HTTPException(
                status_code=500, 
                detail="未配置封面生成服务，请在 AI 模型配置页面进行配置"
            )
        
        provider = config['provider']
        api_key = config['api_key']
        base_url = _normalize_images_base_url(config.get('base_url'))
        model_name = config.get('model_name')
        extra_config = config.get('extra_config', {})
        
        # 根据提供商调用不同的 API
        async with httpx.AsyncClient() as client:
            if provider == "volcengine":
                # 火山引擎即梦 4.0
                api_url = base_url or "https://ark.cn-beijing.volces.com/api/v3"
                model = model_name or "doubao-seedream-4-0-250828"
                
                # 火山引擎的尺寸映射
                size_map = {
                    "3:4": "768:1024",
                    "16:9": "1024:576", 
                    "1:1": "1024:1024"
                }
                size = size_map.get(request.aspect_ratio, "768:1024")
                
                # 构建请求体
                payload = {
                    "model": model,
                    "prompt": request.prompt,
                    "size": extra_config.get("size", "2K"),
                    "aspect_ratio": size,
                    "response_format": "url",
                    "watermark": extra_config.get("watermark", True)
                }
                
                response = await client.post(
                    f"{api_url}/images/generations",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=120.0
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code, 
                        detail=f"火山引擎 API 错误: {response.text}"
                    )
                
                data = response.json()
                
                # 火山引擎返回格式
                if "data" in data and len(data["data"]) > 0:
                    image_url = data["data"][0].get("url")
                    return {
                        "status": "success",
                        "image_url": image_url,
                        "prompt": request.prompt,
                        "aspect_ratio": request.aspect_ratio,
                        "model": model,
                        "provider": "volcengine"
                    }
                else:
                    raise HTTPException(status_code=500, detail="火山引擎未返回图片 URL")
                    
            elif provider == "siliconflow":
                # 硅基流动
                api_url = base_url or "https://api.siliconflow.cn/v1"
                model = model_name or "Pro/jimeng-4.0/text2image"
                
                # 硅基流动的尺寸映射
                size_map = {
                    "3:4": "1140x1472",
                    "4:3": "1472x1140",
                }
                image_size = size_map.get(request.aspect_ratio, "1140x1472")
                
                payload = {
                    "model": model,
                    "prompt": request.prompt,
                    "image_size": image_size,
                    "batch_size": 1,
                    "num_inference_steps": extra_config.get("num_inference_steps", 20),
                    "guidance_scale": extra_config.get("guidance_scale", 7.5),
                    "cfg": extra_config.get("cfg", 10.05),
                    "seed": extra_config.get("seed", 499999999),
                }
                
                response = await client.post(
                    f"{api_url}/images/generations",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=60.0
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"硅基流动 API 错误: {response.text}"
                    )
                
                data = response.json()
                
                # 硅基流动返回格式
                if "images" in data and len(data["images"]) > 0:
                    image_url = data["images"][0].get("url")
                    return {
                        "status": "success",
                        "image_url": image_url,
                        "prompt": request.prompt,
                        "aspect_ratio": request.aspect_ratio,
                        "model": model,
                        "provider": "siliconflow"
                    }
                else:
                    raise HTTPException(status_code=500, detail="硅基流动未返回图片 URL")

            elif provider == "tongyi" or provider == "dashscope":
                # 通义千问 / 阿里云灵积
                api_url = base_url or "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
                model = model_name or "wanx-v1"

                # 通义千问的尺寸映射
                size_map = {
                    "3:4": "768*1024",
                    "16:9": "1024*576",
                    "1:1": "1024*1024"
                }
                size = size_map.get(request.aspect_ratio, "768*1024")

                # 构建请求体
                payload = {
                    "model": model,
                    "input": {
                        "prompt": request.prompt
                    },
                    "parameters": {
                        "size": size,
                        "n": 1,
                        "seed": extra_config.get("seed"),
                        "ref_strength": extra_config.get("ref_strength", 0.5)
                    }
                }

                response = await client.post(
                    api_url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "X-DashScope-Async": "enable"  # 启用异步模式
                    },
                    json=payload,
                    timeout=120.0
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"通义千问 API 错误: {response.text}"
                    )

                data = response.json()

                # 通义千问返回格式 - 同步模式
                if data.get("output") and data["output"].get("results"):
                    results = data["output"]["results"]
                    if len(results) > 0:
                        image_url = results[0].get("url")
                        return {
                            "status": "success",
                            "image_url": image_url,
                            "prompt": request.prompt,
                            "aspect_ratio": request.aspect_ratio,
                            "model": model,
                            "provider": "tongyi"
                        }
                # 异步模式 - 返回任务ID
                elif data.get("output") and data["output"].get("task_id"):
                    task_id = data["output"]["task_id"]
                    # 轮询查询任务状态
                    max_retries = 30  # 最多等待60秒
                    for i in range(max_retries):
                        await asyncio.sleep(2)  # 每2秒查询一次

                        status_response = await client.get(
                            f"{api_url.replace('/image-synthesis', '')}/tasks/{task_id}",
                            headers={
                                "Authorization": f"Bearer {api_key}"
                            }
                        )

                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            task_status = status_data.get("output", {}).get("task_status")

                            if task_status == "SUCCEEDED":
                                results = status_data["output"].get("results", [])
                                if len(results) > 0:
                                    image_url = results[0].get("url")
                                    return {
                                        "status": "success",
                                        "image_url": image_url,
                                        "prompt": request.prompt,
                                        "aspect_ratio": request.aspect_ratio,
                                        "model": model,
                                        "provider": "tongyi"
                                    }
                            elif task_status == "FAILED":
                                error_msg = status_data.get("output", {}).get("message", "生成失败")
                                raise HTTPException(status_code=500, detail=f"通义千问生成失败: {error_msg}")

                    raise HTTPException(status_code=504, detail="通义千问生成超时，请稍后重试")
                else:
                    raise HTTPException(status_code=500, detail="通义千问未返回有效结果")

            elif provider == "openai_compatible":
                # OpenAI 兼容接口 (可用于硅基流动、Ollama等)
                if not base_url:
                    raise HTTPException(status_code=400, detail="OpenAI兼容接口需要配置 base_url")

                model = model_name or "dall-e-3"

                # OpenAI的尺寸映射
                size_map = {
                    "3:4": "1024x1792",  # 竖屏
                    "16:9": "1792x1024",  # 横屏
                    "1:1": "1024x1024"   # 方形
                }
                size = size_map.get(request.aspect_ratio, "1024x1792")

                payload = {
                    "model": model,
                    "prompt": request.prompt,
                    "size": size,
                    "n": 1,
                    "quality": extra_config.get("quality", "standard"),
                    "response_format": "url"
                }

                response = await client.post(
                    f"{base_url}/images/generations",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=120.0
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"OpenAI兼容接口错误: {response.text}"
                    )

                data = response.json()

                # OpenAI 返回格式
                if "data" in data and len(data["data"]) > 0:
                    image_url = data["data"][0].get("url")
                    return {
                        "status": "success",
                        "image_url": image_url,
                        "prompt": request.prompt,
                        "aspect_ratio": request.aspect_ratio,
                        "model": model,
                        "provider": "openai_compatible"
                    }
                else:
                    raise HTTPException(status_code=500, detail="接口未返回图片 URL")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的提供商: {provider}"
                )
                
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"网络请求失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"封面生成失败: {str(e)}")


# ==================== AI模型配置管理 ====================

class AIModelConfigRequest(BaseModel):
    service_type: str  # 'chat', 'cover_generation', 'function_calling'
    provider: str
    api_key: str
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    extra_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = True


@router.get("/model-configs", summary="获取所有AI模型配置")
async def get_model_configs():
    """获取所有AI模型配置"""
    import json
    
    try:
        if mysql_enabled():
            with sa_connection() as conn:
                rows = conn.execute(text("SELECT * FROM ai_model_configs ORDER BY service_type")).mappings().all()
        else:
            import sqlite3
            conn = sqlite3.connect(settings.DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_model_configs ORDER BY service_type")
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()

        configs = []
        for row in rows:
            config = dict(row)
            if config.get("extra_config"):
                try:
                    config["extra_config"] = json.loads(config["extra_config"])
                except Exception:
                    config["extra_config"] = {}
            configs.append(config)
        
        return {
            "status": "success",
            "data": configs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.get("/model-configs/{service_type}", summary="获取特定服务的AI模型配置")
async def get_model_config(service_type: str):
    """获取特定服务的AI模型配置"""
    import json
    
    try:
        if mysql_enabled():
            with sa_connection() as conn:
                row = conn.execute(
                    text("SELECT * FROM ai_model_configs WHERE service_type = :t"),
                    {"t": service_type},
                ).mappings().first()
                row = dict(row) if row else None
        else:
            import sqlite3
            conn = sqlite3.connect(settings.DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_model_configs WHERE service_type = ?", (service_type,))
            row = cursor.fetchone()
            conn.close()
            row = dict(row) if row else None
        
        if not row:
            return {
                "status": "success",
                "data": None
            }
        
        config = dict(row)
        if config.get('extra_config'):
            try:
                config['extra_config'] = json.loads(config['extra_config'])
            except:
                config['extra_config'] = {}
        
        return {
            "status": "success",
            "data": config
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.post("/model-configs", summary="创建或更新AI模型配置")
async def upsert_model_config(request: AIModelConfigRequest):
    """创建或更新AI模型配置"""
    import json
    
    try:
        extra_config_json = json.dumps(request.extra_config) if request.extra_config else None

        if mysql_enabled():
            with sa_connection() as conn:
                existing = conn.execute(
                    text("SELECT id FROM ai_model_configs WHERE service_type = :t"),
                    {"t": request.service_type},
                ).mappings().first()
                if existing:
                    conn.execute(
                        text(
                            """
                            UPDATE ai_model_configs
                            SET provider=:provider, api_key=:api_key, base_url=:base_url, model_name=:model_name,
                                extra_config=:extra_config, is_active=:is_active, updated_at=CURRENT_TIMESTAMP
                            WHERE service_type=:service_type
                            """
                        ),
                        {
                            "provider": request.provider,
                            "api_key": request.api_key,
                            "base_url": request.base_url,
                            "model_name": request.model_name,
                            "extra_config": extra_config_json,
                            "is_active": 1 if request.is_active else 0,
                            "service_type": request.service_type,
                        },
                    )
                else:
                    conn.execute(
                        text(
                            """
                            INSERT INTO ai_model_configs
                            (service_type, provider, api_key, base_url, model_name, extra_config, is_active)
                            VALUES (:service_type, :provider, :api_key, :base_url, :model_name, :extra_config, :is_active)
                            """
                        ),
                        {
                            "service_type": request.service_type,
                            "provider": request.provider,
                            "api_key": request.api_key,
                            "base_url": request.base_url,
                            "model_name": request.model_name,
                            "extra_config": extra_config_json,
                            "is_active": 1 if request.is_active else 0,
                        },
                    )
        else:
            import sqlite3
            conn = sqlite3.connect(settings.DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM ai_model_configs WHERE service_type = ?", (request.service_type,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    """
                    UPDATE ai_model_configs
                    SET provider = ?, api_key = ?, base_url = ?, model_name = ?,
                        extra_config = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE service_type = ?
                    """,
                    (
                        request.provider,
                        request.api_key,
                        request.base_url,
                        request.model_name,
                        extra_config_json,
                        1 if request.is_active else 0,
                        request.service_type,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO ai_model_configs
                    (service_type, provider, api_key, base_url, model_name, extra_config, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request.service_type,
                        request.provider,
                        request.api_key,
                        request.base_url,
                        request.model_name,
                        extra_config_json,
                        1 if request.is_active else 0,
                    ),
                )
            conn.commit()
            conn.close()
        
        _refresh_ai_model_manager()
        return {
            "status": "success",
            "message": f"配置已{'更新' if existing else '创建'}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存配置失败: {str(e)}")


@router.delete("/model-configs/{service_type}", summary="删除AI模型配置")
async def delete_model_config(service_type: str):
    """删除AI模型配置"""
    try:
        if mysql_enabled():
            with sa_connection() as conn:
                res = conn.execute(
                    text("DELETE FROM ai_model_configs WHERE service_type = :t"),
                    {"t": service_type},
                )
                affected = getattr(res, "rowcount", 0) or 0
        else:
            import sqlite3
            conn = sqlite3.connect(settings.DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ai_model_configs WHERE service_type = ?", (service_type,))
            conn.commit()
            affected = cursor.rowcount
            conn.close()

        if affected == 0:
            raise HTTPException(status_code=404, detail="配置不存在")

        _refresh_ai_model_manager()
        return {
            "status": "success",
            "message": "配置已删除"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除配置失败: {str(e)}")


class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    service_type: str
    provider: str
    api_key: str
    base_url: Optional[str] = None
    model_name: Optional[str] = None


@router.post("/test-connection", summary="测试AI模型连接")
async def test_model_connection(request: TestConnectionRequest):
    """
    测试 AI 模型配置是否可以正常连接

    支持的 service_type:
    - chat: 对话模型测试
    - function_calling: Function Calling 模型测试（OpenManus Agent）
    - cover_generation: 图像生成模型测试
    - tikhub: TikHub API 鉴权测试
    """
    import httpx

    try:
        # 根据不同的服务类型进行测试
        if request.service_type in ["chat", "function_calling"]:
            # 对话模型和 Function Calling 模型都使用聊天完成接口测试
            if not request.base_url:
                raise HTTPException(
                    status_code=400,
                    detail="base_url 是必需的参数，请提供 API 端点地址"
                )

            if not request.model_name:
                raise HTTPException(
                    status_code=400,
                    detail="model_name 是必需的参数，请提供模型名称"
                )

            base_url = request.base_url.rstrip('/')

            # 构建测试请求
            test_payload = {
                "model": request.model_name,
                "messages": [
                    {"role": "user", "content": "你好，这是一个连接测试。请回复：测试成功"}
                ],
                "max_tokens": 50,
                "temperature": 0.7
            }

            # 如果是 function_calling 类型，添加工具定义测试
            if request.service_type == "function_calling":
                test_payload["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_current_time",
                            "description": "获取当前时间",
                            "parameters": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        }
                    }
                ]
                test_payload["tool_choice"] = "auto"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {request.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=test_payload
                )

                if response.status_code == 200:
                    response_data = response.json()

                    # 提取AI回复
                    ai_response = ""
                    supports_function_calling = False

                    if "choices" in response_data and len(response_data["choices"]) > 0:
                        message = response_data["choices"][0].get("message", {})
                        ai_response = message.get("content", "")

                        # 检查是否支持 Function Calling
                        if request.service_type == "function_calling":
                            supports_function_calling = "tool_calls" in message or "function_call" in message or message.get("tool_calls") is not None

                    result = {
                        "status": "success",
                        "connected": True,
                        "model_name": request.model_name,
                        "response_preview": ai_response[:100] if ai_response else "模型已成功响应"
                    }

                    if request.service_type == "function_calling":
                        result["message"] = f"✅ Function Calling 模型测试成功！模型: {request.model_name}"
                        result["supports_function_calling"] = supports_function_calling
                        if supports_function_calling:
                            result["message"] += " （支持工具调用）"
                        else:
                            result["message"] += " （警告：模型可能不支持Function Calling）"
                    else:
                        result["message"] = f"✅ 聊天模型测试成功！模型: {request.model_name}"

                    return result
                else:
                    error_text = response.text
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"模型测试失败: {error_text[:200]}"
                    )

        elif request.service_type == "cover_generation":
            # 图像生成模型测试
            if not request.base_url:
                raise HTTPException(
                    status_code=400,
                    detail="base_url 是必需的参数，请提供 API 端点地址"
                )

            if not request.model_name:
                raise HTTPException(
                    status_code=400,
                    detail="model_name 是必需的参数，请提供模型名称"
                )

            async with httpx.AsyncClient(timeout=60.0) as client:
                base_url = _normalize_images_base_url(request.base_url) or ""
                base_url = base_url.rstrip('/')
                request_model = (request.model_name or "").strip()
                model_lower = request_model.lower()
                tiny_png_data_url = (
                    "data:image/png;base64,"
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/6X7nGQAAAAASUVORK5CYII="
                )

                # 构建测试请求
                # 硅基流动API
                if "siliconflow" in base_url.lower():
                    test_payload = {
                        "model": request_model,
                        "prompt": "测试图片：一朵小花",
                        "image_size": "1140x1472",
                        "batch_size": 1,
                        "seed": 499999999,
                        "num_inference_steps": 20,
                        "guidance_scale": 7.5,
                        "cfg": 10.05,
                    }
                    # Qwen-Image-Edit 等图生图模型需要提供 image，否则可能返回“模型不存在/参数错误”
                    if "image-edit" in model_lower or "image_edit" in model_lower:
                        test_payload["image"] = tiny_png_data_url
                # 火山引擎 API
                elif "volces.com" in base_url or "volcengine" in base_url.lower():
                    test_payload = {
                        "model": request_model,
                        "prompt": "测试图片：一朵小花",
                        "size": "512x512"
                    }
                # OpenAI 兼容接口
                else:
                    test_payload = {
                        "model": request_model,
                        "prompt": "测试图片：一朵小花",
                        "size": "512x512",
                        "n": 1
                    }

                response = await client.post(
                    f"{base_url}/images/generations",
                    headers={
                        "Authorization": f"Bearer {request.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=test_payload
                )

                if response.status_code == 200:
                    response_data = response.json()

                    # 检查返回的图片URL
                    image_url = None
                    if "images" in response_data and len(response_data["images"]) > 0:
                        # 硅基流动格式
                        image_url = response_data["images"][0].get("url")
                    elif "data" in response_data and len(response_data["data"]) > 0:
                        # OpenAI格式
                        image_url = response_data["data"][0].get("url") or response_data["data"][0].get("b64_json")

                    return {
                        "status": "success",
                        "message": f"✅ 图片生成模型测试成功！模型: {request.model_name}",
                        "connected": True,
                        "model_name": request.model_name,
                        "image_generated": bool(image_url),
                        "note": "已成功生成测试图片（URL有效期1小时，请及时下载）"
                    }
                else:
                    error_text = response.text
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"图片生成模型测试失败: {error_text[:200]}"
                    )

        elif request.service_type == "speech_recognition":
            # 语音识别服务测试 - 验证API端点可访问性
            if not request.base_url:
                raise HTTPException(
                    status_code=400,
                    detail="base_url 是必需的参数，请提供 API 端点地址"
                )

            if not request.model_name:
                raise HTTPException(
                    status_code=400,
                    detail="model_name 是必需的参数，请提供模型名称"
                )

            # 尝试访问models端点验证认证
            async with httpx.AsyncClient(timeout=30.0) as client:
                base_url = request.base_url.rstrip('/')

                try:
                    # 硅基流动：验证可用模型
                    if "siliconflow" in base_url.lower():
                        # 硅基流动支持的语音识别模型：
                        # - FunAudioLLM/SenseVoiceSmall
                        # - TeleAI/TeleSpeechASR
                        valid_models = [
                            "FunAudioLLM/SenseVoiceSmall",
                            "TeleAI/TeleSpeechASR"
                        ]

                        if request.model_name not in valid_models:
                            return {
                                "status": "success",
                                "message": f"⚠️ 语音识别配置已保存，但模型名称可能不正确",
                                "connected": True,
                                "model_name": request.model_name,
                                "note": f"硅基流动支持的模型：{', '.join(valid_models)}"
                            }
                        else:
                            return {
                                "status": "success",
                                "message": f"✅ 语音识别服务配置有效！模型: {request.model_name}",
                                "connected": True,
                                "model_name": request.model_name,
                                "note": "配置正确。语音识别需要实际音频文件才能完全测试"
                            }

                    # 其他API（OpenAI等）：尝试获取模型列表
                    else:
                        response = await client.get(
                            f"{base_url}/models",
                            headers={"Authorization": f"Bearer {request.api_key}"}
                        )

                        if response.status_code == 200:
                            models_data = response.json()
                            available_models = []
                            if "data" in models_data:
                                available_models = [m.get("id", "") for m in models_data.get("data", [])]

                            model_available = any(request.model_name in m for m in available_models) if available_models else True

                            return {
                                "status": "success",
                                "message": f"✅ 语音识别服务配置有效！模型: {request.model_name}",
                                "connected": True,
                                "model_name": request.model_name,
                                "model_available": model_available,
                                "note": "语音识别需要实际音频文件才能完全测试"
                            }
                        elif response.status_code == 401:
                            raise HTTPException(
                                status_code=401,
                                detail="API Key 无效，请检查"
                            )
                        else:
                            return {
                                "status": "success",
                                "message": f"✅ 语音识别配置已验证！模型: {request.model_name}",
                                "connected": True,
                                "model_name": request.model_name,
                                "note": "API Key 已验证，语音识别需要实际音频文件才能完全测试"
                            }
                except httpx.ConnectError:
                    raise HTTPException(
                        status_code=503,
                        detail="无法连接到 API 端点，请检查 base_url"
                    )

        elif request.service_type == "tikhub":
            base_url = (request.base_url or "https://api.tikhub.io").rstrip("/")
            if base_url.endswith("/api/v1"):
                test_url = f"{base_url}/wechat_channels/fetch_hot_words"
            else:
                test_url = f"{base_url}/api/v1/wechat_channels/fetch_hot_words"

            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    test_url,
                    headers={"Authorization": f"Bearer {request.api_key}"},
                )

            if response.status_code == 200:
                return {
                    "status": "success",
                    "message": "✅ TikHub API 连接成功",
                    "connected": True,
                    "note": "已通过微信视频号热词接口验证授权",
                }
            if response.status_code in {401, 403}:
                raise HTTPException(status_code=response.status_code, detail="TikHub API Key 无效或无权限")

            raise HTTPException(
                status_code=response.status_code,
                detail=f"TikHub 测试失败: {response.text[:200]}",
            )

        elif request.service_type == "video_generation":
            # 视频生成服务测试 - 验证API端点和认证
            if not request.base_url:
                raise HTTPException(
                    status_code=400,
                    detail="base_url 是必需的参数，请提供 API 端点地址"
                )

            if not request.model_name:
                raise HTTPException(
                    status_code=400,
                    detail="model_name 是必需的参数，请提供模型名称"
                )

            async with httpx.AsyncClient(timeout=30.0) as client:
                base_url = request.base_url.rstrip('/')

                try:
                    # 硅基流动：验证模型名称
                    if "siliconflow" in base_url.lower():
                        # 硅基流动支持的视频生成模型
                        valid_models = [
                            "Wan-AI/Wan2.2-T2V-A14B",
                            "Wan-AI/Wan2.1-T2V-14B",
                            "Wan-AI/Wan2.1-T2V-14B-Turbo",
                            "Wan-AI/Wan2.1-I2V-14B-720P",
                            "Wan-AI/Wan2.1-I2V-14B-720P-Turbo"
                        ]

                        if request.model_name not in valid_models:
                            return {
                                "status": "success",
                                "message": f"⚠️ 视频生成配置已保存，但模型名称可能不正确",
                                "connected": True,
                                "model_name": request.model_name,
                                "note": f"硅基流动支持的模型：{', '.join(valid_models[:2])}..."
                            }
                        else:
                            return {
                                "status": "success",
                                "message": f"✅ 视频生成服务配置有效！模型: {request.model_name}",
                                "connected": True,
                                "model_name": request.model_name,
                                "provider": "SiliconFlow",
                                "note": "配置正确。视频生成需要调用submit接口，生成时间约1-5分钟"
                            }

                    # Runway：尝试访问任务列表端点
                    elif "runwayml" in base_url.lower():
                        response = await client.get(
                            f"{base_url}/tasks",
                            headers={"Authorization": f"Bearer {request.api_key}"}
                        )

                        if response.status_code in [200, 404]:
                            return {
                                "status": "success",
                                "message": f"✅ 视频生成服务配置有效！模型: {request.model_name}",
                                "connected": True,
                                "model_name": request.model_name,
                                "provider": "Runway",
                                "note": "API Key 已验证。视频生成需要实际请求且可能需要1-5分钟"
                            }
                        elif response.status_code == 401:
                            raise HTTPException(
                                status_code=401,
                                detail="Runway API Key 无效"
                            )
                    else:
                        # 其他视频生成服务
                        return {
                            "status": "success",
                            "message": f"✅ 视频生成配置已验证！模型: {request.model_name}",
                            "connected": True,
                            "model_name": request.model_name,
                            "note": "配置已保存。视频生成需要实际请求且可能需要较长时间"
                        }
                except httpx.ConnectError:
                    raise HTTPException(
                        status_code=503,
                        detail="无法连接到 API 端点，请检查 base_url"
                    )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的 service_type: {request.service_type}"
            )

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="❌ 连接超时，请检查网络或 API 端点地址是否正确"
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="❌ 无法连接到 API 端点，请检查 base_url 是否正确"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"❌ 测试失败: {str(e)}"
        )


# ==================== 原生 Function Calling 服务 ====================

class FunctionCallingRequest(BaseModel):
    """Function Calling 请求"""
    messages: List[Dict[str, str]]
    max_iterations: Optional[int] = 30
    auto_execute: Optional[bool] = True


@router.post("/function-calling", summary="执行 Function Calling（原生）")
async def function_calling(request: FunctionCallingRequest):
    """
    使用原生 Function Calling 执行任务（替代 OpenManus）

    特点：
    - 单次可控的执行流程
    - 不会无限循环
    - 直接调用 OpenAI 兼容接口
    - 支持自定义工具函数

    Args:
        request: {
            "messages": [{"role": "user", "content": "..."}],
            "max_iterations": 3,  # 最大迭代次数
            "auto_execute": true  # 是否自动执行工具调用
        }

    Returns:
        {
            "success": bool,
            "message": str,  # AI 的最终回复
            "tool_calls": List[Dict],  # 执行的工具调用记录
            "iterations": int  # 实际迭代次数
        }
    """
    try:
        from ai_service.function_calling_service import get_function_calling_service
        from ai_service.function_calling_tools import ALL_TOOLS

        # 获取服务实例
        service = await get_function_calling_service()
        if not service:
            raise HTTPException(
                status_code=400,
                detail="Function Calling 服务未配置，请在 AI 模型配置中添加 'function_calling' 类型的配置"
            )

        # 注册工具
        service.register_tools(ALL_TOOLS)

        # 执行 Function Calling
        result = await service.call(
            messages=request.messages,
            max_iterations=request.max_iterations,
            auto_execute=request.auto_execute
        )

        return {
            "status": "success",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Function Calling 执行失败: {str(e)}"
        )


@router.get("/function-calling/tools", summary="获取可用工具列表")
async def list_tools():
    """
    获取所有可用的 Function Calling 工具

    Returns:
        {
            "tools": [
                {
                    "name": str,
                    "description": str,
                    "parameters": Dict
                }
            ]
        }
    """
    try:
        from ai_service.function_calling_tools import ALL_TOOLS

        tools = []
        for tool in ALL_TOOLS:
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            })

        return {
            "status": "success",
            "data": {
                "tools": tools,
                "total": len(tools)
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取工具列表失败: {str(e)}"
        )


# ==================== 语音识别服务 ====================

class SpeechRecognitionRequest(BaseModel):
    """语音识别请求"""
    audio_url: Optional[str] = None
    audio_file_path: Optional[str] = None
    language: Optional[str] = "zh"


@router.post("/speech-recognition", summary="语音转文字")
async def speech_recognition(request: SpeechRecognitionRequest):
    """
    使用 AI 模型进行语音识别

    支持的提供商:
    - openai: OpenAI Whisper API
    - siliconflow: 硅基流动 Whisper
    - volcengine: 火山引擎语音识别
    - openai_compatible: OpenAI 兼容接口

    Args:
        request: {
            "audio_url": "https://...",  # 音频 URL（二选一）
            "audio_file_path": "/path/to/audio",  # 本地音频路径（二选一）
            "language": "zh"  # 语言代码
        }

    Returns:
        {
            "text": str,  # 识别的文本
            "language": str,  # 检测到的语言
            "duration": float  # 处理时长
        }
    """
    import httpx
    import time
    from pathlib import Path

    try:
        # 检查参数
        if not request.audio_url and not request.audio_file_path:
            raise HTTPException(
                status_code=400,
                detail="必须提供 audio_url 或 audio_file_path 之一"
            )

        # 获取配置
        config = get_ai_config("speech_recognition")
        if not config:
            raise HTTPException(
                status_code=500,
                detail="未配置语音识别服务，请在 AI 模型配置页面进行配置"
            )

        provider = config['provider']
        api_key = config['api_key']
        base_url = config.get('base_url')
        model_name = config.get('model_name')

        start_time = time.time()

        # 准备音频文件
        if request.audio_file_path:
            audio_path = Path(request.audio_file_path)
            if not audio_path.exists():
                raise HTTPException(status_code=404, detail=f"音频文件不存在: {request.audio_file_path}")
            audio_file = open(audio_path, 'rb')
        else:
            # 从 URL 下载音频
            async with httpx.AsyncClient(timeout=30.0) as client:
                audio_resp = await client.get(request.audio_url)
                if audio_resp.status_code != 200:
                    raise HTTPException(status_code=400, detail="下载音频失败")

                # 保存到临时文件
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                temp_file.write(audio_resp.content)
                temp_file.close()
                audio_file = open(temp_file.name, 'rb')

        try:
            # 调用语音识别 API
            async with httpx.AsyncClient(timeout=120.0) as client:
                if provider in ["openai", "openai_compatible", "siliconflow"]:
                    # OpenAI 兼容接口
                    api_url = base_url or "https://api.openai.com/v1"
                    model = model_name or "whisper-1"

                    # 构建 multipart/form-data 请求
                    files = {
                        'file': ('audio.mp3', audio_file, 'audio/mpeg')
                    }
                    data = {
                        'model': model,
                        'language': request.language
                    }

                    response = await client.post(
                        f"{api_url.rstrip('/')}/audio/transcriptions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        files=files,
                        data=data
                    )

                    if response.status_code != 200:
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"语音识别 API 错误: {response.text}"
                        )

                    result = response.json()
                    text = result.get("text", "")
                    detected_language = result.get("language", request.language)

                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"不支持的提供商: {provider}"
                    )

            duration = time.time() - start_time

            return {
                "status": "success",
                "data": {
                    "text": text,
                    "language": detected_language,
                    "duration": round(duration, 2),
                    "provider": provider
                }
            }

        finally:
            # 关闭音频文件
            audio_file.close()
            # 如果是临时文件，删除它
            if request.audio_url:
                import os
                os.unlink(audio_file.name)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"语音识别失败: {str(e)}"
        )


# ==================== 视频生成服务 ====================

class VideoGenerationRequest(BaseModel):
    """视频生成请求"""
    prompt: str
    duration: Optional[int] = 5  # 视频时长（秒）
    aspect_ratio: Optional[str] = "16:9"  # 宽高比


@router.post("/generate-video", summary="AI 生成视频")
async def generate_video(request: VideoGenerationRequest):
    """
    使用 AI 模型生成视频

    支持的提供商:
    - runwayml: Runway Gen-2/Gen-3
    - pika: Pika Labs
    - siliconflow: 硅基流动视频生成
    - openai_compatible: OpenAI 兼容接口

    Args:
        request: {
            "prompt": "视频描述",
            "duration": 5,  # 时长（秒）
            "aspect_ratio": "16:9"  # 宽高比
        }

    Returns:
        {
            "video_url": str,  # 生成的视频 URL
            "task_id": str,  # 任务 ID（用于查询进度）
            "status": str  # 状态
        }
    """
    import httpx
    import asyncio

    try:
        # 获取配置
        config = get_ai_config("video_generation")
        if not config:
            raise HTTPException(
                status_code=500,
                detail="未配置视频生成服务，请在 AI 模型配置页面进行配置"
            )

        provider = config['provider']
        api_key = config['api_key']
        base_url = config.get('base_url')
        model_name = config.get('model_name')
        extra_config = config.get('extra_config', {})

        async with httpx.AsyncClient(timeout=120.0) as client:
            if provider == "runwayml":
                # Runway API
                api_url = base_url or "https://api.runwayml.com/v1"
                model = model_name or "gen3"

                payload = {
                    "model": model,
                    "prompt": request.prompt,
                    "duration": request.duration,
                    "aspect_ratio": request.aspect_ratio
                }

                response = await client.post(
                    f"{api_url}/videos/generations",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Runway API 错误: {response.text}"
                    )

                data = response.json()
                task_id = data.get("id")

                # 轮询任务状态
                max_retries = 60  # 最多等待5分钟
                for i in range(max_retries):
                    await asyncio.sleep(5)  # 每5秒查询一次

                    status_response = await client.get(
                        f"{api_url}/videos/generations/{task_id}",
                        headers={"Authorization": f"Bearer {api_key}"}
                    )

                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        status = status_data.get("status")

                        if status == "completed":
                            video_url = status_data.get("url")
                            return {
                                "status": "success",
                                "data": {
                                    "video_url": video_url,
                                    "task_id": task_id,
                                    "status": "completed",
                                    "provider": "runwayml"
                                }
                            }
                        elif status == "failed":
                            error_msg = status_data.get("error", "生成失败")
                            raise HTTPException(
                                status_code=500,
                                detail=f"Runway 生成失败: {error_msg}"
                            )

                raise HTTPException(
                    status_code=504,
                    detail="视频生成超时，请稍后通过 task_id 查询结果"
                )

            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的提供商: {provider}"
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"视频生成失败: {str(e)}"
        )
