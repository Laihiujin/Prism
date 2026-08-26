"""Stdlib MCP (Model Context Protocol) stdio server exposing Prism's tool catalog.

Run as::

    python -m fastapi_app.agent.mcp_server

This makes the ~30 ``BaseTool`` classes in ``hermes_tools*.py`` / ``tikhub_tools.py``
callable by the Hermes agent as structured MCP tools (``tools/list`` +
``tools/call``) instead of the free-form HTTP/CLI guesses the text-only prompt
inventory currently relies on.

Stdlib-only: newline-delimited JSON-RPC 2.0 over stdio, matching the official
MCP stdio transport used by Hermes's ``mcp.client.stdio`` client. No ``mcp``
package dependency is required on the server side.

Register it in ``tools/hermes-home/config.yaml``::

    mcp_servers:
      prism:
        command: "<python>"
        args: ["-m", "fastapi_app.agent.mcp_server"]
        env: { "PRISM_APP_ROOT": "<repo root>" }
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
from typing import Any, Dict, List, Optional

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "prism"
SERVER_VERSION = "1.0.0"


def _collect_tools() -> Dict[str, Any]:
    from . import hermes_tools, hermes_tools_extended, hermes_tools_social_api, tikhub_tools
    from .tool_runtime import BaseTool

    tools: Dict[str, Any] = {}
    for module in (hermes_tools, hermes_tools_extended, hermes_tools_social_api, tikhub_tools):
        for value in vars(module).values():
            if not inspect.isclass(value):
                continue
            if not issubclass(value, BaseTool) or value is BaseTool:
                continue
            name = str(getattr(value, "name", "")).strip()
            if not name:
                continue
            if name in tools:
                continue  # first module wins (hermes_tools precedes extended aliases)

            parameters = getattr(value, "parameters", {}) or {}
            if not isinstance(parameters, dict):
                parameters = {"type": "object", "properties": {}}
            parameters.setdefault("type", "object")
            parameters.setdefault("properties", {})

            tools[name] = {
                "name": name,
                "description": " ".join(str(getattr(value, "description", "")).split()),
                "inputSchema": parameters,
                "_cls": value,
            }
    return tools


def _result(payload: Any, req_id: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": payload}


def _error(code: int, message: str, req_id: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


async def _call_tool(tool: Dict[str, Any], arguments: Dict[str, Any]) -> Dict[str, Any]:
    cls = tool["_cls"]
    try:
        instance = cls()
        result = await instance.execute(**(arguments or {}))
    except Exception as exc:  # noqa: BLE001 - surface any tool failure to the model
        return {
            "content": [{"type": "text", "text": f"tool error: {type(exc).__name__}: {exc}"}],
            "isError": True,
        }

    if isinstance(result, dict):
        text = json.dumps(result, ensure_ascii=False, default=str)
    else:
        text = str(result)
    return {"content": [{"type": "text", "text": text}], "isError": bool(result.get("error")) if isinstance(result, dict) else False}


def _handle_request(method: str, params: Any, req_id: Any, tools: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if method == "initialize":
        return _result(
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
            req_id,
        )
    if method == "tools/list":
        return _result(
            {
                "tools": [
                    {
                        "name": t["name"],
                        "description": t["description"],
                        "inputSchema": t["inputSchema"],
                    }
                    for t in tools.values()
                ]
            },
            req_id,
        )
    if method == "tools/call":
        if not isinstance(params, dict):
            return _error(-32602, "invalid params", req_id)
        name = params.get("name")
        tool = tools.get(str(name or ""))
        if tool is None:
            return _error(-32602, f"unknown tool: {name}", req_id)
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _error(-32602, "arguments must be an object", req_id)
        try:
            payload = asyncio.run(_call_tool(tool, arguments))
        except Exception as exc:  # noqa: BLE001
            return _error(-32603, f"tool execution failed: {exc}", req_id)
        return _result(payload, req_id)
    if method == "ping":
        return _result({}, req_id)
    # Unknown method → respond with method-not-found (only for requests, not notifications).
    return _error(-32601, f"method not found: {method}", req_id)


def main() -> int:
    tools = _collect_tools()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = message.get("method")
        req_id = message.get("id")

        # Notifications (no id) such as notifications/initialized: never reply.
        if req_id is None:
            continue

        response = _handle_request(str(method or ""), message.get("params"), req_id, tools)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
