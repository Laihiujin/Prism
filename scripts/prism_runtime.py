#!/usr/bin/env python3
"""Select and publish the endpoint shared by every Prism process."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILE = ROOT / "runtime-data" / "runtime.json"


def port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def select_endpoint() -> dict:
    host = os.getenv("PRISM_BACKEND_HOST", "127.0.0.1").strip() or "127.0.0.1"
    explicit_url = os.getenv("PRISM_BACKEND_URL", "").strip().rstrip("/")
    explicit_port = os.getenv("PRISM_BACKEND_PORT", "").strip()
    if explicit_url:
        from urllib.parse import urlsplit
        parsed = urlsplit(explicit_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("PRISM_BACKEND_URL must be an absolute http(s) URL")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        host = parsed.hostname or host
        url = explicit_url
        source = "PRISM_BACKEND_URL"
    elif explicit_port:
        port = int(explicit_port)
        if not 1 <= port <= 65535:
            raise ValueError("PRISM_BACKEND_PORT must be between 1 and 65535")
        url = f"http://{host}:{port}"
        source = "PRISM_BACKEND_PORT"
    else:
        port = next((candidate for candidate in range(7000, 7100) if port_available(host, candidate)), None)
        if port is None:
            raise RuntimeError("No free backend port in 7000-7099")
        url = f"http://{host}:{port}"
        source = "auto"
    state = {"backend_host": host, "backend_port": port, "backend_url": url, "source": source}
    RUNTIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = RUNTIME_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(RUNTIME_FILE)
    return state


def wait_for_health(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=2) as response:
                if response.status < 400:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Backend health check timed out: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "health", "env"))
    parser.add_argument("--timeout", type=float, default=45)
    args = parser.parse_args()
    if args.command == "prepare":
        state = select_endpoint()
    else:
        state = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
    if args.command == "health":
        wait_for_health(state["backend_url"], args.timeout)
    elif args.command == "env":
        print(f"PRISM_BACKEND_HOST={state['backend_host']}")
        print(f"PRISM_BACKEND_PORT={state['backend_port']}")
        print(f"PRISM_BACKEND_URL={state['backend_url']}")
        print(f"NEXT_PUBLIC_BACKEND_URL={state['backend_url']}")
    else:
        print(json.dumps(state))
    return 0


if __name__ == "__main__":
    sys.exit(main())
