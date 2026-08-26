from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class QrLoginState(str, Enum):
    CREATED = "created"
    WAITING = "waiting"
    SCANNED = "scanned"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass(frozen=True)
class QrLoginChallenge:
    platform: str
    challenge_id: str
    qr_content: str
    expires_in: int | None = None
    runtime_context: Mapping[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class QrPollResult:
    state: QrLoginState
    message: str = ""
    retry_after: float = 1.0
    session_established: bool = False
    session_payload: Mapping[str, Any] = field(default_factory=dict, repr=False)
    runtime_context: Mapping[str, Any] = field(default_factory=dict, repr=False)
