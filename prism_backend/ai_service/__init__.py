"""
AI 服务集成模块
支持多平台 AI API：硅基流动、火山引擎、通义万象等。
模型配置统一走 `/api/v1/ai` 的 model-configs（ai_model_configs 表），
不再依赖独立的 ModelManager / AIClient（旧的 config.json 已废弃）。
"""

from .providers import (
    SiliconFlowProvider,
    VolcanoEngineProvider,
    TongyiProvider,
)
from .ai_logger import AILogger

__all__ = [
    "SiliconFlowProvider",
    "VolcanoEngineProvider",
    "TongyiProvider",
    "AILogger",
]
