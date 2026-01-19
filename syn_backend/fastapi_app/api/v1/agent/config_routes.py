"""
OpenManus 配置管理路由
独立的 LLM 配置，用于 OpenManus Agent 工具调用
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, List
import toml
from pathlib import Path
import asyncio
from threading import Lock

from ....core.logger import logger
from ....schemas.common import Response

# OpenManus 路径（用于 LLM 缓存清除）
OPENMANUS_PATH = Path(__file__).parent.parent.parent.parent.parent / "OpenManus-worker"


router = APIRouter(prefix="/config", tags=["Agent Config"])

# 文件锁，防止并发写入冲突
_config_lock = Lock()

# Provider 配置注册表
PROVIDER_BASE_URLS = {
    "siliconflow": "https://api.siliconflow.cn/v1",
    "volcanoengine": "https://api.volcanoengine.com/v1",
    "tongyi": "https://dashscope.aliyuncs.com/api/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1"
}

PROVIDER_MODELS = {
    "siliconflow": {
        "name": "硅基流动 (SiliconFlow)",
        "models": [
            {"id": "Qwen/QwQ-32B", "name": "Qwen QwQ-32B", "description": "高性能推理模型，支持复杂任务"},
            {"id": "deepseek-ai/DeepSeek-V3", "name": "DeepSeek V3", "description": "平衡性能和速度"},
            {"id": "Qwen/Qwen2.5-72B-Instruct", "name": "Qwen 2.5 72B", "description": "通用大模型"}
        ],
        "vision_models": [
            {"id": "Qwen/Qwen2-VL-72B-Instruct", "name": "Qwen2-VL 72B", "description": "视觉语言模型"}
        ]
    },
    "volcanoengine": {
        "name": "火山引擎",
        "models": [
            {"id": "doubao-pro", "name": "豆包 Pro", "description": "高性能模型"},
            {"id": "doubao-lite", "name": "豆包 Lite", "description": "轻量级模型"}
        ],
        "vision_models": []
    },
    "tongyi": {
        "name": "通义千问",
        "models": [
            {"id": "qwen-max", "name": "通义千问 Max", "description": "最强性能"},
            {"id": "qwen-plus", "name": "通义千问 Plus", "description": "平衡选择"},
            {"id": "qwen-turbo", "name": "通义千问 Turbo", "description": "快速响应"}
        ],
        "vision_models": [
            {"id": "qwen-vl-max", "name": "通义千问 VL Max", "description": "视觉语言模型"}
        ]
    },
    "openai": {
        "name": "OpenAI",
        "models": [
            {"id": "gpt-4-turbo-preview", "name": "GPT-4 Turbo", "description": "最新 GPT-4"},
            {"id": "gpt-4", "name": "GPT-4", "description": "标准 GPT-4"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "description": "快速模型"}
        ],
        "vision_models": [
            {"id": "gpt-4-vision-preview", "name": "GPT-4 Vision", "description": "视觉理解"}
        ]
    },
    "anthropic": {
        "name": "Anthropic",
        "models": [
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "description": "最强模型"},
            {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet", "description": "平衡选择"},
            {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku", "description": "快速响应"}
        ],
        "vision_models": []
    }
}


# ============================================
# Pydantic Models
# ============================================

class ManusLLMConfig(BaseModel):
    """OpenManus LLM 配置"""
    provider: Literal["siliconflow", "volcanoengine", "tongyi", "openai", "anthropic"]
    api_key: str = Field(..., min_length=10, description="API 密钥")
    base_url: Optional[str] = Field(None, description="自定义 Base URL（可选）")
    model: str = Field(..., min_length=1, description="模型 ID")
    max_tokens: int = Field(16384, ge=1024, le=32768, description="最大 Token 数")
    temperature: float = Field(0.6, ge=0.0, le=2.0, description="温度参数")


class ManusVisionConfig(BaseModel):
    """OpenManus Vision 模型配置（可选）"""
    model: str = Field(..., min_length=1, description="Vision 模型 ID")
    base_url: Optional[str] = Field(None, description="Vision 模型 Base URL（可选）")
    api_key: Optional[str] = Field(None, description="Vision API Key（可选，默认使用 LLM API Key）")


class ManusFullConfig(BaseModel):
    """完整的 OpenManus 配置"""
    llm: ManusLLMConfig
    vision: Optional[ManusVisionConfig] = None


class ManusConfigResponse(BaseModel):
    """配置响应（不包含 API Key）"""
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 16384
    temperature: float = 0.6
    vision_model: Optional[str] = None
    vision_base_url: Optional[str] = None
    is_configured: bool = False


# ============================================
# Helper Functions
# ============================================

def get_config_path() -> Path:
    """获取 OpenManus 配置文件路径"""
    # 从主项目到 OpenManus-worker
    base_path = Path(__file__).parent.parent.parent.parent.parent / "OpenManus-worker"
    config_dir = base_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.toml"


def read_config() -> Dict:
    """读取配置文件"""
    config_path = get_config_path()
    if not config_path.exists():
        return {}

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return toml.load(f)
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        return {}


def write_config(config: Dict):
    """写入配置文件（带锁）"""
    config_path = get_config_path()

    with _config_lock:
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                toml.dump(config, f)
            logger.info(f"配置已保存到: {config_path}")
        except Exception as e:
            logger.error(f"写入配置文件失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"保存配置失败: {str(e)}"
            )


# ============================================
# API Endpoints
# ============================================

@router.get("/providers")
async def get_supported_providers():
    """
    获取支持的 LLM Provider 列表

    返回每个 Provider 的默认配置和推荐模型
    """
    providers_info = {}

    for provider_id, models_info in PROVIDER_MODELS.items():
        providers_info[provider_id] = {
            "id": provider_id,
            "name": models_info["name"],
            "base_url": PROVIDER_BASE_URLS.get(provider_id, ""),
            "models": models_info["models"],
            "vision_models": models_info["vision_models"]
        }

    return Response(
        success=True,
        data={
            "providers": providers_info,
            "total": len(providers_info)
        }
    )


@router.get("/manus", response_model=Response[ManusConfigResponse])
async def get_manus_config():
    """
    获取当前 OpenManus 配置

    返回已配置的信息（不返回 api_key）
    """
    try:
        config = read_config()

        if not config or "llm" not in config:
            return Response(
                success=True,
                data=ManusConfigResponse(is_configured=False)
            )

        llm_config = config["llm"]
        vision_config = config.get("llm", {}).get("vision", {})

        # 构造响应（脱敏 API Key）
        response_data = ManusConfigResponse(
            provider=llm_config.get("provider", "unknown"),
            model=llm_config.get("model", ""),
            base_url=llm_config.get("base_url", ""),
            max_tokens=llm_config.get("max_tokens", 16384),
            temperature=llm_config.get("temperature", 0.6),
            vision_model=vision_config.get("model"),
            vision_base_url=vision_config.get("base_url"),
            is_configured=True
        )

        return Response(success=True, data=response_data)

    except Exception as e:
        logger.error(f"获取配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取配置失败: {str(e)}"
        )


@router.post("/manus", response_model=Response[Dict])
async def set_manus_config(config: ManusFullConfig):
    """
    设置 OpenManus 的完整配置（包括 LLM 和可选的 Vision）

    将配置保存到 OpenManus-worker/config/config.toml
    """
    try:
        # 构建 TOML 配置
        toml_config = {
            "llm": {
                "provider": config.llm.provider,
                "model": config.llm.model,
                "api_key": config.llm.api_key,
                "base_url": config.llm.base_url or PROVIDER_BASE_URLS.get(config.llm.provider, ""),
                "max_tokens": config.llm.max_tokens,
                "temperature": config.llm.temperature
            }
        }

        # 添加 Vision 配置（如果提供）
        if config.vision:
            toml_config["llm"]["vision"] = {
                "model": config.vision.model,
                "base_url": config.vision.base_url or toml_config["llm"]["base_url"],
                "api_key": config.vision.api_key or config.llm.api_key
            }

        # 写入配置文件
        write_config(toml_config)

        # 清除全局 Agent 实例，强制下次使用时重新初始化
        try:
            from ....agent.manus_agent import _manus_agent_instance
            global _manus_agent_instance
            if _manus_agent_instance:
                await _manus_agent_instance.cleanup()
                _manus_agent_instance = None
            logger.info("已清除 OpenManus Agent 实例，下次将使用新配置")
        except Exception as e:
            logger.warning(f"清除 Agent 实例时出错（可忽略）: {e}")

        return Response(
            success=True,
            data={
                "message": "配置已保存",
                "provider": config.llm.provider,
                "model": config.llm.model,
                "config_path": str(get_config_path())
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存配置失败: {str(e)}"
        )


@router.delete("/manus")
async def delete_manus_config():
    """删除 OpenManus 配置"""
    try:
        config_path = get_config_path()

        if config_path.exists():
            config_path.unlink()
            logger.info(f"配置文件已删除: {config_path}")

        # 清除全局 Agent 实例
        try:
            from ....agent.manus_agent import _manus_agent_instance
            global _manus_agent_instance
            if _manus_agent_instance:
                await _manus_agent_instance.cleanup()
                _manus_agent_instance = None
            logger.info("已清除 OpenManus Agent 实例")
        except Exception as e:
            logger.warning(f"清除 Agent 实例时出错（可忽略）: {e}")

        return Response(
            success=True,
            data={"message": "配置已删除"}
        )

    except Exception as e:
        logger.error(f"删除配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除配置失败: {str(e)}"
        )


@router.post("/manus/test")
async def test_manus_config():
    """
    测试 OpenManus 配置是否有效

    执行简单的 LLM 调用测试
    """
    try:
        # 检查配置是否存在
        config = read_config()
        if not config or "llm" not in config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="配置未找到，请先配置 OpenManus"
            )

        # 尝试初始化并测试 Agent
        from ....agent.manus_agent import get_manus_agent, _manus_agent_instance
        
        logger.info("正在测试 OpenManus 配置...")
        
        # 强制清除全局 Agent 实例和 LLM 缓存，确保使用最新配置
        global _manus_agent_instance
        if _manus_agent_instance:
            try:
                await _manus_agent_instance.cleanup()
            except Exception as e:
                logger.warning(f"清理旧 Agent 实例时出错: {e}")
            _manus_agent_instance = None
        
        # 清除 LLM 单例缓存
        try:
            import sys
            if str(OPENMANUS_PATH) in sys.path:
                from app.llm import LLM
                if "default" in LLM._instances:
                    del LLM._instances["default"]
                    logger.info("已清除 LLM 单例缓存")
        except Exception as e:
            logger.warning(f"清除 LLM 缓存时出错: {e}")
        
        agent = await get_manus_agent()

        # 执行简单测试
        test_goal = "测试连接：请回复 'OpenManus 配置成功！'"
        result = await agent.run_goal(test_goal, {})

        if result.get("success"):
            return Response(
                success=True,
                data={
                    "status": "success",
                    "message": "OpenManus 配置有效，连接测试成功",
                    "provider": config["llm"].get("provider", "unknown"),
                    "model": config["llm"].get("model", "unknown"),
                    "test_result": result.get("result", "")
                }
            )
        else:
            return Response(
                success=False,
                data={
                    "status": "error",
                    "message": "测试失败: " + result.get("error", "Unknown error")
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"配置测试失败: {e}", exc_info=True)
        return Response(
            success=False,
            data={
                "status": "error",
                "message": f"配置测试失败: {str(e)}"
            }
        )
