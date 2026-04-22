#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Supervisor for packaged backend services.

Production mode prefers packaged service executables under resources/services.
Python script fallback is kept only for local/dev usage.
"""

from __future__ import annotations

import io
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

LOG_MAX_BYTES = 50 * 1024 * 1024
LOG_BACKUP_COUNT = 3

_SUPERVISOR_DIR = Path(__file__).resolve().parent
if str(_SUPERVISOR_DIR) not in sys.path:
    sys.path.insert(0, str(_SUPERVISOR_DIR))

_LOGS_DIR = Path("logs")
_LOGS_DIR.mkdir(exist_ok=True)
_LOG_FORMATTER = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")

_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(_LOG_FORMATTER)

_file_handler = RotatingFileHandler(
    _LOGS_DIR / "supervisor.log",
    maxBytes=LOG_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT,
    encoding="utf-8",
    errors="replace",
)
_file_handler.setFormatter(_LOG_FORMATTER)

logger = logging.getLogger("supervisor")
logger.setLevel(logging.INFO)
logger.handlers = [_stream_handler, _file_handler]
logger.propagate = False


class ProcessManager:
    def __init__(self) -> None:
        self.processes: Dict[str, subprocess.Popen] = {}
        self.process_loggers: Dict[str, logging.Logger] = {}
        self.process_log_handlers: Dict[str, RotatingFileHandler] = {}
        self.log_threads: Dict[str, threading.Thread] = {}
        self.should_stop = False

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame) -> None:  # noqa: ANN001
        logger.info("Received signal %s, shutting down...", signum)
        self.should_stop = True
        self.stop_all()
        sys.exit(0)

    def _setup_process_logger(self, name: str) -> logging.Logger:
        proc_logger = logging.getLogger(f"process.{name}")
        proc_logger.setLevel(logging.INFO)
        proc_logger.propagate = False

        old_handler = self.process_log_handlers.pop(name, None)
        if old_handler:
            try:
                proc_logger.removeHandler(old_handler)
            except Exception:
                pass
            old_handler.close()

        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        handler = RotatingFileHandler(
            logs_dir / f"{name}.log",
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
            errors="replace",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        proc_logger.handlers = [handler]
        self.process_log_handlers[name] = handler
        self.process_loggers[name] = proc_logger
        return proc_logger

    def _cleanup_process_logger(self, name: str) -> None:
        handler = self.process_log_handlers.pop(name, None)
        proc_logger = self.process_loggers.pop(name, None)
        if handler:
            if proc_logger:
                try:
                    proc_logger.removeHandler(handler)
                except Exception:
                    pass
            handler.close()

    def _start_log_thread(self, name: str, proc: subprocess.Popen) -> None:
        if name in self.log_threads or not proc.stdout:
            return

        proc_logger = self._setup_process_logger(name)

        def _reader() -> None:
            try:
                for line in proc.stdout:
                    if line:
                        proc_logger.info(line.rstrip("\r\n"))
            except Exception as exc:
                logger.error("[%s] log stream error: %s", name, exc)
            finally:
                try:
                    proc.stdout.close()
                except Exception:
                    pass

        thread = threading.Thread(target=_reader, name=f"{name}-logger", daemon=True)
        self.log_threads[name] = thread
        thread.start()

    def start_process(self, name: str, cmd: List[str], cwd: str, env: Dict[str, str]) -> bool:
        try:
            logger.info("Starting %s...", name)
            logger.info("  Command: %s", " ".join(cmd))
            logger.info("  Working dir: %s", cwd)

            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            self.processes[name] = proc
            self._start_log_thread(name, proc)
            logger.info("%s started successfully (PID: %s)", name, proc.pid)
            return True
        except Exception as exc:
            logger.error("%s failed to start: %s", name, exc)
            return False

    def is_running(self, name: str) -> bool:
        proc = self.processes.get(name)
        return proc is not None and proc.poll() is None

    def stop_process(self, name: str, timeout: int = 10) -> None:
        proc = self.processes.get(name)
        if not proc:
            return

        logger.info("Stopping %s...", name)
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
        finally:
            thread = self.log_threads.pop(name, None)
            if thread:
                thread.join(timeout=2)
            self._cleanup_process_logger(name)
            self.processes.pop(name, None)

    def stop_all(self) -> None:
        logger.info("Stopping all managed services...")
        stop_order = ["celery-worker", "backend", "playwright-worker", "redis"]
        for name in stop_order:
            if name in self.processes:
                self.stop_process(name)
        for name in list(self.processes.keys()):
            self.stop_process(name)


class Supervisor:
    def __init__(self) -> None:
        self.manager = ProcessManager()
        self.service_ports = {"backend": 7000, "playwright-worker": 7001}
        self.external_services: Dict[str, bool] = {}
        self.kill_port_conflict = os.environ.get("SUPERVISOR_KILL_PORT_CONFLICT", "1") != "0"

        env_resources_path = os.environ.get("SYNAPSE_RESOURCES_PATH") or os.environ.get("SYNAPSE_APP_ROOT")
        if env_resources_path:
            self.resources_path = Path(env_resources_path)
            self.is_packaged = True
        elif getattr(sys, "frozen", False):
            self.is_packaged = True
            current = Path(sys.executable).parent
            self.resources_path = current.parent if current.name == "supervisor" else current.parent.parent
        else:
            self.is_packaged = False
            self.resources_path = Path(__file__).parent.parent.parent.parent

        if not (self.resources_path / "syn_backend").exists():
            for candidate in (self.resources_path.parent, self.resources_path.parent.parent):
                if len(candidate.parts) > 1 and (candidate / "syn_backend").exists():
                    self.resources_path = candidate
                    break

        self.backend_dir = self.resources_path / "syn_backend"
        self.synenv_dir = self.resources_path / "synenv"
        self.browsers_dir = self.resources_path / "browsers"
        self.services_dir = self.resources_path / "services"
        self.python_exe = self.synenv_dir / "Scripts" / "python.exe"
        if not self.python_exe.exists():
            self.python_exe = None

        self.service_executables = {
            "backend": (
                self.services_dir / "backend" / "backend.exe",
                self.services_dir / "backend.exe",
            ),
            "playwright-worker": (
                self.services_dir / "playwright-worker" / "playwright-worker.exe",
                self.services_dir / "playwright-worker.exe",
            ),
            "celery-worker": (
                self.services_dir / "celery-worker" / "celery-worker.exe",
                self.services_dir / "celery-worker.exe",
            ),
        }

        logger.info("Environment: %s", "packaged" if self.is_packaged else "dev")
        logger.info("Resources path: %s", self.resources_path)
        logger.info("Backend dir: %s (exists: %s)", self.backend_dir, self.backend_dir.exists())
        logger.info("Services dir: %s (exists: %s)", self.services_dir, self.services_dir.exists())
        logger.info("Browsers dir: %s (exists: %s)", self.browsers_dir, self.browsers_dir.exists())
        logger.info("Python runtime: %s", self.python_exe or "not packaged")

    def build_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = str(self.backend_dir)
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(self.browsers_dir)
        env["PLAYWRIGHT_AUTO_INSTALL"] = "0"
        env["ENABLE_OCR_RESCUE"] = "1"
        env["ENABLE_SELENIUM_RESCUE"] = "1"
        env["ENABLE_SELENIUM_DEBUG"] = "1"
        env["FORKED_BY_MULTIPROCESSING"] = "1"

        chrome_candidates = (
            self.browsers_dir / "chromium" / "chromium-1161" / "chrome-win" / "chrome.exe",
            self.browsers_dir / "chrome-for-testing" / "chrome-143.0.7499.169" / "chrome-win64" / "chrome.exe",
        )
        for chrome_path in chrome_candidates:
            if chrome_path.exists():
                env["LOCAL_CHROME_PATH"] = str(chrome_path)
                break

        firefox_path = self.browsers_dir / "firefox" / "firefox-1495" / "firefox" / "firefox.exe"
        if firefox_path.exists():
            env["LOCAL_FIREFOX_PATH"] = str(firefox_path)

        return env

    def get_service_executable(self, name: str) -> Optional[Path]:
        candidates = self.service_executables.get(name) or ()
        for exe in candidates:
            if exe.exists():
                return exe
        return None

    def get_service_launch(self, name: str) -> Tuple[List[str], str]:
        service_exe = self.get_service_executable(name)
        if service_exe:
            return [str(service_exe)], str(self.backend_dir)

        if not self.python_exe:
            raise FileNotFoundError(f"No packaged executable or python runtime available for service: {name}")

        if name == "backend":
            script = self.backend_dir / "fastapi_app" / "run.py"
            if not script.exists():
                raise FileNotFoundError(f"Backend script not found: {script}")
            return [str(self.python_exe), str(script)], str(self.backend_dir)

        if name == "playwright-worker":
            script = self.backend_dir / "playwright_worker" / "worker.py"
            if not script.exists():
                raise FileNotFoundError(f"Worker script not found: {script}")
            return [str(self.python_exe), str(script)], str(self.backend_dir)

        if name == "celery-worker":
            return [
                str(self.python_exe),
                "-m",
                "celery",
                "-A",
                "fastapi_app.tasks.celery_app.celery_app",
                "worker",
                "--loglevel=info",
                "--pool=threads",
                "--concurrency=1000",
                "--hostname=synapse-worker@supervisor",
            ], str(self.backend_dir)

        raise ValueError(f"Unsupported service: {name}")

    def start_named_service(self, name: str, env: Optional[Dict[str, str]] = None) -> bool:
        if not self.can_start_service(name):
            return False
        launch_cmd, cwd = self.get_service_launch(name)
        return self.manager.start_process(name, launch_cmd, cwd, env or self.build_env())

    def is_port_in_use(self, port: int, host: str = "127.0.0.1") -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                return sock.connect_ex((host, port)) == 0
        except Exception:
            return False

    def _find_pids_by_port(self, port: int) -> List[int]:
        try:
            import psutil
        except Exception:
            return []

        pids = set()
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr and conn.laddr.port == port and conn.pid:
                    pids.add(conn.pid)
        except Exception:
            return []
        return sorted(pids)

    def _terminate_pid(self, pid: int) -> bool:
        if pid <= 0 or pid == os.getpid():
            return False
        if sys.platform == "win32":
            result = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return result.returncode == 0
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception:
            return False

    def _free_port(self, port: int, name: str) -> bool:
        pids = self._find_pids_by_port(port)
        for pid in pids:
            self._terminate_pid(pid)
        if pids:
            time.sleep(1)
        return not self.is_port_in_use(port)

    def mark_external_service(self, name: str, running: bool) -> None:
        if running:
            self.external_services[name] = True
        else:
            self.external_services.pop(name, None)

    def is_external_running(self, name: str) -> bool:
        return bool(self.external_services.get(name))

    def can_start_service(self, name: str) -> bool:
        port = self.service_ports.get(name)
        if not port:
            return True
        if self.is_port_in_use(port):
            if self.kill_port_conflict and self._free_port(port, name):
                self.mark_external_service(name, False)
                return True
            self.mark_external_service(name, True)
            return False
        self.mark_external_service(name, False)
        return True

    def _kill_conflicting_processes(self) -> None:
        for port in (6379, 7000, 7001):
            if self.is_port_in_use(port) and self.kill_port_conflict:
                for pid in self._find_pids_by_port(port):
                    self._terminate_pid(pid)
                time.sleep(0.5)

    def start_redis(self, env: Dict[str, str]) -> None:
        redis_candidates = (
            self.resources_path / "syn_backend" / "Redis",
            self.resources_path / "Redis",
            self.resources_path / "redis",
        )

        redis_dir = None
        redis_exe = None
        redis_conf = None
        for candidate in redis_candidates:
            potential_exe = candidate / "redis-server.exe"
            if potential_exe.exists():
                redis_dir = candidate
                redis_exe = potential_exe
                redis_conf = candidate / "redis.windows.conf"
                break

        if not redis_exe:
            logger.warning("Redis executable not found in packaged resources.")
            return

        redis_in_use = self.is_port_in_use(6379)
        if redis_in_use and self.kill_port_conflict:
            redis_in_use = not self._free_port(6379, "redis")

        if redis_in_use:
            self.mark_external_service("redis", True)
            return

        redis_cmd = [str(redis_exe)]
        if redis_conf and redis_conf.exists():
            redis_cmd.append(str(redis_conf))
        self.manager.start_process("redis", redis_cmd, str(redis_dir), env)
        time.sleep(2)

    def start_services(self) -> None:
        logger.info("=" * 60)
        logger.info("   SynapseAutomation Supervisor Start")
        logger.info("=" * 60)

        self._kill_conflicting_processes()
        env = self.build_env()
        self.external_services = {}

        self.start_redis(env)

        if self.start_named_service("playwright-worker", env):
            time.sleep(2)
        if self.start_named_service("backend", env):
            time.sleep(3)
        self.start_named_service("celery-worker", env)

        logger.info("=" * 60)
        logger.info("All services started")
        logger.info("=" * 60)

    def monitor_loop(self) -> None:
        logger.info("Starting supervisor monitor loop...")
        try:
            while not self.manager.should_stop:
                time.sleep(5)
                for name, proc in list(self.manager.processes.items()):
                    if proc.poll() is not None:
                        logger.warning("%s exited with code %s", name, proc.returncode)
        except KeyboardInterrupt:
            logger.info("Supervisor interrupted.")
        finally:
            self.manager.stop_all()

    def start_all(self) -> None:
        self.start_services()

    def run(self) -> None:
        try:
            from api_server import SupervisorHTTPServer

            self.api_server = SupervisorHTTPServer(self, port=7002)
            self.api_server.start()
            self.start_services()
            self.monitor_loop()
        except Exception as exc:
            logger.error("Supervisor runtime error: %s", exc, exc_info=True)
        finally:
            if hasattr(self, "api_server"):
                self.api_server.stop()
            self.manager.stop_all()


def main() -> None:
    supervisor = Supervisor()
    supervisor.run()


if __name__ == "__main__":
    main()
