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
import uuid
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

# 大陆平台默认强制直连（不走本机 VPN/全局代理）。与前端 platformProxyPreferences 的 direct 一致。
PLATFORM_PROXY_DEFAULTS: Dict[str, str] = {
    "douyin": "direct",
    "kuaishou": "direct",
    "xiaohongshu": "direct",
    "channels": "direct",
    "bilibili": "direct",
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

    def get_exit_code(self, name: str) -> Optional[int]:
        proc = self.processes.get(name)
        if proc is None:
            return None
        code = proc.poll()
        return code

    def tail_process_log(self, name: str, lines: int = 25) -> str:
        """读取最近一次进程日志文件的末尾若干行（失败根因上报用）。"""
        logs_dir = Path("logs")
        log_file = logs_dir / f"{name}.log"
        if not log_file.exists():
            return ""
        try:
            text = log_file.read_text(encoding="utf-8", errors="replace")
            tail = text.splitlines()[-lines:]
            return "\n".join(tail)
        except Exception:
            return ""

    def stop_process(self, name: str, timeout: int = 4) -> None:
        proc = self.processes.get(name)
        if not proc:
            return

        logger.info("Stopping %s...", name)
        try:
            if sys.platform == "win32":
                # 参考 dsh-desktop：SIGTERM 式优雅退出，超时后强杀。
                # Windows 上没有 POSIX 信号，先尝试 taskkill 不带 /F（请求优雅退出），
                # 超时后再 /F 强杀整个进程树。
                subprocess.run(
                    ["taskkill", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=max(timeout + 5, 8),
                )
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                    proc.wait(timeout=5)
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
        except Exception as exc:
            logger.warning("Stop %s raised: %s; forcing kill", name, exc)
            try:
                proc.kill()
            except Exception:
                pass
        finally:
            thread = self.log_threads.pop(name, None)
            if thread:
                thread.join(timeout=2)
            self._cleanup_process_logger(name)
            self.processes.pop(name, None)

    def stop_all(self) -> None:
        logger.info("Stopping all managed services...")
        stop_order = [
            "deepseek-harness",
            "hermes-gateway",
            "hermes-webui",
            "hermes-dashboard",
            "celery-worker",
            "backend",
            "automation-worker",
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
            "backend": self._read_env_port(("BACKEND_PORT", "PRISM_BACKEND_PORT"), 9200),
            "automation-worker": self._read_env_port(("AUTOMATION_WORKER_PORT", "PRISM_AUTOMATION_WORKER_PORT"), 7001),
            "hermes-dashboard": self._read_env_port(("PRISM_HERMES_DASHBOARD_PORT",), 9119),
            "hermes-webui": self._read_env_port(("PRISM_HERMES_WEBUI_PORT",), 9131),
            "deepseek-harness": self._read_env_port(("PRISM_DEEPSEEK_HARNESS_PORT",), 3080),
        }
        self.preferred_service_ports = dict(self.service_ports)
        self.external_services: Dict[str, bool] = {}
        self.kill_port_conflict = os.environ.get("SUPERVISOR_KILL_PORT_CONFLICT", "1") != "0"

        # ── 启动令牌与状态文件（供 Electron 主进程发现 API 端口/服务端口/归属校验）──
        self.launch_token = uuid.uuid4().hex
        self.state_path = Path(
            os.environ.get("PRISM_SUPERVISOR_STATE_PATH")
            or str(Path.home() / ".prism-supervisor" / "state.json")
        )
        self.started_at = time.time()

        # ── 失败诊断与重启策略 ──
        # failures: {name: {count, stage, detail, exit_code, last_error_at, restart_count}}
        self.failures: Dict[str, Dict[str, object]] = {}
        self.restart_policy = {
            "backend": {"max_restarts": 3, "backoff": 3.0, "stable_after": 60.0},
            "automation-worker": {"max_restarts": 3, "backoff": 3.0, "stable_after": 60.0},
            "hermes-dashboard": {"max_restarts": 2, "backoff": 5.0, "stable_after": 90.0},
            "hermes-webui": {"max_restarts": 2, "backoff": 5.0, "stable_after": 90.0},
            "celery-worker": {"max_restarts": 2, "backoff": 5.0, "stable_after": 90.0},
            "hermes-gateway": {"max_restarts": 1, "backoff": 8.0, "stable_after": 120.0},
            "deepseek-harness": {"max_restarts": 3, "backoff": 5.0, "stable_after": 90.0},
        }
        self._login_env_cache: Optional[Dict[str, str]] = None

        env_resources_path = os.environ.get("PRISM_RESOURCES_PATH") or os.environ.get("PRISM_APP_ROOT")
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

        if not (self.resources_path / "prism_backend").exists():
            for candidate in (self.resources_path.parent, self.resources_path.parent.parent):
                if len(candidate.parts) > 1 and (candidate / "prism_backend").exists():
                    self.resources_path = candidate
                    break

        self.backend_dir = self.resources_path / "prism_backend"
        runtime_settings_path = os.environ.get("PRISM_RUNTIME_SETTINGS_PATH")
        self.runtime_data_dir = Path(
            os.environ.get("PRISM_RUNTIME_DATA_DIR")
            or (str(Path(runtime_settings_path).parent / "runtime-data") if runtime_settings_path else "")
            or str(self.resources_path / "runtime-data")
        )
        self.hermes_dir = self.resources_path / "tools" / "hermes-agent"
        self.hermes_home_dir = Path(
            os.environ.get("PRISM_HERMES_HOME")
            or str(self.resources_path / "tools" / "hermes-home")
        )
        self.prismenv_dir = self.resources_path / "prismenv"
        self.prismenv_site_packages = self._resolve_prismenv_site_packages()
        self.browsers_dir = self.resources_path / "prism_backend" / "tools" / "browsers"
        self.services_dir = self.resources_path / "services"
        self.python_exe = self._resolve_prismenv_python()

        self.service_executables = {
            "backend": (
                self.services_dir / "backend" / "backend.exe",
                self.services_dir / "backend.exe",
            ),
            "automation-worker": (
                self.services_dir / "automation-worker" / "automation-worker.exe",
                self.services_dir / "automation-worker.exe",
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
        logger.info("Managed component data: %s", self.runtime_data_dir / "components")
        if self.prismenv_site_packages:
            logger.info("Packaged site-packages: %s", self.prismenv_site_packages)

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

    # ────────────────────────────────────────────────────────────────
    # 完整 shell 环境注入：子进程环境 = 登录环境 + 当前环境 + PRISM 覆盖
    # ────────────────────────────────────────────────────────────────
    def _collect_login_env(self) -> Dict[str, str]:
        """收集用户登录会话的完整环境（PATH 等），参考 dsh-desktop 的 $SHELL -l -i -c env。

        Windows：从注册表读取用户级 + 机器级环境变量；
        macOS/Linux：通过登录 shell（-l -i）导出完整环境。
        结果缓存；失败时回退为 os.environ。
        """
        if self._login_env_cache is not None:
            return self._login_env_cache

        collected: Dict[str, str] = {}
        if sys.platform == "win32":
            collected = self._collect_windows_registry_env()
        else:
            collected = self._collect_login_shell_env()

        if collected:
            # 当前进程 env 覆盖登录环境（Electron 显式设置的变量优先）
            merged = {**collected, **os.environ}
        else:
            merged = os.environ.copy()
        self._login_env_cache = merged
        logger.info("Login environment collected: %d variables", len(merged))
        return merged

    def _collect_windows_registry_env(self) -> Dict[str, str]:
        """从 Windows 注册表（HKCU/HKLM Environment）读取用户/机器环境变量。"""
        ps_script = (
            "$ErrorActionPreference = 'SilentlyContinue'; "
            "$out = @{}; "
            "foreach ($scope in @('User','Machine')) { "
            "  $vars = [Environment]::GetEnvironmentVariables($scope); "
            "  foreach ($key in $vars.Keys) { "
            "    if (-not $out.ContainsKey($key)) { $out[$key] = [string]$vars[$key] } "
            "  } "
            "}; "
            "if ($out.Count -gt 0) { $out | ConvertTo-Json -Compress }"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode != 0:
                logger.warning("Registry env collection failed: %s", result.stderr[:200])
                return {}
            raw = str(result.stdout or "").strip()
            if not raw:
                return {}
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return {}
            return {str(k): str(v) for k, v in parsed.items() if v is not None}
        except Exception as exc:
            logger.warning("Failed to collect registry env: %s", exc)
            return {}

    def _collect_login_shell_env(self) -> Dict[str, str]:
        """macOS/Linux：$SHELL -l -i -c env 收集登录 shell 环境。"""
        shell = os.environ.get("SHELL") or "/bin/sh"
        command = f"{shell} -l -i -c env"
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
            if result.returncode != 0:
                logger.warning("Login shell env collection failed: %s", result.stderr[:200])
                return {}
            env: Dict[str, str] = {}
            for line in str(result.stdout or "").splitlines():
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                if key and key not in env:
                    env[key] = value
            return env
        except Exception as exc:
            logger.warning("Failed to collect login shell env: %s", exc)
            return {}

    # ────────────────────────────────────────────────────────────────
    # 失败诊断 / 启动令牌 / 状态文件
    # ────────────────────────────────────────────────────────────────
    def _record_failure(
        self,
        name: str,
        stage: str,
        detail: str,
        exit_code: Optional[int] = None,
    ) -> None:
        entry = self.failures.setdefault(
            name, {"count": 0, "restart_count": 0, "last_error_at": None}
        )
        entry["count"] = int(entry.get("count") or 0) + 1
        entry["stage"] = stage
        entry["detail"] = detail[:500]
        entry["last_error_at"] = time.time()
        if exit_code is not None:
            entry["exit_code"] = exit_code
        logger.error("[%s] failure recorded: %s — %s", name, stage, detail[:200])

    def _tail_log(self, name: str, lines: int = 25) -> str:
        return self.manager.tail_process_log(name, lines)

    def _is_pid_listening(self, pid: Optional[int], port: int, host: str = "127.0.0.1") -> bool:
        """校验监听端口的进程确实是本 supervisor 拉起的子进程（防止连到陈旧实例）。"""
        if not isinstance(pid, int) or pid <= 0:
            return False
        try:
            import psutil
        except Exception:
            return True  # psutil 不可用时退化为仅 HTTP 探测
        try:
            for conn in psutil.net_connections(kind="inet"):
                if (
                    conn.laddr
                    and conn.laddr.ip == host
                    and conn.laddr.port == port
                    and conn.pid == pid
                ):
                    return True
        except Exception:
            return True
        return False

    def _write_state_file(self, api_port: Optional[int] = None) -> None:
        """把 supervisor 的发现信息写入状态文件，Electron 主进程据此连接。"""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "pid": os.getpid(),
                "startedAt": self.started_at,
                "launchToken": self.launch_token,
                "apiPort": api_port,
                "servicePorts": {
                    name: port for name, port in self.service_ports.items()
                },
            }
            tmp_path = self.state_path.with_suffix(".json.tmp")
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp_path.replace(self.state_path)
        except Exception as exc:
            logger.warning("Failed to write supervisor state file: %s", exc)

    def get_diagnostics(self) -> Dict[str, object]:
        """失败根因上报：服务状态 + 失败记录 + 环境摘要 + 日志路径。"""
        services: Dict[str, object] = {}
        for name in (
            "backend",
            "automation-worker",
            "celery-worker",
            "hermes-gateway",
            "hermes-dashboard",
            "hermes-webui",
            "deepseek-harness",
        ):
            status = self.get_service_status(name)
            failure = self.failures.get(name)
            if failure:
                status["failure"] = failure
                status["log_tail"] = self._tail_log(name)
            services[name.replace("-", "_")] = status

        return {
            "supervisor": {
                "pid": os.getpid(),
                "apiPort": getattr(self, "api_port", None),
                "launchToken": self.launch_token,
                "startedAt": self.started_at,
                "isPackaged": self.is_packaged,
            },
            "services": services,
            "environment": {
                "resourcesPath": str(self.resources_path),
                "backendDir": str(self.backend_dir),
                "python": str(self.python_exe) if self.python_exe else None,
                "prismenvSitePackages": str(self.prismenv_site_packages) if self.prismenv_site_packages else None,
                "servicePorts": {k: v for k, v in self.service_ports.items()},
            },
            "logPaths": {
                "supervisor": str(Path("logs") / "supervisor.log"),
                "backend": str(Path("logs") / "backend.log"),
            },
        }

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
                env["PRISM_HERMES_HOME"] = str(self.hermes_home_dir)
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

    def _resolve_prismenv_python(self) -> Optional[Path]:
        candidates = (
            self.prismenv_dir / "Scripts" / "python.exe",
            self.prismenv_dir / "bin" / "python",
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

    def _resolve_prismenv_site_packages(self) -> Optional[Path]:
        candidates = (
            self.prismenv_dir / "Lib" / "site-packages",
            self.prismenv_dir / "lib" / "site-packages",
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
        for service_name in ("backend", "automation-worker", "hermes-dashboard", "hermes-webui", "deepseek-harness"):
            reserved_ports.add(self._resolve_dynamic_service_port(service_name, reserved_ports))

    def _get_reserved_dynamic_ports(self, current_name: str) -> set[int]:
        reserved_ports: set[int] = set()
        for service_name in ("backend", "automation-worker", "hermes-dashboard", "hermes-webui"):
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
        settings_path_raw = os.environ.get("PRISM_RUNTIME_SETTINGS_PATH")
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

    def _normalize_platform_proxy_preferences(self, raw: object) -> Dict[str, str]:
        normalized = dict(PLATFORM_PROXY_DEFAULTS)
        if not isinstance(raw, dict):
            return normalized

        for platform, default_mode in PLATFORM_PROXY_DEFAULTS.items():
            direct_value = raw.get(platform)
            alias_value = raw.get("tencent") if platform == "channels" else None
            candidate = direct_value if direct_value is not None else alias_value
            normalized[platform] = self._normalize_platform_proxy_choice(candidate, default_mode)

        return normalized

    def _normalize_platform_proxy_choice(self, value: object, fallback: str = "direct") -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"direct", "inherit"}:
            return normalized
        return fallback

    def build_direct_connect_platforms(self, raw: object) -> List[str]:
        preferences = self._normalize_platform_proxy_preferences(raw)
        direct = []
        for platform, mode in preferences.items():
            if mode == "direct":
                direct.append("tencent" if platform == "channels" else platform)
        return direct

    def build_env(self) -> Dict[str, str]:
        # 完整环境：登录会话环境 + 当前进程环境（PRISM_* 显式覆盖）
        env = self._collect_login_env()
        runtime_settings = self._load_runtime_settings()
        browser_headless = runtime_settings.get("browserHeadless")
        automation_runtime = runtime_settings.get("automationRuntime")
        platform_browser_preferences = self._normalize_platform_browser_preferences(
            runtime_settings.get("platformBrowserPreferences")
        )
        settings_path_raw = os.environ.get("PRISM_RUNTIME_SETTINGS_PATH")

        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = self._build_pythonpath(
            self.backend_dir,
            self.prismenv_site_packages,
            base=env.get("PYTHONPATH"),
        )
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(self.browsers_dir)
        env["PLAYWRIGHT_AUTO_INSTALL"] = "0"
        env["PLAYWRIGHT_HEADLESS"] = (
            "true" if isinstance(browser_headless, bool) and browser_headless else
            "false" if isinstance(browser_headless, bool) else
            os.getenv("PLAYWRIGHT_HEADLESS", "true")
        )
        env["PRISM_AUTOMATION_RUNTIME"] = (
            automation_runtime if automation_runtime in {"patchright", "playwright"} else "patchright"
        )
        browser_backend_default = str(runtime_settings.get("browserBackendDefault") or "patchright").lower()
        env["PRISM_BROWSER_BACKEND_DEFAULT"] = (
            browser_backend_default if browser_backend_default in {"patchright", "persona"} else "patchright"
        )
        if settings_path_raw:
            env["PRISM_RUNTIME_SETTINGS_PATH"] = settings_path_raw
        env["PRISM_PLATFORM_BROWSER_PREFERENCES"] = json.dumps(platform_browser_preferences)
        for platform, choice in platform_browser_preferences.items():
            env[f"PRISM_PLATFORM_BROWSER_{platform.upper()}"] = choice
        env["PRISM_PLATFORM_BROWSER_TENCENT"] = platform_browser_preferences.get("channels", "chromium")
        env["PRISM_DIRECT_PLATFORMS"] = ",".join(
            self.build_direct_connect_platforms(runtime_settings.get("platformProxyPreferences"))
        )
        env["BACKEND_PORT"] = str(self.service_ports["backend"])
        env["PRISM_BACKEND_PORT"] = str(self.service_ports["backend"])
        env["AUTOMATION_WORKER_PORT"] = str(self.service_ports["automation-worker"])
        env["ENABLE_OCR_RESCUE"] = "1"
        env["ENABLE_SELENIUM_RESCUE"] = "1"
        env["ENABLE_SELENIUM_DEBUG"] = "1"
        env["FORKED_BY_MULTIPROCESSING"] = "1"
        env["HERMES_HOME"] = str(self.hermes_home_dir)
        env["HERMES_CONFIG_PATH"] = str(self.hermes_home_dir / "config.yaml")
        env["PRISM_HERMES_HOME"] = str(self.hermes_home_dir)
        env["PRISM_SUPERVISOR_MANAGES_HERMES_UI"] = "1"
        env["PRISM_HERMES_DASHBOARD_PORT"] = str(self.service_ports["hermes-dashboard"])
        env["PRISM_HERMES_WEBUI_PORT"] = str(self.service_ports["hermes-webui"])
        env["PRISM_DEEPSEEK_HARNESS_PORT"] = str(self.service_ports["deepseek-harness"])
        # 启动令牌：子进程携带，供归属校验与未来 readiness 校验使用
        env["PRISM_LAUNCH_TOKEN"] = self.launch_token
        if self.python_exe:
            env["PRISM_HERMES_PYTHON"] = str(self.python_exe)

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
            "Runtime settings applied: PLAYWRIGHT_HEADLESS=%s PRISM_AUTOMATION_RUNTIME=%s "
            "PRISM_PLATFORM_BROWSER_PREFERENCES=%s PRISM_DIRECT_PLATFORMS=%s",
            env["PLAYWRIGHT_HEADLESS"],
            env["PRISM_AUTOMATION_RUNTIME"],
            env.get("PRISM_PLATFORM_BROWSER_PREFERENCES", ""),
            env.get("PRISM_DIRECT_PLATFORMS", ""),
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

        if name == "automation-worker":
            script = self.backend_dir / "automation_worker" / "worker.py"
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
                "--hostname=prism-worker@supervisor",
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

        if name == "deepseek-harness":
            harness_dir = self.resources_path / "tools" / "deepseek-harness"
            entry = harness_dir / "apps" / "cli" / "lib" / "bin.js"
            if not entry.exists():
                raise FileNotFoundError(f"DeepSeek Harness CLI entry not found: {entry}")
            node = self._resolve_managed_binary("node", "node")
            if node is None and not self.is_packaged:
                node = shutil.which("node")
            if node is None:
                raise FileNotFoundError(
                    "Prism Node Runtime 未安装；请在 Tools 中安装 Node Runtime 后再启动 DeepSeek Harness"
                )
            return [
                node,
                str(entry),
                "web",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.service_ports["deepseek-harness"]),
                "--no-open",
            ], str(harness_dir)

        raise ValueError(f"Unsupported service: {name}")

    def _resolve_managed_binary(self, component: str, binary: str) -> Optional[str]:
        """Resolve an active versioned native component from its current manifest."""
        manifest_path = self.runtime_data_dir / "components" / component / "current.json"
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        raw = payload.get("binary") or (payload.get("binaries") or {}).get(binary)
        if not raw:
            return None
        candidate = Path(str(raw))
        if not candidate.is_absolute():
            candidate = manifest_path.parent / candidate
        return str(candidate.resolve()) if candidate.is_file() else None

    def get_service_env(self, name: str, base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        env = dict(base_env or self.build_env())
        if name in {"hermes-gateway", "hermes-dashboard", "hermes-webui"}:
            env["PYTHONPATH"] = self._build_pythonpath(
                self.hermes_dir,
                self.prismenv_site_packages,
                base=env.get("PYTHONPATH"),
                exclude=(self.backend_dir,),
            )
            env["HERMES_WEBUI_AGENT_DIR"] = str(self.hermes_dir)
            if self.python_exe:
                env["HERMES_WEBUI_PYTHON"] = str(self.python_exe)
        elif name == "deepseek-harness":
            env["DSH_HOST"] = "127.0.0.1"
            env["DSH_PORT"] = str(self.service_ports["deepseek-harness"])
            env["PRISM_DEEPSEEK_HARNESS_ROOT"] = str(self.resources_path / "tools" / "deepseek-harness")

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

        proc = self.manager.processes.get(name)
        child_pid = proc.pid if proc is not None else None

        if name == "hermes-dashboard":
            port = self.service_ports["hermes-dashboard"]
            return (
                self.is_port_in_use(port)
                and self._is_pid_listening(child_pid, port)
                and self._http_ok(f"http://127.0.0.1:{port}/")
            )

        if name == "hermes-webui":
            port = self.service_ports["hermes-webui"]
            if not self.is_port_in_use(port):
                return False
            return (
                self._is_pid_listening(child_pid, port)
                and self._http_ok(f"http://127.0.0.1:{port}/?prism_shell_health=1")
                and self._http_ok(f"http://127.0.0.1:{port}/static/boot.js?prism_shell_health=1")
            )

        if name == "deepseek-harness":
            port = self.service_ports["deepseek-harness"]
            return (
                self.is_port_in_use(port)
                and self._is_pid_listening(child_pid, port)
                and self._http_ok(f"http://127.0.0.1:{port}/")
            )

        if name == "backend":
            port = self.service_ports["backend"]
            return (
                self.is_port_in_use(port)
                and self._is_pid_listening(child_pid, port)
                and self._http_ok(f"http://127.0.0.1:{port}/health")
            )

        if name == "automation-worker":
            port = self.service_ports["automation-worker"]
            return (
                self.is_port_in_use(port)
                and self._is_pid_listening(child_pid, port)
                and self._http_ok(f"http://127.0.0.1:{port}/health")
            )

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
                self._record_failure(name, "start", "进程启动失败（start_process 返回 False）")
                return False
            if name in {"backend", "automation-worker", "hermes-dashboard", "hermes-webui", "deepseek-harness"}:
                ready = self.wait_for_service_ready(name)
                if not ready:
                    probe_port = self.service_ports.get(name)
                    log_tail = self._tail_log(name)
                    self._record_failure(
                        name,
                        "readiness",
                        f"启动后未通过就绪探测（端口 {probe_port}）；日志尾部: {log_tail[-300:] or '无'}",
                    )
                    self.manager.stop_process(name)
                    return False
            return True
        except Exception as exc:
            logger.warning("Skipping %s startup: %s", name, exc)
            self._record_failure(name, "exception", str(exc))
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
        elif name == "automation-worker":
            payload["port"] = self.service_ports["automation-worker"]
            payload["url"] = f"http://127.0.0.1:{self.service_ports['automation-worker']}"
        elif name == "hermes-dashboard":
            payload["port"] = self.service_ports["hermes-dashboard"]
            payload["url"] = f"http://127.0.0.1:{self.service_ports['hermes-dashboard']}"
            payload["dashboard_url"] = payload["url"]
        elif name == "hermes-webui":
            payload["port"] = self.service_ports["hermes-webui"]
            payload["url"] = f"http://127.0.0.1:{self.service_ports['hermes-webui']}"
            payload["webui_url"] = payload["url"]
        elif name == "deepseek-harness":
            payload["port"] = self.service_ports["deepseek-harness"]
            payload["url"] = f"http://127.0.0.1:{self.service_ports['deepseek-harness']}"
            payload["cli"] = str(self.resources_path / "tools" / "deepseek-harness" / "apps" / "cli" / "lib" / "bin.js")
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
        if name == "deepseek-harness":
            port = self.service_ports["deepseek-harness"]
            if self.is_port_in_use(port) and self._http_ok(f"http://127.0.0.1:{port}/"):
                self.mark_external_service(name, True)
                return False
            self.mark_external_service(name, False)
            return True

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

        if name in {"backend", "automation-worker", "hermes-dashboard", "hermes-webui"}:
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
        managed_redis = self._resolve_managed_binary("redis", "redis-server")
        redis_candidates = (
            self.resources_path / "prism_backend" / "Redis",
            self.resources_path / "Redis",
            self.resources_path / "redis",
        )

        redis_dir = Path(managed_redis).parent if managed_redis else None
        redis_exe = Path(managed_redis) if managed_redis else None
        redis_conf = None
        for candidate in redis_candidates:
            if redis_exe:
                break
            potential_exe = candidate / "redis-server.exe"
            if potential_exe.exists():
                redis_dir = candidate
                redis_exe = potential_exe
                redis_conf = candidate / "redis.windows.conf"
                break

        if not redis_exe and not self.is_packaged:
            system_redis = shutil.which("redis-server")
            if system_redis:
                redis_exe = Path(system_redis)
                redis_dir = redis_exe.parent

        if not redis_exe:
            logger.warning("Prism Redis Runtime 未安装；生产模式不会回退用户机器上的 Redis。")
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
        logger.info("   Prism Supervisor Start")
        logger.info("=" * 60)

        self._kill_conflicting_processes()
        self._refresh_dynamic_service_ports()
        env = self.build_env()
        self.external_services = {}

        self.start_redis(env)

        if self.start_named_service("automation-worker", env):
            time.sleep(2)
        if self.start_named_service("backend", env):
            time.sleep(3)
        self.start_named_service("hermes-dashboard", env)
        self.start_named_service("hermes-webui", env)
        self.start_named_service("deepseek-harness", env)
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
        env = self.build_env()
        restart_counts: Dict[str, int] = {}
        last_alive_at: Dict[str, float] = {}
        restart_in_flight: set[str] = set()

        def _restart(name: str, proc: subprocess.Popen) -> None:
            policy = self.restart_policy.get(name) or {}
            max_restarts = int(policy.get("max_restarts", 0))
            backoff = float(policy.get("backoff", 5.0))
            count = restart_counts.get(name, 0)
            try:
                if count >= max_restarts:
                    self._record_failure(
                        name, "crash-limit", f"已达最大重启次数 {max_restarts}，停止自动重启"
                    )
                    return
                restart_counts[name] = count + 1
                self._record_failure(
                    name, "crash", f"进程退出，准备第 {count + 1} 次重启",
                    exit_code=proc.returncode,
                )
                time.sleep(backoff)
                if self.manager.should_stop:
                    return
                logger.info("Restarting %s (attempt %d/%d)...", name, count + 1, max_restarts)
                self.start_named_service(name, env)
                self._write_state_file(getattr(self, "api_port", None))
            finally:
                restart_in_flight.discard(name)

        try:
            while not self.manager.should_stop:
                time.sleep(3)
                now = time.time()
                for name, proc in list(self.manager.processes.items()):
                    if proc.poll() is None:
                        last_alive_at[name] = now
                        continue
                    if name in restart_in_flight:
                        continue
                    policy = self.restart_policy.get(name) or {}
                    stable_after = float(policy.get("stable_after", 60.0))
                    if restart_counts.get(name, 0) > 0 and (now - last_alive_at.get(name, 0.0)) >= stable_after:
                        restart_counts[name] = 0
                        logger.info("%s 稳定运行，重启计数已重置", name)
                    logger.warning("%s exited with code %s", name, proc.returncode)
                    if name in self.restart_policy:
                        restart_in_flight.add(name)
                        threading.Thread(
                            target=_restart, args=(name, proc), daemon=True, name=f"restart-{name}"
                        ).start()
        except KeyboardInterrupt:
            logger.info("Supervisor interrupted.")
        finally:
            self.manager.stop_all()

    def _resolve_api_port(self) -> int:
        """解析 supervisor HTTP API 端口：env 显式 → 7002 → 递增找可用端口。"""
        env_port = self._read_env_port(("PRISM_SUPERVISOR_PORT", "SUPERVISOR_API_PORT"), 0)
        if env_port and self._can_bind_port(env_port):
            return env_port
        if self._can_bind_port(7002):
            return 7002
        return self._find_available_port(7002)

    def start_all(self) -> None:
        self.start_services()

    def run(self) -> None:
        try:
            from api_server import SupervisorHTTPServer

            self.api_port = self._resolve_api_port()
            self.api_server = SupervisorHTTPServer(self, port=self.api_port)
            if not self.api_server.start():
                raise RuntimeError(f"Supervisor API 启动失败（端口 {self.api_port}）")
            self.api_port = self.api_server.port  # 动态分配时回读实际绑定端口
            self._write_state_file(self.api_port)
            self.start_services()
            self._write_state_file(self.api_port)  # 服务端口确定后再写一次
            self.monitor_loop()
        except Exception as exc:
            logger.error("Supervisor runtime error: %s", exc, exc_info=True)
            self._record_failure("supervisor", "runtime", str(exc))
        finally:
            if hasattr(self, "api_server"):
                self.api_server.stop()
            self.manager.stop_all()


def main() -> None:
    supervisor = Supervisor()
    supervisor.run()


if __name__ == "__main__":
    main()
