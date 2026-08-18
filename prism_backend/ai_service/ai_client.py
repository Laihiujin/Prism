"""
AI 客户端 - 统一接口
管理 AI 调用、指令解析、脚本执行
"""

import asyncio
import json
import re
import time
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, AsyncGenerator
from .model_manager import ModelManager
from .ai_logger import AILogger


class AIClient:
    """AI 客户端 - 统一接口"""

    # 系统提示词模板
    SYSTEM_PROMPTS = {
        "default": """你是一个社交媒体内容发布的 AI 助手。
你有以下能力：
1. 生成社交媒体文案和话题
2. 管理社交媒体账号（查看、添加、删除）
3. 一键发布素材到多个平台
4. 分析素材和平台数据

当用户要求执行某个操作时，你需要：
1. 理解用户的意图
2. 如果需要执行系统功能，使用以下格式：[EXEC]script_name(param1, param2)[/EXEC]
3. 返回执行结果或建议

支持的脚本命令：
- [EXEC]list_accounts()[/EXEC] - 列出所有账号
- [EXEC]list_materials()[/EXEC] - 列出所有素材
- [EXEC]publish_material(material_id, accounts)[/EXEC] - 发布素材
- [EXEC]add_account(platform, credentials)[/EXEC] - 添加账号
- [EXEC]delete_account(account_id)[/EXEC] - 删除账号
- [EXEC]get_account_info(account_id)[/EXEC] - 获取账号信息
""",
        "copywriter": """你是一个专业的社交媒体文案创意专家。
你的任务是：
1. 根据素材内容生成高质量的社交媒体文案
2. 为不同平台优化文案（微博、抖音、快手、小红书）
3. 提供热门话题建议
4. 分析内容的潜在推广价值

请确保文案简洁有力、富有感染力，能够吸引目标受众的关注。
""",
        "manager": """你是一个社交媒体账号管理助手。
你的任务是：
1. 帮助用户管理多个社交媒体账号
2. 监控账号状态和绑定情况
3. 处理账号的添加、删除、更新操作
4. 提供账号管理建议

支持的操作：
- [EXEC]list_accounts()[/EXEC]
- [EXEC]get_account_info(account_id)[/EXEC]
- [EXEC]add_account(platform, credentials)[/EXEC]
- [EXEC]delete_account(account_id)[/EXEC]
""",
    }

    def __init__(self, model_manager: ModelManager, logger: AILogger):
        self.model_manager = model_manager
        self.logger = logger
        self.instruction_handlers: Dict[str, callable] = {}
        self._register_handlers()
        self._load_prompts_from_config()

    def _load_prompts_from_config(self):
        """从统一配置文件加载提示词"""
        try:
            # 使用新的统一配置文件 ai_prompts_unified.yaml
            base_dir = Path(__file__).parent.parent

            # 优先使用统一配置文件
            config_path = base_dir / "config" / "ai_prompts_unified.yaml"

            # 如果统一配置不存在，回退到旧配置
            if not config_path.exists():
                config_path = base_dir / "config" / "ai_prompts.yaml"

            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)

                if config:
                    # 映射统一配置到 SYSTEM_PROMPTS
                    # 1. 加载聊天助手
                    if 'chat_assistant' in config:
                        self.SYSTEM_PROMPTS['default'] = config['chat_assistant'].get('system_prompt', self.SYSTEM_PROMPTS['default'])

                    # 2. 加载内容生成模块
                    if 'content_generation' in config:
                        content_gen = config['content_generation']

                        if 'title_generation' in content_gen:
                            self.SYSTEM_PROMPTS['title_generator'] = content_gen['title_generation'].get('system_prompt', '')

                        if 'description_generation' in content_gen:
                            self.SYSTEM_PROMPTS['description_generator'] = content_gen['description_generation'].get('system_prompt', '')

                        if 'tags_generation' in content_gen:
                            self.SYSTEM_PROMPTS['tags_generator'] = content_gen['tags_generation'].get('system_prompt', '')

                        if 'cover_generation' in content_gen:
                            self.SYSTEM_PROMPTS['cover_generator'] = content_gen['cover_generation'].get('system_prompt', '')

                    # 兼容旧格式（直接在根级别）
                    else:
                        if 'title_generation' in config:
                            self.SYSTEM_PROMPTS['title_generator'] = config['title_generation'].get('system_prompt', '')

                        if 'description_generation' in config:
                            self.SYSTEM_PROMPTS['description_generator'] = config['description_generation'].get('system_prompt', '')

                        if 'tags_generation' in config:
                            self.SYSTEM_PROMPTS['tags_generator'] = config['tags_generation'].get('system_prompt', '')

                print(f"[AIClient] Loaded prompts from {config_path}")
            else:
                print(f"[AIClient] Config file not found: {config_path}")

        except Exception as e:
            print(f"[AIClient] Failed to load prompts: {e}")

    def _register_handlers(self):
        """注册指令处理器"""
        self.instruction_handlers = {
            "list_accounts": self._handle_list_accounts,
            "list_materials": self._handle_list_materials,
            "publish_material": self._handle_publish_material,
            "add_account": self._handle_add_account,
            "delete_account": self._handle_delete_account,
            "get_account_info": self._handle_get_account_info,
        }

    async def chat(
        self,
        user_message: str,
        context: Optional[List[Dict[str, str]]] = None,
        role: str = "default",
        **kwargs
    ) -> Dict[str, Any]:
        """对话接口"""
        start_time = time.time()
        provider = self.model_manager.get_current_provider()
        
        if not provider or not self.model_manager.current_model:
            return {
                "status": "failed",
                "error": "No AI provider configured"
            }

        # 构建消息列表
        system_prompt = self.SYSTEM_PROMPTS.get(role, self.SYSTEM_PROMPTS["default"])
        messages = context or []
        messages.append({"role": "user", "content": user_message})

        try:
            # 调用 AI 模型
            response = await provider.call_model(
                model_id=self.model_manager.current_model,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                **kwargs
            )

            execution_time = time.time() - start_time
            
            if response["status"] == "success":
                content = response.get("content", "")
                
                # 记录日志
                self.logger.log_call(
                    provider=self.model_manager.current_provider,
                    model_id=self.model_manager.current_model,
                    instruction=user_message,
                    status="success",
                    response=content,
                    execution_time=execution_time,
                    tokens_used=response.get("usage", {}).get("total_tokens")
                )
                
                # 检查并执行指令
                scripts = self._extract_scripts(content)
                script_results = {}
                
                for script_name, params in scripts:
                    try:
                        handler = self.instruction_handlers.get(script_name)
                        if handler:
                            result = await handler(*params)
                            script_results[script_name] = result
                            
                            self.logger.log_call(
                                provider=self.model_manager.current_provider,
                                model_id=self.model_manager.current_model,
                                instruction=user_message,
                                status="success",
                                script_called=script_name,
                                script_result=json.dumps(result)
                            )
                    except Exception as e:
                        script_results[script_name] = {"error": str(e)}
                        self.logger.log_call(
                            provider=self.model_manager.current_provider,
                            model_id=self.model_manager.current_model,
                            instruction=user_message,
                            status="failed",
                            script_called=script_name,
                            script_result=json.dumps({"error": str(e)})
                        )
                
                return {
                    "status": "success",
                    "content": content,
                    "model": self.model_manager.current_model,
                    "provider": self.model_manager.current_provider,
                    "execution_time": execution_time,
                    "scripts": script_results,
                    "tokens": response.get("usage", {}),
                }
            else:
                self.logger.log_call(
                    provider=self.model_manager.current_provider,
                    model_id=self.model_manager.current_model,
                    instruction=user_message,
                    status="failed",
                    error=response.get("error"),
                    execution_time=execution_time
                )
                
                return {
                    "status": "failed",
                    "error": response.get("error"),
                    "model": self.model_manager.current_model,
                    "provider": self.model_manager.current_provider,
                    "execution_time": execution_time,
                }
        except Exception as e:
            execution_time = time.time() - start_time
            
            self.logger.log_call(
                provider=self.model_manager.current_provider,
                model_id=self.model_manager.current_model,
                instruction=user_message,
                status="failed",
                error=str(e),
                execution_time=execution_time
            )
            
            return {
                "status": "failed",
                "error": str(e),
                "model": self.model_manager.current_model,
                "provider": self.model_manager.current_provider,
                "execution_time": execution_time,
            }

    async def stream_chat(
        self,
        user_message: str,
        context: Optional[List[Dict[str, str]]] = None,
        role: str = "default",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式对话接口"""
        provider = self.model_manager.get_current_provider()
        
        if not provider or not self.model_manager.current_model:
            yield "[ERROR] No AI provider configured"
            return

        system_prompt = self.SYSTEM_PROMPTS.get(role, self.SYSTEM_PROMPTS["default"])
        messages = context or []
        messages.append({"role": "user", "content": user_message})

        try:
            async for chunk in provider.stream_call_model(
                model_id=self.model_manager.current_model,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                **kwargs
            ):
                yield chunk
        except Exception as e:
            yield f"[ERROR] {str(e)}"

    def _extract_scripts(self, content: str) -> List[tuple]:
        """从内容中提取脚本命令"""
        pattern = r'\[EXEC\](\w+)\((.*?)\)\[/EXEC\]'
        scripts = []
        
        for match in re.finditer(pattern, content):
            script_name = match.group(1)
            params_str = match.group(2)
            
            # 简单的参数解析
            try:
                params = [p.strip().strip('"\'') for p in params_str.split(',')]
                scripts.append((script_name, params))
            except:
                pass
        
        return scripts

    async def _handle_list_accounts(self) -> Dict[str, Any]:
        """处理：列出所有账号"""
        # 这些函数实际调用后端 API
        return {"action": "list_accounts", "status": "pending"}

    async def _handle_list_materials(self) -> Dict[str, Any]:
        """处理：列出所有素材"""
        return {"action": "list_materials", "status": "pending"}

    async def _handle_publish_material(self, material_id: str, accounts: str) -> Dict[str, Any]:
        """处理：发布素材"""
        return {
            "action": "publish_material",
            "material_id": material_id,
            "accounts": accounts.split(","),
            "status": "pending"
        }

    async def _handle_add_account(self, platform: str, credentials: str) -> Dict[str, Any]:
        """处理：添加账号"""
        return {
            "action": "add_account",
            "platform": platform,
            "status": "pending"
        }

    async def _handle_delete_account(self, account_id: str) -> Dict[str, Any]:
        """处理：删除账号"""
        return {
            "action": "delete_account",
            "account_id": account_id,
            "status": "pending"
        }

    async def _handle_get_account_info(self, account_id: str) -> Dict[str, Any]:
        """处理：获取账号信息"""
        return {
            "action": "get_account_info",
            "account_id": account_id,
            "status": "pending"
        }

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        results = {}
        
        for provider_name, provider in self.model_manager.get_all_providers().items():
            try:
                check_result = await provider.test_connection()
                results[provider_name] = check_result
                self.logger.log_health_check(
                    provider=provider_name,
                    status=check_result.get("status", "unknown"),
                    error=check_result.get("error")
                )
            except Exception as e:
                results[provider_name] = {
                    "status": "failed",
                    "error": str(e)
                }
                self.logger.log_health_check(
                    provider=provider_name,
                    status="failed",
                    error=str(e)
                )
        
        return results

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        all_stats = self.logger.get_statistics()
        provider_stats = {}
        
        for provider_name in self.model_manager.get_all_providers().keys():
            provider_stats[provider_name] = self.logger.get_statistics(provider=provider_name)
        
        return {
            "all": all_stats,
            "by_provider": provider_stats,
            "recent_calls": self.logger.get_recent_calls(limit=10),
        }

    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        status = {}
        
        for provider_name in self.model_manager.get_all_providers().keys():
            status[provider_name] = self.logger.get_provider_health(provider=provider_name)
        
        return status
