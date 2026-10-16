#!/usr/bin/env python3
"""Print platform-specific or ratio-only social thumbnail presets."""

from __future__ import annotations

import argparse
import json


PLATFORM_PRESETS = {
    "xiaohongshu": {"width": 1080, "height": 1440, "ratio": "3:4", "status": "common-working-preset", "use": "Xiaohongshu image-note cover"},
    "wechat-channels": {"width": 1080, "height": 1260, "ratio": "6:7", "status": "common-working-preset", "use": "WeChat Channels feed cover"},
    "youtube": {"width": 3840, "height": 2160, "ratio": "16:9", "status": "official-recommendation", "use": "Standard YouTube video thumbnail"},
    "youtube-shorts": {"width": 2160, "height": 3840, "ratio": "9:16", "status": "official-recommendation", "use": "Uploaded YouTube Shorts thumbnail"},
    "douyin": {"width": 1080, "height": 1920, "ratio": "9:16", "status": "common-working-preset", "use": "Douyin vertical cover"},
}

RATIO_PRESETS = {
    "1:1": {"width": 1080, "height": 1080, "use": "Square social cover"},
    "4:3": {"width": 1600, "height": 1200, "use": "Landscape presentation or classic video cover"},
    "3:4": {"width": 1080, "height": 1440, "use": "Portrait social cover"},
    "4:5": {"width": 1080, "height": 1350, "use": "Portrait feed cover"},
    "6:7": {"width": 1080, "height": 1260, "use": "WeChat Channels-style portrait cover"},
    "16:9": {"width": 1920, "height": 1080, "use": "Landscape video cover"},
    "9:16": {"width": 1080, "height": 1920, "use": "Full-height vertical video cover"},
}

# Backward-compatible export for scripts importing the old name.
PRESETS = PLATFORM_PRESETS

PLATFORM_ALIASES = {
    "xhs": "xiaohongshu", "rednote": "xiaohongshu", "wechat": "wechat-channels",
    "shipinhao": "wechat-channels", "youtube-long": "youtube",
    "shorts": "youtube-shorts", "tiktok-cn": "douyin",
}

RATIO_ALIASES = {
    "square": "1:1", "4-3": "4:3", "landscape-4-3": "4:3",
    "3-4": "3:4", "portrait-3-4": "3:4", "4-5": "4:5",
    "portrait-4-5": "4:5", "6-7": "6:7", "wechat-ratio": "6:7",
    "16-9": "16:9", "landscape": "16:9", "landscape-16-9": "16:9",
    "9-16": "9:16", "vertical": "9:16", "portrait-9-16": "9:16",
}


def resolve_platform(value: str) -> str:
    normalized = value.strip().lower()
    return PLATFORM_ALIASES.get(normalized, normalized)


def resolve_ratio(value: str) -> str:
    normalized = value.strip().lower().replace("×", ":").replace("/", ":")
    return RATIO_ALIASES.get(normalized, normalized)


def _print_presets(selected: dict[str, dict[str, object]], kind: str, as_json: bool) -> None:
    if as_json:
        print(json.dumps({kind: selected}, ensure_ascii=False, indent=2))
        return
    for name, preset in selected.items():
        status = f" [{preset['status']}]" if "status" in preset else ""
        print(f"{name:16} {preset['width']}x{preset['height']} ({preset.get('ratio', name)}){status}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List all platform presets")
    group.add_argument("--list-ratios", action="store_true", help="List all generic ratio presets")
    group.add_argument("--platform", help="Print one platform preset by name or alias")
    group.add_argument("--ratio", help="Print one generic ratio preset, such as 4:3 or 16:9")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    args = parser.parse_args()

    if args.list:
        _print_presets(PLATFORM_PRESETS, "platforms", args.json)
    elif args.list_ratios:
        _print_presets(RATIO_PRESETS, "ratios", args.json)
    elif args.platform:
        key = resolve_platform(args.platform)
        if key not in PLATFORM_PRESETS:
            parser.error(f"unknown platform '{args.platform}'. Choose: {', '.join(PLATFORM_PRESETS)}")
        _print_presets({key: PLATFORM_PRESETS[key]}, "platforms", args.json)
    else:
        key = resolve_ratio(args.ratio)
        if key not in RATIO_PRESETS:
            parser.error(f"unknown ratio '{args.ratio}'. Choose: {', '.join(RATIO_PRESETS)}")
        _print_presets({key: RATIO_PRESETS[key]}, "ratios", args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
