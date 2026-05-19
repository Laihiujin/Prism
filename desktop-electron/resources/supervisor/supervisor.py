#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Supervisor for packaged backend services.

Production mode prefers packaged service executables under resources/services.
Python script fallback is kept only for local/dev usage.
"""

from __future__ import annotations

import io
import glob
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
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


PLATFORM_BROWSER_DEFAULTS: Dict[str, str] = {
    "douyin": "chromium",
    "kuaishou": "chromium",
    "xiaohongshu": "chromium",
    "channels": "chromium",
    "bilibili": "chromium",
}


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
        stop_order = [
            "hermes-gateway",
            "hermes-webui",
            "hermes-dashboard",
            "celery-worker",
            "backend",
            "playwright-worker",
            "redis",
        ]
        for name in stop_order:
            if name in self.processes:
                self.stop_process(name)
        for name in list(self.processes.keys()):
            self.stop_process(name)


class Supervisor:
    def __init__(self) -> None:
        self.manager = ProcessManager()
        self.service_ports = {
            "backend": self._read_env_port(("BACKEND_PORT", "SYN_BACKEND_PORT"), 7000),
            "playwright-worker": self._read_env_port(("PLAYWRIGHT_WORKER_PORT", "SYN_PLAYWRIGHT_WORKER_PORT"), 7001),
            "hermes-dashboard": self._read_env_port(("SYNAPSE_HERMES_DASHBOARD_PORT",), 9119),
            "hermes-webui": self._read_env_port(("SYNAPSE_HERMES_WEBUI_PORT",), 9131),
        }
        self.preferred_service_ports = dict(self.service_ports)
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
        self.hermes_dir = self.resources_path / "tools" / "hermes-agent"
        self.hermes_home_dir = Path(
            os.environ.get("SYNAPSE_HERMES_HOME")
            or str(self.resources_path / "tools" / "hermes-home")
        )
        self.synenv_dir = self.resources_path / "synenv"
        self.synenv_site_packages = self._resolve_synenv_site_packages()
        self.browsers_dir = self.resources_path / "browsers"
        self.services_dir = self.resources_path / "services"
        self.python_exe = self._resolve_synenv_python()

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
        logger.info("Shared Python runtime: %s", self.python_exe or "not available")
        if self.synenv_site_packages:
            logger.info("Packaged site-packages: %s", self.synenv_site_packages)

    @staticmethod
    def _read_env_port(keys: Tuple[str, ...], default: int) -> int:
        for key in keys:
            raw_value = str(os.environ.get(key) or "").strip()
            if not raw_value:
                continue
            try:
                parsed = int(raw_value)
            except ValueError:
                continue
            if parsed > 0:
                return parsed
        return default

    def _get_gateway_state_path(self) -> Path:
        return self.hermes_home_dir / "gateway_state.json"

    def _get_hermes_webui_state_path(self) -> Path:
        return self.hermes_home_dir / "webui"

    def _get_hermes_workspace_root(self) -> Path:
        return self.resources_path

    def _is_pid_alive(self, pid: Optional[int]) -> bool:
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

    def _read_gateway_state(self) -> Dict[str, object]:
        gateway_state_path = self._get_gateway_state_path()
        if not gateway_state_path.exists():
            return {}
        try:
            payload = json.loads(gateway_state_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception as exc:
            logger.warning("Failed to read Hermes gateway state: %s", exc)
            return {}

    def _get_gateway_platform_status(self) -> Dict[str, object]:
        if not self.hermes_dir.exists():
            return {
                "configured": False,
                "platforms": [],
                "reason": "Hermes runtime is not installed.",
            }

        try:
            if self.python_exe and Path(self.python_exe).exists():
                env = os.environ.copy()
                env["HERMES_HOME"] = str(self.hermes_home_dir)
                env["HERMES_CONFIG_PATH"] = str(self.hermes_home_dir / "config.yaml")
                env["SYNAPSE_HERMES_HOME"] = str(self.hermes_home_dir)
                result = subprocess.run(
                    [
                        str(self.python_exe),
                        "-c",
                        (
                            "import json, sys; "
                            "sys.path.insert(0, sys.argv[1]); "
                            "from gateway.config import Platform, load_gateway_config; "
                            "config = load_gateway_config(); "
                            "platforms = sorted("
                            "platform.value "
                            "for platform, platform_config in (config.platforms or {}).items() "
                            "if getattr(platform_config, 'enabled', False) and platform != Platform.LOCAL"
                            "); "
                            "print(json.dumps({'platforms': platforms}, ensure_ascii=False))"
                        ),
                        str(self.hermes_dir),
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=str(self.hermes_dir),
                    env=env,
                    check=True,
                )
                payload = json.loads((result.stdout or "").strip() or "{}")
                platforms = payload.get("platforms", [])
                if not isinstance(platforms, list):
                    raise ValueError("Invalid Hermes gateway platform payload")
            else:
                hermes_dir_str = str(self.hermes_dir)
                added_sys_path = False
                if hermes_dir_str not in sys.path:
                    sys.path.insert(0, hermes_dir_str)
                    added_sys_path = True
                try:
                    from gateway.config import Platform, load_gateway_config

                    config = load_gateway_config()
                    platforms = sorted(
                        platform.value
                        for platform, platform_config in (config.platforms or {}).items()
                        if getattr(platform_config, "enabled", False) and platform != Platform.LOCAL
                    )
                finally:
                    if added_sys_path:
                        try:
                            sys.path.remove(hermes_dir_str)
                        except ValueError:
                            pass
        except Exception as exc:
            logger.warning("Failed to inspect Hermes gateway configuration: %s", exc)
            return {
                "configured": False,
                "platforms": [],
                "reason": f"Failed to inspect Hermes gateway configuration: {exc}",
            }

        if platforms:
            return {
                "configured": True,
                "platforms": platforms,
                "reason": "",
            }

        return {
            "configured": False,
            "platforms": [],
            "reason": "No messaging platforms are configured for Hermes gateway.",
        }

    def _find_git_bash(self) -> Optional[str]:
        candidates = (
            self.resources_path / "tools" / "git" / "bin" / "bash.exe",
            self.resources_path / "tools" / "git" / "usr" / "bin" / "bash.exe",
            Path(os.getenv("ProgramFiles", "")) / "Git" / "bin" / "bash.exe",
            Path(os.getenv("ProgramFiles", "")) / "Git" / "usr" / "bin" / "bash.exe",
            Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Git" / "bin" / "bash.exe",
        )
        for candidate in candidates:
            if candidate and candidate.exists():
                return str(candidate)
        return None

    def _find_browser_executable(self, patterns: Iterable[str]) -> Optional[Path]:
        for pattern in patterns:
            matches = sorted(glob.glob(str(self.browsers_dir / pattern)))
            if matches:
                return Path(matches[-1])
        return None

    def _resolve_synenv_python(self) -> Optional[Path]:
        candidates = (
            self.synenv_dir / "Scripts" / "python.exe",
            self.synenv_dir / "bin" / "python",
        )
        for candidate in candidates:
            if candidate.exists() and self._python_is_usable(candidate):
                return candidate
            if candidate.exists():
                logger.warning("Packaged Python exists but is not usable: %s", candidate)
        system_python = self._resolve_system_python()
        if system_python:
            logger.warning("Falling back to system Python for Hermes scripts: %s", system_python)
            return system_python
        return None

    def _resolve_system_python(self) -> Optional[Path]:
        for command in ("python", "python3"):
            try:
                result = subprocess.run(
                    [command, "-c", "import sys; print(sys.executable)"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                    check=False,
                )
            except Exception:
                continue
            if result.returncode == 0:
                executable = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else command
                path = Path(executable)
                return path if path.exists() else Path(command)
        return None

    def _python_is_usable(self, python_path: Path) -> bool:
        try:
            result = subprocess.run(
                [str(python_path), "-c", "import sys; print(sys.version)"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _resolve_synenv_site_packages(self) -> Optional[Path]:
        candidates = (
            self.synenv_dir / "Lib" / "site-packages",
            self.synenv_dir / "lib" / "site-packages",
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _build_pythonpath(
        self,
        *preferred: object,
        base: Optional[str] = None,
        exclude: Optional[Iterable[object]] = None,
    ) -> str:
        entries: List[str] = []
        seen: set[str] = set()
        excluded: set[str] = set()

        for raw in exclude or ():
            if raw is None:
                continue
            text = str(raw).strip()
            if text:
                excluded.add(os.path.normcase(os.path.normpath(text)))

        def add(raw: object) -> None:
            if raw is None:
                return
            text = str(raw).strip()
            if not text:
                return
            normalized = os.path.normcase(os.path.normpath(text))
            if any(normalized == root or normalized.startswith(root + os.sep) for root in excluded):
                return
            if normalized in seen:
                return
            seen.add(normalized)
            entries.append(text)

        for item in preferred:
            add(item)

        for raw_entry in str(base or "").split(os.pathsep):
            add(raw_entry)

        return os.pathsep.join(entries)

    def _can_bind_port(self, port: int, host: str = "127.0.0.1") -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((host, port))
            return True
        except OSError:
            return False
        except Exception:
            return False

    def _find_available_port(
        self,
        preferred_port: int,
        *,
        host: str = "127.0.0.1",
        max_attempts: int = 32,
        reserved_ports: Optional[set[int]] = None,
    ) -> int:
        candidate = max(int(preferred_port), 1)
        for _ in range(max_attempts):
            if reserved_ports and candidate in reserved_ports:
                candidate += 1
                continue
            if self._can_bind_port(candidate, host=host):
                return candidate
            candidate += 1
        raise RuntimeError(f"No available port found starting from {preferred_port}")

    def _resolve_dynamic_service_port(self, name: str, reserved_ports: Optional[set[int]] = None) -> int:
        preferred_port = self.preferred_service_ports.get(name, self.service_ports.get(name))
        if preferred_port is None:
            raise KeyError(f"Unknown service port mapping: {name}")
        current_port = self.service_ports.get(name, preferred_port)
        if (not reserved_ports or current_port not in reserved_ports) and self._can_bind_port(current_port):
            return current_port

        resolved_port = self._find_available_port(preferred_port, reserved_ports=reserved_ports)
        if resolved_port != current_port:
            logger.warning(
                "Port %s for %s is unavailable; reassigned to %s",
                current_port,
                name,
                resolved_port,
            )
        self.service_ports[name] = resolved_port
        return resolved_port

    def _refresh_dynamic_service_ports(self) -> None:
        reserved_ports: set[int] = set()
        for service_name in ("backend", "playwright-worker", "hermes-dashboard", "hermes-webui"):
            reserved_ports.add(self._resolve_dynamic_service_port(service_name, reserved_ports))

    def _get_reserved_dynamic_ports(self, current_name: str) -> set[int]:
        reserved_ports: set[int] = set()
        for service_name in ("backend", "playwright-worker", "hermes-dashboard", "hermes-webui"):
            if service_name == current_name:
                continue
            port = self.service_ports.get(service_name)
            if isinstance(port, int) and port > 0:
                reserved_ports.add(port)
        return reserved_ports

    def _build_hermes_cli_launch(self, *cli_args: str) -> List[str]:
        if not self.python_exe:
            raise FileNotFoundError("No shared python runtime available for Hermes CLI")
        source_path = str(self.hermes_dir)
        bootstrap = (
            "import runpy, sys; "
            f"sys.path.insert(0, {source_path!r}); "
            "runpy.run_module('hermes_cli.main', run_name='__main__')"
        )
        return [str(self.python_exe), "-c", bootstrap, *cli_args]

    def _build_run_path_launch(self, script_path: Path, *sys_paths: Path) -> List[str]:
        if not self.python_exe:
            raise FileNotFoundError("No shared python runtime available for scripted launch")
        inserts = "".join(
            f"sys.path.insert(0, {str(path)!r}); " for path in sys_paths if path
        )
        bootstrap = (
            "import runpy, sys; "
            f"{inserts}"
            f"runpy.run_path({str(script_path)!r}, run_name='__main__')"
        )
        return [str(self.python_exe), "-c", bootstrap]

    def _load_runtime_settings(self) -> Dict[str, object]:
        settings_path_raw = os.environ.get("SYNAPSE_RUNTIME_SETTINGS_PATH")
        if not settings_path_raw:
            return {}

        settings_path = Path(settings_path_raw)
        if not settings_path.exists():
            return {}

        try:
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception as exc:
            logger.warning("Failed to load runtime settings from %s: %s", settings_path, exc)
        return {}

    def _normalize_platform_browser_choice(self, value: object, fallback: str = "chromium") -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"auto", "chromium", "firefox"}:
            return normalized
        return fallback

    def _normalize_platform_browser_preferences(self, raw: object) -> Dict[str, str]:
        normalized = dict(PLATFORM_BROWSER_DEFAULTS)
        if not isinstance(raw, dict):
            return normalized

        for platform, default_choice in PLATFORM_BROWSER_DEFAULTS.items():
            direct_value = raw.get(platform)
            alias_value = raw.get("tencent") if platform == "channels" else None
            candidate = direct_value if direct_value is not None else alias_value
            normalized[platform] = self._normalize_platform_browser_choice(candidate, default_choice)

        return normalized

    def build_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        runtime_settings = self._load_runtime_settings()
        browser_headless = runtime_settings.get("browserHeadless")
        automation_runtime = runtime_settings.get("automationRuntime")
        platform_browser_preferences = self._normalize_platform_browser_preferences(
            runtime_settings.get("platformBrowserPreferences")
        )
        settings_path_raw = os.environ.get("SYNAPSE_RUNTIME_SETTINGS_PATH")

        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = self._build_pythonpath(
            self.backend_dir,
            self.synenv_site_packages,
            base=env.get("PYTHONPATH"),
        )
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(self.browsers_dir)
        env["PLAYWRIGHT_AUTO_INSTALL"] = "0"
        env["PLAYWRIGHT_HEADLESS"] = (
            "true" if isinstance(browser_headless, bool) and browser_headless else
            "false" if isinstance(browser_headless, bool) else
            os.getenv("PLAYWRIGHT_HEADLESS", "true")
        )
        env["SYNAPSE_PLAYWRIGHT_RUNTIME"] = (
            str(automation_runtime)
            if automation_runtime in {"patchright", "playwright"}
            else os.getenv("SYNAPSE_PLAYWRIGHT_RUNTIME", "patchright")
        )
        if settings_path_raw:
            env["SYNAPSE_RUNTIME_SETTINGS_PATH"] = settings_path_raw
        env["SYNAPSE_PLATFORM_BROWSER_PREFERENCES"] = json.dumps(platform_browser_preferences)
        for platform, choice in platform_browser_preferences.items():
            env[f"SYNAPSE_PLATFORM_BROWSER_{platform.upper()}"] = choice
        env["SYNAPSE_PLATFORM_BROWSER_TENCENT"] = platform_browser_preferences.get("channels", "chromium")
        env["BACKEND_PORT"] = str(self.service_ports["backend"])
        env["SYN_BACKEND_PORT"] = str(self.service_ports["backend"])
        env["PLAYWRIGHT_WORKER_PORT"] = str(self.service_ports["playwright-worker"])
        env["ENABLE_OCR_RESCUE"] = "1"
        env["ENABLE_SELENIUM_RESCUE"] = "1"
        env["ENABLE_SELENIUM_DEBUG"] = "1"
        env["FORKED_BY_MULTIPROCESSING"] = "1"
        env["HERMES_HOME"] = str(self.hermes_home_dir)
        env["HERMES_CONFIG_PATH"] = str(self.hermes_home_dir / "config.yaml")
        env["SYNAPSE_HERMES_HOME"] = str(self.hermes_home_dir)
        env["SYNAPSE_SUPERVISOR_MANAGES_HERMES_UI"] = "1"
        env["SYNAPSE_HERMES_DASHBOARD_PORT"] = str(self.service_ports["hermes-dashboard"])
        env["SYNAPSE_HERMES_WEBUI_PORT"] = str(self.service_ports["hermes-webui"])
        if self.python_exe:
            env["SYNAPSE_HERMES_PYTHON"] = str(self.python_exe)

        git_bash = self._find_git_bash()
        if git_bash:
            env["HERMES_GIT_BASH_PATH"] = git_bash

        chrome_path = self._find_browser_executable(
            (
                "chromium/hibbiki-*/Chrome-bin/chrome.exe",
                "chromium/chromium-*/chrome-win64/chrome.exe",
                "chromium/chromium-*/chrome-win/chrome.exe",
                "chromium-*/chrome-win64/chrome.exe",
                "chromium-*/chrome-win/chrome.exe",
                "chrome-for-testing/chrome-*/chrome-win64/chrome.exe",
            )
        )
        if chrome_path:
            env["LOCAL_CHROME_PATH"] = str(chrome_path)

        headless_shell_path = self._find_browser_executable(
            ("chromium_headless_shell-*/chrome-headless-shell-win64/chrome-headless-shell.exe",)
        )
        if headless_shell_path:
            env["LOCAL_CHROME_HEADLESS_SHELL_PATH"] = str(headless_shell_path)

        firefox_path = self._find_browser_executable(
            (
                "firefox-*/firefox/firefox.exe",
                "firefox/firefox-*/firefox/firefox.exe",
            )
        )
        if firefox_path and firefox_path.exists():
            env["LOCAL_FIREFOX_PATH"] = str(firefox_path)

        logger.info(
            "Runtime settings applied: PLAYWRIGHT_HEADLESS=%s SYNAPSE_PLAYWRIGHT_RUNTIME=%s SYNAPSE_PLATFORM_BROWSER_PREFERENCES=%s",
            env["PLAYWRIGHT_HEADLESS"],
            env["SYNAPSE_PLAYWRIGHT_RUNTIME"],
            env.get("SYNAPSE_PLATFORM_BROWSER_PREFERENCES", ""),
        )

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

        if name == "hermes-gateway":
            script = self.hermes_dir / "hermes_cli" / "main.py"
            if not script.exists():
                raise FileNotFoundError(f"Hermes gateway entry script not found: {script}")
            if not self.python_exe:
                raise FileNotFoundError("No Hermes python runtime available for hermes-gateway")
            return self._build_hermes_cli_launch(
                "gateway",
                "run",
                "--replace",
                "--accept-hooks",
            ), str(self.resources_path)

        if name == "hermes-dashboard":
            dashboard_port = str(self.service_ports["hermes-dashboard"])
            dashboard_dist = self.hermes_dir / "hermes_cli" / "web_dist" / "index.html"
            if not dashboard_dist.exists():
                raise FileNotFoundError(f"Hermes dashboard dist not found: {dashboard_dist}")
            if not self.python_exe:
                raise FileNotFoundError("No Hermes python runtime available for hermes-dashboard")
            return self._build_hermes_cli_launch(
                "dashboard",
                "--host",
                "127.0.0.1",
                "--port",
                dashboard_port,
                "--no-open",
                "--skip-build",
            ), str(self.hermes_dir)

        if name == "hermes-webui":
            script = self.resources_path / "tools" / "hermes-webui" / "server.py"
            index_html = self.resources_path / "tools" / "hermes-webui" / "static" / "index.html"
            if not script.exists() or not index_html.exists():
                raise FileNotFoundError(f"Hermes WebUI is not installed under: {script.parent}")
            if not self.python_exe:
                raise FileNotFoundError("No Hermes python runtime available for hermes-webui")
            return self._build_run_path_launch(
                script,
                script.parent,
                self.hermes_dir,
            ), str(script.parent)

        raise ValueError(f"Unsupported service: {name}")

    def get_service_env(self, name: str, base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        env = dict(base_env or self.build_env())
        if name in {"hermes-gateway", "hermes-dashboard", "hermes-webui"}:
            env["PYTHONPATH"] = self._build_pythonpath(
                self.hermes_dir,
                self.synenv_site_packages,
                base=env.get("PYTHONPATH"),
                exclude=(self.backend_dir,),
            )
            env["HERMES_WEBUI_AGENT_DIR"] = str(self.hermes_dir)
            if self.python_exe:
                env["HERMES_WEBUI_PYTHON"] = str(self.python_exe)

        if name == "hermes-dashboard":
            env["HERMES_WEB_DIST"] = str(self.hermes_dir / "hermes_cli" / "web_dist")
        elif name == "hermes-webui":
            self._get_hermes_webui_state_path().mkdir(parents=True, exist_ok=True)
            self._get_hermes_workspace_root().mkdir(parents=True, exist_ok=True)
            env["HERMES_WEBUI_HOST"] = "127.0.0.1"
            env["HERMES_WEBUI_PORT"] = str(self.service_ports["hermes-webui"])
            env["HERMES_WEBUI_STATE_DIR"] = str(self._get_hermes_webui_state_path())
            env["HERMES_WEBUI_DEFAULT_WORKSPACE"] = str(self._get_hermes_workspace_root())
            env.setdefault("HERMES_SKIP_CHMOD", "1")
        return env

    def _http_ok(self, url: str, timeout: float = 2.0) -> bool:
        try:
            request = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return 200 <= getattr(response, "status", 0) < 500
        except Exception:
            return False

    def _is_service_ready(self, name: str) -> bool:
        if not self.manager.is_running(name):
            return False

        if name == "hermes-dashboard":
            port = self.service_ports["hermes-dashboard"]
            return self.is_port_in_use(port) and self._http_ok(f"http://127.0.0.1:{port}/")

        if name == "hermes-webui":
            port = self.service_ports["hermes-webui"]
            if not self.is_port_in_use(port):
                return False
            return (
                self._http_ok(f"http://127.0.0.1:{port}/?syn_shell_health=1")
                and self._http_ok(f"http://127.0.0.1:{port}/static/boot.js?syn_shell_health=1")
            )

        if name == "backend":
            port = self.service_ports["backend"]
            return self.is_port_in_use(port) and self._http_ok(f"http://127.0.0.1:{port}/health")

        if name == "playwright-worker":
            port = self.service_ports["playwright-worker"]
            return self.is_port_in_use(port) and self._http_ok(f"http://127.0.0.1:{port}/health")

        return True

    def wait_for_service_ready(self, name: str, timeout: float = 20.0, poll_interval: float = 0.5) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            proc = self.manager.processes.get(name)
            if proc is not None and proc.poll() is not None:
                return False
            if self._is_service_ready(name):
                return True
            time.sleep(poll_interval)
        return self._is_service_ready(name)

    def start_named_service(self, name: str, env: Optional[Dict[str, str]] = None) -> bool:
        if not self.can_start_service(name):
            return False
        try:
            launch_cmd, cwd = self.get_service_launch(name)
            started = self.manager.start_process(name, launch_cmd, cwd, self.get_service_env(name, env))
            if not started:
                return False
            if name in {"backend", "playwright-worker", "hermes-dashboard", "hermes-webui"} and not self.wait_for_service_ready(name):
                logger.warning("%s failed readiness after startup", name)
                self.manager.stop_process(name)
                return False
            return True
        except Exception as exc:
            logger.warning("Skipping %s startup: %s", name, exc)
            return False

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

    def get_service_status(self, name: str) -> Dict[str, object]:
        gateway_platform_status = None
        if name == "hermes-gateway":
            gateway_platform_status = self._get_gateway_platform_status()

        proc = self.manager.processes.get(name)
        managed_running = self.manager.is_running(name)
        external_running = self.is_external_running(name)
        service_port = self.service_ports.get(name)

        if not managed_running and service_port:
            port_open = self.is_port_in_use(service_port)
            if port_open and not external_running:
                external_running = True
                self.mark_external_service(name, True)
            elif external_running and not port_open:
                external_running = False
                self.mark_external_service(name, False)

        pid = proc.pid if managed_running and proc else None

        if name == "hermes-gateway" and external_running and pid is None:
            gateway_state = self._read_gateway_state()
            gateway_pid = gateway_state.get("pid")
            if isinstance(gateway_pid, int):
                pid = gateway_pid

        source = "managed" if managed_running else "external" if external_running else "stopped"
        payload = {
            "running": bool(managed_running or external_running),
            "pid": pid,
            "external": external_running,
            "managed": managed_running,
            "source": source,
        }
        if name == "backend":
            payload["port"] = self.service_ports["backend"]
            payload["url"] = f"http://127.0.0.1:{self.service_ports['backend']}"
        elif name == "playwright-worker":
            payload["port"] = self.service_ports["playwright-worker"]
            payload["url"] = f"http://127.0.0.1:{self.service_ports['playwright-worker']}"
        elif name == "hermes-dashboard":
            payload["port"] = self.service_ports["hermes-dashboard"]
            payload["url"] = f"http://127.0.0.1:{self.service_ports['hermes-dashboard']}"
            payload["dashboard_url"] = payload["url"]
        elif name == "hermes-webui":
            payload["port"] = self.service_ports["hermes-webui"]
            payload["url"] = f"http://127.0.0.1:{self.service_ports['hermes-webui']}"
            payload["webui_url"] = payload["url"]
        if gateway_platform_status is not None:
            payload["configured"] = bool(gateway_platform_status["configured"])
            payload["platforms"] = gateway_platform_status["platforms"]
            payload["reason"] = gateway_platform_status["reason"]
            if not gateway_platform_status["configured"]:
                payload["running"] = False
                payload["pid"] = None
                payload["external"] = False
                payload["managed"] = False
                payload["source"] = "disabled"
        return payload

    def can_start_service(self, name: str) -> bool:
        if name == "hermes-gateway":
            gateway_platform_status = self._get_gateway_platform_status()
            if not gateway_platform_status["configured"]:
                self.mark_external_service(name, False)
                return False
            gateway_state = self._read_gateway_state()
            gateway_pid = gateway_state.get("pid")
            if self._is_pid_alive(gateway_pid if isinstance(gateway_pid, int) else None):
                if self.kill_port_conflict and isinstance(gateway_pid, int):
                    if self._terminate_pid(gateway_pid):
                        time.sleep(1)
                        self.mark_external_service(name, False)
                        return True
                self.mark_external_service(name, True)
                return False
            self.mark_external_service(name, False)
            return True

        if name in {"backend", "playwright-worker", "hermes-dashboard", "hermes-webui"}:
            self._resolve_dynamic_service_port(name, self._get_reserved_dynamic_ports(name))
            self.mark_external_service(name, False)
            return True

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
        for port in (6379,):
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
        self._refresh_dynamic_service_ports()
        env = self.build_env()
        self.external_services = {}

        self.start_redis(env)

        if self.start_named_service("playwright-worker", env):
            time.sleep(2)
        if self.start_named_service("backend", env):
            time.sleep(3)
        self.start_named_service("hermes-dashboard", env)
        self.start_named_service("hermes-webui", env)
        self.start_named_service("celery-worker", env)
        gateway_platform_status = self._get_gateway_platform_status()
        if gateway_platform_status["configured"]:
            self.start_named_service("hermes-gateway", env)
        else:
            logger.info(
                "Skipping hermes-gateway startup: %s",
                gateway_platform_status["reason"],
            )

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
