"""Cross-platform Prism process manager.

Stdlib-only orchestration for Prism's backend processes, adapted for macOS
first but working on Windows and Linux too. Replaces the fragmented Windows
``scripts/launchers/*.bat`` with a single command::

    python -m utils.process_manager start|stop|restart|status|logs|list

PIDs and logs live under ``<repo>/logs/run`` so they never enter git.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "prism_backend"
FRONTEND_ROOT = REPO_ROOT / "prism_frontend"
HERMES_SOURCE = REPO_ROOT / "tools" / "hermes-agent"
HERMES_HOME = REPO_ROOT / "tools" / "hermes-home"
HERMES_WEBUI = REPO_ROOT / "tools" / "hermes-webui"
LOG_DIR = REPO_ROOT / "logs"
RUN_DIR = LOG_DIR / "run"

IS_WINDOWS = sys.platform == "win32"

# Service registry order matters for start/stop sequencing.
SERVICE_NAMES = (
    "redis", "worker", "backend", "celery",
    "hermes-dashboard", "hermes-webui", "frontend",
)

DEFAULT_PORTS: Dict[str, int] = {
    "backend": 9200,
    "worker": 7001,
    "frontend": 3000,
    "redis": 6379,
    "hermes-dashboard": 9119,
    "hermes-webui": 9131,
}


@dataclass
class Service:
    name: str
    cwd: Path
    cmd: List[str]
    port: Optional[int]
    health_path: Optional[str]
    optional: bool = False
    env_extra: Dict[str, str] = field(default_factory=dict)

    @property
    def pid_file(self) -> Path:
        return RUN_DIR / f"{self.name}.pid"

    @property
    def log_file(self) -> Path:
        return LOG_DIR / f"{self.name}.log"

    def is_available(self) -> bool:
        """A service is unavailable when a required executable is missing."""
        if not self.cmd:
            return False
        exe = self.cmd[0]
        if os.path.isabs(exe):
            return Path(exe).exists()
        return shutil.which(exe) is not None


def _which_python() -> Optional[str]:
    """Resolve the Python interpreter to run backend services."""
    override = os.getenv("PRISM_PYTHON")
    if override and Path(override).exists():
        return override

    candidates: List[Path] = []
    if IS_WINDOWS:
        candidates += [
            REPO_ROOT / "prismenv" / "Scripts" / "python.exe",
            REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        ]
    else:
        candidates += [
            # Backend runtime first; prismenv is the Hermes-only runtime on
            # macOS/Linux and lacks the Prism backend deps.
            REPO_ROOT / ".venv_test" / "bin" / "python",
            REPO_ROOT / ".venv" / "bin" / "python",
            REPO_ROOT / "prismenv" / "bin" / "python",
        ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _which_node() -> Optional[str]:
    override = os.getenv("PRISM_NODE")
    if override and Path(override).exists():
        return override
    return shutil.which("node")


def _next_bin() -> Optional[str]:
    # Prefer the real Next.js entry over the npm `.bin` shim (the shim is a
    # POSIX shell wrapper on macOS/Linux and cannot be run via `node`).
    entry = FRONTEND_ROOT / "node_modules" / "next" / "dist" / "bin" / "next"
    if entry.exists():
        return str(entry)
    return shutil.which("next")


def _hermes_python() -> Optional[str]:
    """Resolve the Hermes runtime interpreter (prismenv)."""
    override = os.getenv("PRISM_HERMES_PYTHON")
    if override and Path(override).exists():
        return override
    if IS_WINDOWS:
        candidate = REPO_ROOT / "prismenv" / "Scripts" / "python.exe"
    else:
        candidate = REPO_ROOT / "prismenv" / "bin" / "python"
    return str(candidate) if candidate.exists() else None


def _hermes_bootstrap(source: str, *cli_args: str) -> str:
    return (
        "import runpy, sys; "
        f"sys.path.insert(0, {source!r}); "
        "runpy.run_module('hermes_cli.main', run_name='__main__')"
    )


def _base_env() -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    # Never trigger a browser download at startup; use the system Chrome
    # (see utils.chrome_detector) instead.
    env["PLAYWRIGHT_AUTO_INSTALL"] = "0"
    env.setdefault("PLAYWRIGHT_HEADLESS", "true")
    env["PYTHONPATH"] = str(BACKEND_ROOT)
    return env


def build_services(dev_frontend: bool = False) -> Dict[str, Service]:
    python = _which_python()
    node = _which_node()
    next_bin = _next_bin()

    services: Dict[str, Service] = {}

    redis_exe = shutil.which("redis-server")
    services["redis"] = Service(
        name="redis",
        cwd=REPO_ROOT,
        cmd=[redis_exe] if redis_exe else [],
        port=DEFAULT_PORTS["redis"],
        health_path=None,
        optional=True,
    )

    if python:
        services["worker"] = Service(
            name="worker",
            cwd=BACKEND_ROOT,
            cmd=[python, str(BACKEND_ROOT / "automation_worker" / "worker.py")],
            port=DEFAULT_PORTS["worker"],
            health_path="/health",
        )
        services["backend"] = Service(
            name="backend",
            cwd=BACKEND_ROOT,
            cmd=[python, str(BACKEND_ROOT / "fastapi_app" / "run.py")],
            port=DEFAULT_PORTS["backend"],
            health_path="/health",
        )
        services["celery"] = Service(
            name="celery",
            cwd=BACKEND_ROOT,
            cmd=[
                python,
                "-m",
                "celery",
                "-A",
                "fastapi_app.tasks.celery_app.celery_app",
                "worker",
                "--loglevel=info",
                "--pool=threads",
                "--concurrency=8",
            ],
            port=None,
            health_path=None,
            optional=True,
        )
    else:
        services["worker"] = Service("worker", BACKEND_ROOT, [], DEFAULT_PORTS["worker"], "/health", optional=True)
        services["backend"] = Service("backend", BACKEND_ROOT, [], DEFAULT_PORTS["backend"], "/health", optional=True)
        services["celery"] = Service("celery", BACKEND_ROOT, [], None, None, optional=True)

    if node and next_bin:
        frontend_args = ["dev"] if dev_frontend else ["start"]
        services["frontend"] = Service(
            name="frontend",
            cwd=FRONTEND_ROOT,
            cmd=[node, next_bin, *frontend_args, "-p", str(DEFAULT_PORTS["frontend"])],
            port=DEFAULT_PORTS["frontend"],
            health_path="/",
        )
    else:
        services["frontend"] = Service("frontend", FRONTEND_ROOT, [], DEFAULT_PORTS["frontend"], "/", optional=True)

    # Hermes agent UI surfaces (dashboard + webui). These run under the
    # separate prismenv runtime and are optional when Hermes is not installed.
    hermes_python = _hermes_python()
    hermes_dashboard_port = DEFAULT_PORTS["hermes-dashboard"]
    hermes_webui_port = DEFAULT_PORTS["hermes-webui"]

    hermes_base_env = {
        "HERMES_HOME": str(HERMES_HOME),
        "HERMES_CONFIG_PATH": str(HERMES_HOME / "config.yaml"),
        "HERMES_YOLO_MODE": "1",
    }

    if hermes_python and HERMES_SOURCE.exists():
        services["hermes-dashboard"] = Service(
            name="hermes-dashboard",
            cwd=HERMES_SOURCE,
            cmd=[
                hermes_python,
                "-c",
                _hermes_bootstrap(str(HERMES_SOURCE)),
                "dashboard",
                "--host",
                "127.0.0.1",
                "--port",
                str(hermes_dashboard_port),
                "--no-open",
                "--skip-build",
            ],
            port=hermes_dashboard_port,
            health_path="/",
            optional=True,
            env_extra={
                **hermes_base_env,
                "PYTHONPATH": str(HERMES_SOURCE),
                "HERMES_WEB_DIST": str(HERMES_SOURCE / "hermes_cli" / "web_dist"),
            },
        )
        services["hermes-webui"] = Service(
            name="hermes-webui",
            cwd=HERMES_WEBUI,
            cmd=[
                hermes_python,
                "-c",
                (
                    "import runpy, sys; "
                    f"sys.path.insert(0, {str(HERMES_WEBUI)!r}); "
                    f"sys.path.insert(0, {str(HERMES_SOURCE)!r}); "
                    f"runpy.run_path({str(HERMES_WEBUI / 'server.py')!r}, run_name='__main__')"
                ),
            ],
            port=hermes_webui_port,
            health_path="/?prism_shell_health=1",
            optional=True,
            env_extra={
                **hermes_base_env,
                "PYTHONPATH": os.pathsep.join([str(HERMES_WEBUI), str(HERMES_SOURCE)]),
                "HERMES_WEBUI_AGENT_DIR": str(HERMES_SOURCE),
                "HERMES_WEBUI_HOST": "127.0.0.1",
                "HERMES_WEBUI_PORT": str(hermes_webui_port),
                "HERMES_WEBUI_PYTHON": hermes_python,
                "HERMES_WEBUI_STATE_DIR": str(HERMES_HOME / "webui"),
                "HERMES_WEBUI_DEFAULT_WORKSPACE": str(REPO_ROOT),
                "HERMES_SKIP_CHMOD": "1",
            },
        )
    else:
        services["hermes-dashboard"] = Service(
            "hermes-dashboard", HERMES_SOURCE, [], hermes_dashboard_port, "/", optional=True,
        )
        services["hermes-webui"] = Service(
            "hermes-webui", HERMES_WEBUI, [], hermes_webui_port, "/?prism_shell_health=1", optional=True,
        )

    return services


def _read_pid(pid_file: Path) -> Optional[int]:
    try:
        raw = pid_file.read_text(encoding="utf-8").strip()
        return int(raw) if raw else None
    except (OSError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _port_in_use(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.4)
            return sock.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2.0) as resp:
            return 200 <= resp.status < 500
    except (urllib.error.URLError, OSError):
        return False


def is_running(svc: Service) -> bool:
    pid = _read_pid(svc.pid_file)
    pid_alive = pid is not None and _pid_alive(pid)
    if svc.port is not None:
        return _port_in_use(svc.port) or pid_alive
    return pid_alive


def start_service(svc: Service, env: Dict[str, str]) -> bool:
    if is_running(svc):
        print(f"[{svc.name}] already running")
        return True
    if not svc.is_available():
        if svc.optional:
            print(f"[{svc.name}] skipped (executable not found)")
            return True
        print(f"[{svc.name}] FAILED: executable not found: {svc.cmd[:1] or '(unset)'}", file=sys.stderr)
        return False

    service_env = dict(env)
    service_env.update(svc.env_extra)

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    log = open(svc.log_file, "ab", buffering=0)
    kwargs: Dict[str, object] = {
        "cwd": str(svc.cwd),
        "env": service_env,
        "stdout": log,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
    }
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(svc.cmd, **kwargs)
    except OSError as exc:
        log.close()
        print(f"[{svc.name}] FAILED to spawn: {exc}", file=sys.stderr)
        return False

    svc.pid_file.write_text(str(proc.pid), encoding="utf-8")
    print(f"[{svc.name}] started (pid={proc.pid}, log={svc.log_file})")
    return True


def stop_service(svc: Service) -> bool:
    pid = _read_pid(svc.pid_file)
    if pid is not None and _pid_alive(pid):
        try:
            if IS_WINDOWS:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            time.sleep(0.6)
        except (OSError, ProcessLookupError):
            pass
    svc.pid_file.unlink(missing_ok=True)
    if svc.port is not None and _port_in_use(svc.port):
        print(f"[{svc.name}] still bound to port {svc.port} after stop", file=sys.stderr)
        return False
    print(f"[{svc.name}] stopped")
    return True


def _select_services(names: Optional[Sequence[str]], services: Dict[str, Service]) -> List[Service]:
    if names:
        unknown = [n for n in names if n not in services]
        if unknown:
            raise ValueError(f"unknown service(s): {', '.join(unknown)}")
        return [services[n] for n in SERVICE_NAMES if n in names]
    return [services[n] for n in SERVICE_NAMES if n in services]


def cmd_start(names: Optional[Sequence[str]], dev_frontend: bool) -> int:
    services = build_services(dev_frontend=dev_frontend)
    env = _base_env()
    selected = _select_services(names, services)
    failed = 0
    for svc in selected:
        if not start_service(svc, env):
            failed += 1
        time.sleep(0.4)
    return 1 if failed else 0


def cmd_stop(names: Optional[Sequence[str]]) -> int:
    services = build_services()
    selected = _select_services(names, services)
    for svc in reversed(selected):
        stop_service(svc)
    return 0


def cmd_restart(names: Optional[Sequence[str]], dev_frontend: bool) -> int:
    cmd_stop(names)
    time.sleep(0.5)
    return cmd_start(names, dev_frontend)


def cmd_status(names: Optional[Sequence[str]]) -> int:
    services = build_services()
    selected = _select_services(names, services)
    for svc in selected:
        pid = _read_pid(svc.pid_file)
        port_state = f":{svc.port}" if svc.port else ""
        running = is_running(svc)
        state = "running" if running else "stopped"
        print(f"[{svc.name}] {state} (pid={pid or '-'}{port_state})")
    return 0


def cmd_logs(name: Optional[str], follow: bool, lines: int) -> int:
    if not name:
        print("Usage: logs <service> [--follow] [--lines N]", file=sys.stderr)
        print("Available:", ", ".join(SERVICE_NAMES), file=sys.stderr)
        return 2
    svc = build_services().get(name)
    if svc is None:
        print(f"unknown service: {name}", file=sys.stderr)
        return 2

    if not svc.log_file.exists():
        print(f"[{name}] no log file yet: {svc.log_file}")
        return 0

    if follow:
        with open(svc.log_file, "rb") as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if line:
                    sys.stdout.buffer.write(line)
                    sys.stdout.buffer.flush()
                else:
                    time.sleep(0.3)
    else:
        data = svc.log_file.read_bytes().splitlines()
        for line in data[-lines:]:
            sys.stdout.buffer.write(line + b"\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prism service", description="Prism 跨平台进程管理")
    sub = parser.add_subparsers(dest="command", required=True)

    for cmd_name in ("start", "stop", "restart", "status"):
        p = sub.add_parser(cmd_name, help=f"{cmd_name} services")
        p.add_argument("names", nargs="*", help="service names (default: all)")

    start_p = sub.choices["start"]
    restart_p = sub.choices["restart"]
    for p in (start_p, restart_p):
        p.add_argument("--dev", action="store_true", help="frontend uses `next dev` instead of `next start`")

    logs_p = sub.add_parser("logs", help="tail service logs")
    logs_p.add_argument("name", nargs="?", help="service name")
    logs_p.add_argument("-f", "--follow", action="store_true", help="follow output")
    logs_p.add_argument("-n", "--lines", type=int, default=50, help="lines to show (default 50)")

    sub.add_parser("list", help="list services and availability")
    return parser


def cmd_list() -> int:
    services = build_services()
    for name in SERVICE_NAMES:
        svc = services.get(name)
        if svc is None:
            continue
        available = svc.is_available()
        running = is_running(svc)
        port = f":{svc.port}" if svc.port else ""
        tag = "optional" if svc.optional else "core"
        print(f"{name:<10} {tag:<8} available={'yes' if available else 'no':<4} running={'yes' if running else 'no':<4}{port}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command

    if command == "list":
        return cmd_list()
    if command == "start":
        return cmd_start(args.names, getattr(args, "dev", False))
    if command == "stop":
        return cmd_stop(args.names)
    if command == "restart":
        return cmd_restart(args.names, getattr(args, "dev", False))
    if command == "status":
        return cmd_status(args.names)
    if command == "logs":
        return cmd_logs(args.name, args.follow, args.lines)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
