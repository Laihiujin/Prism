"""Bundle a Windows venv's base Python without inheriting installed packages."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def stage_runtime(env_dir: Path) -> None:
    env_dir = env_dir.resolve()
    python = env_dir / "Scripts" / "python.exe"
    probe = subprocess.check_output(
        [str(python), "-I", "-c", "import json,sys; print(json.dumps({'base':sys.base_prefix,'version':sys.version.split()[0]}))"],
        text=True,
    )
    info = json.loads(probe)
    base = Path(info["base"]).resolve()
    target = env_dir / "_python"
    if base != target:
        if base.is_relative_to(env_dir) or env_dir.is_relative_to(base):
            raise RuntimeError("The base interpreter and venv must be separate directories")
        if not (base / "Lib" / "encodings" / "__init__.py").is_file():
            raise RuntimeError("The base interpreter has no standard library")
        if (base / "conda-meta").exists():
            raise RuntimeError("Use a standalone Python installation to build this venv package")
        target.mkdir(parents=True, exist_ok=True)
        for pattern in ("python*.exe", "*.dll"):
            for source in base.glob(pattern):
                shutil.copy2(source, target / source.name)
        ignore = shutil.ignore_patterns("site-packages", "__pycache__")
        for directory in ("Lib", "DLLs", "tcl"):
            if (base / directory).is_dir():
                shutil.copytree(base / directory, target / directory, dirs_exist_ok=True, ignore=ignore)
    if not (target / "python.exe").is_file():
        raise RuntimeError("The bundled interpreter is missing")
    cfg = "\n".join((f"home = {target}", f"executable = {target / 'python.exe'}",
                     "include-system-site-packages = false", f"version = {info['version']}", ""))
    (env_dir / "pyvenv.cfg").write_text(cfg, encoding="utf-8")
    child_env = dict(os.environ)
    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        child_env.pop(key, None)
    subprocess.run([str(python), "-I", "-c",
                    "import encodings,ssl,sqlite3,zlib,sys,pathlib; "
                    "assert pathlib.Path(sys.base_prefix).resolve() == pathlib.Path(sys.prefix,'_python').resolve()"],
                   env=child_env, check=True)


if __name__ == "__main__":
    stage_runtime(Path(sys.argv[1]))
