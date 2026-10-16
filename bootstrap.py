#!/usr/bin/env python3
"""Prism 一键环境引导（跨平台）。

这是 Prism 自托管部署的“配方”入口：在一台干净的机器上，
用一个命令就把 micromamba conda 环境（prismenv）、Python 依赖、前端/根目录 npm 依赖
（根目录提供 macOS 用的 pm2）、.env、Redis、浏览器（Chromium / Firefox）一次性准备到可运行状态。

它把之前散落在 README / 命令行里的手工步骤统一起来，
并保证可重复执行（幂等）：已经做过的步骤会跳过，不会重复装。

用法（单命令，跨平台）
----
    python3 bootstrap.py                 # 一键部署：装齐 Node/npm、Redis、依赖、浏览器 + PM2 启动
    python3 bootstrap.py start           # 快速启动（假定环境已就绪，跳过浏览器）
    python3 bootstrap.py stop            # 停止（pm2 delete all，保留数据）
    python3 bootstrap.py status          # 查看 PM2 进程状态
    python3 bootstrap.py --dev           # 部署时额外安装开发依赖 requirements-dev.txt
    python3 bootstrap.py --no-browsers   # 部署时跳过浏览器安装（首次装 Chromium 较大）
    python3 bootstrap.py --check         # 只检查环境，不改动

唯一前提：机器上有一个 Python 3.11+（macOS 自带；Windows 装一次官方安装包即可）。
其余（Node/npm、Redis、pip 依赖、前端与根目录依赖、浏览器、整套服务）都由本命令自动装齐并拉起。

设计约定
--------
- 统一使用项目根目录下名为 `prismenv` 的虚拟环境（这是整个仓库的规范命名，
  脚本 / 打包 / README / 桌面端都依赖这个名字）。不再使用 `.venv`。
- Redis 是系统服务（不是 pip 包），本脚本负责探测并给出安装/启动指引，
  但不会擅自改系统；请按提示手动安装。
- 幂等依赖：环境内 `.requirements-ready` 时间戳文件，若比 requirements 文件新则跳过 pip 安装。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# Preserve the drive created by start.bat's pushd. resolve() dereferences
# mapped network drives back to UNC, which cmd.exe cannot use as its cwd.
REPO_ROOT = Path(os.path.abspath(__file__)).parent
ENV_NAME = "prismenv"
ENV_DIR = Path(os.environ.get("PRISM_ENV_DIR", REPO_ROOT / ENV_NAME))
FRONTEND_DIR = REPO_ROOT / "prism_frontend"
REQUIREMENTS = [REPO_ROOT / "requirements.txt"]
REQUIREMENTS_DEV = [REPO_ROOT / "requirements-dev.txt"]
STAMP_NAME = ".requirements-ready"

# macOS 上的系统浏览器路径（用于“复用本机 Chrome，免下载 Chromium”）
_SYSTEM_CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
]


def _runtime_python() -> Path:
    if os.name == "nt":
        return ENV_DIR / "python.exe"
    return ENV_DIR / "bin" / "python"


def _log(msg: str) -> None:
    print(f"[prism-bootstrap] {msg}")


def _run(cmd: list[str], *, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    kwargs.setdefault("cwd", str(REPO_ROOT))
    if os.name == "nt":
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    # Windows utilities may emit GBK even when the parent uses PYTHONUTF8.
    if kwargs.get("text") or kwargs.get("universal_newlines") or kwargs.get("encoding"):
        kwargs.setdefault("errors", "replace")
    if os.name == "nt" and isinstance(cmd, list) and cmd[0].lower().endswith((".cmd", ".bat")):
        kwargs.setdefault("shell", True)
    return subprocess.run(cmd, check=check, **kwargs)


def _iter_python_candidates() -> list[str]:
    """候选 base Python 可执行文件列表（含常见绝对安装路径 + PATH）。"""
    found: list[str] = []
    # 常见绝对路径（在这些系统上 python3.11 不一定在 PATH 里）
    known = [
        "/opt/homebrew/opt/python@3.11/bin/python3.11",
        "/usr/local/opt/python@3.11/bin/python3.11",
        "/opt/homebrew/opt/python@3.12/bin/python3.12",
        "/usr/local/opt/python@3.12/bin/python3.12",
        "/usr/bin/python3.11",
        "/usr/bin/python3.12",
        "/usr/bin/python3",
    ]
    for p in known:
        if Path(p).is_file():
            found.append(p)
    for cand in ("python3.11", "python3.12", "python3", "python", "py"):
        exe = shutil.which(cand)
        if exe and exe not in found and not Path(exe).absolute().is_relative_to(ENV_DIR):
            found.append(exe)
    if not Path(sys.executable).absolute().is_relative_to(ENV_DIR) and sys.executable not in found:
        found.append(sys.executable)
    return found


def _python_version(exe: str) -> str | None:
    try:
        out = _run(
            [exe, "-c", "import sys;print('%d.%d'%sys.version_info[:2])"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        return out or None
    except Exception:
        return None


def _base_python() -> str:
    """解析系统里最合适的 base Python（优先 3.11，兼容 3.9~3.12）。"""
    preferred = ("3.11", "3.12", "3.10")
    fallback: str | None = None
    for exe in _iter_python_candidates():
        v = _python_version(exe)
        if v is None:
            continue
        if v in preferred:
            return exe
        if fallback is None:
            fallback = exe  # 记录第一个可用版本作为兜底
    if fallback:
        return fallback
    raise RuntimeError(
        "未找到可用 Python。请先安装 Python 3.11：\n"
        "  macOS:   brew install python@3.11\n"
        "  Ubuntu:  sudo apt install python3.11\n"
        "  Windows: 官网 https://www.python.org/downloads/ 安装时勾选 Add to PATH"
    )


def ensure_runtime() -> bool:
    """通过统一供给器创建 micromamba 环境。"""
    py = _runtime_python()
    if py.exists() and (ENV_DIR / "conda-meta").is_dir() and (ENV_DIR / "prism-runtime.json").is_file():
        _log(f"micromamba 环境已存在: {ENV_DIR}")
        return False
    base = _base_python()
    _log("使用 micromamba 供给 prismenv ...")
    _run([base, str(REPO_ROOT / "scripts/packaging/provision/provision.py"),
          "--env-dir", str(ENV_DIR), "--skip-inject"])
    _log("OK micromamba 环境创建完成")
    return True


def _requirements_recent_enough(stamp: Path, files: list[Path]) -> bool:
    if not stamp.exists():
        return False
    stamp_mtime = stamp.stat().st_mtime
    for f in files:
        if f.exists() and f.stat().st_mtime > stamp_mtime:
            return False
    return True


def ensure_python_deps(*, dev: bool) -> None:
    """安装 requirements.txt（可选 dev）到 prismenv。幂等。"""
    py = _runtime_python()
    if not py.exists():
        raise RuntimeError("prismenv 虚拟环境不存在，请先运行 ensure_runtime")
    stamp = ENV_DIR / STAMP_NAME
    if not dev and (ENV_DIR / ".prism-provision-ready").exists():
        return
    files = list(REQUIREMENTS) + (list(REQUIREMENTS_DEV) if dev else [])
    if _requirements_recent_enough(stamp, files):
        _log("Python 依赖已是最新，跳过安装")
        return
    _log("升级 pip ...")
    _run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    for req in files:
        if not req.exists():
            continue
        _log(f"安装依赖: {req.name} ...")
        _run([str(py), "-m", "pip", "install", "-r", str(req)])
    stamp.write_text("ok\n", encoding="utf-8")
    _log("OK Python 依赖安装完成")


def ensure_env() -> None:
    """若缺失 .env，则从 env.example 复制。"""
    crawler_root = REPO_ROOT / "prism_backend" / "douyin_tiktok_api" / "crawlers" / "tiktok"
    for kind in ("web", "app"):
        crawler_config = crawler_root / kind / "config.yaml"
        if not crawler_config.exists():
            crawler_config.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(crawler_root / "web" / "config.example.yaml", crawler_config)
            _log(f"已生成 TikTok {kind} 爬虫空配置（使用该功能时填写登录态/代理）")
    bili_dir = crawler_root.parent / "bilibili" / "web"
    if not (bili_dir / "config.yaml").exists():
        shutil.copyfile(bili_dir / "config.example.yaml", bili_dir / "config.yaml")
        _log("已生成 Bilibili 爬虫空配置")
    env = REPO_ROOT / ".env"
    example = REPO_ROOT / "env.example"
    if env.exists():
        _log(".env 已存在")
        return
    if not example.exists():
        _log("警告: 未找到 env.example，跳过 .env 生成")
        return
    shutil.copyfile(example, env)
    _log("OK 已从 env.example 生成 .env（请按需填写 REDIS_URL / API Key / 浏览器路径）")


# 项目内 npm 缓存：避免依赖用户级 ~/.npm 的权限/磁盘问题（常见于容器/不同用户跑 npm）
NPM_CACHE = REPO_ROOT / ".cache" / "npm"


def _npm_install(dirpath: Path) -> None:
    NPM_CACHE.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, npm_config_cache=str(NPM_CACHE))
    for registry in ("https://registry.npmmirror.com", "https://registry.npmjs.org"):
        env["npm_config_registry"] = registry
        env["npm_config_fetch_retries"] = "2"
        env["npm_config_fetch_timeout"] = "60000"
        command = "npm install" if os.name == "nt" else ["npm", "install"]
        result = _run(command, cwd=str(dirpath), shell=os.name == "nt", env=env, check=False)
        if result.returncode == 0:
            return
    raise RuntimeError(f"All npm registries failed for {dirpath.name}")


def _ensure_node() -> None:
    """确保 Node.js 18+ 与 npm 可用；缺失则尽量用系统包管理器自动安装。"""
    if shutil.which("node") and shutil.which("npm"):
        _log("Node/npm 已就绪")
        return
    raise RuntimeError("Node/npm missing: use start.bat or start-mac.sh to provision the private Node runtime")


def ensure_node_deps() -> None:
    """安装前端依赖（prism_frontend）与根目录依赖（提供 pm2 等进程管理工具）。"""
    _ensure_node()
    if shutil.which("npm") is None:
        _log("警告: 仍无法使用 npm，跳过 Node 依赖安装。请先安装 Node 18+。")
        return
    # 前端依赖
    if (FRONTEND_DIR / "node_modules").exists():
        _log("前端 node_modules 已存在，跳过")
    else:
        _log("安装前端依赖 (npm install) ...")
        _npm_install(FRONTEND_DIR)
        _log("OK 前端依赖安装完成")
    # 根目录依赖：提供 pm2（macOS 用 PM2 托管所有进程）
    pm2_bin = "pm2.cmd" if os.name == "nt" else "pm2"
    if (REPO_ROOT / "node_modules" / ".bin" / pm2_bin).exists():
        _log("根目录 node_modules/pm2 已就绪，跳过")
    else:
        _log("安装根目录依赖（含 pm2）(npm install) ...")
        _npm_install(REPO_ROOT)
        _log("OK 根目录依赖安装完成")


def _redis_status() -> tuple[bool, str]:
    cli = shutil.which("redis-cli")
    if not cli and (ENV_DIR / "bin" / "redis-cli").is_file():
        cli = str(ENV_DIR / "bin" / "redis-cli")
    bundled = REPO_ROOT / "desktop-electron" / "resources" / "redis"
    if not cli and os.name == "nt" and (bundled / "redis-cli.exe").is_file():
        cli = str(bundled / "redis-cli.exe")
    if cli:
        try:
            out = _run([cli, "ping"], check=False, capture_output=True, text=True).stdout.strip()
            if out == "PONG":
                return True, "已运行"
        except Exception:
            pass
    if shutil.which("redis-server") or (ENV_DIR / "bin" / "redis-server").is_file() or (os.name == "nt" and (bundled / "redis-server.exe").is_file()):
        return False, "已安装未运行"
    return False, "未安装"


def ensure_redis() -> bool:
    """Redis is provisioned before startup; PM2 exclusively owns its lifecycle."""
    if _redis_status()[0]:
        return True
    candidates = [ENV_DIR / "bin" / "redis-server", ENV_DIR / "Library" / "bin" / "redis-server.exe",
                  REPO_ROOT / "desktop-electron/resources/redis/redis-server.exe"]
    if os.environ.get("PRISM_REDIS_SERVER") and Path(os.environ["PRISM_REDIS_SERVER"]).is_file():
        return True
    if any(p.is_file() for p in candidates) or shutil.which("redis-server"):
        return True
    raise RuntimeError("Redis provisioning failed; see the first-run installation log")


def _chrome_executable() -> str | None:
    for p in _SYSTEM_CHROME_PATHS:
        if Path(p).is_file():
            return p
    return None


def _xurl_available() -> bool:
    """xurl CLI（推特/X 发布依赖）是否可用。"""
    return shutil.which("xurl") is not None


def ensure_xurl() -> bool:
    """确保 xurl CLI 可用；缺失时用 npm 全局安装（Prism 已确保 npm）。"""
    if _xurl_available():
        _log("xurl 已就绪")
        return True
    npm = shutil.which("npm")
    if npm is None:
        _log("警告: 找不到 npm，无法自动安装 xurl。请手动: npm install -g @xdevplatform/xurl")
        return False
    _log("未找到 xurl，用 npm 全局安装 @xdevplatform/xurl ...")
    try:
        _run([npm, "install", "-g", "@xdevplatform/xurl"],
             check=False, env=dict(os.environ, npm_config_cache=str(NPM_CACHE)))
    except Exception as exc:
        _log(f"自动安装 xurl 失败: {exc}")
    if _xurl_available():
        _log("OK xurl 已安装")
        return True
    _log("xurl 仍未就绪。请手动安装: npm install -g @xdevplatform/xurl")
    return False


def _chromium_in_browsers() -> bool:
    runtime_data = Path(os.environ.get("PRISM_RUNTIME_DATA_DIR", REPO_ROOT / "runtime-data"))
    chromium_dir = runtime_data / "components" / "browsers"
    if not chromium_dir.exists():
        return False
    for exe in chromium_dir.rglob("*"):
        if exe.is_file() and exe.name in ("chrome", "Chromium", "chrome.exe"):
            return True
    return False


def ensure_browsers(*, auto: bool) -> bool:
    """优先复用系统 Chrome；否则视情况用 patchright 安装 Chromium。"""
    if os.getenv("LOCAL_CHROME_PATH") and Path(os.environ["LOCAL_CHROME_PATH"]).is_file():
        _log("浏览器: 使用 LOCAL_CHROME_PATH")
        return True
    sys_chrome = _chrome_executable()
    if sys_chrome:
        _log(f"浏览器: 复用系统 Chrome（{sys_chrome}），无需下载")
        return True
    if _chromium_in_browsers():
        _log("浏览器: browsers/chromium 下已有 Chromium")
        return True
    if not auto:
        _log("浏览器: 未发现 Chromium（可用 python3 bootstrap.py --browsers 安装）")
        return False
    py = _runtime_python()
    if not py.exists():
        _log("浏览器: 虚拟环境不存在，跳过安装")
        return False
    _log("浏览器: 使用 patchright 安装 Chromium（首次约 150MB）...")
    try:
        _run([str(py), "-m", "patchright", "install", "chromium"], check=False)
        _log("OK 浏览器安装完成")
        return True
    except Exception as exc:
        _log(f"浏览器: 安装失败（{exc}）。请手动执行: {py} -m patchright install chromium")
        return False


# --------------------------------------------------------------------------
# PM2 子命令（跨平台，单命令入口：start / stop / status）
# --------------------------------------------------------------------------
def _pm2_bin() -> Path | None:
    exe = "pm2.cmd" if os.name == "nt" else "pm2"
    for base in (REPO_ROOT / "node_modules" / ".bin", FRONTEND_DIR / "node_modules" / ".bin"):
        p = base / exe
        if p.exists():
            return p
    found = shutil.which("pm2")
    return Path(found) if found else None


def _pm2_env() -> dict:
    env = dict(os.environ)
    env["PM2_HOME"] = str(REPO_ROOT / "runtime-data" / "pm2")
    return env


def _verify_started_services(names: list[str], timeout: int = 120) -> bool:
    """Require every enabled process to stay online without restarting."""
    script = (
        "const p=require('pm2');p.connect(e=>{if(e)process.exit(1);"
        "p.list((e,rows)=>{if(e)process.exit(1);console.log(JSON.stringify(rows.map(x=>"
        "({name:x.name,status:x.pm2_env.status,restarts:x.pm2_env.restart_time}))));p.disconnect()})})"
    )
    deadline = time.monotonic() + timeout
    stable_since = None
    last = {}
    previous_counts = None
    while time.monotonic() < deadline:
        result = _run([shutil.which("node") or "node", "-e", script], env=_pm2_env(),
                      capture_output=True, text=True, check=False)
        try:
            last = {row["name"]: row for row in json.loads(result.stdout)}
        except (ValueError, TypeError):
            last = {}
        failed = [name for name in names if last.get(name, {}).get("status") == "stopped"]
        if failed:
            _log("[ERROR] 服务恢复后仍已停止: " + ", ".join(failed))
            return False
        counts = {name: last.get(name, {}).get("restarts", 0) for name in names}
        if counts != previous_counts:
            stable_since = None
        previous_counts = counts
        ready = all(last.get(name, {}).get("status") == "online" for name in names)
        if ready:
            stable_since = stable_since or time.monotonic()
            if time.monotonic() - stable_since >= 8:
                try:
                    for url in ("http://127.0.0.1:3000/", "http://127.0.0.1:7001/health"):
                        with urllib.request.urlopen(url, timeout=5) as response:
                            if response.status != 200:
                                raise ValueError(f"HTTP {response.status}")
                    _log("全部已启用服务通过稳定性检查: " + ", ".join(names))
                    return True
                except Exception:
                    pass
        else:
            stable_since = None
        time.sleep(2)
    _log("[ERROR] 服务启动验证超时: " + ", ".join(
        f"{name}={last.get(name, {}).get('status', 'missing')}" for name in names))
    return False


def _pm2_start() -> int:
    """用 PM2 拉起整套服务（假定环境已就绪）。"""
    pm2 = _pm2_bin()
    if pm2 is None:
        _log("[ERROR] 未找到 pm2。请先运行: python3 bootstrap.py")
        return 1
    env = _pm2_env()
    pm2 = str(pm2)
    py = str(_runtime_python())
    runtime = str(REPO_ROOT / "scripts" / "prism_runtime.py")

    _run([pm2, "delete", "all"], check=False, env=env)
    _run([py, runtime, "prepare"], check=False, env=env, capture_output=True)

    _log("启动 PM2 栈（Redis + 后端 ...）")
    # An externally managed Redis may already own 6379; do not start a competing server.
    core = "prism-backend" if _redis_status()[0] else "prism-redis,prism-backend"
    if _run([pm2, "start", str(REPO_ROOT / "ecosystem.config.js"), "--only", core, "--update-env"], check=False, env=env).returncode != 0:
        return 1
    if _run([py, runtime, "health", "--timeout", "60"], check=False, env=env, capture_output=True).returncode != 0:
        _log("[WARN] 后端未绑定所选端口，重选端口并重试一次 ...")
        _run([pm2, "delete", "prism-backend"], check=False, env=env)
        _run([py, runtime, "prepare"], check=False, env=env, capture_output=True)
        _run([pm2, "start", str(REPO_ROOT / "ecosystem.config.js"), "--only", "prism-backend", "--update-env"], check=False, env=env)
        if _run([py, runtime, "health", "--timeout", "60"], check=False, env=env, capture_output=True).returncode != 0:
            _log("[ERROR] 后端健康检查仍失败")
            return 1

    _log("启动其余服务（Worker/Celery/前端/Persona/Hermes ...）")
    services = ["prism-worker", "prism-celery", "prism-frontend", "prism-recovery", "prism-cms"]
    cms_config = REPO_ROOT / "runtime-data" / "cms" / "config.json"
    if cms_config.exists() and json.loads(cms_config.read_text(encoding="utf-8")).get("publicEnabled"):
        services.append("prism-cms-tunnel")
    optional = {
        "persona-api": Path(os.environ.get("PRISM_COMPONENT_ENV_DIR", REPO_ROOT / "prism_components")) / "persona" / ("Scripts/persona.exe" if os.name == "nt" else "bin/persona"),
        "persona-proxy": REPO_ROOT / "tools" / "persona-studio" / "proxies" / "mihomo",
        "persona-dashboard": Path(os.environ.get("PRISM_PERSONA_SOURCE", REPO_ROOT / "tools" / "persona-studio")) / "dashboard" / "node_modules" / "vite" / "bin" / "vite.js",
        "hermes-dashboard": Path(os.environ.get("PRISM_COMPONENT_ENV_DIR", REPO_ROOT / "prism_components")) / "hermes" / ("Scripts/hermes.exe" if os.name == "nt" else "bin/hermes"),
        "hermes-webui": Path(os.environ.get("PRISM_HERMES_WEBUI_SOURCE", REPO_ROOT / "tools" / "hermes-webui")) / "server.py",
        "deepseek-harness": REPO_ROOT / "tools" / "deepseek-harness" / "apps" / "cli" / "lib" / "bin.js",
    }
    for name, entry in optional.items():
        if entry.is_file():
            services.append(name)
        else:
            _log(f"跳过尚未安装的可选服务: {name}")
    result = _run([pm2, "start", str(REPO_ROOT / "ecosystem.config.js"), "--only",
          ",".join(services),
          "--update-env"], check=False, env=env)
    if result.returncode != 0 or not _verify_started_services(core.split(",") + services):
        return 1

    try:
        backend_url = json.loads((REPO_ROOT / "runtime-data" / "runtime.json").read_text()).get("backend_url", "http://127.0.0.1:7000")
    except Exception:
        backend_url = "http://127.0.0.1:7000"

    print()
    _run([pm2, "list"], check=False, env=env)
    print()
    print("访问:")
    print("  前端        http://localhost:3000")
    print("  后端        " + backend_url + "/api/docs")
    print("  Worker      http://127.0.0.1:7001/health")
    print("  Persona API http://127.0.0.1:8787")
    print()
    print("  停止: python3 bootstrap.py stop   |   日志: pm2 logs")
    return 0


def _pm2_stop() -> int:
    pm2 = _pm2_bin()
    if pm2 is None:
        _log("[ERROR] 未找到 pm2")
        return 1
    _log("停止 Prism PM2 栈 ...")
    _run([str(pm2), "delete", "all"], check=False, env=_pm2_env())
    _log("完成。数据与日志保留在 runtime-data/pm2")
    return 0


def _pm2_status() -> int:
    pm2 = _pm2_bin()
    if pm2 is None:
        _log("[ERROR] 未找到 pm2")
        return 1
    return _run([str(pm2), "list"], check=False, env=_pm2_env()).returncode


# --------------------------------------------------------------------------
# 环境引导
# --------------------------------------------------------------------------
def _bootstrap(*, dev: bool, no_browsers: bool, check: bool) -> int:
    if check:
        _log("检查模式（只读）...")
        running, state = _redis_status()
        _log(f"Redis: {state}")
        _log(f"prismenv python: {_runtime_python()} -> {'存在' if _runtime_python().exists() else '不存在'}")
        _log(f"前端 node_modules: {'存在' if (FRONTEND_DIR / 'node_modules').exists() else '不存在'}")
        _log(f"根目录 pm2: {'存在' if _pm2_bin() else '不存在'}")
        _log(f"浏览器: {'可用' if (_chrome_executable() or _chromium_in_browsers()) else '需安装'}")
        _log(f"xurl: {'可用' if _xurl_available() else '需安装 (npm install -g @xdevplatform/xurl)'}")
        return 0

    ensure_runtime()
    ensure_python_deps(dev=dev)
    ensure_env()
    ensure_node_deps()
    ensure_xurl()
    ensure_redis()
    if not no_browsers:
        ensure_browsers(auto=True)

    _log("=" * 60)
    running, state = _redis_status()
    if running or state == "已安装未运行":
        _log(f"环境就绪。Redis {state}，未运行时由 PM2 启动。")
        _log("部署:  python3 bootstrap.py   |   下次启动:  python3 bootstrap.py start")
    else:
        _log("环境基本就绪，但 Redis 尚未就绪。")
        _log(f"    {_redis_install_hint()}")
    _log("=" * 60)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prism 一键部署（跨平台）：装齐依赖 + PM2 启动/停止 + Web UI")
    parser.add_argument("command", nargs="?", default="bootstrap",
                        choices=("bootstrap", "start", "stop", "status", "webui"),
                        help="bootstrap=完整部署(默认) | start=快速启动(假定环境已就绪) | stop=停止 | status=状态 | webui=打开部署 Web UI")
    parser.add_argument("--dev", action="store_true", help="环境引导时同时安装开发依赖 requirements-dev.txt")
    parser.add_argument("--no-browsers", action="store_true", help="跳过浏览器安装")
    parser.add_argument("--check", action="store_true", help="仅检查环境，不改动")
    parser.add_argument("--port", type=int, default=8440, help="webui 监听端口")
    parser.add_argument("--host", default="127.0.0.1", help="webui 监听地址")
    parser.add_argument("--no-open", action="store_true", help="webui 不自动打开浏览器")
    args = parser.parse_args()

    if args.command == "webui":
        import importlib.util
        p = REPO_ROOT / "deploy" / "webui_server.py"
        spec = importlib.util.spec_from_file_location("prismwebui", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.serve(port=args.port, host=args.host, no_open=args.no_open)
    if args.command == "stop":
        return _pm2_stop()
    if args.command == "status":
        return _pm2_status()
    if args.command == "start":
        if args.check:
            return _bootstrap(dev=False, no_browsers=True, check=True)
        if _bootstrap(dev=False, no_browsers=True, check=False) != 0:
            _log("[ERROR] 环境未就绪，请先运行: python3 bootstrap.py")
            return 1
        return _pm2_start()

    # default: bootstrap = 完整一键部署（装齐依赖 + 启动）
    print("=" * 60)
    print("  Prism 一键部署 (bootstrap + PM2)")
    print("=" * 60)
    if args.check:
        return _bootstrap(dev=args.dev, no_browsers=args.no_browsers, check=True)
    if _bootstrap(dev=args.dev, no_browsers=args.no_browsers, check=False) != 0:
        _log("[ERROR] 环境引导失败")
        return 1
    return _pm2_start()


if __name__ == "__main__":
    raise SystemExit(main())
