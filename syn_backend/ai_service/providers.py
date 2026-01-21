"""
具体的 AI 提供商实现 - 使用官方 SDK
支持：硅基流动（OpenAI 兼容）、火山引擎、通义万象
"""

from .base_provider import BaseProvider, AIModel
from typing import Dict, List, Any, Optional
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class SiliconFlowProvider(BaseProvider):
    """硅基流动 API 提供商 - 使用 OpenAI SDK"""

    _DEFAULT_MODELS = [
        AIModel("Qwen/Qwen2.5-72B-Instruct", "通义千问 2.5 72B", "siliconflow", max_tokens=8192),
        AIModel("Qwen/Qwen2.5-7B-Instruct", "通义千问 2.5 7B", "siliconflow", max_tokens=8192),
        AIModel("meta-llama/Llama-3.1-405B-Instruct", "Llama 3.1 405B", "siliconflow", max_tokens=8192),
        AIModel("meta-llama/Llama-3.1-70B-Instruct", "Llama 3.1 70B", "siliconflow", max_tokens=8192),
        AIModel("deepseek-ai/DeepSeek-V3", "DeepSeek V3", "siliconflow", max_tokens=8192),
        AIModel("Pro/deepseek-ai/DeepSeek-V3", "DeepSeek V3 (Pro)", "siliconflow", max_tokens=8192),
        AIModel("ByteDance/Seed-OSS-36B-Instruct", "Seed OSS 36B", "siliconflow", max_tokens=8192),
    ]

    def __init__(self, api_key: str):
        super().__init__(api_key, base_url="https://api.siliconflow.cn/v1")
        self._init_models()
        try:
            from openai import OpenAI
            print(f"[SiliconFlow] Initializing with API key: {api_key[:20]}...")
            self.client = OpenAI(api_key=api_key, base_url=self.base_url)
            print(f"[SiliconFlow] Client initialized successfully")
        except ImportError as e:
            print(f"[SiliconFlow] OpenAI SDK not installed: {e}")
            self.client = None
        except Exception as e:
            print(f"[SiliconFlow] Error initializing OpenAI client: {e}")
            self.client = None

    @property
    def provider_name(self) -> str:
        return "siliconflow"

    def _init_models(self):
        """初始化模型列表"""
        for model in self._DEFAULT_MODELS:
            self.register_model(model)

    async def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            if self.client is None:
                return {
                    "status": "failed",
                    "provider": "siliconflow",
                    "error": "OpenAI SDK not installed"
                }
            
            # 在线程池中运行同步调用
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="Qwen/Qwen2.5-7B-Instruct",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=10
                )
            )
            return {"status": "success", "provider": "siliconflow"}
        except Exception as e:
            logger.error(f"SiliconFlow test_connection failed: {str(e)}")
            return {
                "status": "failed",
                "provider": "siliconflow",
                "error": str(e)
            }

    async def get_available_models(self) -> List[AIModel]:
        """获取可用模型"""
        return list(self.models.values())

    async def call_model(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """调用模型"""
        if not self.validate_model(model_id):
            raise ValueError(f"Model {model_id} not found")

        try:
            if self.client is None:
                return {
                    "status": "failed",
                    "model": model_id,
                    "provider": "siliconflow",
                    "error": "OpenAI SDK not installed"
                }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=model_id.replace("Pro/", ""),
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens or 2048,
                    **kwargs
                )
            )
            
            return {
                "status": "success",
                "model": model_id,
                "provider": "siliconflow",
                "content": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            }
        except Exception as e:
            logger.error(f"SiliconFlow call_model failed: {str(e)}")
            return {
                "status": "failed",
                "model": model_id,
                "provider": "siliconflow",
                "error": str(e)
            }

    async def stream_call_model(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """流式调用模型"""
        if not self.validate_model(model_id):
            raise ValueError(f"Model {model_id} not found")

        try:
            if self.client is None:
                yield "[ERROR] OpenAI SDK not installed"
                return

            loop = asyncio.get_event_loop()
            stream = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=model_id.replace("Pro/", ""),
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens or 2048,
                    stream=True,
                    **kwargs
                )
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"SiliconFlow stream_call_model failed: {str(e)}")
            yield f"[ERROR] {str(e)}"


