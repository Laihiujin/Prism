from __future__ import annotations

from abc import ABC, abstractmethod

from .models import QrLoginChallenge, QrPollResult


class QrLoginAdapter(ABC):
    """Protocol boundary for QR login without persisting replayable secrets."""

    platform: str

    @abstractmethod
    async def create_challenge(self) -> QrLoginChallenge:
        raise NotImplementedError

    @abstractmethod
    async def poll(self, challenge: QrLoginChallenge) -> QrPollResult:
        raise NotImplementedError

    @abstractmethod
    async def close(self, challenge: QrLoginChallenge) -> None:
        raise NotImplementedError
