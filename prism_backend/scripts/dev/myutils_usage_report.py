"""
Generate a quick report of which `syn_backend/myUtils/*.py` modules are imported
by the backend/uploader code.

Usage:
  python syn_backend/scripts/dev/myutils_usage_report.py
"""

from __future__ import annotations

import ast
import warnings
from pathlib import Path
from typing import Iterable, Set


REPO_ROOT = Path(__file__).resolve().parents[3]
SYN_BACKEND = REPO_ROOT / "syn_backend"
MYUTILS_DIR = SYN_BACKEND / "myUtils"


def iter_py_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        parts = set(path.parts)
        if "__pycache__" in parts:
            continue
        if "venv" in parts or ".venv" in parts or "synenv" in parts:
            continue
        yield path


def imported_myutils_modules(py_file: Path) -> Set[str]:
    try:
        text = py_file.read_text(encoding="utf-8")
    except Exception:
        return set()
    try:
        tree = ast.parse(text, filename=str(py_file))
    except SyntaxError:
        return set()

    modules: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "myUtils" or node.module.startswith("myUtils."):
                modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "myUtils" or alias.name.startswith("myUtils."):
                    modules.add(alias.name)
    return modules


def main() -> int:
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    if not MYUTILS_DIR.exists():
        print(f"[ERR] myUtils dir not found: {MYUTILS_DIR}")
        return 2

    myutils_modules = {
        f"myUtils.{p.stem}"
        for p in MYUTILS_DIR.glob("*.py")
        if p.name != "__init__.py"
    }

    referenced: Set[str] = set()
    for py in iter_py_files(SYN_BACKEND):
        if MYUTILS_DIR in py.parents:
            continue
        referenced |= imported_myutils_modules(py)

    used = sorted(m for m in myutils_modules if m in referenced)
    unused = sorted(m for m in myutils_modules if m not in referenced)

    print("== myUtils usage report ==")
    print(f"myUtils modules: {len(myutils_modules)}")
    print(f"referenced modules: {len(used)}")
    print("")
    print("-- referenced --")
    for m in used:
        print(m)
    print("")
    print("-- NOT referenced (may be standalone scripts / legacy) --")
    for m in unused:
        print(m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
