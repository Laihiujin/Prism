#!/usr/bin/env python
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple


PROTECTED_FUNCTIONS: Dict[str, List[str]] = {
    "syn_backend/app_new/platforms/douyin.py": ["_extract_user_info"],
    "syn_backend/app_new/platforms/xiaohongshu.py": ["_extract_user_info"],
    "syn_backend/app_new/platforms/kuaishou.py": ["_extract_user_info"],
    "syn_backend/app_new/platforms/tencent.py": ["_extract_user_info"],
}


def _run_git(args: List[str]) -> Tuple[int, str]:
    try:
        completed = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
        )
        out = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode, out.strip()
    except FileNotFoundError:
        return 2, "git not found"


def _has_head() -> bool:
    code, _ = _run_git(["rev-parse", "--verify", "HEAD"])
    return code == 0


def _load_from_head(path: str) -> Optional[str]:
    code, out = _run_git(["show", f"HEAD:{path}"])
    if code != 0:
        return None
    return out


def _load_working(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_function_block(text: str, func_name: str) -> Optional[str]:
    lines = text.splitlines()
    pattern = re.compile(rf"^(\s*)(async\s+def|def)\s+{re.escape(func_name)}\s*\(")
    start = None
    indent = 0
    for i, line in enumerate(lines):
        m = pattern.match(line)
        if m:
            start = i
            indent = len(m.group(1))
            break
    if start is None:
        return None

    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        leading = len(line) - len(line.lstrip(" "))
        if leading <= indent and re.match(r"\s*(async\s+def|def)\s+\w+\s*\(", line):
            end = i
            break

    return "\n".join(lines[start:end]).rstrip()


def main() -> int:
    if not _has_head():
        print("[check] No git HEAD found; skipping protected extractor check.")
        return 0

    failures: List[str] = []

    for path, funcs in PROTECTED_FUNCTIONS.items():
        base_text = _load_from_head(path)
        work_text = _load_working(path)
        if base_text is None or work_text is None:
            failures.append(f"{path}: missing in HEAD or working tree")
            continue

        for func in funcs:
            base_block = _extract_function_block(base_text, func)
            work_block = _extract_function_block(work_text, func)
            if base_block is None or work_block is None:
                failures.append(f"{path}: function '{func}' not found")
                continue
            if base_block != work_block:
                failures.append(f"{path}: function '{func}' changed")

    if failures:
        print("Protected account-info extractors changed. Revert or update intentionally.")
        for item in failures:
            print(f"- {item}")
        return 1

    print("[check] Protected account-info extractors unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
