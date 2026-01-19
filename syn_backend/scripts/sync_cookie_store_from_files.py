import json
from pathlib import Path

from myUtils.cookie_manager import cookie_manager


PLATFORMS = {"bilibili", "kuaishou", "douyin", "xiaohongshu", "channels"}


def _parse_platform_and_account_id(filename: str):
    stem = Path(filename).stem
    for platform in PLATFORMS:
        prefix = f"{platform}_"
        if stem.startswith(prefix):
            return platform, stem[len(prefix) :]
    return None, None


def main():
    cookies_dir = Path(cookie_manager.cookies_dir)
    if not cookies_dir.exists():
        print(f"[sync] cookies dir not found: {cookies_dir}")
        return

    files = sorted(cookies_dir.glob("*.json"))
    if not files:
        print(f"[sync] no cookie files in {cookies_dir}")
        return

    added = 0
    skipped = 0
    for path in files:
        platform, account_id = _parse_platform_and_account_id(path.name)
        if not platform or not account_id:
            skipped += 1
            continue

        if cookie_manager.get_account_by_id(account_id):
            skipped += 1
            continue

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            skipped += 1
            continue

        extracted = cookie_manager._extract_user_info_from_cookie(platform, payload) or {}
        account_details = {
            "id": account_id,
            "name": extracted.get("name") or account_id,
            "status": "valid",
            "cookie": payload,
            "user_id": extracted.get("user_id"),
            "avatar": extracted.get("avatar"),
            "note": "-",
        }

        try:
            cookie_manager.add_account(platform, account_details)
            added += 1
            print(f"[sync] added {platform} {account_id}")
        except Exception as exc:
            skipped += 1
            print(f"[sync] failed {platform} {account_id}: {exc}")

    print(f"[sync] done: added={added} skipped={skipped}")


if __name__ == "__main__":
    main()
