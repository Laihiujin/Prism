#!/usr/bin/env python3
"""Prism 本地一键部署「命令」核心编排器（纯标准库，跨平台）。

这是「纯 cmd/terminal 就能部署」的引擎：它把一台新机器上要做的所有事
（检测/补齐 Node、Redis、Python 运行时、prismenv、前端依赖、.env、浏览器、
PM2 启动、健康检查）编排成可重复执行的步骤；并暴露给 `webui` 子命令所带的
部署 Web UI 逐条调用（plan / install-tools / bootstrap / start / stop / status）。

原则：
  * 只用标准库（在这台机器上还没 python 之前就能跑）。
  * 幂等——每一坑都检测「已经做好就跳过」，可反复执行。
  * 日志同时打到 stdout 与 runtime-data/deploy.log，供 Web UI 以 SSE 流式尾随。

常用命令（仓库根目录）：
    python3 deploy/deploy.py plan                 # 只探测/打印部署计划，不改动
    python3 deploy/deploy.py install-tools        # 补齐缺失的 Node/Redis 等外部工具
    python3 deploy/deploy.py bootstrap            # Prism 运行时（prismenv/前端/.env/浏览器）
    python3 deploy/deploy.py start                # PM2 拉起整套进程 + 健康检查
    python3 deploy/deploy.py status               # 进程 + 端点存活快照（供 Web UI）
    python3 deploy/deploy.py stop                 # 停掉 PM2 管理的整套进程
    python3 deploy/deploy.py full                 # plan -> install-tools -> bootstrap -> start（一键）
    python3 deploy/deploy.py webui                # 启动部署 Web UI（默认 127.0.0.1:8440）

选项：
    --mirror tuna|aliyun|official   供给时使用的镜像（默认 tuna）
    --port <port>                   webui 监听端口（默认 8440）
    --no-open                       webui 不自动打开浏览器
    --json                          让 plan/status 输出机器可读 JSON
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------- 路径/常量 -----

REPO_ROOT = Path(__file__).resolve().parents[1]        # deploy/ -> 仓库根
DEPLOY_DIR = Path(__file__).resolve().parent
RUNTIME_DATA = Path(os.environ.get("PRISM_RUNTIME_DATA_DIR", REPO_ROOT / "runtime-data"))
DEPLOY_LOG = RUNTIME_DATA / "deploy.log"
STATE_FILE = RUNTIME_DATA / "deploy-state.json"
TOOLS_DIR = Path(os.environ.get("PRISM_TOOLS_DIR", REPO_ROOT / ".tools"))

PRISMENV = REPO_ROOT / "prismenv"
FRONTEND = REPO_ROOT / "prism_frontend"
IS_WIN = os.name == "nt"

DEFAULT_MIRROR = "tuna"
NPM_CACHE = REPO_ROOT / ".cache" / "npm"

# 供 Web UI 展示的端点清单（探测存活用）
ENDPOINTS = [
    {"name": "Prism 控制台", "label": "frontend", "url": "http://localhost:3000"},
    {"name": "后端 API", "label": "backend", "url": None},          # 端口动态，从 runtime.json 取
    {"name": "Worker 健康", "label": "worker", "url": "http://127.0.0.1:7001/health"},
    {"name": "Persona API", "label": "persona-api", "url": "http://127.0.0.1:8787"},
    {"name": "Hermes 面板", "label": "hermes-dashboard", "url": "http://127.0.0.1:9119"},
    {"name": "Hermes WebUI", "label": "hermes-webui", "url": "http://127.0.0.1:9131"},
    {"name": "DeepSeek", "label": "deepseek-harness", "url": "http://127.0.0.1:3080"},
    {"name": "Persona 代理", "label": "persona-proxy", "url": "http://127.0.0.1:7771"},
]

# ----------------------------------------------- 日志（stdout + deploy.log） ----

def log(msg: str, *, sink: bool = True) -> None:
    line = f"[deploy] {msg}"
    print(line, flush=True)
    if sink:
        try:
            RUNTIME_DATA.mkdir(parents=True, exist_ok=True)
            with open(DEPLOY_LOG, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            pass


def warn(msg: str) -> None:
    log(f"[warn] {msg}")


def err(msg: str) -> None:
    log(f"[ERROR] {msg}")
    print(f"[deploy][ERROR] {msg}", file=sys.stderr, flush=True)


def _live_env(extra: dict | None = None) -> dict:
    """返回一份 PATH 已扩展、带 .tools/prismenv 的进程环境。"""
    env = dict(os.environ)
    path_dirs = []
    for p in (TOOLS_DIR / "node" / "bin", TOOLS_DIR / "node", TOOLS_DIR / "redis",
              TOOLS_DIR / "python" / "bin", TOOLS_DIR / "python",
              REPO_ROOT / "node_modules" / ".bin",
              PRISMENV / "bin", PRISMENV / "Scripts"):
        if p.exists():
            path_dirs.append(str(p))
    env["PATH"] = os.pathsep.join(path_dirs + [env.get("PATH", "")])
    env["npm_config_cache"] = str(NPM_CACHE)
    if extra:
        env.update(extra)
    return env


def run(cmd: list[str], *, cwd: str | None = None, check: bool = True,
        capture: bool = False, timeout: float | None = None, extra_env: dict | None = None,
        desc: str | None = None) -> subprocess.CompletedProcess:
    """跨平台 shell 执行。Windows 上含 .cmd/.bat 的命令需 shell=True。"""
    if desc:
        log(desc)
    env = _live_env(extra_env)
    force_shell = IS_WIN and any(c.endswith((".cmd", ".bat", ".ps1")) or c in ("npm", "npx")
                                  for c in cmd[:4])
    kwargs = dict(cwd=cwd or str(REPO_ROOT), env=env, shell=force_shell)
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    if timeout:
        kwargs["timeout"] = timeout
    proc = subprocess.run(cmd, **kwargs)
    if check and proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-8:]
        raise RuntimeError(f"命令失败(exit {proc.returncode}): {' '.join(cmd)}\n" + "\n".join(tail))
    return proc


def which(name: str) -> str | None:
    return shutil.which(name)


# ------------------------------------------------------------- 下载/解压工具 ----

def download(url: str, dest: Path, desc: str | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if desc:
        log(desc)
    req = urllib.request.Request(url, headers={"User-Agent": "Prism-Deployer/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            if total:
                pct = min(100, int(done * 100 / total))
                log(f"    {desc} {done // 1048576}MB/{total // 1048576}MB ({pct}%)", sink=False)
    log(f"OK 下载完成 -> {dest} ({dest.stat().st_size // 1048576}MB)")
    return dest


def extract_archive(archive: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    log(f"解压 {archive.name} -> {dest}")
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
    elif archive.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive, "r:gz") as tf:
            _safe_extract(tf, dest)
    else:
        raise RuntimeError(f"不支持的归档格式: {archive}")
    return dest


def _safe_extract(tf: tarfile.TarFile, dest: Path) -> None:
    for m in tf.getmembers():
        resolved = (dest / m.name).resolve()
        if not str(resolved).startswith(str(dest.resolve())):
            raise RuntimeError(f"tar 中检测到非法路径: {m.name}")
    tf.extractall(dest)


# ------------------------------------------------------------- 探测外部工具 ----

def _detect_python() -> dict:
    if IS_WIN:
        candidates = ["py", "python", "python3"]
    else:
        candidates = ["python3", "python"]
    found: dict = {}
    for cand in candidates:
        exe = which(cand)
        if not exe:
            continue
        try:
            out = run([exe, "-c", "import sys;print('%d.%d'%sys.version_info[:2])"],
                      capture=True, check=False).stdout.strip()
        except Exception:
            out = ""
        if out:
            ver = tuple(int(x) for x in out.split(".")[:2])
            found[exe] = {"python": exe, "version": out, "tuple": ver}
    for exe, info in sorted(found.items(),
                            key=lambda kv: (kv[1]["tuple"] >= (3, 11), kv[1]["tuple"] >= (3, 9)),
                            reverse=True):
        return {**info, "kind": "system"}
    if found:
        first = next(iter(found.values()))
        return {**first, "kind": "system"}
    return {"kind": "missing", "python": None, "version": None}


def _detect_node() -> dict:
    node = which("node")
    npm = which("npm")
    if node and npm:
        try:
            v = run([node, "--version"], capture=True, check=False).stdout.strip()
        except Exception:
            v = "?"
        return {"present": True, "node": node, "npm": npm, "version": v}
    return {"present": False, "node": None, "npm": None, "version": None}


def _detect_redis() -> dict:
    return {"present": which("redis-server") is not None,
            "server": which("redis-server"), "cli": which("redis-cli")}


def _detect_git() -> dict:
    return {"present": which("git") is not None, "path": which("git")}


def _system_chrome() -> str | None:
    cands = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Firefox.app/Contents/MacOS/firefox",
        "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium", "/usr/bin/firefox",
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    ]
    for c in cands:
        if Path(c).is_file():
            return c
    return None


def _prismenv_python() -> Path | None:
    for cand in (PRISMENV / "bin" / "python", PRISMENV / "Scripts" / "python.exe",
                 PRISMENV / "python.exe"):
        if cand.exists():
            return cand
    return None


def check_redis_ping() -> bool:
    cli = which("redis-cli")
    if not cli:
        return False
    try:
        out = run([cli, "ping"], capture=True, check=False, timeout=10).stdout.strip()
        return out == "PONG"
    except Exception:
        return False


# ------------------------------------------------------------------- plan -----

def compute_plan() -> dict:
    data = {"os": {"name": os.name, "platform": platform.system(),
                   "release": platform.release(), "arch": platform.machine()},
            "repository": str(REPO_ROOT), "time": time.strftime("%Y-%m-%d %H:%M:%S")}

    py = _detect_python()
    data["python"] = py
    node = _detect_node()
    data["node"] = node
    redis = _detect_redis()
    redis_running = check_redis_ping()
    data["redis"] = {**redis, "running": redis_running}
    git = _detect_git()
    data["git"] = git
    data["micromamba"] = {"embedded": (REPO_ROOT / "scripts" / "packaging" / "provision" /
                                        "micromamba" / "micromamba").exists(),
                          "path": which("micromamba")}
    data["prismenv_python"] = str(_prismenv_python()) if _prismenv_python() else None
    data["frontend_node_modules"] = (FRONTEND / "node_modules").exists()
    data["root_pm2"] = (REPO_ROOT / "node_modules" / ".bin" /
                        ("pm2.cmd" if IS_WIN else "pm2")).exists()
    data["chrome"] = _system_chrome()
    data["managed_browsers"] = any((RUNTIME_DATA / "components" / "browsers").glob("*"))
    data["runtime_backend"] = _read_runtime_backend()

    python_ok = py["kind"] == "system" or _prismenv_python() is not None
    node_ok = node.get("present", False)
    redis_ok = redis.get("present", False)
    git_ok = git.get("present", False)
    browser_ok = bool(data["chrome"] or data["managed_browsers"])

    data["stages"] = {
        "python":  {"ok": python_ok, "need": not python_ok,
                    "action": "使用仓库内嵌 micromamba 自供给 prismenv" if not python_ok else "已可用"},
        "node":    {"ok": node_ok, "need": not node_ok,
                    "action": "下载便携 Node(官方包) 到 .tools/node" if not node_ok else "已可用"},
        "redis":   {"ok": redis_ok, "need": not redis_ok,
                    "action": ("启动本机 redis-server" if redis_ok else
                               ("下载便携 Redis(仅 Windows) 到 .tools/redis"
                                if IS_WIN else "安装 Redis(brew/apt)。见提示"))},
        "git":     {"ok": git_ok, "need": not git_ok, "soft": True,
                    "action": "可选：仅克隆/更新仓库时需要"},
        "browser": {"ok": browser_ok, "need": not browser_ok, "soft": True,
                    "action": "未发现本机/受管浏览器，可稍后 patchright install chromium"},
        "env":     {"ok": (REPO_ROOT / ".env").exists(), "need": not (REPO_ROOT / ".env").exists(),
                    "action": "从 env.example 复制生成 .env"},
    }
    data["all_ready"] = python_ok and node_ok and redis_ok and data["stages"]["env"]["ok"]
    return data


def _read_runtime_backend() -> dict | None:
    try:
        return json.loads((RUNTIME_DATA / "runtime.json").read_text(encoding="utf-8"))
    except Exception:
        return None


def cmd_plan(args) -> int:
    data = compute_plan()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print("=" * 70)
    print(f"  Prism 部署计划  ({data['os']['platform']}/{data['os']['arch']})")
    print("=" * 70)
    for key, label in (("python", "Python"), ("node", "Node/npm"), ("redis", "Redis"),
                       ("git", "git"), ("micromamba", "micromamba")):
        v = data.get(key, {})
        present = bool(v.get("present", True) if key != "python" else v.get("kind") == "system")
        detail = ""
        if key == "python":
            detail = v.get("version") or (f"prismenv={_prismenv_python()}" if _prismenv_python() else "缺失")
        elif key == "node":
            detail = v.get("version") or "缺失"
        elif key == "redis":
            detail = (v.get("server") or "缺失") + (" (运行中)" if v.get("running") else " (未运行)")
        elif key == "git":
            detail = v.get("path") or "缺失"
        elif key == "micromamba":
            detail = ("内嵌" if v.get("embedded") else "缺失") + (f" | PATH={v['path']}" if v.get("path") else "")
        mark = "✓" if present else ("⚠" if v.get("soft") or key in ("git",) else "✗")
        print(f"  {mark} {label:<11} {detail}")
    print("-" * 70)
    for key, s in data["stages"].items():
        mark = "✓" if s["ok"] else ("⚠" if s.get("soft") else "✗")
        print(f"  {mark} {key:<9} {s['action']}")
    print("=" * 70)
    print("  结论:", "可一键部署 ✓" if data["all_ready"] else "存在缺失项，运行 install-tools/bootstrap 补齐")
    print("  一键: python3 deploy/deploy.py full")
    return 0


# ------------------------------------------------------------ install-tools ----

def _resolve_node_dist() -> tuple[str, bool, str]:
    """从 nodejs.org 解析当前平台最新 LTS 安装包：返回 (url, 是否zip, 顶层目录名)。"""
    spec = "win" if IS_WIN else ("darwin" if platform.system() == "Darwin" else "linux")
    arch = platform.machine().lower()
    if arch in ("x86_64", "amd64"):
        arch = "x64"
    elif arch in ("arm64", "aarch64"):
        arch = "arm64"
    req = urllib.request.Request("https://nodejs.org/dist/index.json",
                                 headers={"User-Agent": "Prism-Deployer/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        index = json.loads(resp.read().decode("utf-8"))
    ver = None
    for entry in index:
        if entry.get("lts"):
            ver = entry["version"]
            break
    if not ver:
        raise RuntimeError("无法从 nodejs.org 解析 LTS 版本")
    ext = "zip" if spec == "win" else "tar.gz"
    fname = f"node-{ver}-{spec}-{arch}"
    return f"https://nodejs.org/dist/{ver}/{fname}.{ext}", ext == "zip", fname


def install_node() -> bool:
    if _detect_node()["present"]:
        log("Node 已存在，跳过下载")
        return True
    url, is_zip, top = _resolve_node_dist()
    log(f"下载便携 Node: {url}")
    archive = TOOLS_DIR / (os.path.basename(url) or "node")
    download(url, archive, "下载 Node...")
    extract_archive(archive, TOOLS_DIR / "_node_extract")
    src = TOOLS_DIR / "_node_extract" / top
    dst = TOOLS_DIR / "node"
    if dst.exists() and not (dst / ("bin" if not IS_WIN else "node.exe")).exists():
        shutil.rmtree(dst, ignore_errors=True)
    if not dst.exists():
        src.rename(dst)
    shutil.rmtree(TOOLS_DIR / "_node_extract", ignore_errors=True)
    shutil.rmtree(archive, ignore_errors=True)
    log(f"Node 就绪: {dst}（PATH 已加入）")
    return True


def install_redis() -> bool:
    d = _detect_redis()
    if d["present"]:
        log("redis-server 已存在，跳过下载")
        return True
    if not IS_WIN:
        warn("非 Windows 平台：请用系统包管理器安装 Redis（brew/apt），脚本不自动改系统。")
        return False
    url = ("https://github.com/tporadowski/redis/releases/download/v5.0.14.1/"
           "Redis-x64-5.0.14.1.zip")
    log("下载便携 Redis(Windows)...")
    archive = TOOLS_DIR / "redis.zip"
    download(url, archive, "下载 Redis...")
    extract_archive(archive, TOOLS_DIR / "_redis_extract")
    srcdirs = [p for p in (TOOLS_DIR / "_redis_extract").iterdir() if p.is_dir()]
    if not srcdirs:
        raise RuntimeError("Redis 解压后未见目录")
    dst = TOOLS_DIR / "redis"
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    srcdirs[0].rename(dst)
    shutil.rmtree(TOOLS_DIR / "_redis_extract", ignore_errors=True)
    shutil.rmtree(archive, ignore_errors=True)
    log(f"Redis 就绪: {dst}（已加入 PATH）")
    return True


def cmd_install_tools(args) -> int:
    data = compute_plan()
    ok = True
    if data["node"]["present"] is False:
        ok &= install_node()
    if data["redis"]["present"] is False:
        if IS_WIN:
            ok &= install_redis()
    if data["git"]["present"] is False:
        warn("git 缺失（可选，仅在需要克隆/更新仓库时需要）。")
    if data["python"]["kind"] == "missing" and _prismenv_python() is None:
        warn("未找到 Python：将由 bootstrap 阶段用内嵌 micromamba 自供给 prismenv。")
    log("install-tools 完成。继续: python3 deploy/deploy.py bootstrap")
    return 0 if ok else 2


# --------------------------------------------------------------- bootstrap ----

def ensure_python_runtime(mirror: str) -> Path:
    if _prismenv_python() and _prismenv_python().exists():
        log(f"复用 prismenv: {_prismenv_python()}")
        return _prismenv_python()
    mm_embedded = REPO_ROOT / "scripts" / "packaging" / "provision" / "micromamba" / "micromamba"
    mm = str(mm_embedded) if mm_embedded.exists() else which("micromamba")
    if not mm:
        err("未找到 micromamba，且无 prismenv。请先在 provision/micromamba/ 放入对应平台二进制。")
        raise RuntimeError("micromamba missing")
    base = _detect_python()
    if base["kind"] != "system":
        err("未找到可用的 Python 来运行 provision.py。")
        raise RuntimeError("python missing")
    log(f"用 micromamba 自供给 prismenv（python=3.11, mirror={mirror}）...")
    prov = REPO_ROOT / "scripts" / "packaging" / "provision" / "provision.py"
    run([base["python"], str(prov), "--all", "--mirror", mirror],
        desc="  供给共享运行时 + 隔离组件环境(provision.py --all) ...")
    py = _prismenv_python()
    if not py or not py.exists():
        raise RuntimeError("供给完成但未见 prismenv python")
    return py


def ensure_node_deps() -> None:
    if _detect_node()["present"] is False:
        err("Node 仍不可用，跳过 npm 依赖。先运行 install-tools。")
        raise RuntimeError("node missing")
    if not (FRONTEND / "node_modules").exists():
        log("安装前端依赖 (npm install, prism_frontend)...")
        run(["npm", "install"], cwd=str(FRONTEND), desc="  npm install prism_frontend")
        log("OK 前端依赖")
    else:
        log("前端 node_modules 已存在")
    pm2_bin = "pm2.cmd" if IS_WIN else "pm2"
    if not (REPO_ROOT / "node_modules" / ".bin" / pm2_bin).exists():
        log("安装根目录依赖(含 pm2) (npm install)...")
        run(["npm", "install"], cwd=str(REPO_ROOT), desc="  npm install root")
        log("OK 根目录依赖")
    else:
        log("根目录 pm2 已就绪")


def ensure_env_file() -> None:
    env = REPO_ROOT / ".env"
    if env.exists():
        log(".env 已存在")
        return
    example = REPO_ROOT / "env.example"
    if example.exists():
        shutil.copyfile(example, env)
        log("OK 已从 env.example 复制生成 .env")


def ensure_browser(py: Path) -> None:
    if _system_chrome():
        log("浏览器: 复用本机浏览器")
        return
    if any((RUNTIME_DATA / "components" / "browsers").glob("*")):
        log("浏览器: 已有受管浏览器")
        return
    log("浏览器: 未发现浏览器，尝试 patchright 安装 chromium(约150MB)...")
    try:
        run([str(py), "-m", "patchright", "install", "chromium"], check=False,
            desc="  patchright install chromium（失败不致命）")
        log("OK 浏览器安装完成")
    except Exception:
        warn("浏览器安装失败，可在账号登录前再一键安装。功能不受影响。")


def ensure_redis_up() -> None:
    if check_redis_ping():
        log("Redis 运行中")
        return
    srv = _detect_redis()
    if srv["present"]:
        log("检测到 redis-server 但未运行，尝试后台启动...")
        try:
            run([srv["server"], "--daemonize", "yes"], check=False)
            time.sleep(1.5)
            log("Redis 运行中" if check_redis_ping() else "Redis 启动后未响应，请检查日志")
        except Exception:
            warn("Redis 启动失败，请手动: redis-server --daemonize yes")
    else:
        warn("Redis 缺失：请先运行 install-tools 或安装 Redis。")


def cmd_bootstrap(args) -> int:
    mirror = getattr(args, "mirror", None) or os.environ.get("PRISM_PROVISION_MIRROR", DEFAULT_MIRROR)
    py = ensure_python_runtime(mirror)
    ensure_node_deps()
    ensure_env_file()
    ensure_redis_up()
    ensure_browser(py)
    log("bootstrap 阶段完成 ✅")
    return 0


# ----------------------------------------------------------------- start -----

def resolve_pm2() -> str:
    cands = [REPO_ROOT / "node_modules" / ".bin" / ("pm2.cmd" if IS_WIN else "pm2"),
             FRONTEND / "node_modules" / ".bin" / ("pm2.cmd" if IS_WIN else "pm2"),
             Path(which("pm2")) if which("pm2") else None]
    for c in cands:
        if c and Path(c).exists():
            return str(c)
    raise RuntimeError("未找到 pm2。请先: python3 deploy/deploy.py bootstrap")


def cmd_start(args) -> int:
    pm2 = resolve_pm2()
    py = _prismenv_python()
    if not py:
        err("prismenv python 不存在，请先 bootstrap")
        return 2
    RUNTIME_DATA.mkdir(parents=True, exist_ok=True)
    log("清理旧进程(pm2 delete all) ...")
    run([pm2, "delete", "all"], check=False, desc="  pm2 delete all")
    log("选择后端端口(prism_runtime prepare)...")
    run([str(py), str(REPO_ROOT / "scripts" / "prism_runtime.py"), "prepare"],
        desc="  prism_runtime prepare")
    log("启动 redis + backend ...")
    run([pm2, "start", "ecosystem.config.js", "--only", "prism-redis,prism-backend", "--update-env"],
        desc="  pm2 start prism-redis,prism-backend")
    log("健康检查后端(最多60s)...")
    if run([str(py), str(REPO_ROOT / "scripts" / "prism_runtime.py"), "health", "--timeout", "60"],
           check=False).returncode != 0:
        warn("后端绑定失败，重选端口并重试一次...")
        run([pm2, "delete", "prism-backend"], check=False)
        run([str(py), str(REPO_ROOT / "scripts" / "prism_runtime.py"), "prepare"], check=False)
        run([pm2, "start", "ecosystem.config.js", "--only", "prism-backend", "--update-env"], check=False)
        run([str(py), str(REPO_ROOT / "scripts" / "prism_runtime.py"), "health", "--timeout", "60"], check=False)
    log("启动全套进程(worker/celery/frontend/persona/hermes/deepseek)...")
    # 可选组件（deepseek-harness 等）可能未克隆，缺失只警告、不视为失败；核心进程与否靠健康检查兜底。
    rc = run([pm2, "start", "ecosystem.config.js", "--only",
              "prism-worker,prism-celery,prism-frontend,persona-api,persona-proxy,persona-dashboard,"
              "hermes-dashboard,hermes-webui,deepseek-harness", "--update-env"],
             desc="  pm2 start 其余进程", check=False)
    if rc.returncode != 0:
        warn("部分进程启动返回非零（通常是可选组件缺失，如 deepseek-harness）。核心进程不受影响。")
    log("=" * 52)
    log("  Prism 已启动")
    log("=" * 52)
    backend = _read_runtime_backend()
    log("  前端控制台  http://localhost:3000")
    if backend:
        log(f"  后端 API    {backend.get('backend_url')}/api/docs")
    log("  常用: PM2_HOME=runtime-data/pm2 pm2 logs / restart all / stop all")
    return 0


# ------------------------------------------------------------------ stop -----

def cmd_stop(args) -> int:
    pm2 = resolve_pm2()
    log("停止 PM2 管理的全部进程...")
    run([pm2, "delete", "all"], check=False, desc="  pm2 delete all")
    if not IS_WIN:
        for pat in ("fastapi_app/run.py", "automation_worker/worker.py", "celery -A fastapi_app"):
            try:
                run(["pkill", "-f", pat], check=False)
            except Exception:
                pass
    log("已停止")
    return 0


# ---------------------------------------------------------------- status -----

def probe(url: str, timeout: float = 4) -> bool:
    import urllib.error
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True  # 服务器有响应即视为存活
    except urllib.error.HTTPError:
        return True      # 4xx/5xx 也说明服务在监听
    except Exception:
        return False     # 连不上/超时


def cmd_status(args) -> int:
    data = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "backend": _read_runtime_backend(),
            "pm2": [], "endpoints": []}
    pm2 = None
    try:
        pm2 = resolve_pm2()
    except Exception:
        pass
    if pm2:
        try:
            out = run([pm2, "jlist"], capture=True, check=False).stdout
            data["pm2"] = json.loads(out.strip() or "[]")
        except Exception:
            data["pm2"] = []
    backend_url = (data["backend"] or {}).get("backend_url")
    for ep in ENDPOINTS:
        url = ep["url"]
        if ep["label"] == "backend" and backend_url:
            url = backend_url + "/health"
        up = probe(url) if url else False
        data["endpoints"].append({**ep, "ok": up})
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print("=" * 70)
    print("  Prism 运行状态")
    print("=" * 70)
    if data["pm2"]:
        print(f"  {'Name':<18}{'Status':<11}{'Restarts'}")
        for app in data["pm2"]:
            print(f"  {app.get('name','?'):<18}{app.get('pm2_env',{}).get('status','?'):<11}"
                  f"{app.get('pm2_env',{}).get('restart_time',0)}")
    else:
        print("  (pm2 未运行或无进程)")
    print("-" * 70)
    print("  Endpoint                              Status")
    for ep in data["endpoints"]:
        mark = "UP   " if ep["ok"] else "DOWN "
        url = (ep.get("url") or (backend_url + "/health" if ep["label"] == "backend" else ""))
        print(f"  {mark} {ep['label']:<14} {url}")
    print("=" * 70)
    return 0


# ----------------------------------------------------------------- full ------

def cmd_full(args) -> int:
    log("============ Prism 一键部署 ============")
    log("阶段 1/4 探测... (plan)")
    compute_plan()
    log("阶段 2/4 补齐外部工具... (install-tools)")
    cmd_install_tools(args)
    log("阶段 3/4 引导 Prism 运行时... (bootstrap)")
    cmd_bootstrap(args)
    log("阶段 4/4 启动全套进程... (start)")
    cm = cmd_start(args)
    log("---------- 一键部署完成 ----------")
    return cm


# ---------------------------------------------------------------- webui -------

def cmd_webui(args) -> int:
    import importlib.util
    p = Path(__file__).resolve().parent / "webui_server.py"
    spec = importlib.util.spec_from_file_location("prismwebui", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.serve(port=args.port, host=args.host, no_open=args.no_open)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prism 本地一键部署命令核心")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan").add_argument("--json", action="store_true")
    sub.add_parser("install-tools")
    sub.add_parser("bootstrap").add_argument("--mirror", default=None)
    sub.add_parser("start")
    sub.add_parser("stop")
    sub.add_parser("status").add_argument("--json", action="store_true")
    sub.add_parser("full")
    sw = sub.add_parser("webui")
    sw.add_argument("--port", type=int, default=8440)
    sw.add_argument("--host", default="127.0.0.1")
    sw.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    RUNTIME_DATA.mkdir(parents=True, exist_ok=True)

    dispatch = {
        "plan": cmd_plan, "install-tools": cmd_install_tools, "bootstrap": cmd_bootstrap,
        "start": cmd_start, "stop": cmd_stop, "status": cmd_status, "full": cmd_full,
        "webui": cmd_webui,
    }
    try:
        return dispatch[args.cmd](args)
    except KeyboardInterrupt:
        return 130
    except RuntimeError as exc:
        err(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
