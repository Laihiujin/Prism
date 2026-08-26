from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class CapturedExchange:
    """A deliberately incomplete and sanitized HTTP exchange.

    Raw cookies, authorization values and request/response bodies must never be
    persisted in this object. Captures are protocol documentation, not replay
    files.
    """

    platform: str
    operation: str
    method: str
    url: str
    request_headers: Mapping[str, str] = field(default_factory=dict)
    request_shape: Any = None
    status_code: int | None = None
    response_headers: Mapping[str, str] = field(default_factory=dict)
    response_shape: Any = None


@dataclass(frozen=True)
class ReversePublishResult:
    accepted: bool
    confirmed: bool = False
    platform_post_id: str | None = None
    error_code: str | None = None
    retryable: bool = False
    requires_human_action: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)
