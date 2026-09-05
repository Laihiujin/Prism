#!/usr/bin/env python3
"""Prism 本地一键部署 Web UI（纯标准库 HTTP 服务器）。

用 `python3 deploy/deploy.py webui` 启动（或 `./deploy.sh`）。
仅监听 127.0.0.1（默认端口 8440），供本机浏览器驱动一条命令完成部署。

接口：
    GET  /                       部署面板（index.html）
    GET  /api/plan               探测部署计划（JSON）
    GET  /api/status             进程 + 端点存活快照（JSON）
    POST /api/action?cmd=<...>   在后台线程执行 deploy.py 对应子命令
                                 cmd ∈ plan|install-tools|bootstrap|start|stop|full|status
    GET  /api/logs               SSE：流式尾随 runtime-data/deploy.log

保护：同一时间只允许一个动作（busy 时返回 409），避免多个部署并发互相踩。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import time
import types
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

def _load_deploy():
    """加载同目录 deploy.py（避免 'deploy' 既是目录又是模块的歧义）。"""
    p = Path(__file__).resolve().parent / "deploy.py"
    spec = importlib.util.spec_from_file_location("prismdeploy", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

deploy = _load_deploy()

DEPLOY_LOG = deploy.DEPLOY_LOG
ACTIONS = ("plan", "install-tools", "bootstrap", "start", "stop", "status", "full")


class _Runner:
    """单动作守卫：后台线程执行 deploy 子命令，产出 JSON 摘要并写 state。"""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.busy = False
        self.current: str | None = None
        self.last: dict | None = None

    def _state(self) -> dict:
        try:
            return json.loads(deploy.STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, payload: dict) -> None:
        try:
            deploy.RUNTIME_DATA.mkdir(parents=True, exist_ok=True)
            deploy.STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def start(self, cmd: str) -> bool:
        with self.lock:
            if self.busy:
                return False
            self.busy = True
            self.current = cmd
        t = threading.Thread(target=self._run, args=(cmd,), daemon=True)
        t.start()
        return True

    def _run(self, cmd: str) -> None:
        deploy.log(f"============ 动作开始: {cmd} ============")
        code = 0
        try:
            ns = types.SimpleNamespace(json=(cmd in ("plan", "status")), mirror=None,
                                       port=deploy.ENDPOINTS and 8440, host="127.0.0.1",
                                       no_open=True)
            fn = {
                "plan": deploy.cmd_plan, "install-tools": deploy.cmd_install_tools,
                "bootstrap": deploy.cmd_bootstrap, "start": deploy.cmd_start,
                "stop": deploy.cmd_stop, "status": deploy.cmd_status, "full": deploy.cmd_full,
            }[cmd]
            code = fn(ns)
        except Exception as exc:  # noqa: BLE001
            deploy.log(f"[ERROR] 动作失败: {exc}")
            code = 1
        finally:
            self._save({"cmd": cmd, "code": code, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "ok": code == 0})
            self.last = {"cmd": cmd, "code": code, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "ok": code == 0}
            deploy.log(f"============ 动作结束: {cmd} (exit {code}) ============")
            with self.lock:
                self.busy = False
                self.current = None


RUNNER = _Runner()


class Handler(BaseHTTPRequestHandler):
    server_version = "PrismDeploy/1.0"

    def log_message(self, fmt, *args):  # 静默默认访问日志
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, data) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"))

    # ------------------------------------------------------------------ GET ----
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            html = (REPO_ROOT / "deploy" / "webui" / "index.html")
            if html.exists():
                self._send(200, html.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(200, b"<h1>Prism Deploy</h1><p>index.html missing</p>",
                           "text/html; charset=utf-8")
            return
        if path == "/api/plan":
            try:
                self._json(200, deploy.compute_plan())
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": str(exc)})
            return
        if path == "/api/status":
            try:
                ns = types.SimpleNamespace(json=True)
                import io
                from contextlib import redirect_stdout
                buf = io.StringIO()
                with redirect_stdout(buf):
                    deploy.cmd_status(ns)
                # cmd_status(json=True) 已把 JSON 打印到 stdout；解析回来
                self._json(200, json.loads(buf.getvalue() or "{}"))
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": str(exc)})
            return
        if path == "/api/logs":
            self._sse()
            return
        self._json(404, {"error": "not found", "path": path})

    # ------------------------------------------------------------------ SSE ----
    def _sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            offset = 0
            if DEPLOY_LOG.exists():
                offset = DEPLOY_LOG.stat().st_size
                # 先回放最近 40 行，让面板一打开就有内容
                lines = DEPLOY_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
                for ln in lines:
                    self._sse_data("log", ln)
            while True:
                time.sleep(0.6)
                if RUNNER.busy or (DEPLOY_LOG.exists() and DEPLOY_LOG.stat().st_size > offset):
                    with open(DEPLOY_LOG, "r", encoding="utf-8", errors="replace") as fh:
                        fh.seek(offset)
                        new = fh.read()
                    offset += len(new)
                    for ln in new.splitlines():
                        self._sse_data("log", ln)
                    if not RUNNER.busy and RUNNER.last:
                        self._sse_data("done", json.dumps(RUNNER.last, ensure_ascii=False))
                        RUNNER.last = None
                elif not RUNNER.busy:
                    # 心跳，避免代理/浏览器把连接判死
                    self._sse_data("ping", int(time.time()))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:  # noqa: BLE001
            pass

    def _sse_data(self, event: str, data) -> None:
        self.wfile.write(f"event: {event}\ndata: {data}\n\n".encode("utf-8"))
        self.wfile.flush()

    # ----------------------------------------------------------------- POST ----
    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path != "/api/action":
            self._json(404, {"error": "not found"})
            return
        import urllib.parse
        qs = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        cmd = (qs.get("cmd") or [""])[0]
        if cmd not in ACTIONS:
            self._json(400, {"error": f"unknown cmd, expected one of {ACTIONS}"})
            return
        if not RUNNER.start(cmd):
            self._json(409, {"error": "busy", "current": RUNNER.current})
            return
        deploy.log(f"Web UI 触发: {cmd}")
        self._json(200, {"ok": True, "started": cmd})


def serve(port: int = 8440, host: str = "127.0.0.1", no_open: bool = False) -> int:
    deploy.RUNTIME_DATA.mkdir(parents=True, exist_ok=True)
    # 确保 deploy.log 存在，SSE 才能正确 seek
    if not DEPLOY_LOG.exists():
        DEPLOY_LOG.write_text("", encoding="utf-8")
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    deploy.log(f"部署 Web UI 已启动: {url}  （仅本机可访问）")
    deploy.log("关闭: Ctrl+C")
    if not no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        deploy.log("Web UI 关闭")
        httpd.server_close()
    return 0
