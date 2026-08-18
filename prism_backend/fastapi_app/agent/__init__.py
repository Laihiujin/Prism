"""Agent entrypoints."""

from .hermes_agent import get_hermes_agent, reset_hermes_agent, run_hermes_goal
from .openclaw_agent import get_openclaw_agent, reset_openclaw_agent, run_openclaw_goal

__all__ = [
    "get_hermes_agent",
    "reset_hermes_agent",
    "run_hermes_goal",
    "get_openclaw_agent",
    "reset_openclaw_agent",
    "run_openclaw_goal",
]
