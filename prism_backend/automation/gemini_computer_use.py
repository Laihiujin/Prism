"""Gemini Computer Use diagnostics for Patchright pages.

This adapter is deliberately *not* the primary publisher.  It is used after a
stable locator fails and returns visual action candidates from Gemini. Prism
records those candidates as diagnostic evidence only; it never executes them
in a live publisher.

Gemini Computer Use is an API tool, rather than an MCP server.  Keeping this
small adapter separate also lets an MCP host expose the same guarded methods
without handing a remote model unrestricted browser control.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_MODEL = "gemini-3.6-flash"
@dataclass(frozen=True)
class ComputerUseAction:
    name: str
    arguments: dict[str, Any]
    intent: str = ""
    call_id: str = ""
    safety_decision: str = ""


class ComputerUsePolicyError(RuntimeError):
    """Raised when a visual action is outside Prism's allowed recovery scope."""


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _allowed_domains(platform: str) -> set[str]:
    builtin = {
        "douyin": {"creator.douyin.com"},
        "kuaishou": {"cp.kuaishou.com"},
        "xiaohongshu": {"creator.xiaohongshu.com"},
        "channels": {"channels.weixin.qq.com"},
        "tencent": {"channels.weixin.qq.com"},
        "bilibili": {"member.bilibili.com"},
        "tiktok": {"tiktok.com", "www.tiktok.com"},
        "youtube": {"studio.youtube.com", "youtube.com", "www.youtube.com"},
    }
    configured = os.getenv("PRISM_COMPUTER_USE_ALLOWED_DOMAINS", "")
    extra = {item.strip().lower() for item in configured.split(",") if item.strip()}
    return builtin.get(platform.lower(), set()) | extra


def _matches_allowed_domain(url: str, domains: Iterable[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


class GeminiComputerUseRecovery:
    """Capture a visual diagnostic when a deterministic platform step fails."""

    def __init__(self, *, api_key: Optional[str] = None, audit_dir: Optional[str | Path] = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = os.getenv("PRISM_GEMINI_COMPUTER_USE_MODEL", DEFAULT_MODEL)
        self.enabled = _env_flag("PRISM_GEMINI_COMPUTER_USE_ENABLED")
        data_dir = Path(os.getenv("PRISM_DATA_DIR", Path(__file__).resolve().parents[1]))
        self.audit_dir = Path(audit_dir) if audit_dir else data_dir / "logs" / "computer_use"

    async def suggest(self, page: Any, *, platform: str, objective: str) -> list[ComputerUseAction]:
        """Get one recovery turn from Gemini; does not execute model output."""
        if not self.enabled:
            raise ComputerUsePolicyError("Gemini Computer Use is disabled (set PRISM_GEMINI_COMPUTER_USE_ENABLED=true).")
        if not self.api_key:
            raise ComputerUsePolicyError("GEMINI_API_KEY is required for Gemini Computer Use recovery.")
        if not _matches_allowed_domain(page.url, _allowed_domains(platform)):
            raise ComputerUsePolicyError(f"Recovery is not allowed on this domain: {page.url}")

        screenshot = await page.screenshot(type="png")
        prompt = (
            "You are Prism's visual recovery assistant. A deterministic Patchright locator failed. "
            f"Platform: {platform}. Goal: {objective}. "
            "Propose at most one reversible UI action. Never publish, post, submit, delete, "
            "purchase, change permissions, log out, or navigate outside the current site."
        )
        payload = {
            "model": self.model,
            "input": [
                {"type": "text", "text": prompt},
                {"type": "image", "data": base64.b64encode(screenshot).decode("ascii"), "mime_type": "image/png"},
            ],
            "tools": [{
                "type": "computer_use",
                "environment": "browser",
                "enable_prompt_injection_detection": True,
                "excluded_predefined_functions": ["drag_and_drop"],
            }],
        }
        import httpx

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(API_URL, headers={"x-goog-api-key": self.api_key}, json=payload)
            response.raise_for_status()
            result = response.json()

        actions = self._extract_actions(result)
        self._audit("suggested", page.url, platform, actions)
        return actions

    @staticmethod
    def _extract_actions(result: dict[str, Any]) -> list[ComputerUseAction]:
        actions: list[ComputerUseAction] = []
        decision = str(result.get("safety_decision") or "")
        for step in result.get("steps") or []:
            if step.get("type") != "function_call":
                continue
            args = step.get("arguments") or {}
            actions.append(
                ComputerUseAction(
                    name=str(step.get("name") or ""),
                    arguments=dict(args) if isinstance(args, dict) else {},
                    intent=str(args.get("intent") or "") if isinstance(args, dict) else "",
                    call_id=str(step.get("id") or step.get("call_id") or ""),
                    safety_decision=decision,
                )
            )
        return actions

    def _audit(self, event: str, url: str, platform: str, actions: list[ComputerUseAction]) -> None:
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "at": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "platform": platform,
            "url": url,
            "actions": [asdict(action) for action in actions],
        }
        record["checksum"] = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
        path = self.audit_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


__all__ = [
    "ComputerUseAction",
    "ComputerUsePolicyError",
    "GeminiComputerUseRecovery",
]
