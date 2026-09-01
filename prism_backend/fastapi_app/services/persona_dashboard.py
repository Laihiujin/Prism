"""
Persona Studio Dashboard 托管服务（内嵌进 Prism 前端用）。

Persona Studio 自带一个独立 Vite + React Dashboard（tools/persona-studio/dashboard/），
它通过 HTTP 与 persona serve API（:8787）通信。本模块负责把该 Dashboard 作为一个
子进程拉起/停止/探测，供 Prism 前端 iframe 内嵌（类似 Hermes WebUI 的内嵌方式）。

启动方式：
    node node_modules/vite/bin/vite.js --no-open --host 127.0.0.1 --port 5173

注意：
- vite.config.js 里 server.open=true，启动时必须用 --no-open 覆盖，避免自动弹浏览器。
- dashboard 的 node_modules 缺失时先执行 npm install（一次性，可能耗时）。
- 本服务只管 Dashboard 前端进程；persona serve API（:8787）由 PM2 / persona-api 单独托管。
"""
from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from loguru import logger

from fastapi_app.core.config import settings

# Dashboard 目录（tools/persona-studio/dashboard）
BACKEND_ROOT = Path(__file__).resolve().parents[2]  # fastapi_app/../.. = prism_backend
REPO_ROOT = BACKEND_ROOT.parent
DASHBOARD_DIR = REPO_ROOT / "tools" / "persona-studio" / "dashboard"

# 与 dashboard/vite.config.js 保持一致
DASHBOARD_PORT = 5173
DASHBOARD_HOST = "127.0.0.1"

# 进程状态（单实例）
_dashboard_process: Optional[asyncio.subprocess.Process] = None
_dashboard_log_task: Optional[asyncio.Task[None]] = None


def _npm_command() -> str:
    return "npm.cmd" if sys.platform == "win32" else "npm"


def _dashboard_url() -> str:
    public_host = str(os.getenv("PRISM_PERSONA_DASHBOARD_HOST") or DASHBOARD_HOST).strip() or DASHBOARD_HOST
    return f"http://{public_host}:{DASHBOARD_PORT}"


def _is_local_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _is_pid_alive(pid: Optional[int]) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False
    except Exception:
        return False


async def _pump_dashboard_logs(process: asyncio.subprocess.Process) -> None:
    """把 Dashboard 子进程 stdout 转发到 Prism 日志，便于排查启动失败。"""
    assert process.stdout is not None
    while True:
        chunk = await process.stdout.readline()
        if not chunk:
            break
        line = chunk.decode("utf-8", errors="ignore").strip()
        if line:
            logger.info(f"[PersonaDashboard] {line}")


async def get_persona_dashboard_status() -> Dict[str, Any]:
    """返回 Dashboard 运行状态（进程存活或端口已监听即视为 running）。"""
    global _dashboard_process

    running = False
    pid: Optional[int] = None
    if _dashboard_process is not None and _dashboard_process.returncode is None:
        running = True
        pid = _dashboard_process.pid
    elif _is_local_port_open(DASHBOARD_PORT):
        running = True

    # persona serve API 是否在线（Dashboard 依赖它展示真实数据）
    api_online = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.PERSONA_API_URL}/api/health")
            api_online = resp.status_code == 200
    except Exception:
        api_online = False

    return {
        "running": running,
        "pid": pid if running and _is_pid_alive(pid) else None,
        "port": DASHBOARD_PORT,
        "url": _dashboard_url(),
        "api_online": api_online,
        "api_url": settings.PERSONA_API_URL,
        "dir": str(DASHBOARD_DIR),
    }


async def _ensure_dashboard_deps() -> None:
    """确保 dashboard 依赖已安装（node_modules 存在）。缺失时执行 npm install。"""
    if (DASHBOARD_DIR / "node_modules").is_dir():
        return
    if not (DASHBOARD_DIR / "package.json").is_file():
        raise RuntimeError(f"Persona Dashboard 目录缺失: {DASHBOARD_DIR}")

    logger.info(f"[PersonaDashboard] 首次启动，安装依赖: {DASHBOARD_DIR}")
    proc = await asyncio.create_subprocess_exec(
        _npm_command(),
        "install",
        cwd=str(DASHBOARD_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output_bytes, _ = await proc.communicate()
    if proc.returncode != 0:
        tail = output_bytes.decode("utf-8", errors="ignore")[-500:]
        raise RuntimeError(f"npm install 失败: {tail}")


async def start_persona_dashboard() -> Dict[str, Any]:
    """拉起 Persona Dashboard 子进程（幂等：已在运行则直接返回状态）。"""
    global _dashboard_process, _dashboard_log_task

    status = await get_persona_dashboard_status()
    if status["running"]:
        return status

    await _ensure_dashboard_deps()

    vite_bin = DASHBOARD_DIR / "node_modules" / "vite" / "bin" / "vite.js"
    if not vite_bin.is_file():
        raise RuntimeError(f"未找到 vite: {vite_bin}（请确认 npm install 完成）")

    env = dict(os.environ)
    env.setdefault("VITE_API_URL", settings.PERSONA_API_URL)

    process = await asyncio.create_subprocess_exec(
        "node",
        str(vite_bin),
        "--no-open",
        "--host",
        DASHBOARD_HOST,
        "--port",
        str(DASHBOARD_PORT),
        "--strictPort",
        cwd=str(DASHBOARD_DIR),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    _dashboard_process = process
    _dashboard_log_task = asyncio.create_task(_pump_dashboard_logs(process))

    # 等待端口就绪（最长 ~30s；Vite dev 冷启动较快，首次可能慢）
    for _ in range(60):
        if process.returncode is not None:
            break
        if _is_local_port_open(DASHBOARD_PORT):
            return await get_persona_dashboard_status()
        await asyncio.sleep(0.5)

    await stop_persona_dashboard()
    raise RuntimeError(
        "Persona Dashboard 启动失败。请检查 tools/persona-studio/dashboard 的依赖与 vite 是否可运行。"
    )


async def _stop_spawned_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                logger.warning("Timed out waiting for Persona Dashboard %s to exit", process.pid)
        else:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await asyncio.wait_for(process.wait(), timeout=5)
    except ProcessLookupError:
        pass
    except Exception as exc:
        logger.warning("Failed to stop Persona Dashboard %s cleanly: %s", process.pid, exc)


async def stop_persona_dashboard() -> Dict[str, Any]:
    """停止 Dashboard 子进程（进程由本服务拉起时才停，不抢占外部端口占用）。"""
    global _dashboard_process, _dashboard_log_task

    if _dashboard_process is not None and _dashboard_process.returncode is None:
        await _stop_spawned_process(_dashboard_process)

    if _dashboard_log_task is not None:
        try:
            await _dashboard_log_task
        except Exception:
            pass

    _dashboard_process = None
    _dashboard_log_task = None
    return await get_persona_dashboard_status()
