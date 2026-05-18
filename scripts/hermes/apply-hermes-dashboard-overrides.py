from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


BOOTSTRAP_SNIPPET = """<script>(function(){try{if(!window.localStorage.getItem('hermes-dashboard-theme'))window.localStorage.setItem('hermes-dashboard-theme','mono');if(!window.localStorage.getItem('hermes-locale'))window.localStorage.setItem('hermes-locale','zh');document.documentElement.lang='zh-CN';}catch(e){document.documentElement.lang='zh-CN';}})()</script>"""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def replace_once(content: str, old: str, new: str, label: str) -> str:
    if new in content:
        return content
    if old not in content:
        raise RuntimeError(f"Expected snippet for {label} was not found.")
    return content.replace(old, new, 1)


def replace_regex(content: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.M | re.S)
    if count != 1:
        raise RuntimeError(f"Expected pattern for {label} was not found.")
    return updated


def patch_dashboard_index(path: Path) -> None:
    content = read_text(path)
    content = replace_regex(
        content,
        r"<html lang=\"[^\"]+\">",
        '<html lang="zh-CN">',
        "dashboard html lang",
    )
    content = replace_regex(
        content,
        r'<link rel="icon"[^>]*href="/favicon\.ico"\s*/>',
        '<link rel="icon" type="image/x-icon" href="/favicon.ico" />',
        "dashboard favicon link",
    )
    if BOOTSTRAP_SNIPPET in content:
        write_text(path, content)
        return
    content = replace_regex(
        content,
        r'(<script type="module" crossorigin src="/assets/index-[^"]+\.js"></script>)',
        BOOTSTRAP_SNIPPET + "\n    " + r"\1",
        "dashboard bootstrap defaults",
    )
    write_text(path, content)


def patch_config_example(path: Path) -> None:
    content = read_text(path)
    content = replace_once(content, "  skin: default", "  skin: mono", "default skin")
    if "  language: zh" not in content:
        content = replace_once(content, "  skin: mono", "  skin: mono\n  language: zh", "default language")
    if re.search(r"(?m)^dashboard:\n(?:  .*\n)*  theme: mono$", content):
        write_text(path, content)
        return
    if re.search(r"(?m)^dashboard:\n", content):
        section_pattern = r"(?ms)^dashboard:\n(?P<body>(?:  .*\n)*)"
        section_match = re.search(section_pattern, content)
        if not section_match:
            raise RuntimeError("Expected dashboard section was not found.")
        section_body = section_match.group("body")
        if re.search(r"(?m)^  theme: .*$", section_body):
            section_body = re.sub(r"(?m)^  theme: .*$", "  theme: mono", section_body, count=1)
        else:
            section_body += "  theme: mono\n"
        content = re.sub(section_pattern, "dashboard:\n" + section_body, content, count=1)
    else:
        content = content.rstrip() + "\n\n# SynapseAutomation Hermes dashboard defaults\ndashboard:\n  theme: mono\n"
    write_text(path, content)


def copy_dashboard_favicon(repo_root: Path, dashboard_dist: Path) -> None:
    source = repo_root / "scripts" / "hermes" / "assets" / "favicon.ico"
    target = dashboard_dist / "favicon.ico"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--dashboard-dist", required=True)
    parser.add_argument("--config-example", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    dashboard_dist = Path(args.dashboard_dist).resolve()

    patch_dashboard_index(dashboard_dist / "index.html")
    patch_config_example(Path(args.config_example).resolve())
    copy_dashboard_favicon(repo_root, dashboard_dist)


if __name__ == "__main__":
    main()
