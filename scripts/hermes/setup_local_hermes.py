#!/usr/bin/env python3
"""Compatibility entry point; all runtime installation uses micromamba."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    data = Path(os.environ.get("PRISM_RUNTIME_DATA_DIR", ROOT / "runtime-data"))
    if args.check:
        stamp = data / "runtime-manifest.json"
        print(json.dumps({"ready": stamp.exists()}))
        return 0 if stamp.exists() else 1
    code = "const r=require(process.argv[1]);r.ensureRuntime(process.argv[2],process.argv[3]).catch(e=>{console.error(e.message);process.exitCode=1})"
    return subprocess.run([os.environ.get("PRISM_NODE", "node"), "-e", code, str(ROOT / "scripts/runtime/ensure-runtime.cjs"), str(ROOT), str(data)],
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode

if __name__ == "__main__":
    raise SystemExit(main())
