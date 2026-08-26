#!/usr/bin/env python3
"""Cross-platform Hermes runtime setup for Prism (macOS / Linux / Windows).

The Windows-only ``setup-local-hermes.ps1`` prepares ``tools/hermes-agent`` +
``prismenv`` and stamps the runtime as ready. This script is the same job for
macOS/Linux (and works on Windows too), so ``get_runtime_summary()["agent_installed"]``
can become true on any platform.

Usage::

    python scripts/hermes/setup_local_hermes.py --check      # report status only
    python scripts/hermes/setup_local_hermes.py --install    # create prismenv + install deps + stamp
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HERMES_ROOT = REPO_ROOT / "tools" / "hermes-agent"
PRISMENV_ROOT = REPO_ROOT / "prismenv"
STAMP = PRISMENV_ROOT / ".hermes-runtime-ready"


def _prismenv_python() -> Path:
    if sys.platform == "win32":
        return PRISMENV_ROOT / "Scripts" / "python.exe"
    return PRISMENV_ROOT / "bin" / "python"


def _venv_python_candidates() -> list[Path]:
    # Hermes requires Python >=3.11; put the 3.12 venv ahead of the 3.9 venv.
    if sys.platform == "win32":
        return [
            REPO_ROOT / ".venv_test" / "Scripts" / "python.exe",
            REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        ]
    return [
        REPO_ROOT / ".venv_test" / "bin" / "python",
        REPO_ROOT / ".venv" / "bin" / "python",
    ]


def _python_version_ok(exe: str) -> bool:
    try:
        result = subprocess.run(
            [exe, "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"],
            capture_output=True, check=False,
        )
        return result.returncode == 0
    except OSError:
        return False


def _resolve_base_python() -> str:
    # Prefer the interpreter running this script when it is new enough.
    if _python_version_ok(sys.executable):
        return sys.executable
    for candidate in _venv_python_candidates():
        if candidate.exists() and _python_version_ok(str(candidate)):
            return str(candidate)
    for name in ("python3.12", "python3.11", "python3", "python"):
        found = subprocess.run(
            [name, "-c", "import sys; print(sys.executable)"],
            capture_output=True, text=True, check=False,
        )
        if found.returncode == 0 and found.stdout.strip():
            exe = found.stdout.strip().splitlines()[-1]
            if _python_version_ok(exe):
                return exe
    raise RuntimeError("No Python >=3.11 interpreter found (Hermes requires >=3.11).")


def _hermes_dependencies() -> list[str]:
    pyproject = HERMES_ROOT / "pyproject.toml"
    if not pyproject.exists():
        raise FileNotFoundError(pyproject)

    data = json.loads(subprocess.run(
        [sys.executable, "-c", (
            "import json, pathlib, tomllib; "
            "d = tomllib.loads(pathlib.Path('pyproject.toml').read_text()); "
            "p = d.get('project', {}); "
            "deps = list(p.get('dependencies', [])); "
            "deps.extend((p.get('optional-dependencies') or {}).get('web', [])); "
            "print(json.dumps(deps))"
        )],
        cwd=str(HERMES_ROOT), capture_output=True, text=True, check=True,
    ).stdout)
    return [d for d in data if isinstance(d, str)]


def check() -> int:
    summary = {
        "hermes_root": str(HERMES_ROOT),
        "hermes_root_exists": HERMES_ROOT.exists(),
        "prismenv_python": str(_prismenv_python()),
        "python_exists": _prismenv_python().exists(),
        "stamp": str(STAMP),
        "stamp_exists": STAMP.exists(),
        "agent_installed": HERMES_ROOT.exists() and _prismenv_python().exists() and STAMP.exists(),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["agent_installed"] else 1


def install() -> int:
    if not HERMES_ROOT.exists():
        raise FileNotFoundError(f"Hermes source not found: {HERMES_ROOT}")

    base_python = _resolve_base_python()
    python_exe = _prismenv_python()

    if not python_exe.exists():
        print(f"[1/3] Creating prismenv from {base_python} ...")
        subprocess.run([base_python, "-m", "venv", str(PRISMENV_ROOT)], check=True)

    print("[2/3] Installing Hermes dependencies into prismenv ...")
    subprocess.run([str(python_exe), "-m", "pip", "install", "--upgrade", "pip", "wheel"], check=True)
    deps = _hermes_dependencies()
    subprocess.run([str(python_exe), "-m", "pip", "install", *deps], check=True)

    print("[3/3] Stamping Hermes runtime as ready ...")
    STAMP.write_text(f"{subprocess.run([str(python_exe), '--version'], capture_output=True, text=True).stdout.strip()}\n", encoding="utf-8")

    print("Hermes runtime prepared.")
    print(f"  python : {python_exe}")
    print(f"  stamp  : {STAMP}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes runtime setup (cross-platform)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="report runtime status only")
    group.add_argument("--install", action="store_true", help="create prismenv + install deps + stamp")
    args = parser.parse_args()

    if args.check:
        return check()
    return install()


if __name__ == "__main__":
    raise SystemExit(main())
