"""Local tool runtime for the OpenClaw/Hermes agent layer."""

from __future__ import annotations

from typing import Any, Dict, Optional


class ToolResult(dict):
    """JSON-serializable tool result."""

    def __init__(
        self,
        output: str = "",
        error: Optional[str] = None,
        data: Optional[Any] = None,
    ) -> None:
        payload: Dict[str, Any] = {"output": output}
        if error is not None:
            payload["error"] = error
        if data is not None:
            payload["data"] = data
        super().__init__(payload)


class BaseTool:
    """Minimal tool interface used by the local Hermes wrapper."""

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError
