#!/usr/bin/env python3
"""Prism 一键环境引导（跨平台）。

这是 Prism 自托管部署的“配方”入口：在一台干净的机器上，
用一个命令就把 Python venv（prismenv）、Python 依赖、前端/根目录 npm 依赖
（根目录提供 macOS 用的 pm2）、.env、Redis、浏览器（Chromium / Firefox）一次性准备到可运行状态。

它把之前散落在 README / start.bat / start-mac.sh 里的手工步骤统一起来，
并保证可重复执行（幂等）：已经做过的步骤会跳过，不会重复装。

用法
----
    python3 bootstrap.py                 # 完整引导
    python3 bootstrap.py --dev           # 额外安装 requirements-dev.txt（开发/测试用）
    python3 bootstrap.py --no-browsers   # 跳过浏览器安装（首次装 Chromium 较大）
    python3 bootstrap.py --check         # 只检查环境，不改动任何东西

之后启动：
    一键启动见仓库根目录：./start-mac.sh （macOS/Linux） 或 start.bat （Windows）。

设计约定
--------
- 统一使用项目根目录下名为 `prismenv` 的虚拟环境（这是整个仓库的规范命名，
  脚本 / 打包 / README / 桌面端都依赖这个名字）。不再使用 `.venv`。
- Redis 是系统服务（不是 pip 包），本脚本负责探测并给出安装/启动指引，
  但不会擅自改系统；请按提示手动安装。
- 幂等依赖：venv 内 `.requirements-ready` 时间戳文件，若比 requirements 文件新则跳过 pip 安装。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
VENV_NAME = "prismenv"
VENV_DIR = REPO_ROOT / VENV_NAME
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


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _log(msg: str) -> None:
    print(f"[prism-bootstrap] {msg}")


def _run(cmd: list[str], *, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
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
        if exe and exe not in found:
            found.append(exe)
    return found


def _python_version(exe: str) -> str | None:
    try:
        out = subprocess.run(
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


def ensure_venv() -> bool:
    """创建 prismenv 虚拟环境（已存在则跳过）。返回是否新建。"""
    py = _venv_python()
    if py.exists():
        _log(f"虚拟环境已存在: {VENV_DIR}")
        return False
    base = _base_python()
    _log(f"创建虚拟环境 prismenv（base: {base}）...")
    _run([base, "-m", "venv", str(VENV_DIR)])
    _log("OK 虚拟环境创建完成")
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
    py = _venv_python()
    if not py.exists():
        raise RuntimeError("prismenv 虚拟环境不存在，请先运行 ensure_venv")
    stamp = VENV_DIR / STAMP_NAME
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
    if os.name == "nt":
        # Windows 上 npm 是 .cmd，subprocess 需走 shell 才能解析
        _run("npm install", cwd=str(dirpath), shell=True, env=env)
    else:
        _run(["npm", "install"], cwd=str(dirpath), env=env)


def ensure_node_deps() -> None:
    """安装前端依赖（prism_frontend）与根目录依赖（提供 pm2 等进程管理工具）。"""
    if shutil.which("npm") is None:
        _log("警告: 未找到 npm，跳过 Node 依赖安装。请先安装 Node 18+。")
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
    if cli:
        try:
            out = _run([cli, "ping"], check=False, capture_output=True, text=True).stdout.strip()
            if out == "PONG":
                return True, "已运行"
        except Exception:
            pass
    if shutil.which("redis-server"):
        return False, "已安装未运行"
    return False, "未安装"


def _redis_install_hint() -> str:
    if shutil.which("brew"):
        return "brew install redis && redis-server --daemonize yes"
    if shutil.which("apt-get"):
        return "sudo apt install redis-server"
    if os.name == "nt":
        return "下载 https://github.com/tporadowski/redis/releases 并解压到 PATH"
    return "请安装 Redis（https://redis.io/download）"


def check_redis() -> bool:
    running, state = _redis_status()
    if running:
        _log(f"Redis {state}")
        return True
    _log(f"Redis {state}。请先安装/启动 Redis：")
    _log(f"    {_redis_install_hint()}")
    if shutil.which("redis-server"):
        _log("检测到 redis-server 但未运行，可在配置后手动执行: redis-server --daemonize yes")
    return False


def _chrome_executable() -> str | None:
    for p in _SYSTEM_CHROME_PATHS:
        if Path(p).is_file():
            return p
    return None


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
    py = _venv_python()
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Prism 一键环境引导")
    parser.add_argument("--dev", action="store_true", help="同时安装开发依赖 requirements-dev.txt")
    parser.add_argument("--no-browsers", action="store_true", help="跳过浏览器安装")
    parser.add_argument("--check", action="store_true", help="仅检查环境，不做改动")
    args = parser.parse_args()

    print("=" * 60)
    print("  Prism 环境引导 (bootstrap)")
    print("=" * 60)

    if args.check:
        _log("检查模式（只读）...")
        running, state = _redis_status()
        _log(f"Redis: {state}")
        _log(f"prismenv python: {_venv_python()} -> {'存在' if _venv_python().exists() else '不存在'}")
        _log(f"前端 node_modules: {'存在' if (FRONTEND_DIR / 'node_modules').exists() else '不存在'}")
        _log(f"根目录 pm2: {'存在' if (REPO_ROOT / 'node_modules' / '.bin' / ('pm2.cmd' if os.name == 'nt' else 'pm2')).exists() else '不存在'}")
        _log(f"浏览器: {'可用' if (_chrome_executable() or _chromium_in_browsers()) else '需安装'}")
        return 0

    ensure_venv()
    ensure_python_deps(dev=args.dev)
    ensure_env()
    ensure_node_deps()
    if not args.no_browsers:
        ensure_browsers(auto=True)

    _log("=" * 60)
    running, state = _redis_status()
    if running:
        _log(f"全部就绪。Redis {state}。")
        _log("启动:  ./start-mac.sh  （macOS/Linux） 或  start.bat  （Windows）")
    else:
        _log("环境基本就绪，但 Redis 尚未运行。")
        _log(f"    {_redis_install_hint()}")
        _log("启动 Redis 后再运行 ./start-mac.sh 或 start.bat。")
    _log("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