class VolcanoEngineProvider(BaseProvider):
    """火山引擎 API 提供商 - 使用官方 volcengine SDK"""

    _DEFAULT_MODELS = [
        AIModel("doubao-pro-32k", "豆包 Pro 32K", "volcanoengine", max_tokens=32768),
        AIModel("doubao-lite-32k", "豆包 Lite 32K", "volcanoengine", max_tokens=32768),
        AIModel("doubao-pro-4k", "豆包 Pro 4K", "volcanoengine", max_tokens=4096),
    ]

    def __init__(self, api_key: str):
        super().__init__(api_key, base_url="https://ark.cn-beijing.volces.com/api/v3")
        self._init_models()
        try:
            # 火山引擎 SDK 需要更复杂的初始化
            # api_key 格式通常是 "region|access_key|secret_key"
            self.client = None
            self._setup_volcengine_client()
        except ImportError:
            logger.warning("volcengine SDK not installed")
            self.client = None

    def _setup_volcengine_client(self):
        """设置火山引擎客户端"""
        try:
            from volcengine.service import Service
            
            # 解析 API Key
            # 火山引擎的 API 认证需要 access_key 和 secret_key
            # 这里假设 api_key 是合并后的格式
            self.service = Service('cv', 'cn-beijing', self.api_key)
        except Exception as e:
            logger.warning(f"Failed to setup volcengine client: {str(e)}")

    @property
    def provider_name(self) -> str:
        return "volcanoengine"

    def _init_models(self):
        """初始化模型列表"""
        for model in self._DEFAULT_MODELS:
            self.register_model(model)

    async def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            # 火山引擎没有标准的 test_connection API
            # 改为测试一个简单的调用
            loop = asyncio.get_event_loop()
            
            # 使用异步执行器运行同步调用
            result = await loop.run_in_executor(
                None,
                self._test_connection_sync
            )
            return result
        except Exception as e:
            logger.error(f"VolcanoEngine test_connection failed: {str(e)}")
            return {
                "status": "failed",
                "provider": "volcanoengine",
                "error": str(e)
            }

    def _test_connection_sync(self) -> Dict[str, Any]:
        """同步测试连接"""
        try:
            import requests
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "doubao-lite-32k",
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 10,
            }
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                return {"status": "success", "provider": "volcanoengine"}
            else:
                return {
                    "status": "failed",
                    "provider": "volcanoengine",
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "status": "failed",
                "provider": "volcanoengine",
                "error": str(e)
            }

    async def get_available_models(self) -> List[AIModel]:
        """获取可用模型"""
        return list(self.models.values())

    async def call_model(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """调用模型"""
        if not self.validate_model(model_id):
            raise ValueError(f"Model {model_id} not found")

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._call_model_sync,
                model_id,
                messages,
                temperature,
                max_tokens,
                kwargs
            )
            return result
        except Exception as e:
            logger.error(f"VolcanoEngine call_model failed: {str(e)}")
            return {
                "status": "failed",
                "model": model_id,
                "provider": "volcanoengine",
                "error": str(e)
            }

    def _call_model_sync(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """同步调用模型"""
        try:
            import requests
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 2048,
                **kwargs
            }
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "success",
                    "model": model_id,
                    "provider": "volcanoengine",
                    "content": data.get("choices", [{}])[0].get("message", {}).get("content", ""),
                    "usage": data.get("usage", {}),
                }
            else:
                return {
                    "status": "failed",
                    "model": model_id,
                    "provider": "volcanoengine",
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "status": "failed",
                "model": model_id,
                "provider": "volcanoengine",
                "error": str(e)
            }

    async def stream_call_model(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """流式调用模型"""
        if not self.validate_model(model_id):
            raise ValueError(f"Model {model_id} not found")

        try:
            import requests
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 2048,
                "stream": True,
                **kwargs
            }
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60,
                stream=True
            )
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith("data: "):
                            try:
                                data = json.loads(line_str[6:])
                                if "choices" in data:
                                    delta = data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        yield delta["content"]
                            except:
                                pass
            else:
                yield f"[ERROR] HTTP {response.status_code}: {response.text}"
        except Exception as e:
            logger.error(f"VolcanoEngine stream_call_model failed: {str(e)}")
            yield f"[ERROR] {str(e)}"


