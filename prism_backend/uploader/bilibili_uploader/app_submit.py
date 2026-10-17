"""Submit through the official biliup CLI's App API for options the web API ignores.

The web submit API (python biliup) silently drops comment/danmaku switches; a private
test archive kept comments open with up_close_reply set. The biliup CLI submits through
the App API by default and exposes these switches, so archives that need them are handed
to the CLI. It needs a biliup login file with an App access token next to the Prism
cookie file: `<account>.biliup.json`, created by `biliup -u <that file> login`.
"""
from __future__ import annotations

import json
from pathlib import Path

# Switches that only take effect through the App submit API.
APP_ONLY_FIELDS = ("up_selection_reply", "up_close_reply", "up_close_danmu")


def needs_app_submit(extra: dict | None) -> bool:
    return any((extra or {}).get(name) for name in APP_ONLY_FIELDS)


def app_cookie_file(account_file: str | Path) -> Path:
    """Return the biliup App login file for a Prism cookie file, or explain how to create it."""
    account = Path(account_file)
    app_file = account.with_name(f"{account.stem}.biliup.json")
    try:
        token = (json.loads(app_file.read_text(encoding="utf-8")).get("token_info") or {}).get("access_token")
    except (OSError, ValueError):
        token = None
    if not token:
        raise RuntimeError(
            "关闭评论/弹幕、精选评论需要 B站 App 登录凭据。请先在终端运行 "
            f"`biliup -u {app_file} login` 并用 B站 App 扫码，然后重试。")
    return app_file


def build_upload_command(app_file: Path, video_paths: list, data, cover_url: str = "") -> list[str]:
    """Translate a filled python-biliup Data object into `biliup upload --submit app` arguments."""
    command = ["-u", str(app_file), "upload", "--submit", "app", *[str(p) for p in video_paths],
               "--title", data.title, "--desc", data.desc or "", "--tid", str(data.tid),
               "--copyright", str(data.copyright)]
    if data.tag:
        command += ["--tag", data.tag if isinstance(data.tag, str) else ",".join(data.tag)]
    if data.source:
        command += ["--source", data.source]
    if data.dynamic:
        command += ["--dynamic", data.dynamic]
    if cover_url or data.cover:
        command += ["--cover", cover_url or data.cover]
    if data.dtime:
        command += ["--dtime", str(int(data.dtime))]
    for name, flag in (("no_reprint", "--no-reprint"), ("is_only_self", "--is-only-self"),
                       ("dolby", "--dolby"), ("lossless_music", "--hires")):
        if getattr(data, name, 0):
            command += [flag, "1"]
    for name, flag in (("up_selection_reply", "--up-selection-reply"),
                       ("up_close_reply", "--up-close-reply"), ("up_close_danmu", "--up-close-danmu")):
        if getattr(data, name, False):
            command.append(flag)
    return command
