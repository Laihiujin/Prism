#!/usr/bin/env python3
"""Prism runtime self-provisioning — micromamba 版。

目标：让 Prism 在目标机器上全权接管自己的 Python runtime，
不再依赖用户机器上预装的 Python。

做法：用 micromamba（单静态二进制、无 base 环境、可内嵌）在目标机创建一个
conda 环境（默认 conda-forge + 中国镜像），把 FastAPI / Celery / Persona /
Patchright 等依赖一次性装进去；可按需再加 per-component 环境
（persona-studio、hermes-agent、deepseek-harness 等）。

本脚本只用标准库，因为运行时此时还不存在。

典型用法（在仓库根目录或打包后的 resources 下）：
    python3 scripts/packaging/provision/provision.py --check
    python3 scripts/packaging/provision/provision.py --print-python
    python3 scripts/packaging/provision/provision.py --mirror tuna
    python3 scripts/packaging/provision/provision.py --component persona
    python3 scripts/packaging/provision/provision.py --dry-run

产物：<env-dir>/prism-runtime.json —— 记录该环境实际 python 路径、镜像、
管理器类型，供 Electron 壳 / supervisor 读取，而不是靠猜 venv 布局。

约定：
    - 共享运行时环境默认落在 REPO_ROOT/prismenv（与现有命名一致）。
    - 幂等：<env-dir>/.prism-provision-ready 记录镜像与输入散列，重跑跳过。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]  # scripts/packaging/provision -> repo root
PROVISION_DIR = HERE
MIRROR_FILE = PROVISION_DIR / "mirror.json"
CONDA_DEPS_FILE = PROVISION_DIR / "conda-deps.txt"
PIP_REQS_FILE = PROVISION_DIR / "requirements.prism.lock.txt"
COMPONENTS_DIR = PROVISION_DIR / "components"
MICROMAMBA_ROOT = PROVISION_DIR / ".mamba"  # 自包含的 repodata 缓存根

# 内嵌 micromamba 二进制统一放这里（可能按平台/架构分目录）
EMBED_MICROMAMBA_DIR = PROVISION_DIR / "micromamba"

READY_STAMP = ".prism-provision-ready"
RUNTIME_MANIFEST = "prism-runtime.json"
COMPONENTS_JSON = PROVISION_DIR / "components.json"

# 说明：persona / hermes 的 console-script 入口（bin/persona、bin/hermes）
# 来自把对应源码以可编辑方式装进共享环境。若 `bin/<entrypoint>` 消失，
# ecosystem 会回退到 `python -m <name>`，而包没装时两者都会失败 ——
# 这正是 PM2 拉不起 persona-api / hermes-dashboard 的原因。


def load_components() -> dict:
    """读取 components.json：哪些组件注入共享环境、哪些隔离成独立 env。"""
    if not COMPONENTS_JSON.exists():
        return {"inject": [], "isolated": []}
    try:
        return json.loads(COMPONENTS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {"inject": [], "isolated": []}


def resolve_component_src(src_rel: str) -> Path:
    return REPO_ROOT / src_rel


def is_python_project(p: Path) -> bool:
    return (p / "pyproject.toml").exists() or (p / "setup.py").exists() or (p / "setup.cfg").exists()


def write_launcher_wrapper(env_dir: Path, src: Path, name: str, launch_module: str, dry_run: bool = False) -> bool:
    """为非 pip 组件生成一个 bin/<name> 启动器（把组件源码塞进 sys.path 后调用其 main）。"""
    bin_dir = env_dir / ("Scripts" if os.name == "nt" else "bin")
    wrapper_name = f"{name}.cmd" if os.name == "nt" else name
    if dry_run:
        log("[dry-run] 生成启动器", bin_dir / wrapper_name, "->", launch_module)
        return True
    bin_dir.mkdir(parents=True, exist_ok=True)
    path = bin_dir / wrapper_name
    content = (
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        f"sys.path.insert(0, {str(src)!r})\n"
        f"from {launch_module} import main\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)
    log(f"已生成启动器: {path} (module={launch_module})")
    return True


def install_component(env_dir: Path, comp: dict, mirror, dry_run: bool = False) -> bool:
    """把组件接入目标 env（venv 或 conda 均可）。best-effort，不因单个组件失败而中止供给。

    - 组件带 pip 安装目标（comp['pip'] 或 comp['src'] 本身是 Python 项目）→ pip install -e 生成 console-script。
    - 否则若有 comp['launch_module'] → 生成 bin/<name> 启动器。
    - 都没有 → 警告并依赖 ecosystem 的 python -m/PYTHONPATH 回退。
    """
    name = comp.get("name", "?")
    py = env_python_path(env_dir)
    if not py.exists():
        warn(f"环境 python 不存在，无法接入 {name}: {py}")
        return False

    src = resolve_component_src(comp.get("src", ""))
    pip_rel = comp.get("pip")
    if pip_rel:
        pip_target = resolve_component_src(pip_rel)
    else:
        pip_target = src if is_python_project(src) else None

    if pip_target is not None and pip_target.exists():
        if dry_run:
            log("[dry-run]", py, "-m pip install -e", pip_target)
            return True
        log(f"安装组件 {name} -> {pip_target}")
        rc = run([str(py), "-m", "pip", "install", "-e", str(pip_target)],
                 env_extra={"PIP_INDEX_URL": mirror["pypi"]}, check=False)
        if rc == 0:
            log(f"组件 {name} 已安装（console-script 应已生成）")
            return True
        warn(f"pip install -e 失败（{name}），尝试启动器回退: {pip_target}")

    launch_module = comp.get("launch_module")
    if launch_module:
        if src.exists():
            return write_launcher_wrapper(env_dir, src, name, launch_module, dry_run=dry_run)
        warn(f"组件 {name} 无源码目录，无法生成启动器: {src}")

    warn(f"组件 {name} 无 pip 项目或启动器；若未生成 bin/{name}，ecosystem 将回退 python -m {name}。")
    return False


def log(*args) -> None:
    print("[provision]", *args, flush=True)


def warn(*args) -> None:
    print("[provision][warn]", *args, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- mirror ----

def load_mirror(name: str | None = None):
    try:
        cfg = json.loads(MIRROR_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        cfg = {}
    providers = cfg.get("providers", {}) or {}
    default = cfg.get("default") or "official"
    provider = (name or os.environ.get("PRISM_PROVISION_MIRROR") or default or "official")
    picked = providers.get(provider, providers.get(default, providers.get("official", {})))
    if not picked:
        picked = {"channels": ["conda-forge"], "pypi": "https://pypi.org/simple"}
    return {"name": provider, **picked}


def channels_block(channels) -> str:
    return "".join(f"  - {c}\n" for c in channels)


def read_conda_deps() -> list[str]:
    if not CONDA_DEPS_FILE.exists():
        return ["python=3.11", "pip"]
    out = []
    for line in CONDA_DEPS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out or ["python=3.11", "pip"]


# ---------------------------------------------------------- micromamba ----

def resolve_micromamba() -> str:
    """按优先级找 micromamba：内嵌 -> PRISM_MICROMAMBA env -> PATH。"""
    env_path = os.environ.get("PRISM_MICROMAMBA")
    if env_path and Path(env_path).exists():
        return env_path

    if EMBED_MICROMAMBA_DIR.exists():
        candidates = [
            EMBED_MICROMAMBA_DIR / "micromamba.exe",   # Windows
            EMBED_MICROMAMBA_DIR / "micromamba",        # macOS/Linux
        ]
        for c in candidates:
            if c.exists():
                return str(c)

    found = shutil.which("micromamba")
    if found:
        return found

    # 给出清晰的安装指引（内嵌方式附后）
    raise RuntimeError(
        "未找到 micromamba。请任选其一：\n"
        "  a) 把 micromamba 二进制放到 provision/micromamba/ 下（随包内嵌，推荐）；\n"
        "  b) 设置环境变量 PRISM_MICROMAMBA 指向 micromamba；\n"
        "  c) 手动安装到 PATH（macOS: brew install micromamba）。"
    )


def mimamba_env(extra=None) -> dict:
    # 只设 MAMBA_ROOT_PREFIX；always-yes 用 -y 标志，不要设 MAMBA_ALWAYS_YES=1
    # 这类布尔 env（micromamba 2.9 会把字符串 '1' 转成 yaml bool 失败）。
    env = dict(os.environ)
    env.setdefault("MAMBA_ROOT_PREFIX", str(MICROMAMBA_ROOT))
    if extra:
        env.update(extra)
    return env


def run(cmd, env_extra=None, check=True) -> int:
    log("$", " ".join(_shell_quote(c) for c in cmd))
    proc = subprocess.run(cmd, env=mimamba_env(env_extra))
    if check and proc.returncode != 0:
        raise RuntimeError(f"命令失败（exit {proc.returncode}）: {cmd[0]}")
    return proc.returncode


def _shell_quote(s: str) -> str:
    if all(ch.isalnum() or ch in "/._=-" for ch in s):
        return s
    return '"' + s.replace('"', '\\"') + '"'


# ----------------------------------------------------------- env build ----

def inputs_digest(mirror, conda_deps, pip_text, inject=None) -> str:
    h = hashlib.sha256()
    h.update(json.dumps(mirror, sort_keys=True).encode())
    h.update(("\n".join(conda_deps)).encode())
    h.update(pip_text.encode())
    if inject:
        for comp in inject:
            h.update(("|" + str(comp.get("name")) + ":" + str(comp.get("src"))).encode())
    return h.hexdigest()[:16]


def is_provisioned(env_dir: Path, digest: str) -> bool:
    stamp = env_dir / READY_STAMP
    if not stamp.exists():
        return False
    try:
        return json.loads(stamp.read_text(encoding="utf-8")).get("digest") == digest
    except Exception:
        return False


def write_stamp(env_dir: Path, digest: str, mirror, env_python: str, kind: str = "conda") -> None:
    (env_dir / READY_STAMP).write_text(
        json.dumps({"digest": digest, "mirror": mirror, "python": env_python, "kind": kind}, ensure_ascii=False),
        encoding="utf-8",
    )


def build_env_yml(mirror, conda_deps, pip_reqs_path: Path) -> str:
    """生成临时 micromamba environment.yml（含 conda 层 + pip 层 + 镜像通道）。"""
    lines = [
        "name: prism-runtime",
        "channels:",
        channels_block(mirror["channels"]),
        "dependencies:",
    ]
    for dep in conda_deps:
        lines.append(f"  - {dep}")
    lines.append("  - pip:")
    # 用绝对路径，避免 micromamba 相对当前工作目录找不到
    lines.append(f'      - "-r {str(pip_reqs_path.resolve())}"')
    return "\n".join(lines) + "\n"


def env_python_path(env_dir: Path) -> Path:
    candidates = [
        env_dir / "bin" / "python",          # Unix venv/conda
        env_dir / "python.exe",              # Windows conda
        env_dir / "Scripts" / "python.exe",  # Windows venv
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0] if os.name != "nt" else candidates[1]


def env_kind(env_dir: Path) -> str:
    """'conda' 有 conda-meta；'venv' 有 pyvenv.cfg；否则 'empty'。"""
    if (env_dir / "conda-meta").exists():
        return "conda"
    if (env_dir / "pyvenv.cfg").exists():
        return "venv"
    return "empty"


def entrypoint_candidates(env_dir: Path, ep: str) -> list[Path]:
    """console-script 入口：Unix 是 bin/<ep>，Windows conda 是 Scripts/<ep>.exe。"""
    return [
        env_dir / "bin" / ep,
        env_dir / "Scripts" / f"{ep}.exe",
        env_dir / "Scripts" / ep,
    ]


def find_entrypoint(env_dir: Path, ep: str) -> Path | None:
    for c in entrypoint_candidates(env_dir, ep):
        if c.exists():
            return c
    return None


def create_env(env_dir: Path, mm, mirror, conda_deps, pip_reqs_path: Path, force: bool = False, component: str | None = None, inject=None, dry_run: bool = False, env_file: Path | None = None) -> Path:
    env_dir = Path(env_dir)
    inject = inject or []
    kind = env_kind(env_dir)

    if env_file is not None:
        env_text = env_file.read_text(encoding="utf-8")
    else:
        pip_text = pip_reqs_path.read_text(encoding="utf-8") if pip_reqs_path.exists() else ""
        env_text = pip_text
    digest = inputs_digest(mirror, conda_deps, env_text, inject)

    # 旧 venv（bootstrap.py 生成）保护：默认不破坏运行中的环境，仅注入组件入口；
    # 需要真正迁移为 micromamba conda 环境时用 --force。
    if kind == "venv" and not force:
        warn("检测到旧 venv（bootstrap.py 生成）。为不破坏运行中环境，跳过 conda 重建，仅注入组件入口到该 venv。")
        warn("如需迁移为 micromamba conda 环境，请用 --force（会先把旧 venv 备份为 *.venv.bak）。")
        py = env_python_path(env_dir)
        for comp in inject:
            install_component(env_dir, comp, mirror, dry_run=dry_run)
        if py.exists():
            if not dry_run:
                write_stamp(env_dir, digest, mirror, str(py), kind="venv")
            return py
        raise RuntimeError(f"prismenv 是 venv 但 python 缺失: {py}")

    if not force and is_provisioned(env_dir, digest):
        py = env_python_path(env_dir)
        log(f"已就绪，跳过供给（{env_dir}）python={py if py.exists() else '(缺失?)'}")
        return py

    # --force 且目标已被旧 venv 占用：先备份，再全新建 conda 环境
    if force and kind == "venv":
        backup = env_dir.with_name(env_dir.name + ".venv.bak")
        log(f"迁移：将现有 venv 备份到 {backup}")
        shutil.rmtree(backup, ignore_errors=True)
        env_dir.rename(backup)
        env_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = None
    try:
        if env_file is not None:
            env_yml_path = env_file
            if dry_run:
                log("[dry-run] 使用组件 env.yaml:", env_file)
        else:
            tmp = tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False, encoding="utf-8")
            tmp.write(build_env_yml(mirror, conda_deps, pip_reqs_path))
            tmp.flush()
            tmp.close()
            tmp_path = Path(tmp.name)
            env_yml_path = tmp_path
            if dry_run:
                print(env_yml_path.read_text(encoding="utf-8"))

        if dry_run:
            log("[dry-run] micromamba env create -p", env_dir, "-f", str(env_yml_path))
            return env_python_path(env_dir)

        log(f"创建环境: {env_dir}")
        run([mm, "--root-prefix", str(MICROMAMBA_ROOT), "env", "create", "-p", str(env_dir), "-f", str(env_yml_path), "-y"],
            env_extra={"PIP_INDEX_URL": mirror["pypi"]})
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    py = env_python_path(env_dir)
    if not py.exists():
        raise RuntimeError(f"环境创建完成但未见 python: {py}")

    # 把需要 console-script 入口的组件以可编辑方式装进共享环境
    for comp in inject:
        install_component(env_dir, comp, mirror, dry_run=dry_run)

    write_stamp(env_dir, digest, mirror, str(py), kind="conda")
    log(f"环境就绪: {env_dir} -> {py}")
    return py


def write_manifest(env_dir: Path, env_python: Path, mirror, manager: str, component: str | None) -> Path:
    manifest = {
        "manager": manager,
        "mirror": mirror.get("name"),
        "envDir": str(env_dir),
        "python": str(env_python),
        "component": component,
    }
    path = env_dir / RUNTIME_MANIFEST
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ------------------------------------------------------------- CLI ----

def list_components() -> list[str]:
    if not COMPONENTS_DIR.exists():
        return []
    return sorted(p.name for p in COMPONENTS_DIR.iterdir() if p.is_dir() and (p / "env.yaml").exists())


def component_env_path(name: str) -> Path:
    yml = COMPONENTS_DIR / name / "env.yaml"
    if not yml.exists():
        raise RuntimeError(f"未知组件: {name}。可用: {list_components() or '(无)'}")
    return yml


def cmd_check(mm, mirror, env_dir: Path) -> int:
    print(f"micromamba : {mm}")
    print(f"mirror     : {mirror['name']} -> {mirror['channels']}")
    print(f"pip mirror : {mirror['pypi']}")
    print(f"env dir    : {env_dir}")
    print(f"conda deps : {read_conda_deps()}")
    print(f"pip reqs   : {PIP_REQS_FILE.name} ({PIP_REQS_FILE.stat().st_size} bytes)")
    print(f"components : {list_components() or '(无)'}")
    return 0


# ------------------------------------------------------------- verify ----

def _has_browser_chromium() -> tuple[bool, str]:
    browsers = REPO_ROOT / "browsers"
    if not browsers.exists():
        return False, "browsers/ 不存在"
    hits = []
    for p in browsers.rglob("*"):
        if p.is_file() and p.name.lower() in ("chrome", "chromium", "chrome.exe", "headless_shell", "chrome-headless-shell"):
            hits.append(str(p))
    # 限制避免遍历过深
    for sub in ("chromium", "chrome-for-testing"):
        d = browsers / sub
        if d.exists():
            hits.append(f"{d}/ (目录)")
    return bool(hits), (hits[0] if hits else "(未发现 Chromium)")


def readiness(env_dir: Path, component_env_root: Path) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    try:
        mm = resolve_micromamba()
        checks.append(("micromamba", True, mm))
    except RuntimeError as exc:
        checks.append(("micromamba", False, str(exc).splitlines()[0] or "missing"))

    py = env_python_path(env_dir)
    checks.append(("prismenv python", py.exists(), str(py)))

    comps = load_components()
    for comp in comps.get("inject", []):
        for ep in comp.get("entrypoints", []):
            exe = find_entrypoint(env_dir, ep)
            checks.append((f"{ep} 入口", exe is not None, str(exe) if exe else f"({ep} 未找到，PM2 将回退 python -m {ep})"))

    for comp in comps.get("isolated", []):
        epath = Path(component_env_root) / comp["name"]
        cpy = env_python_path(epath)
        checks.append((f"[isolated] {comp['name']}", cpy.exists(), str(cpy)))

    redis = shutil.which("redis-server")
    checks.append(("redis-server", bool(redis), redis or "(missing, 需安装)"))

    ok_b, detail_b = _has_browser_chromium()
    checks.append(("chromium", ok_b, detail_b))

    front = REPO_ROOT / "prism_frontend"
    node = front / "node_modules"
    checks.append(("frontend node_modules", node.exists(), str(node)))
    checks.append(("frontend build (.next)", (front / ".next").exists(), str(front / ".next")))

    mihomo = REPO_ROOT / "tools" / "persona-studio" / "proxies" / "mihomo"
    checks.append(("mihomo proxy", mihomo.exists(), str(mihomo)))

    checks.append((".env", (REPO_ROOT / ".env").exists(), str(REPO_ROOT / ".env")))

    return checks


def cmd_verify(env_dir: Path, component_env_root: Path) -> int:
    print("Prism runtime readiness")
    print("=" * 72)
    checks = readiness(env_dir, component_env_root)
    all_ok = True
    for label, ok, detail in checks:
        mark = "ok " if ok else "MISS"
        all_ok = all_ok and ok
        print(f"[{mark}] {label:<22} {detail}")
    print("=" * 72)
    print("全部就绪" if all_ok else "存在缺失项（上表 MISS），请先执行 provision.py 供给。")
    return 0 if all_ok else 1


# ------------------------------------------------------- system deps ----

def stage_env_file() -> tuple[bool, str]:
    env = REPO_ROOT / ".env"
    example = REPO_ROOT / "env.example"
    if env.exists():
        return True, f".env 已存在"
    if not example.exists():
        return False, "env.example 不存在，跳过 .env 生成"
    shutil.copyfile(example, env)
    return True, f"已从 env.example 生成 .env"


def stage_redis() -> tuple[bool, str]:
    redis = shutil.which("redis-server")
    if redis:
        return True, f"redis-server: {redis}"
    return False, "未发现 redis-server。请先安装/启动（macOS: brew install redis && redis-server --daemonize yes）"


def stage_browsers(env_dir: Path) -> tuple[bool, str]:
    ok_b, detail_b = _has_browser_chromium()
    if ok_b:
        return True, detail_b
    py = env_python_path(env_dir)
    if not py.exists():
        return False, "chromium 缺失，且环境 python 不存在"
    log("chromium 缺失，尝试用 patchright 安装（可跳过，约 150MB）...")
    rc = run([str(py), "-m", "patchright", "install", "chromium"], check=False)
    if rc == 0:
        return True, "chromium 已安装（patchright）"
    return False, "patchright 安装 chromium 失败，请手动执行: <env>/bin/python -m patchright install chromium"


def stage_frontend() -> tuple[bool, str]:
    front = REPO_ROOT / "prism_frontend"
    if (front / "node_modules").exists():
        return True, "前端 node_modules 已存在"
    return False, "前端 node_modules 缺失，请先：(cd prism_frontend && npm install && npm run build)"


def run_system_stage(env_dir: Path) -> int:
    print("== 系统依赖 stage ==")
    checks = [stage_env_file(), stage_redis(), stage_browsers(env_dir), stage_frontend()]
    all_ok = True
    for ok, detail in checks:
        print(f"[{'ok' if ok else 'MISS'}] {detail}")
        all_ok = all_ok and ok
    print("== 系统依赖 stage 结束 ==")
    return 0 if all_ok else 1


# --------------------------------------------------------- provisioning ----

def _filter_inject(inject, with_names, skip_inject) -> list:
    out = list(inject or [])
    if skip_inject:
        return []
    if with_names:
        keep = set(with_names)
        out = [c for c in out if c.get("name") in keep]
    return out


def provision_shared(mm, mirror, env_dir, inject, force, dry_run) -> int:
    conda_deps = read_conda_deps()
    if dry_run:
        if env_kind(Path(env_dir)) == "venv":
            warn("检测到旧 venv；dry-run：将不会重建 conda 环境，仅注入组件入口。用 --force 才会迁移为 conda。")
            for comp in inject:
                install_component(Path(env_dir), comp, mirror, dry_run=True)
            return 0
        print(build_env_yml(mirror, conda_deps, PIP_REQS_FILE))
        for comp in inject:
            install_component(Path(env_dir), comp, mirror, dry_run=True)
        return 0
    py = create_env(Path(env_dir), mm, mirror, conda_deps, PIP_REQS_FILE, force=force, inject=inject)
    write_manifest(Path(env_dir), py, mirror, "micromamba", None)
    return 0


def provision_component(mm, mirror, name, component_env_root, force, dry_run) -> int:
    env_dir = Path(component_env_root) / name
    yml = component_env_path(name)
    content = yml.read_text(encoding="utf-8")
    env_file = yml
    tmp_path = None
    if "{{CHANNELS}}" in content:
        content = content.replace("{{CHANNELS}}", channels_block(mirror["channels"]))
        tmp = tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False, encoding="utf-8")
        tmp.write(content)
        tmp.flush()
        tmp.close()
        tmp_path = Path(tmp.name)
        env_file = tmp_path
    try:
        py = create_env(env_dir, mm, mirror, read_conda_deps(), PIP_REQS_FILE,
                        force=force, component=name, inject=None, dry_run=dry_run, env_file=env_file)
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    if not dry_run:
        write_manifest(env_dir, py, mirror, "micromamba", name)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Prism runtime self-provisioning (micromamba)")
    parser.add_argument("--mirror", help="镜像提供方: tuna | aliyun | official（默认读取 mirror.json default）")
    parser.add_argument("--component", help="只供给某个隔离组件环境（components/<name>/env.yaml）")
    parser.add_argument("--env-dir", default=str(REPO_ROOT / "prismenv"), help="共享运行时环境目录")
    parser.add_argument("--component-env-dir", default=str(REPO_ROOT / "prism_components"), help="组件环境根目录")
    parser.add_argument("--print-python", action="store_true", help="只打印共享环境 python 路径（供壳捕获）")
    parser.add_argument("--list-components", action="store_true", help="列出可用隔离组件环境目录")
    parser.add_argument("--list", action="store_true", help="列出组件清单（inject + isolated）")
    parser.add_argument("--with", dest="with_names", action="append", metavar="NAME", help="只注入指定的共享组件（可重复）")
    parser.add_argument("--skip-inject", action="store_true", help="跳过把组件注入共享环境")
    parser.add_argument("--system", action="store_true", help="只跑系统依赖 stage（.env/Redis/browser/frontend）")
    parser.add_argument("--all", action="store_true", help="供给共享环境 + 全部隔离组件环境 + 系统依赖 stage")
    parser.add_argument("--check", action="store_true", help="只检查依赖/配置，不实际安装")
    parser.add_argument("--verify", action="store_true", help="输出完整 runtime 就绪性报告")
    parser.add_argument("--dry-run", action="store_true", help="只打印将执行的命令，不安装")
    parser.add_argument("--force", action="store_true", help="忽略幂等标记，强制重装")
    config = parser.parse_args(argv)

    mirror = load_mirror(config.mirror)

    if config.list_components:
        print("\n".join(list_components()))
        return 0

    if config.list:
        comps = load_components()
        print("inject:")
        for c in comps.get("inject", []):
            print("  ", c.get("name"), "->", c.get("src"))
        print("isolated:")
        for c in comps.get("isolated", []):
            print("  ", c.get("name"), "->", c.get("src"))
        return 0

    if config.verify:
        return cmd_verify(Path(config.env_dir), Path(config.component_env_dir))

    # --print-python 只需计算路径，不需要 micromamba 已安装
    if config.print_python:
        py = env_python_path(Path(config.env_dir))
        print(py)
        return 0 if py.exists() else 1

    try:
        mm = resolve_micromamba()
    except RuntimeError as exc:
        if config.dry_run or config.check:
            warn(str(exc))
            mm = "micromamba"
        else:
            warn(str(exc))
            return 2

    if config.check:
        return cmd_check(mm, mirror, Path(config.env_dir))

    inject = _filter_inject(load_components().get("inject", []), config.with_names, config.skip_inject)

    if config.all:
        rc = provision_shared(mm, mirror, config.env_dir, inject, config.force, config.dry_run)
        if rc != 0:
            return rc
        for name in list_components():
            rc = provision_component(mm, mirror, name, config.component_env_dir, config.force, config.dry_run)
            if rc != 0:
                return rc
        return 0

    if config.component:
        return provision_component(mm, mirror, config.component, config.component_env_dir, config.force, config.dry_run)

    return provision_shared(mm, mirror, config.env_dir, inject, config.force, config.dry_run)


if __name__ == "__main__":
    sys.exit(main())
