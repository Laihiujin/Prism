"""Generate creator.douyin.com ``a_bogus`` with the current web signer.

The JavaScript runtime is kept in a long-lived Node subprocess so signing does
not launch Chromium and does not pay process/bootstrap cost for every poll.
Only the query string, form body and User-Agent cross the local stdin pipe.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class SignerError(RuntimeError):
    """The local Douyin signing runtime failed or returned invalid output."""


class DouyinABogusSigner:
    def __init__(self, *, node_binary: str = "node") -> None:
        self.node_binary = node_binary
        self._runner = Path(__file__).with_name("douyin_abogus_runner.js")
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()

    async def _start(self) -> asyncio.subprocess.Process:
        if self._process and self._process.returncode is None:
            return self._process
        self._process = await asyncio.create_subprocess_exec(
            self.node_binary,
            str(self._runner),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return self._process

    async def sign(self, query: str, body: str, user_agent: str) -> str:
        """Return one fresh signature for the exact encoded query and body."""
        if not user_agent:
            raise ValueError("user_agent is required")
        request = json.dumps(
            {"query": query, "body": body, "userAgent": user_agent},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode() + b"\n"

        async with self._lock:
            process = await self._start()
            assert process.stdin and process.stdout
            process.stdin.write(request)
            await process.stdin.drain()
            raw = await asyncio.wait_for(process.stdout.readline(), timeout=5)
            if not raw:
                error = ""
                if process.stderr:
                    error = (await process.stderr.read()).decode(errors="replace")[-500:]
                self._process = None
                raise SignerError(f"Douyin signer stopped unexpectedly: {error}")

        try:
            response: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SignerError("Douyin signer returned non-JSON output") from exc
        signature = response.get("a_bogus")
        if not response.get("ok") or not isinstance(signature, str) or len(signature) < 100:
            raise SignerError(str(response.get("error") or "invalid a_bogus output"))
        return signature

    async def close(self) -> None:
        process, self._process = self._process, None
        if not process or process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

    async def __aenter__(self) -> "DouyinABogusSigner":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
