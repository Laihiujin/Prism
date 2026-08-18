"""Function calling service for OpenAI-compatible chat models."""

from __future__ import annotations

import inspect
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
from loguru import logger


class Tool:
    """Callable tool definition exposed to the model."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        function: Callable[..., Any],
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self.function = function

    def to_openai_format(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, **kwargs: Any) -> Any:
        if inspect.iscoroutinefunction(self.function):
            return await self.function(**kwargs)
        return self.function(**kwargs)


class FunctionCallingService:
    """Minimal OpenAI-compatible function calling runtime."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.tools: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool
        logger.info(f"Registered function tool: {tool.name}")

    def register_tools(self, tools: List[Tool]) -> None:
        for tool in tools:
            self.register_tool(tool)

    async def call(
        self,
        messages: List[Dict[str, Any]],
        max_iterations: int = 3,
        auto_execute: bool = True,
        event_handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        tool_calls_history: List[Dict[str, Any]] = []
        conversation = messages.copy()
        iteration = 0
        last_assistant_content = ""

        async def emit(event: Dict[str, Any]) -> None:
            if event_handler is None:
                return
            maybe_result = event_handler(event)
            if inspect.isawaitable(maybe_result):
                await maybe_result

        try:
            tools_definitions = [tool.to_openai_format() for tool in self.tools.values()]

            while iteration < max_iterations:
                if should_stop and should_stop():
                    await emit({"type": "stopped", "iteration": iteration})
                    return {
                        "success": False,
                        "message": "Execution stopped by user.",
                        "tool_calls": tool_calls_history,
                        "iterations": iteration,
                        "stopped": True,
                    }

                iteration += 1
                await emit({"type": "iteration", "iteration": iteration})

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "messages": conversation,
                            "tools": tools_definitions,
                            "tool_choice": "auto",
                        },
                    )

                if response.status_code != 200:
                    error_text = response.text[:400]
                    logger.error(f"Function calling LLM request failed: {error_text}")
                    await emit(
                        {
                            "type": "error",
                            "iteration": iteration,
                            "error": error_text,
                        }
                    )
                    return {
                        "success": False,
                        "message": f"LLM request failed: {error_text}",
                        "tool_calls": tool_calls_history,
                        "iterations": iteration,
                    }

                result = response.json()
                choice = result["choices"][0]
                message = choice["message"]
                finish_reason = choice.get("finish_reason")

                conversation.append(message)
                if message.get("content"):
                    last_assistant_content = message["content"]
                    await emit(
                        {
                            "type": "assistant_message",
                            "iteration": iteration,
                            "content": last_assistant_content,
                            "finish_reason": finish_reason,
                        }
                    )

                if finish_reason == "tool_calls" and "tool_calls" in message:
                    if not auto_execute:
                        await emit(
                            {
                                "type": "pending_tool_calls",
                                "iteration": iteration,
                                "tool_calls": message["tool_calls"],
                            }
                        )
                        return {
                            "success": True,
                            "message": message.get("content", ""),
                            "tool_calls": message["tool_calls"],
                            "iterations": iteration,
                            "pending_execution": True,
                        }

                    tool_results = []
                    for tool_call in message["tool_calls"]:
                        if should_stop and should_stop():
                            await emit({"type": "stopped", "iteration": iteration})
                            return {
                                "success": False,
                                "message": "Execution stopped by user.",
                                "tool_calls": tool_calls_history,
                                "iterations": iteration,
                                "stopped": True,
                            }

                        tool_name = tool_call["function"]["name"]
                        tool_args_raw = tool_call["function"]["arguments"]
                        tool_call_id = tool_call["id"]

                        try:
                            tool_args = json.loads(tool_args_raw)
                        except json.JSONDecodeError as exc:
                            error_msg = f"Invalid tool arguments: {exc}"
                            await emit(
                                {
                                    "type": "tool_error",
                                    "iteration": iteration,
                                    "tool_name": tool_name,
                                    "error": error_msg,
                                }
                            )
                            tool_results.append(
                                {
                                    "tool_call_id": tool_call_id,
                                    "role": "tool",
                                    "name": tool_name,
                                    "content": json.dumps({"error": error_msg}, ensure_ascii=False),
                                }
                            )
                            continue

                        await emit(
                            {
                                "type": "tool_call",
                                "iteration": iteration,
                                "tool_name": tool_name,
                                "arguments": tool_args,
                            }
                        )

                        if tool_name not in self.tools:
                            tool_result: Any = {"error": f"Unknown tool: {tool_name}"}
                        else:
                            tool_result = await self.tools[tool_name].execute(**tool_args)

                        tool_calls_history.append(
                            {
                                "name": tool_name,
                                "arguments": tool_args,
                                "result": tool_result,
                            }
                        )

                        await emit(
                            {
                                "type": "tool_result",
                                "iteration": iteration,
                                "tool_name": tool_name,
                                "result": tool_result,
                            }
                        )

                        tool_results.append(
                            {
                                "tool_call_id": tool_call_id,
                                "role": "tool",
                                "name": tool_name,
                                "content": json.dumps(tool_result, ensure_ascii=False),
                            }
                        )

                    conversation.extend(tool_results)
                    continue

                if finish_reason == "stop":
                    await emit(
                        {
                            "type": "final_message",
                            "iteration": iteration,
                            "content": message.get("content", ""),
                        }
                    )
                    return {
                        "success": True,
                        "message": message.get("content", ""),
                        "tool_calls": tool_calls_history,
                        "iterations": iteration,
                    }

                await emit(
                    {
                        "type": "error",
                        "iteration": iteration,
                        "error": f"Unexpected finish_reason: {finish_reason}",
                    }
                )
                return {
                    "success": False,
                    "message": message.get("content", ""),
                    "tool_calls": tool_calls_history,
                    "iterations": iteration,
                    "finish_reason": finish_reason,
                }

            best_effort_message = last_assistant_content or "Execution reached max iterations."
            await emit(
                {
                    "type": "max_iterations_reached",
                    "iteration": iteration,
                    "content": best_effort_message,
                }
            )
            return {
                "success": True,
                "message": best_effort_message,
                "tool_calls": tool_calls_history,
                "iterations": iteration,
                "max_iterations_reached": True,
            }
        except Exception as exc:
            logger.error(f"Function calling execution failed: {exc}", exc_info=True)
            await emit({"type": "error", "iteration": iteration, "error": str(exc)})
            return {
                "success": False,
                "message": f"Execution failed: {exc}",
                "tool_calls": tool_calls_history,
                "iterations": iteration,
            }


async def get_function_calling_service() -> Optional[FunctionCallingService]:
    """Load the active function-calling model config from the database."""

    try:
        db_path = os.getenv("SYNAPSE_DATABASE_PATH")
        if not db_path:
            try:
                from fastapi_app.core.config import settings

                db_path = settings.DATABASE_PATH
            except Exception:
                base_dir = Path(__file__).resolve().parent.parent
                db_path = str(base_dir / "db" / "database.db")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM ai_model_configs
            WHERE service_type = 'function_calling' AND is_active = 1
            """
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            logger.warning("No active function-calling model config found.")
            return None

        config = dict(row)
        service = FunctionCallingService(
            api_key=config["api_key"],
            base_url=config.get("base_url") or "https://api.openai.com/v1",
            model=config.get("model_name") or "gpt-4o",
        )
        logger.info(
            "Loaded function-calling service: provider=%s model=%s",
            config["provider"],
            service.model,
        )
        return service
    except Exception as exc:
        logger.error(f"Failed to load function-calling service config: {exc}")
        return None
