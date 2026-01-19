"""
原生 Function Calling 服务
替代 OpenManus 框架，提供可控的单次调用模式

特点：
- 直接调用 OpenAI 兼容接口
- 单次响应，不会无限循环执行
- 支持自定义工具函数
- 完全可控的执行流程
"""
import json
import httpx
from typing import Dict, Any, List, Optional, Callable
from loguru import logger
import inspect


class Tool:
    """工具函数定义"""
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        function: Callable
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.function = function

    def to_openai_format(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    async def execute(self, **kwargs) -> Any:
        """执行工具函数"""
        # 检查函数是否是异步的
        if inspect.iscoroutinefunction(self.function):
            return await self.function(**kwargs)
        else:
            return self.function(**kwargs)


class FunctionCallingService:
    """原生 Function Calling 服务"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        timeout: float = 60.0
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.tools: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool):
        """注册工具函数"""
        self.tools[tool.name] = tool
        logger.info(f"✅ 注册工具: {tool.name}")

    def register_tools(self, tools: List[Tool]):
        """批量注册工具函数"""
        for tool in tools:
            self.register_tool(tool)

    async def call(
        self,
        messages: List[Dict[str, str]],
        max_iterations: int = 3,
        auto_execute: bool = True
    ) -> Dict[str, Any]:
        """
        执行 Function Calling

        Args:
            messages: 对话消息列表
            max_iterations: 最大迭代次数（防止无限循环）
            auto_execute: 是否自动执行工具调用

        Returns:
            {
                "success": bool,
                "message": str,  # 最终的 AI 回复
                "tool_calls": List[Dict],  # 执行的工具调用记录
                "iterations": int  # 实际迭代次数
            }
        """
        try:
            conversation = messages.copy()
            tool_calls_history = []
            iteration = 0
            last_assistant_content = ""

            # 准备工具定义
            tools_definitions = [tool.to_openai_format() for tool in self.tools.values()]

            while iteration < max_iterations:
                iteration += 1
                logger.info(f"📝 Function Calling 迭代 {iteration}/{max_iterations}")

                # 调用 LLM
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model,
                            "messages": conversation,
                            "tools": tools_definitions,
                            "tool_choice": "auto"
                        }
                    )

                    if response.status_code != 200:
                        error_text = response.text
                        logger.error(f"❌ LLM 调用失败: {error_text}")
                        return {
                            "success": False,
                            "message": f"LLM 调用失败: {error_text[:200]}",
                            "tool_calls": tool_calls_history,
                            "iterations": iteration
                        }

                    result = response.json()

                # 获取 AI 响应
                choice = result["choices"][0]
                message = choice["message"]
                finish_reason = choice.get("finish_reason")

                # 将 AI 响应添加到对话历史
                conversation.append(message)
                if message.get("content"):
                    last_assistant_content = message["content"]

                # 检查是否有工具调用
                if finish_reason == "tool_calls" and "tool_calls" in message:
                    if not auto_execute:
                        # 不自动执行，返回工具调用信息
                        return {
                            "success": True,
                            "message": message.get("content", ""),
                            "tool_calls": message["tool_calls"],
                            "iterations": iteration,
                            "pending_execution": True
                        }

                    # 执行工具调用
                    tool_results = []
                    for tool_call in message["tool_calls"]:
                        tool_name = tool_call["function"]["name"]
                        tool_args_str = tool_call["function"]["arguments"]
                        tool_call_id = tool_call["id"]

                        logger.info(f"🔧 执行工具: {tool_name}")
                        logger.debug(f"   参数: {tool_args_str}")

                        try:
                            # 解析参数
                            tool_args = json.loads(tool_args_str)

                            # 查找工具
                            if tool_name not in self.tools:
                                error_msg = f"工具 '{tool_name}' 未注册"
                                logger.error(f"❌ {error_msg}")
                                tool_result = {"error": error_msg}
                            else:
                                # 执行工具
                                tool = self.tools[tool_name]
                                result_data = await tool.execute(**tool_args)
                                tool_result = result_data

                            # 记录工具调用
                            tool_calls_history.append({
                                "name": tool_name,
                                "arguments": tool_args,
                                "result": tool_result
                            })

                            # 构建工具响应消息
                            tool_results.append({
                                "tool_call_id": tool_call_id,
                                "role": "tool",
                                "name": tool_name,
                                "content": json.dumps(tool_result, ensure_ascii=False)
                            })

                        except json.JSONDecodeError as e:
                            error_msg = f"解析工具参数失败: {e}"
                            logger.error(f"❌ {error_msg}")
                            tool_results.append({
                                "tool_call_id": tool_call_id,
                                "role": "tool",
                                "name": tool_name,
                                "content": json.dumps({"error": error_msg}, ensure_ascii=False)
                            })
                        except Exception as e:
                            error_msg = f"工具执行失败: {str(e)}"
                            logger.error(f"❌ {error_msg}")
                            tool_results.append({
                                "tool_call_id": tool_call_id,
                                "role": "tool",
                                "name": tool_name,
                                "content": json.dumps({"error": error_msg}, ensure_ascii=False)
                            })

                    # 将工具结果添加到对话历史
                    conversation.extend(tool_results)

                    # 继续下一轮对话（让 AI 总结结果）
                    continue

                elif finish_reason == "stop":
                    # AI 完成响应，没有更多工具调用
                    final_message = message.get("content", "")
                    logger.info(f"✅ Function Calling 完成，迭代次数: {iteration}")
                    return {
                        "success": True,
                        "message": final_message,
                        "tool_calls": tool_calls_history,
                        "iterations": iteration
                    }

                else:
                    # 其他 finish_reason
                    logger.warning(f"⚠️ 未知的 finish_reason: {finish_reason}")
                    return {
                        "success": False,
                        "message": message.get("content", ""),
                        "tool_calls": tool_calls_history,
                        "iterations": iteration,
                        "finish_reason": finish_reason
                    }

            # 达到最大迭代次数
            logger.warning(f"⚠️ 达到最大迭代次数 {max_iterations}")
            # 给模型一次“强制收束”的机会：不再允许工具调用，直接输出当前可得的结果/结论。
            best_effort_message = last_assistant_content or "已达到最大迭代次数，部分任务可能未完成。"
            try:
                summary_conversation = conversation + [{
                    "role": "user",
                    "content": (
                        "请基于以上对话与工具返回结果，给出你能确定的结论/输出；"
                        "若仍有未完成部分，请明确说明卡点并给出下一步建议。"
                        "不要再调用任何工具。"
                    )
                }]
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model,
                            "messages": summary_conversation,
                            "tool_choice": "none",
                        }
                    )
                if response.status_code != 200:
                    # 兼容部分 OpenAI-compatible 实现不支持 tool_choice="none"
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": self.model,
                                "messages": summary_conversation,
                            }
                        )
                if response.status_code == 200:
                    result = response.json()
                    message = result["choices"][0]["message"]
                    if message.get("content"):
                        best_effort_message = message["content"]
                else:
                    logger.warning(f"⚠️ 强制收束调用失败: {response.text[:200]}")
            except Exception as e:
                logger.warning(f"⚠️ 强制收束调用异常: {e}")

            return {
                "success": True,
                "message": best_effort_message,
                "tool_calls": tool_calls_history,
                "iterations": iteration,
                "max_iterations_reached": True
            }

        except Exception as e:
            logger.error(f"❌ Function Calling 执行失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"执行失败: {str(e)}",
                "tool_calls": tool_calls_history if 'tool_calls_history' in locals() else [],
                "iterations": iteration if 'iteration' in locals() else 0
            }


# ============================================
# 从数据库加载配置并创建服务实例
# ============================================

async def get_function_calling_service() -> Optional[FunctionCallingService]:
    """
    从数据库加载 Function Calling 配置并创建服务实例

    Returns:
        FunctionCallingService 实例，如果配置不存在则返回 None
    """
    import sqlite3
    import os
    from pathlib import Path

    try:
        db_path = os.getenv("SYNAPSE_DATABASE_PATH")
        if not db_path:
            try:
                from fastapi_app.core.config import settings

                db_path = settings.DATABASE_PATH
            except Exception:
                base_dir = Path(__file__).resolve().parent.parent  # syn_backend
                db_path = str(base_dir / "db" / "database.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM ai_model_configs
            WHERE service_type = 'function_calling' AND is_active = 1
        """)

        row = cursor.fetchone()
        conn.close()

        if not row:
            logger.warning("⚠️ 未找到激活的 Function Calling 配置")
            return None

        config = dict(row)

        # 创建服务实例
        service = FunctionCallingService(
            api_key=config['api_key'],
            base_url=config.get('base_url') or "https://api.openai.com/v1",
            model=config.get('model_name') or "gpt-4o"
        )

        logger.info(
            f"✅ Function Calling 服务已创建 - "
            f"Provider: {config['provider']}, Model: {service.model}"
        )

        return service

    except Exception as e:
        logger.error(f"❌ 创建 Function Calling 服务失败: {e}")
        return None
