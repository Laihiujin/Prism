"""Platform-specific Prism CLI."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PROJECT_ROOT / "prism_backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SCHEDULE_FORMAT = "%Y-%m-%d %H:%M"
PLATFORMS = ("douyin", "kuaishou", "xiaohongshu", "bilibili", "channels", "baijiahao", "tiktok", "youtube")


def runtime_home() -> Path:
    return Path(os.getenv("PRISM_DATA_DIR", str(BACKEND_ROOT))).expanduser().resolve()


def account_file(platform: str, account: str) -> Path:
    platform = "tencent" if platform == "channels" else platform
    target = runtime_home() / "cookiesFile" / f"{platform}_{account}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def parse_tags(value: str | None) -> list[str]:
    return [tag.strip().lstrip("#") for tag in (value or "").split(",") if tag.strip().lstrip("#")]


def existing_file(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"File not found: {value}")
    return path.resolve()


def schedule_value(value: str) -> datetime:
    try:
        return datetime.strptime(value, SCHEDULE_FORMAT)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected schedule format YYYY-MM-DD HH:MM") from exc


def add_runtime_flags(parser: argparse.ArgumentParser, default_headless: bool = True) -> None:
    parser.add_argument("--debug", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--headed", dest="headless", action="store_false")
    group.add_argument("--headless", dest="headless", action="store_true")
    parser.set_defaults(headless=default_headless)


def add_login_check(actions: Any, name: str, runtime_flags: bool = True, qr_probe: bool = False) -> None:
    for action in ("login", "check"):
        command = actions.add_parser(action, help=f"{name} {action}")
        command.add_argument("--account", required=True)
        if action == "login" and runtime_flags:
            if qr_probe:
                command.add_argument(
                    "--qr-only",
                    action="store_true",
                    help="Emit a QR-code event once and exit without completing login",
                )
            add_runtime_flags(command)


def add_video(actions: Any, name: str, scheduling: bool = True, thumbnail: bool = False) -> argparse.ArgumentParser:
    command = actions.add_parser("upload-video", help=f"Upload one video to {name}")
    command.add_argument("--account", required=True)
    command.add_argument("--file", required=True, type=existing_file)
    command.add_argument("--title", required=True)
    command.add_argument("--desc", "--description", default="")
    command.add_argument("--tags", default="")
    if scheduling:
        command.add_argument("--schedule", type=schedule_value, help="Publish at YYYY-MM-DD HH:MM")
    if thumbnail:
        command.add_argument("--thumbnail", type=existing_file)
    add_runtime_flags(command)
    return command


def add_note(actions: Any, name: str) -> None:
    command = actions.add_parser("upload-note", help=f"Upload one image post to {name}")
    command.add_argument("--account", required=True)
    command.add_argument("--images", required=True, nargs="+", type=existing_file)
    command.add_argument("--title", required=True)
    command.add_argument("--note", default="")
    command.add_argument("--notef")
    command.add_argument("--tags", default="")
    command.add_argument("--schedule", type=schedule_value, help="Publish at YYYY-MM-DD HH:MM")
    if name == "douyin":
        command.add_argument("--bgm", default="")
        command.add_argument("--declaration")
        command.add_argument("--location", default="")
    add_runtime_flags(command)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prism", description="Prism multi-platform publishing CLI")
    roots = parser.add_subparsers(dest="platform", required=True)

    # 跨平台进程管理：prism service start|stop|restart|status|logs|list
    service_cmd = roots.add_parser("service", help="Manage Prism services (start/stop/status/logs)")
    service_cmd.add_argument(
        "service_args",
        nargs=argparse.REMAINDER,
        help="arguments forwarded to `prism service` (run `prism service -h`)",
    )

    for name in ("douyin", "kuaishou", "xiaohongshu"):
        actions = roots.add_parser(name).add_subparsers(dest="action", required=True)
        add_login_check(actions, name, qr_probe=True)
        video = add_video(actions, name, thumbnail=True)
        if name == "douyin":
            video.add_argument("--thumbnail-landscape", type=existing_file)
            video.add_argument("--thumbnail-portrait", type=existing_file)
            video.add_argument("--product-link", default="")
            video.add_argument("--product-title", default="")
            video.add_argument("--declaration")
            video.add_argument("--random-cover", action="store_true")
            video.add_argument("--mini-program-link", default="")
            video.add_argument("--mini-program-title", default="")
            video.add_argument("--location", default="")
        add_note(actions, name)

    actions = roots.add_parser("bilibili").add_subparsers(dest="action", required=True)
    add_login_check(actions, "bilibili", runtime_flags=False)
    video = add_video(actions, "bilibili", thumbnail=True)
    video.add_argument("--tid", required=True, type=int)

    actions = roots.add_parser("channels", aliases=["tencent"]).add_subparsers(dest="action", required=True)
    add_login_check(actions, "channels")
    video = add_video(actions, "channels", thumbnail=True)
    video.add_argument("--thumbnail-landscape", type=existing_file)
    video.add_argument("--thumbnail-portrait", type=existing_file)
    video.add_argument("--short-title")
    video.add_argument("--category", type=int)
    video.add_argument("--draft", action="store_true")

    actions = roots.add_parser("baijiahao", aliases=["baijia"]).add_subparsers(dest="action", required=True)
    add_login_check(actions, "baijiahao")
    add_video(actions, "baijiahao")

    actions = roots.add_parser("tiktok", aliases=["tk"]).add_subparsers(dest="action", required=True)
    add_login_check(actions, "tiktok")
    add_video(actions, "tiktok", thumbnail=True)

    actions = roots.add_parser("youtube", aliases=["yt"]).add_subparsers(dest="action", required=True)
    add_login_check(actions, "youtube")
    video = add_video(actions, "youtube", scheduling=False, thumbnail=True)
    video.add_argument("--playlist")
    video.add_argument("--visibility", choices=("public", "unlisted", "private"), default="public")
    return parser


def login_result(value: Any, path: Path) -> dict[str, Any]:
    return value if isinstance(value, dict) else {"success": bool(value), "account_file": str(path)}


async def emit_qrcode(payload: dict[str, Any]) -> None:
    """Emit a machine-readable QR event while the login command is waiting.

    The image file remains available until the login flow completes, so desktop
    callers and Hermes can display it immediately instead of waiting for the
    final login result.
    """
    print(json.dumps({"event": "qrcode", **payload}, ensure_ascii=False), flush=True)


async def login(platform: str, path: Path, args: argparse.Namespace) -> dict[str, Any]:
    if platform == "douyin":
        if args.qr_only:
            from uploader.douyin_uploader.main_refactored import douyin_cookie_gen
            return await douyin_cookie_gen(str(path), qrcode_callback=emit_qrcode, headless=args.headless, poll_interval=0.1, max_checks=1)
        from uploader.douyin_uploader.main_refactored import douyin_setup
        return login_result(await douyin_setup(str(path), handle=True, return_detail=True, qrcode_callback=emit_qrcode, headless=args.headless), path)
    if platform == "kuaishou":
        if args.qr_only:
            from uploader.ks_uploader.main_refactored import get_ks_cookie
            return await get_ks_cookie(str(path), qrcode_callback=emit_qrcode, headless=args.headless, poll_interval=0.1, max_checks=1)
        from uploader.ks_uploader.main_refactored import ks_setup
        return login_result(await ks_setup(str(path), handle=True, return_detail=True, qrcode_callback=emit_qrcode, headless=args.headless), path)
    if platform == "xiaohongshu":
        if args.qr_only:
            from uploader.xiaohongshu_uploader.main_refactored import xiaohongshu_cookie_gen
            return await xiaohongshu_cookie_gen(str(path), qrcode_callback=emit_qrcode, headless=args.headless, poll_interval=0.1, max_checks=1)
        from uploader.xiaohongshu_uploader.main_refactored import xiaohongshu_setup
        return login_result(await xiaohongshu_setup(str(path), handle=True, return_detail=True, qrcode_callback=emit_qrcode, headless=args.headless), path)
    if platform == "bilibili":
        from uploader.bilibili_uploader.runtime import run_biliup_command
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return {"success": False, "account_file": str(path), "message": "Bilibili login requires an interactive local terminal."}
        return {"success": run_biliup_command(["-u", str(path), "login"], interactive=True).returncode == 0, "account_file": str(path)}
    if platform == "channels":
        from uploader.tencent_uploader.main import weixin_setup
        return login_result(await weixin_setup(str(path), handle=True), path)
    if platform == "baijiahao":
        from uploader.baijiahao_uploader.main import baijiahao_setup
        return login_result(await baijiahao_setup(str(path), handle=True), path)
    if platform == "tiktok":
        from uploader.tk_uploader.main_chrome import tiktok_setup
        return login_result(await tiktok_setup(str(path), handle=True), path)
    if platform == "youtube":
        from uploader.youtube_uploader.main_refactored import youtube_setup
        return login_result(await youtube_setup(str(path), handle=True, return_detail=True, headless=False), path)
    raise RuntimeError(f"Unsupported platform: {platform}")


async def check(platform: str, path: Path) -> bool:
    if not path.is_file():
        return False
    if platform == "douyin":
        from uploader.douyin_uploader.main_refactored import cookie_auth
    elif platform == "kuaishou":
        from uploader.ks_uploader.main_refactored import cookie_auth
    elif platform == "xiaohongshu":
        from uploader.xiaohongshu_uploader.main_refactored import cookie_auth
    elif platform == "bilibili":
        from uploader.bilibili_uploader.runtime import run_biliup_command
        return run_biliup_command(["-u", str(path), "renew"]).returncode == 0
    elif platform == "channels":
        from uploader.tencent_uploader.main import cookie_auth
    elif platform == "baijiahao":
        from uploader.baijiahao_uploader.main import cookie_auth
    elif platform == "tiktok":
        from uploader.tk_uploader.main_chrome import cookie_auth
    elif platform == "youtube":
        from uploader.youtube_uploader.main_refactored import cookie_auth
    else:
        return False
    return bool(await cookie_auth(str(path)))


def note_body(args: argparse.Namespace) -> str:
    if not args.notef:
        return args.note
    source = Path(args.notef).expanduser()
    if not source.is_file():
        raise FileNotFoundError(source)
    return source.read_text(encoding="utf-8")


async def upload_note(platform: str, path: Path, args: argparse.Namespace) -> None:
    tags, body, images, date = parse_tags(args.tags), note_body(args), [str(item) for item in args.images], args.schedule or 0
    if platform == "douyin":
        from uploader.douyin_uploader.main_refactored import DouYinNote, DOUYIN_PUBLISH_STRATEGY_SCHEDULED
        app = DouYinNote(images, body, tags, date, str(path), title=args.title, publish_strategy=DOUYIN_PUBLISH_STRATEGY_SCHEDULED if args.schedule else "immediate", debug=args.debug, headless=args.headless, bgm=args.bgm, declaration=args.declaration, location=args.location)
    elif platform == "kuaishou":
        from uploader.ks_uploader.main_refactored import KSNote, KUAISHOU_PUBLISH_STRATEGY_SCHEDULED
        app = KSNote(images, body, tags, date, str(path), title=args.title, publish_strategy=KUAISHOU_PUBLISH_STRATEGY_SCHEDULED if args.schedule else "immediate", debug=args.debug, headless=args.headless)
    elif platform == "xiaohongshu":
        from uploader.xiaohongshu_uploader.main_refactored import XiaoHongShuNote, XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED
        app = XiaoHongShuNote(images, body, tags, date, str(path), title=args.title, publish_strategy=XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED if args.schedule else "immediate", debug=args.debug, headless=args.headless)
    else:
        raise RuntimeError(f"{platform} does not support image posts")
    await app.main()


async def upload_video(platform: str, path: Path, args: argparse.Namespace) -> None:
    tags, date = parse_tags(args.tags), args.schedule or 0
    if platform == "douyin":
        from uploader.douyin_uploader.main_refactored import DouYinVideo, DOUYIN_PUBLISH_STRATEGY_SCHEDULED
        app = DouYinVideo(args.title, str(args.file), tags, date, str(path), thumbnail_landscape_path=str(args.thumbnail_landscape) if args.thumbnail_landscape else None, thumbnail_portrait_path=str(args.thumbnail_portrait or args.thumbnail) if args.thumbnail_portrait or args.thumbnail else None, productLink=args.product_link, productTitle=args.product_title, desc=args.desc, publish_strategy=DOUYIN_PUBLISH_STRATEGY_SCHEDULED if args.schedule else "immediate", debug=args.debug, headless=args.headless, declaration=args.declaration, random_cover=args.random_cover, miniprogramLink=args.mini_program_link, miniprogramTitle=args.mini_program_title, location=args.location)
    elif platform == "kuaishou":
        from uploader.ks_uploader.main_refactored import KSVideo, KUAISHOU_PUBLISH_STRATEGY_SCHEDULED
        app = KSVideo(args.title, str(args.file), tags, date, str(path), thumbnail_path=str(args.thumbnail) if args.thumbnail else None, desc=args.desc, publish_strategy=KUAISHOU_PUBLISH_STRATEGY_SCHEDULED if args.schedule else "immediate", debug=args.debug, headless=args.headless)
    elif platform == "xiaohongshu":
        from uploader.xiaohongshu_uploader.main_refactored import XiaoHongShuVideo, XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED
        app = XiaoHongShuVideo(args.title, str(args.file), tags, date, str(path), thumbnail_path=str(args.thumbnail) if args.thumbnail else None, desc=args.desc, publish_strategy=XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED if args.schedule else "immediate", debug=args.debug, headless=args.headless)
    elif platform == "bilibili":
        from uploader.bilibili_uploader.runtime import run_biliup_command
        command = ["-u", str(path), "upload", str(args.file), "--title", args.title, "--desc", args.desc, "--tid", str(args.tid)]
        if tags: command.extend(["--tag", ",".join(tags)])
        if args.thumbnail: command.extend(["--cover", str(args.thumbnail)])
        if args.schedule: command.extend(["--dtime", str(int(args.schedule.timestamp()))])
        result = run_biliup_command(command)
        if result.returncode: raise RuntimeError((result.stderr or result.stdout or "Bilibili upload failed").strip())
        return
    elif platform == "channels":
        from uploader.tencent_uploader.main import TencentVideo
        app = TencentVideo(args.title, str(args.file), tags, date, str(path), category=args.category, thumbnail_path=str(args.thumbnail) if args.thumbnail else None)
    elif platform == "baijiahao":
        from uploader.baijiahao_uploader.main import BaiJiaHaoVideo
        app = BaiJiaHaoVideo(args.title, str(args.file), tags, date, str(path))
    elif platform == "tiktok":
        from uploader.tk_uploader.main_chrome import TiktokVideo
        app = TiktokVideo("\n\n".join(item for item in (args.title, args.desc) if item), str(args.file), tags, date, str(path), thumbnail_path=str(args.thumbnail) if args.thumbnail else None)
    elif platform == "youtube":
        from uploader.youtube_uploader.main_refactored import YouTubeVideo
        app = YouTubeVideo(args.title, str(args.file), tags, str(path), description=args.desc, thumbnail_path=str(args.thumbnail) if args.thumbnail else None, playlist=args.playlist, visibility=args.visibility, debug=args.debug, headless=args.headless)
    else:
        raise RuntimeError(f"Unsupported platform: {platform}")
    await app.main()


async def dispatch(args: argparse.Namespace) -> int:
    platform = {"tencent": "channels", "baijia": "baijiahao", "tk": "tiktok", "yt": "youtube"}.get(args.platform, args.platform)
    path = account_file(platform, args.account)
    if args.action == "login":
        result = await login(platform, path, args)
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0 if result.get("success") else 1
    if args.action == "check":
        valid = await check(platform, path)
        print(json.dumps({"success": valid, "account_file": str(path)}, ensure_ascii=False))
        return 0 if valid else 1
    if not path.exists():
        raise FileNotFoundError(f"Account not found: {path}; run prism {platform} login first.")
    if args.action == "upload-note":
        await upload_note(platform, path, args)
        print(json.dumps({"success": True, "platform": platform, "kind": "note"}, ensure_ascii=False))
        return 0
    if args.action == "upload-video":
        await upload_video(platform, path, args)
        print(json.dumps({"success": True, "platform": platform, "kind": "video"}, ensure_ascii=False))
        return 0
    raise RuntimeError(f"Unsupported action: {args.action}")


def main() -> int:
    args = build_parser().parse_args()
    if args.platform == "service":
        from utils.process_manager import main as service_main

        return service_main(args.service_args)
    try:
        return asyncio.run(dispatch(args))
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"prism: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
