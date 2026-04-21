"""Local Hermes-style agent wrapper used by the OpenClaw entrypoints."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from ai_service.function_calling_service import (
    FunctionCallingService,
    Tool as FunctionTool,
    get_function_calling_service,
)

from ..api.v1.agent.prompts import SYSTEM_PROMPT
from .hermes_config import read_agent_config
from .openclaw_tools import (
    AccountVideoCrawlerTool,
    CreatePublishPlanTool,
    DataAnalyticsTool,
    ExternalVideoCrawlerTool,
    GenerateAIMetadataTool,
    GetFileDetailTool,
    GetTaskStatusTool,
    ListAccountsTool,
    ListFilesTool,
    ListPublishPlansTool,
    ListTasksStatusTool,
    PublishBatchVideosTool,
    UsePresetToPublishTool,
)
from .openclaw_tools_extended import CookieManagerTool, IPPoolTool, RunScriptTool
from .openclaw_tools_social_api import (
    BilibiliFetchUserInfoTool,
    BilibiliFetchUserVideosTool,
    BilibiliFetchVideoDetailTool,
    DouyinFetchUserInfoTool,
    DouyinFetchUserVideosTool,
    DouyinFetchVideoDetailTool,
    TikTokFetchUserInfoTool,
    TikTokFetchUserVideosTool,
    TikTokFetchVideoDetailTool,
)
from .tikhub_tools import (
    TikHubKuaishouUserInfoTool,
    TikHubKuaishouUserPostsTool,
    TikHubWeChatChannelsHomeTool,
    TikHubWeChatChannelsVideoDetailTool,
    TikHubXiaohongshuNoteIdTool,
    TikHubXiaohongshuUserInfoTool,
    TikHubXiaohongshuUserNotesTool,
)


def _tool_to_function_tool(tool: Any) -> FunctionTool:
    async def _run(**kwargs: Any) -> Dict[str, Any]:
        result = await tool.execute(**kwargs)
        return dict(result) if isinstance(result, dict) else {"output": str(result)}

    return FunctionTool(
        name=tool.name,
        description=getattr(tool, "description", "") or tool.name,
        parameters=getattr(tool, "parameters", {"type": "object", "properties": {}}),
        function=_run,
    )


class HermesAgentWrapper:
    """Function-calling based local agent for the OpenClaw entrypoints."""

    def __init__(self) -> None:
        self._agent: Optional[FunctionCallingService] = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized and self._agent is not None:
            return

        self._agent = await self._build_service()
        self._register_tools(self._agent)
        self._initialized = True
        logger.info("Hermes agent initialized with local tool runtime.")

    async def _build_service(self) -> FunctionCallingService:
        config = read_agent_config()
        llm = config.get("llm") or {}
        if llm.get("api_key"):
            return FunctionCallingService(
                api_key=llm["api_key"],
                base_url=llm.get("base_url") or "https://api.openai.com/v1",
                model=llm.get("model") or "gpt-4o",
                timeout=90.0,
            )

        service = await get_function_calling_service()
        if service is not None:
            return service

        raise ValueError(
            "No Hermes/OpenClaw model configuration found. Configure /api/v1/agent/config first."
        )

    def _register_tools(self, service: FunctionCallingService) -> None:
        tool_instances = [
            ListAccountsTool(),
            ListFilesTool(),
            GetFileDetailTool(),
            GenerateAIMetadataTool(),
            PublishBatchVideosTool(),
            CreatePublishPlanTool(),
            ListPublishPlansTool(),
            UsePresetToPublishTool(),
            GetTaskStatusTool(),
            ListTasksStatusTool(),
            DataAnalyticsTool(),
            ExternalVideoCrawlerTool(),
            AccountVideoCrawlerTool(),
            IPPoolTool(),
            RunScriptTool(),
            CookieManagerTool(),
            DouyinFetchUserInfoTool(),
            DouyinFetchUserVideosTool(),
            DouyinFetchVideoDetailTool(),
            TikTokFetchUserInfoTool(),
            TikTokFetchUserVideosTool(),
            TikTokFetchVideoDetailTool(),
            BilibiliFetchUserInfoTool(),
            BilibiliFetchUserVideosTool(),
            BilibiliFetchVideoDetailTool(),
            TikHubKuaishouUserInfoTool(),
            TikHubKuaishouUserPostsTool(),
            TikHubXiaohongshuUserInfoTool(),
            TikHubXiaohongshuUserNotesTool(),
            TikHubXiaohongshuNoteIdTool(),
            TikHubWeChatChannelsHomeTool(),
            TikHubWeChatChannelsVideoDetailTool(),
        ]
        service.register_tools([_tool_to_function_tool(tool) for tool in tool_instances])

    async def run_goal(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        event_handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        if not self._initialized or self._agent is None:
            await self.initialize()

        messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

        if context:
            context_lines = [f"- {key}: {value}" for key, value in context.items()]
            messages.append(
                {
                    "role": "system",
                    "content": "Runtime context:\n" + "\n".join(context_lines),
                }
            )

        messages.append({"role": "user", "content": goal})

        result = await self._agent.call(
            messages=messages,
            max_iterations=8,
            auto_execute=True,
            event_handler=event_handler,
            should_stop=should_stop,
        )

        return {
            "success": bool(result.get("success")),
            "result": result.get("message", ""),
            "steps": result.get("tool_calls", []),
            "error": None if result.get("success") else result.get("message", ""),
            "stopped": bool(result.get("stopped")),
        }

    async def cleanup(self) -> None:
        self._agent = None
        self._initialized = False


_hermes_agent_instance: Optional[HermesAgentWrapper] = None


async def get_hermes_agent() -> HermesAgentWrapper:
    global _hermes_agent_instance
    if _hermes_agent_instance is None:
        _hermes_agent_instance = HermesAgentWrapper()
        await _hermes_agent_instance.initialize()
    return _hermes_agent_instance


async def reset_hermes_agent() -> None:
    global _hermes_agent_instance
    if _hermes_agent_instance is not None:
        await _hermes_agent_instance.cleanup()
    _hermes_agent_instance = None


async def run_hermes_goal(
    goal: str,
    context: Optional[Dict[str, Any]] = None,
    event_handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    agent = await get_hermes_agent()
    return await agent.run_goal(
        goal=goal,
        context=context,
        event_handler=event_handler,
        should_stop=should_stop,
    )


