"""OpenClaw entrypoints backed by the local Hermes agent."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .hermes_agent import (
    HermesAgentWrapper,
    get_hermes_agent,
    reset_hermes_agent,
    run_hermes_goal,
)

OpenClawAgentWrapper = HermesAgentWrapper


async def get_openclaw_agent() -> OpenClawAgentWrapper:
    return await get_hermes_agent()


async def reset_openclaw_agent() -> None:
    await reset_hermes_agent()


async def run_openclaw_goal(
    goal: str,
    context: Optional[Dict[str, Any]] = None,
    event_handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    return await run_hermes_goal(
        goal=goal,
        context=context,
        event_handler=event_handler,
        should_stop=should_stop,
    )


__all__ = [
    "OpenClawAgentWrapper",
    "get_openclaw_agent",
    "reset_openclaw_agent",
    "run_openclaw_goal",
]
