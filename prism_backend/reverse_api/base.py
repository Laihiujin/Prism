from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from .models import ReversePublishResult


@dataclass(frozen=True)
class ReverseSession:
    """Runtime-only credentials supplied by Prism's account/session service."""

    account_id: str
    headers: Mapping[str, str]
    cookies: Mapping[str, str]


class ReversePlatformAdapter(ABC):
    platform: str

    @abstractmethod
    async def validate_session(self, session: ReverseSession) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def publish(self, session: ReverseSession, payload: Mapping[str, Any]) -> ReversePublishResult:
        raise NotImplementedError

    @abstractmethod
    async def query_publish_status(
        self, session: ReverseSession, submission_id: str
    ) -> ReversePublishResult:
        raise NotImplementedError
