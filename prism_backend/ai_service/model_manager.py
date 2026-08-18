"""
AI 模型管理器
管理多个提供商、模型切换、配置持久化
"""

from typing import Dict, List, Optional, Any
from .base_provider import BaseProvider, AIModel
from .providers import SiliconFlowProvider, VolcanoEngineProvider, TongyiProvider, OpenAICompatibleProvider
import json
from pathlib import Path
import os


class ModelManager:
    """AI 模型管理器"""

    def __init__(self, config_path: Optional[str] = None):
        self.providers: Dict[str, BaseProvider] = {}
        self.config_path = Path(config_path) if config_path else Path(__file__).parent / "config.json"
        self.current_provider: Optional[str] = None
        self.current_model: Optional[str] = None
        self._load_config()

    def _normalize_provider_name(self, provider_name: Optional[str]) -> str:
        name = (provider_name or "").strip().lower()
        if name in {"custom", "openai", "openai-compatible", "openai_compatible"}:
            return "openai_compatible"
        return name

    def _resolve_db_path(self) -> str:
        env_path = os.getenv("SYNAPSE_DATABASE_PATH")
        if env_path:
            return env_path
        try:
            from fastapi_app.core.config import settings

            return settings.DATABASE_PATH
        except Exception:
            base_dir = Path(__file__).resolve().parent.parent  # syn_backend
            return str(base_dir / "db" / "database.db")

    def _load_config(self):
        """加载配置"""
        # 1. 尝试从数据库加载
        try:
            import sqlite3

            conn = sqlite3.connect(self._resolve_db_path())
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 加载聊天配置
            cursor.execute("SELECT * FROM ai_model_configs WHERE service_type = 'chat' AND is_active = 1")
            chat_config = cursor.fetchone()
            
            if chat_config:
                config = dict(chat_config)
                provider_name = self._normalize_provider_name(config.get("provider"))
                api_key = config.get("api_key") or ""
                base_url = config.get('base_url')
                model_name = config.get('model_name')
                
                # 初始化提供商
                self._init_provider(provider_name, api_key, base_url)
                
                # 设置当前提供商和模型
                effective_provider = provider_name
                if effective_provider not in self.providers and "openai_compatible" in self.providers:
                    effective_provider = "openai_compatible"
                if effective_provider in self.providers:
                    self.current_provider = effective_provider
                    self.current_model = model_name
                
                # 如果没有指定模型，使用默认的
                if self.current_provider and not self.current_model:
                     if self.current_provider in self.providers:
                        models = self.providers[self.current_provider].models
                        self.current_model = list(models.keys())[0] if models else None
            
            conn.close()
        except Exception as e:
            print(f"Failed to load config from database: {e}")

        # 2. 加载文件配置（作为补充或后备）
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    
                    # 如果当前没有提供商（数据库加载失败或为空），则使用文件配置
                    if not self.current_provider:
                        # 加载提供商（新格式）
                        providers_config = config.get("providers", {})
                        for provider_name, provider_info in providers_config.items():
                            if isinstance(provider_info, dict):
                                if provider_info.get("enabled") and provider_info.get("api_key"):
                                    self._init_provider(
                                        provider_name, 
                                        provider_info.get("api_key"),
                                        provider_info.get("base_url")
                                    )
                            else:
                                # 旧格式兼容
                                if provider_info:
                                    self._init_provider(provider_name, provider_info)
                        
                        # 自动选择第一个可用的提供商
                        if not self.current_provider and self.providers:
                            self.current_provider = list(self.providers.keys())[0]
                            models = self.providers[self.current_provider].models
                            self.current_model = list(models.keys())[0] if models else None
                        
                        self.current_provider = config.get("current_provider", self.current_provider)
                        self.current_model = config.get("current_model", self.current_model)
            except Exception as e:
                print(f"Failed to load config file: {e}")

    def _save_config(self):
        """保存配置"""
        try:
            # 读取现有配置
            config = {}
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            
            # 更新当前选择
            config["current_provider"] = self.current_provider
            config["current_model"] = self.current_model
            
            # 更新提供商列表（保留原有的结构和额外信息）
            if "providers" not in config:
                config["providers"] = {}
            
            for name, provider in self.providers.items():
                if name not in config["providers"]:
                    config["providers"][name] = {
                        "enabled": True,
                        "api_key": provider.api_key,
                        "base_url": provider.base_url
                    }
                else:
                    config["providers"][name]["api_key"] = provider.api_key
                    config["providers"][name]["enabled"] = True
            
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def _init_provider(self, provider_name: str, api_key: str, base_url: Optional[str] = None):
        """Initialize provider."""
        try:
            provider_key = self._normalize_provider_name(provider_name)
            if provider_key == "siliconflow":
                self.providers[provider_key] = SiliconFlowProvider(api_key)
            elif provider_key == "volcanoengine":
                self.providers[provider_key] = VolcanoEngineProvider(api_key)
            elif provider_key == "tongyi":
                self.providers[provider_key] = TongyiProvider(api_key)
            elif provider_key == "openai_compatible":
                if not base_url:
                    print(f"Warning: base_url is required for {provider_key}")
                    return
                self.providers[provider_key] = OpenAICompatibleProvider(api_key, base_url)
            elif base_url:
                self.providers["openai_compatible"] = OpenAICompatibleProvider(api_key, base_url)
        except Exception as e:
            print(f"Failed to initialize provider {provider_name}: {e}")

    def add_provider(self, provider_name: str, api_key: str, base_url: Optional[str] = None) -> bool:
        """Add provider."""
        try:
            self._init_provider(provider_name, api_key, base_url)
            provider_key = self._normalize_provider_name(provider_name)
            if provider_key not in self.providers and "openai_compatible" in self.providers:
                provider_key = "openai_compatible"
            if not self.current_provider and provider_key in self.providers:
                self.current_provider = provider_key
                models = self.providers[provider_key].models
                if models:
                    self.current_model = list(models.keys())[0]
            self._save_config()
            return True
        except Exception as e:
            print(f"Failed to add provider: {e}")
            return False

    def remove_provider(self, provider_name: str) -> bool:
        """移除提供商"""
        if provider_name in self.providers:
            del self.providers[provider_name]
            if self.current_provider == provider_name:
                self.current_provider = None
                self.current_model = None
            self._save_config()
            return True
        return False

    def switch_provider(self, provider_name: str) -> bool:
        """切换提供商"""
        if provider_name not in self.providers:
            return False
        self.current_provider = provider_name
        models = self.providers[provider_name].models
        self.current_model = list(models.keys())[0] if models else None
        self._save_config()
        return True

    def switch_model(self, model_id: str) -> bool:
        """切换模型"""
        if not self.current_provider:
            return False
        if not self.providers[self.current_provider].validate_model(model_id):
            return False
        self.current_model = model_id
        self._save_config()
        return True

    def get_current_provider(self) -> Optional[BaseProvider]:
        """获取当前提供商"""
        if self.current_provider and self.current_provider in self.providers:
            return self.providers[self.current_provider]
        return None

    def get_provider(self, provider_name: str) -> Optional[BaseProvider]:
        """获取指定提供商"""
        return self.providers.get(provider_name)

    def get_all_providers(self) -> Dict[str, BaseProvider]:
        """获取所有提供商"""
        return self.providers.copy()

    def get_all_models(self, provider_name: Optional[str] = None) -> List[AIModel]:
        """获取所有模型"""
        if provider_name:
            provider = self.providers.get(provider_name)
            if provider:
                return list(provider.models.values())
            return []
        
        models = []
        for provider in self.providers.values():
            models.extend(provider.models.values())
        return models

    def get_current_model_info(self) -> Optional[Dict[str, Any]]:
        """获取当前模型信息"""
        provider = self.get_current_provider()
        if provider and self.current_model:
            model = provider.get_model_info(self.current_model)
            if model:
                return {
                    "provider": self.current_provider,
                    "model_id": self.current_model,
                    "model_info": model.to_dict()
                }
        return None

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "current_provider": self.current_provider,
            "current_model": self.current_model,
            "providers": {
                name: {
                    "name": provider.provider_name,
                    "models_count": len(provider.models)
                }
                for name, provider in self.providers.items()
            }
        }

    async def call_current_model(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        provider = self.get_current_provider()
        if not provider:
            return {"status": "failed", "error": "No AI provider configured"}

        if not self.current_model:
            models = provider.models
            self.current_model = next(iter(models.keys()), None) if models else None

        if not self.current_model:
            return {"status": "failed", "error": "No AI model configured"}

        return await provider.call_model(
            model_id=self.current_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

    async def stream_call_current_model(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        provider = self.get_current_provider()
        if not provider:
            yield "[ERROR] No AI provider configured"
            return

        if not self.current_model:
            models = provider.models
            self.current_model = next(iter(models.keys()), None) if models else None

        if not self.current_model:
            yield "[ERROR] No AI model configured"
            return

        async for chunk in provider.stream_call_model(
            model_id=self.current_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        ):
            yield chunk


    def reload(self) -> None:
        self.providers = {}
        self.current_provider = None
        self.current_model = None
        self._load_config()

# 全局单例实例

_model_manager_instance: Optional[ModelManager] = None


def get_model_manager(config_path: Optional[str] = None) -> ModelManager:
    """
    获取 ModelManager 的全局单例实例

    Args:
        config_path: 配置文件路径（仅在首次调用时有效）

    Returns:
        ModelManager 实例
    """
    global _model_manager_instance
    if _model_manager_instance is None:
        _model_manager_instance = ModelManager(config_path)
    return _model_manager_instance
