"""
AI 提供商基类
定义所有 AI 提供商需要实现的接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import json


class AIModel:
    """AI 模型信息"""
    def __init__(self, model_id: str, name: str, provider: str, max_tokens: int = 4096, **kwargs):
        self.model_id = model_id
        self.name = name
        self.provider = provider
        self.max_tokens = max_tokens
        self.config = kwargs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "provider": self.provider,
            "max_tokens": self.max_tokens,
            "config": self.config,
        }


class BaseProvider(ABC):
    """AI 提供商基类"""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self.models: Dict[str, AIModel] = {}

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供商名称"""
        pass

    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        pass

    @abstractmethod
    async def get_available_models(self) -> List[AIModel]:
        """获取可用模型列表"""
        pass

    @abstractmethod
    async def call_model(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """调用模型"""
        pass

    @abstractmethod
    async def stream_call_model(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """流式调用模型"""
        pass

    def validate_model(self, model_id: str) -> bool:
        """验证模型是否存在"""
        return model_id in self.models

    def get_model_info(self, model_id: str) -> Optional[AIModel]:
        """获取模型信息"""
        return self.models.get(model_id)

    def register_model(self, model: AIModel):
        """注册模型"""
        self.models[model.model_id] = model
