"""Project-local Hermes CLI bridge for the SynapseAutomation agent UI."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional

from loguru import logger

from .hermes_config import (
    build_hermes_pythonpath,
    detect_git_bash_path,
    ensure_runtime_ui_defaults,
    get_backend_root,
    get_hermes_dashboard_dist_path,
    get_hermes_home_path,
    get_hermes_python_path,
    get_hermes_source_path,
    get_hermes_webui_path,
    get_hermes_webui_state_path,
    get_runtime_summary,
    get_workspace_root,
    read_agent_config,
    sync_agent_config_to_runtime,
)


_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_dashboard_process: Optional[asyncio.subprocess.Process] = None
_dashboard_log_task: Optional[asyncio.Task[None]] = None
_dashboard_backend: Optional[str] = None
_webui_process: Optional[asyncio.subprocess.Process] = None
_webui_log_task: Optional[asyncio.Task[None]] = None
_project_tool_catalog_cache: Optional[List[Dict[str, Any]]] = None


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text).replace("\r", "").strip()


def _stringify_context(context: Optional[Dict[str, Any]]) -> str:
    if not context:
        return ""

    lines: List[str] = []
    for key, value in context.items():
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            rendered = str(value)
        lines.append(f"- {key}: {rendered}")
    return "\n".join(lines)


def _get_agent_api_base_url() -> str:
    candidate = os.getenv("AGENT_API_BASE_URL") or os.getenv("MANUS_API_BASE_URL") or "http://127.0.0.1:7000/api/v1"
    return str(candidate).rstrip("/")


def _collect_project_tool_catalog() -> List[Dict[str, Any]]:
    global _project_tool_catalog_cache
    if _project_tool_catalog_cache is not None:
        return _project_tool_catalog_cache

    from . import hermes_tools, hermes_tools_extended, hermes_tools_social_api, tikhub_tools
    from .tool_runtime import BaseTool

    catalog: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for module in (hermes_tools, hermes_tools_extended, hermes_tools_social_api, tikhub_tools):
        for value in vars(module).values():
            if not inspect.isclass(value):
                continue
            if not issubclass(value, BaseTool) or value is BaseTool:
                continue

            tool_name = str(getattr(value, "name", "")).strip()
            if not tool_name or tool_name in seen:
                continue

            parameters = getattr(value, "parameters", {}) or {}
            properties = parameters.get("properties", {}) if isinstance(parameters, dict) else {}
            catalog.append(
                {
                    "name": tool_name,
                    "description": " ".join(str(getattr(value, "description", "")).split()),
                    "parameters": list(properties.keys())[:8],
                }
            )
            seen.add(tool_name)

    catalog.sort(key=lambda item: item["name"])
    _project_tool_catalog_cache = catalog
    return catalog


def _build_project_capabilities_block() -> str:
    api_base = _get_agent_api_base_url()
    tools = _collect_project_tool_catalog()

    lines = [
        "Project capabilities:",
        f"- Workspace root: {get_workspace_root()}",
        f"- Backend API base: {api_base}",
        "- API docs: http://127.0.0.1:7000/api/docs",
        "- Frontend app: http://127.0.0.1:3000",
        "- Scripts directory: scripts/ and syn_backend/scripts/",
        "- Tool modules: syn_backend/fastapi_app/agent/hermes_tools*.py and tikhub_tools.py",
        "- Prefer using repo-local scripts, backend APIs, and project files before generic web actions.",
    ]

    if tools:
        lines.append("Project tool inventory:")
        for item in tools:
            params = ", ".join(item["parameters"]) if item["parameters"] else "no structured params"
            lines.append(f"- {item['name']}: {item['description']} [params: {params}]")

    return "\n".join(lines)


def _build_prompt(goal: str, context: Optional[Dict[str, Any]]) -> str:
    sections = [
        "You are Hermes Agent running inside the SynapseAutomation project.",
        f"Working directory: {get_workspace_root()}",
        "Answer in Chinese unless the user explicitly requests another language.",
        "You may use the Hermes CLI runtime together with the current repository, local scripts, and local backend APIs to complete the task.",
        _build_project_capabilities_block(),
    ]

    context_block = _stringify_context(context)
    if context_block:
        sections.append("Runtime context:\n" + context_block)

    sections.append("User goal:\n" + goal.strip())
    return "\n\n".join(sections)


def _ensure_runtime_home(config: Optional[Dict[str, Any]] = None) -> Path:
    home_path = get_hermes_home_path()
    home_path.mkdir(parents=True, exist_ok=True)

    config_yaml_path = home_path / "config.yaml"
    if config and config.get("llm"):
        sync_agent_config_to_runtime(config)
    elif not config_yaml_path.exists():
        config_yaml_path.write_text("{}\n", encoding="utf-8")

    env_path = home_path / ".env"
    if not env_path.exists():
        env_path.write_text("", encoding="utf-8")

    ensure_runtime_ui_defaults()
    return home_path


def _build_hermes_pythonpath() -> str:
    """Build a child-process PYTHONPATH without the backend utils shadowing Hermes."""
    return build_hermes_pythonpath(
        get_hermes_source_path(),
        base=os.environ.get("PYTHONPATH"),
        exclude=(get_backend_root(),),
    )


def _build_process_env(home_path: Path) -> Dict[str, str]:
    env = dict(os.environ)
    env["HERMES_HOME"] = str(home_path)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = _build_hermes_pythonpath()
    env["HERMES_CONFIG_PATH"] = str(home_path / "config.yaml")
    env["HERMES_YOLO_MODE"] = "1"
    env["AGENT_API_BASE_URL"] = _get_agent_api_base_url()
    env["SYNAPSE_WORKSPACE_ROOT"] = str(get_workspace_root())

    git_bash_path = detect_git_bash_path()
    if git_bash_path:
        env["HERMES_GIT_BASH_PATH"] = str(git_bash_path)

    return env


def _build_hermes_cli_bootstrap_args(*cli_args: str) -> List[str]:
    source_path = str(get_hermes_source_path())
    bootstrap = (
        "import runpy, sys; "
        f"sys.path.insert(0, {source_path!r}); "
        "runpy.run_module('hermes_cli.main', run_name='__main__')"
    )
    return ["-c", bootstrap, *cli_args]


def _build_run_path_bootstrap_args(script_path: Path, *sys_paths: str) -> List[str]:
    inserts = "".join(f"sys.path.insert(0, {path!r}); " for path in sys_paths if path)
    bootstrap = (
        "import runpy, sys; "
        f"{inserts}"
        f"runpy.run_path({str(script_path)!r}, run_name='__main__')"
    )
    return ["-c", bootstrap]


def _seed_webui_preferences(state_dir: Path) -> None:
    settings_path = state_dir / "settings.json"
    payload: Dict[str, Any] = {}

    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                payload.update(existing)
        except Exception:
            payload = {}

    if str(payload.get("theme") or "").strip().lower() not in {"light", "dark", "system"}:
        payload["theme"] = "dark"
    if str(payload.get("skin") or "").strip().lower() in {"", "default"}:
        payload["skin"] = "mono"
    if str(payload.get("language") or "").strip().lower() in {"", "en"}:
        payload["language"] = "zh"

    state_dir.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _dashboard_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def _get_runtime_port(env_key: str, fallback: int) -> int:
    raw = str(os.getenv(env_key) or "").strip()
    if not raw:
        return fallback
    try:
        port = int(raw)
    except ValueError:
        return fallback
    return port if 1 <= port <= 65535 else fallback


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


def _read_gateway_state() -> Dict[str, Any]:
    gateway_state_path = get_hermes_home_path() / "gateway_state.json"
    if not gateway_state_path.exists():
        return {}
    try:
        payload = json.loads(gateway_state_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _ensure_runtime_ready() -> Dict[str, Any]:
    config = read_agent_config()
    if not config.get("llm"):
        raise ValueError("Hermes Agent 尚未配置。请先在 /ai-agent/settings 保存模型配置。")

    runtime_summary = get_runtime_summary()
    if not runtime_summary.get("agent_installed"):
        wrapper_path = runtime_summary.get("wrapper_path") or "scripts\\hermes\\setup-local-hermes.ps1"
        raise ValueError(f"项目内 Hermes CLI 尚未安装。请先运行 {wrapper_path}")

    home_path = _ensure_runtime_home(config)
    runtime_summary["home_path"] = str(home_path)
    return runtime_summary


class HermesAgentWrapper:
    """Adapter that invokes the official Hermes CLI from a project-local venv."""

    def __init__(self) -> None:
        self._initialized = False

    async def initialize(self) -> None:
        _ensure_runtime_ready()
        self._initialized = True
        logger.info("Hermes CLI runtime is ready.")

    async def _run_non_interactive(
        self,
        prompt: str,
        env: Dict[str, str],
        cwd: Path,
    ) -> Dict[str, Any]:
        python_path = get_hermes_python_path()
        process = await asyncio.create_subprocess_exec(
            str(python_path),
            *_build_hermes_cli_bootstrap_args("-z", prompt),
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        output_bytes, _ = await process.communicate()
        output = _strip_ansi(output_bytes.decode("utf-8", errors="ignore"))

        if process.returncode != 0:
            raise RuntimeError(output or f"Hermes CLI exited with code {process.returncode}")

        return {
            "success": True,
            "result": output,
            "steps": [],
            "error": None,
            "stopped": False,
        }

    async def _run_streaming(
        self,
        prompt: str,
        env: Dict[str, str],
        cwd: Path,
        event_handler: Callable[[Dict[str, Any]], Any],
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        python_path = get_hermes_python_path()
        config = read_agent_config()
        runtime = config.get("runtime") or {}
        max_turns = str(int(runtime.get("max_turns") or 12))

        process = await asyncio.create_subprocess_exec(
            str(python_path),
            *_build_hermes_cli_bootstrap_args(
                "chat",
                "-q",
                prompt,
                "--source",
                "tool",
                "--max-turns",
                max_turns,
            ),
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        transcript_parts: List[str] = []
        stopped = False

        assert process.stdout is not None

        async def _read_stdout() -> None:
            nonlocal transcript_parts
            while True:
                chunk = await process.stdout.readline()
                if not chunk:
                    break
                line = _strip_ansi(chunk.decode("utf-8", errors="ignore"))
                if not line:
                    continue
                transcript_parts.append(line)
                await event_handler(
                    {
                        "type": "assistant_message",
                        "content": "\n".join(transcript_parts),
                    }
                )

        reader_task = asyncio.create_task(_read_stdout())

        try:
            while True:
                if should_stop and should_stop():
                    stopped = True
                    process.kill()
                    break
                try:
                    await asyncio.wait_for(process.wait(), timeout=0.25)
                    break
                except asyncio.TimeoutError:
                    continue
        finally:
            await reader_task
            if process.returncode is None:
                await process.wait()

        transcript = "\n".join(transcript_parts).strip()

        if stopped:
            return {
                "success": False,
                "result": transcript,
                "steps": [],
                "error": "Task stopped by user",
                "stopped": True,
            }

        if process.returncode != 0:
            raise RuntimeError(transcript or f"Hermes CLI exited with code {process.returncode}")

        return {
            "success": True,
            "result": transcript,
            "steps": [],
            "error": None,
            "stopped": False,
        }

    async def run_goal(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        event_handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        if not self._initialized:
            await self.initialize()

        runtime_summary = _ensure_runtime_ready()
        prompt = _build_prompt(goal, context)
        cwd = get_workspace_root()
        env = _build_process_env(Path(runtime_summary["home_path"]))

        if event_handler is None:
            return await self._run_non_interactive(prompt=prompt, env=env, cwd=cwd)

        return await self._run_streaming(
            prompt=prompt,
            env=env,
            cwd=cwd,
            event_handler=event_handler,
            should_stop=should_stop,
        )

    async def cleanup(self) -> None:
        self._initialized = False


_hermes_agent_instance: Optional[HermesAgentWrapper] = None


async def get_hermes_agent() -> HermesAgentWrapper:
    global _hermes_agent_instance
    if _hermes_agent_instance is None:
        _hermes_agent_instance = HermesAgentWrapper()
        await _hermes_agent_instance.initialize()
    return _hermes_agent_instance


async def reset_hermes_agent() -> None:
    global _hermes_agent_instance
    if _hermes_agent_instance is not None:
        await _hermes_agent_instance.cleanup()
    _hermes_agent_instance = None


async def run_hermes_goal(
    goal: str,
    context: Optional[Dict[str, Any]] = None,
    event_handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    agent = await get_hermes_agent()
    return await agent.run_goal(
        goal=goal,
        context=context,
        event_handler=event_handler,
        should_stop=should_stop,
    )


async def _pump_dashboard_logs(
    process: asyncio.subprocess.Process,
    *,
    label: Optional[str] = None,
) -> None:
    backend = label or _dashboard_backend or "dashboard"
    assert process.stdout is not None
    while True:
        chunk = await process.stdout.readline()
        if not chunk:
            break
        line = _strip_ansi(chunk.decode("utf-8", errors="ignore"))
        if line:
            logger.info(f"[Hermes:{backend}] {line}")


def _resolve_dashboard_backend(
    runtime: Dict[str, Any],
    requested_backend: Optional[Literal["official", "webui"]] = None,
) -> Optional[str]:
    if requested_backend == "official" and runtime.get("official_dashboard_installed"):
        return "official"
    if requested_backend == "webui" and runtime.get("webui_installed"):
        return "webui"

    preferred = runtime.get("preferred_dashboard_backend")
    if preferred in {"official", "webui"}:
        return str(preferred)
    return None


async def get_hermes_runtime_status(
    port: Optional[int] = None,
    webui_port: Optional[int] = None,
) -> Dict[str, Any]:
    global _dashboard_process, _dashboard_backend, _webui_process

    port = port if isinstance(port, int) and port > 0 else _get_runtime_port("SYNAPSE_HERMES_DASHBOARD_PORT", 9119)
    webui_port = (
        webui_port
        if isinstance(webui_port, int) and webui_port > 0
        else _get_runtime_port("SYNAPSE_HERMES_WEBUI_PORT", 9131)
    )

    runtime = get_runtime_summary()
    running = False
    if _dashboard_process is not None and _dashboard_process.returncode is None:
        running = True
    elif _is_local_port_open(port):
        running = True

    webui_running = False
    if _webui_process is not None and _webui_process.returncode is None:
        webui_running = True
    elif _is_local_port_open(webui_port):
        webui_running = True

    url = _dashboard_url(port)
    webui_url = _dashboard_url(webui_port)
    gateway_state = _read_gateway_state()
    gateway_pid = gateway_state.get("pid")
    gateway_platform_configured = bool(runtime.get("gateway_platform_configured"))
    gateway_running = (
        _is_pid_alive(gateway_pid if isinstance(gateway_pid, int) else None)
        if gateway_platform_configured
        else False
    )
    gateway_state_label = (
        str(gateway_state.get("gateway_state") or "stopped")
        if gateway_platform_configured
        else "not_configured"
    )
    runtime.update(
        {
            "gateway_running": gateway_running,
            "gateway_pid": gateway_pid if gateway_running and isinstance(gateway_pid, int) else None,
            "gateway_state": gateway_state_label,
            "gateway_restart_requested": bool(gateway_state.get("restart_requested")),
            "dashboard_port": port,
            "dashboard_url": url,
            "dashboard_running": running,
            "dashboard_backend": "official" if running else "official",
            "webui_port": webui_port,
            "webui_url": webui_url,
            "webui_running": webui_running,
            "webui_backend": "webui" if webui_running else "webui",
        }
    )
    return runtime


async def _start_dashboard_backend(
    backend: Literal["official", "webui"],
    port: int,
) -> Dict[str, Any]:
    global _dashboard_process, _dashboard_log_task, _dashboard_backend, _webui_process, _webui_log_task

    runtime = get_runtime_summary()
    if not runtime.get("agent_installed"):
        raise RuntimeError("Hermes Agent CLI 尚未安装，请先运行 scripts\\hermes\\setup-local-hermes.ps1。")
    if backend == "official" and not runtime.get("official_dashboard_installed"):
        raise RuntimeError("Hermes Dashboard is not installed. Run scripts\\hermes\\setup-local-hermes.ps1 first.")
    if backend == "webui" and not runtime.get("webui_installed"):
        raise RuntimeError("Hermes WebUI is not installed. Run scripts\\hermes\\setup-local-hermes.ps1 first.")
    if backend == "official":
        if _dashboard_process is not None and _dashboard_process.returncode is None:
            return await get_hermes_runtime_status(port)
        if _is_local_port_open(port):
            _dashboard_backend = backend
            return await get_hermes_runtime_status(port)
    else:
        if _webui_process is not None and _webui_process.returncode is None:
            return await get_hermes_runtime_status()
        if _is_local_port_open(port):
            return await get_hermes_runtime_status()

    config = read_agent_config()
    home_path = _ensure_runtime_home(config if config.get("llm") else None)
    webui_state_path = get_hermes_webui_state_path()
    workspace_root = get_workspace_root()

    webui_state_path.mkdir(parents=True, exist_ok=True)
    workspace_root.mkdir(parents=True, exist_ok=True)
    _seed_webui_preferences(webui_state_path)

    env = _build_process_env(home_path)
    if backend == "official":
        source_path = get_hermes_source_path()
        dashboard_dist_path = get_hermes_dashboard_dist_path()
        env["HERMES_WEB_DIST"] = str(dashboard_dist_path)
        process = await asyncio.create_subprocess_exec(
            str(get_hermes_python_path()),
            *_build_hermes_cli_bootstrap_args(
                "dashboard",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-open",
                "--skip-build",
            ),
            cwd=str(source_path),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    else:
        webui_path = get_hermes_webui_path()
        env["HERMES_WEBUI_AGENT_DIR"] = str(get_hermes_source_path())
        env["HERMES_WEBUI_HOST"] = "127.0.0.1"
        env["HERMES_WEBUI_PORT"] = str(port)
        env["HERMES_WEBUI_PYTHON"] = str(get_hermes_python_path())
        env["HERMES_WEBUI_STATE_DIR"] = str(webui_state_path)
        env["HERMES_WEBUI_DEFAULT_WORKSPACE"] = str(workspace_root)
        env.setdefault("HERMES_SKIP_CHMOD", "1")
        process = await asyncio.create_subprocess_exec(
            str(get_hermes_python_path()),
            *_build_run_path_bootstrap_args(
                webui_path / "server.py",
                str(webui_path),
                str(get_hermes_source_path()),
            ),
            cwd=str(webui_path),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

    if backend == "official":
        _dashboard_backend = backend
        _dashboard_process = process
        _dashboard_log_task = asyncio.create_task(_pump_dashboard_logs(process, label="dashboard"))
    else:
        _webui_process = process
        _webui_log_task = asyncio.create_task(_pump_dashboard_logs(process, label="webui"))

    for _ in range(40):
        if process.returncode is not None:
            break
        if _is_local_port_open(port):
            return await get_hermes_runtime_status(port if backend == "official" else 9119)
        await asyncio.sleep(0.5)

    await stop_hermes_dashboard(backend)
    if backend == "official":
        raise RuntimeError("Hermes Dashboard 启动失败，请检查本地运行时、web_dist 和 dashboard 依赖。")
    raise RuntimeError("Hermes WebUI 启动失败，请检查本地运行时和依赖。")


async def start_hermes_dashboard(
    port: int = 9119,
    backend_override: Optional[Literal["official", "webui"]] = None,
) -> Dict[str, Any]:
    runtime = get_runtime_summary()
    backend = _resolve_dashboard_backend(runtime, backend_override)
    if backend is None:
        raise RuntimeError("Hermes dashboard backend is not installed. Run scripts\\hermes\\setup-local-hermes.ps1 first.")
    return await _start_dashboard_backend(backend, port)


async def start_hermes_interfaces(
    dashboard_port: int = 9119,
    webui_port: int = 9131,
) -> Dict[str, Any]:
    await _start_dashboard_backend("official", dashboard_port)
    return await _start_dashboard_backend("webui", webui_port)


async def _stop_spawned_process(
    process: asyncio.subprocess.Process,
    *,
    label: str,
) -> None:
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
                logger.warning("Timed out waiting for Hermes %s process %s to exit", label, process.pid)
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
        logger.warning("Failed to stop Hermes %s process %s cleanly: %s", label, process.pid, exc)


async def stop_hermes_dashboard(
    backend: Optional[Literal["official", "webui"]] = None,
) -> Dict[str, Any]:
    global _dashboard_process, _dashboard_log_task, _dashboard_backend, _webui_process, _webui_log_task

    if backend in (None, "official"):
        if _dashboard_process is not None and _dashboard_process.returncode is None:
            await _stop_spawned_process(_dashboard_process, label="dashboard")

        if _dashboard_log_task is not None:
            try:
                await _dashboard_log_task
            except Exception:
                pass

        _dashboard_process = None
        _dashboard_log_task = None

    if backend in (None, "webui"):
        if _webui_process is not None and _webui_process.returncode is None:
            await _stop_spawned_process(_webui_process, label="webui")

        if _webui_log_task is not None:
            try:
                await _webui_log_task
            except Exception:
                pass

        _webui_process = None
        _webui_log_task = None

    if backend in (None, "official"):
        _dashboard_backend = None
    return await get_hermes_runtime_status()