class TongyiProvider(BaseProvider):
    """阿里通义万象 API 提供商 - 使用 DashScope SDK"""

    _DEFAULT_MODELS = [
        AIModel("qwen-turbo", "通义千问 Turbo", "tongyi", max_tokens=8192),
        AIModel("qwen-plus", "通义千问 Plus", "tongyi", max_tokens=8192),
        AIModel("qwen-max", "通义千问 Max", "tongyi", max_tokens=8192),
    ]

    def __init__(self, api_key: str):
        super().__init__(api_key, base_url="https://dashscope.aliyuncs.com/api/v1")
        self._init_models()
        try:
            import dashscope
            print(f"[Tongyi] Initializing with API key: {api_key[:20]}...")
            dashscope.api_key = api_key
            self.dashscope = dashscope
            print(f"[Tongyi] Client initialized successfully")
        except ImportError as e:
            print(f"[Tongyi] DashScope SDK not installed: {e}")
            self.dashscope = None
        except Exception as e:
            print(f"[Tongyi] Error initializing DashScope: {e}")
            self.dashscope = None

    @property
    def provider_name(self) -> str:
        return "tongyi"

    def _init_models(self):
        """初始化模型列表"""
        for model in self._DEFAULT_MODELS:
            self.register_model(model)

    async def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            if self.dashscope is None:
                return {
                    "status": "failed",
                    "provider": "tongyi",
                    "error": "DashScope SDK not installed"
                }
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._test_connection_sync
            )
            return result
        except Exception as e:
            logger.error(f"Tongyi test_connection failed: {str(e)}")
            return {
                "status": "failed",
                "provider": "tongyi",
                "error": str(e)
            }

    def _test_connection_sync(self) -> Dict[str, Any]:
        """同步测试连接"""
        try:
            from dashscope import Generation
            
            response = Generation.call(
                model="qwen-turbo",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
            
            if response.status_code == 200:
                return {"status": "success", "provider": "tongyi"}
            else:
                return {
                    "status": "failed",
                    "provider": "tongyi",
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "status": "failed",
                "provider": "tongyi",
                "error": str(e)
            }

    async def get_available_models(self) -> List[AIModel]:
        """获取可用模型"""
        return list(self.models.values())

    async def call_model(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """调用模型"""
        if not self.validate_model(model_id):
            raise ValueError(f"Model {model_id} not found")

        try:
            if self.dashscope is None:
                return {
                    "status": "failed",
                    "model": model_id,
                    "provider": "tongyi",
                    "error": "DashScope SDK not installed"
                }

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._call_model_sync,
                model_id,
                messages,
                temperature,
                max_tokens,
                kwargs
            )
            return result
        except Exception as e:
            logger.error(f"Tongyi call_model failed: {str(e)}")
            return {
                "status": "failed",
                "model": model_id,
                "provider": "tongyi",
                "error": str(e)
            }

    def _call_model_sync(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """同步调用模型"""
        try:
            from dashscope import Generation
            
            response = Generation.call(
                model=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or 2048,
                **kwargs
            )
            
            if response.status_code == 200:
                # DashScope 的响应结构是：response.output.text
                # choices 通常为 None，使用 text 字段获取内容
                content = ""
                if hasattr(response, 'output') and response.output:
                    if hasattr(response.output, 'text'):
                        content = response.output.text
                    elif hasattr(response.output, 'choices') and response.output.choices:
                        # 备选方案，如果有 choices
                        content = response.output.choices[0].message.content
                
                return {
                    "status": "success",
                    "model": model_id,
                    "provider": "tongyi",
                    "content": content,
                    "usage": {
                        "prompt_tokens": response.usage.input_tokens if hasattr(response, 'usage') and response.usage else 0,
                        "completion_tokens": response.usage.output_tokens if hasattr(response, 'usage') and response.usage else 0,
                        "total_tokens": (response.usage.input_tokens + response.usage.output_tokens) if hasattr(response, 'usage') and response.usage else 0,
                    },
                }
            else:
                return {
                    "status": "failed",
                    "model": model_id,
                    "provider": "tongyi",
                    "error": f"HTTP {response.status_code}: {response.message}"
                }
        except Exception as e:
            return {
                "status": "failed",
                "model": model_id,
                "provider": "tongyi",
                "error": str(e)
            }

    async def stream_call_model(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """流式调用模型"""
        if not self.validate_model(model_id):
            raise ValueError(f"Model {model_id} not found")

        try:
            if self.dashscope is None:
                yield "[ERROR] DashScope SDK not installed"
                return

            from dashscope import Generation
            
            # DashScope 使用流式处理
            response = Generation.call(
                model=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or 2048,
                stream=True,
                **kwargs
            )
            
            for event in response:
                if event.status_code == 200:
                    # 使用 text 字段而不是 choices
                    if hasattr(event, 'output') and event.output:
                        if hasattr(event.output, 'text') and event.output.text:
                            yield event.output.text
                        elif hasattr(event.output, 'choices') and event.output.choices:
                            # 备选方案
                            yield event.output.choices[0].message.content
                else:
                    yield f"[ERROR] HTTP {event.status_code}: {event.message}"
                    break
        except Exception as e:
            logger.error(f"Tongyi stream_call_model failed: {str(e)}")
            yield f"[ERROR] {str(e)}"


class OpenAICompatibleProvider(BaseProvider):
    """通用 OpenAI 兼容 API 提供商"""

    def __init__(self, api_key: str, base_url: str):
        super().__init__(api_key, base_url=base_url)
        self.client = None
        self._models_cache = None
        self._models_cache_time = None
        self._cache_ttl = 300  # 缓存 5 分钟
        self._init_client()

    def _init_client(self):
        try:
            from openai import OpenAI
            
            processed_base_url = self.base_url
            if processed_base_url:
                # Auto-correct base_url if user includes /models, /v1/models or /chat/completions
                processed_base_url = processed_base_url.rstrip("/")
                if processed_base_url.endswith("/v1/models"):
                    processed_base_url = processed_base_url[:-10]
                elif processed_base_url.endswith("/models"):
                    processed_base_url = processed_base_url[:-7]
                elif processed_base_url.endswith("/chat/completions"):
                    processed_base_url = processed_base_url[:-17]
            
            logger.debug("[OpenAI Compatible] Initializing with Base URL: %s", processed_base_url)
            self.client = OpenAI(api_key=self.api_key, base_url=processed_base_url)
        except ImportError:
            logger.warning("[OpenAI Compatible] OpenAI SDK not installed")
            self.client = None
        except Exception as e:
            logger.warning("[OpenAI Compatible] Error initializing client: %s", e)
            self.client = None

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    async def get_available_models(self, model_type: Optional[str] = None, sub_type: Optional[str] = None) -> List[AIModel]:
        """获取可用模型列表，支持筛选"""
        if not self.client:
            return []

        # 检查缓存
        import time
        current_time = time.time()
        if self._models_cache is not None and self._models_cache_time is not None:
            if current_time - self._models_cache_time < self._cache_ttl:
                logger.debug("[OpenAI Compatible] Using cached models (%d models)", len(self._models_cache))
                return self._models_cache

        loop = asyncio.get_event_loop()
        try:
            # 总是获取所有模型，忽略 type/sub_type 过滤参数，防止 API 不支持导致返回空
            logger.debug(
                "[OpenAI Compatible] Fetching all models (ignoring filters: type=%s, sub_type=%s)",
                model_type,
                sub_type
            )

            response = await loop.run_in_executor(
                None,
                self.client.models.list
            )

            # 使用 built-in type 函数
            import builtins
            logger.debug("[OpenAI Compatible] Raw response type: %s", builtins.type(response))

            models: List[AIModel] = []
            # 检查 response 是否有 data 属性，或者它本身就是列表
            data_list = getattr(response, 'data', [])
            if not data_list and isinstance(response, list):
                data_list = response

            logger.debug("[OpenAI Compatible] Found %s models in response", len(data_list))

            for model in data_list:
                models.append(AIModel(
                    model_id=model.id,
                    name=model.id,
                    provider=self.provider_name,
                    description=f"Model {model.id}"
                ))

            # 更新缓存
            self._models_cache = models
            self._models_cache_time = current_time

            return models
        except Exception as e:
            logger.warning("[OpenAI Compatible] Failed to list models: %s", e)
            # 如果请求失败但有缓存，返回旧缓存
            if self._models_cache is not None:
                logger.debug("[OpenAI Compatible] Using stale cache due to error")
                return self._models_cache
            return []

    async def test_connection(self) -> Dict[str, Any]:
        """测试连接 - 只检查客户端是否可用，不获取模型列表"""
        try:
            if self.client is None:
                return {"status": "failed", "error": "OpenAI SDK not installed"}

            # 只检查客户端是否初始化成功，不实际调用 API
            # 这样可以避免频繁的网络请求
            return {
                "status": "success",
                "provider": "openai_compatible"
            }
        except Exception as e:
            logger.error(f"OpenAI Compatible test_connection failed: {str(e)}")
            return {
                "status": "failed",
                "provider": "openai_compatible",
                "error": str(e)
            }

    async def call_model(self, model_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        if self.client is None:
            return {"status": "failed", "error": "Client not initialized"}
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    **kwargs
                )
            )
            return {
                "status": "success",
                "content": response.choices[0].message.content,
                "usage": {
                    "total_tokens": response.usage.total_tokens
                }
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def stream_call_model(self, model_id: str, messages: List[Dict[str, str]], **kwargs):
        if self.client is None:
            yield "[ERROR] Client not initialized"
            return

        try:
            loop = asyncio.get_event_loop()
            stream = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    stream=True,
                    **kwargs
                )
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"[ERROR] {str(e)}"
