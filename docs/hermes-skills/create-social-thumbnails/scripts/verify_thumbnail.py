#!/usr/bin/env python3
"""Verify PNG or JPEG dimensions against a platform or generic ratio preset."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from platform_presets import PLATFORM_PRESETS, RATIO_PRESETS, resolve_platform, resolve_ratio


def png_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) >= 24 and header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR":
        return struct.unpack(">II", header[16:24])
    return None


def jpeg_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        if handle.read(2) != b"\xff\xd8":
            return None
        while True:
            byte = handle.read(1)
            while byte == b"\xff":
                byte = handle.read(1)
            if not byte:
                return None
            marker = byte[0]
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                continue
            length_bytes = handle.read(2)
            if len(length_bytes) != 2:
                return None
            segment_length = struct.unpack(">H", length_bytes)[0]
            if segment_length < 2:
                return None
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                data = handle.read(5)
                if len(data) != 5:
                    return None
                height, width = struct.unpack(">HH", data[1:5])
                return width, height
            handle.seek(segment_length - 2, 1)


def image_size(path: Path) -> tuple[int, int]:
    size = png_size(path) or jpeg_size(path)
    if size is None:
        raise ValueError("unsupported or invalid image; expected PNG or JPEG")
    return size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="PNG or JPEG file to verify")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--platform", help="Platform preset or alias")
    target.add_argument("--ratio", help="Generic ratio preset, such as 4:3 or 16:9")
    parser.add_argument("--aspect-only", action="store_true", help="Accept non-canonical dimensions when the aspect ratio matches")
    args = parser.parse_args()

    if args.platform:
        key = resolve_platform(args.platform)
        if key not in PLATFORM_PRESETS:
            parser.error(f"unknown platform '{args.platform}'. Choose: {', '.join(PLATFORM_PRESETS)}")
        preset = PLATFORM_PRESETS[key]
        target_name = key
        expected_ratio_label = str(preset["ratio"])
    else:
        key = resolve_ratio(args.ratio)
        if key not in RATIO_PRESETS:
            parser.error(f"unknown ratio '{args.ratio}'. Choose: {', '.join(RATIO_PRESETS)}")
        preset = RATIO_PRESETS[key]
        target_name = f"ratio {key}"
        expected_ratio_label = key

    if not args.image.is_file():
        parser.error(f"image not found: {args.image}")

    try:
        width, height = image_size(args.image)
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    expected_width = int(preset["width"])
    expected_height = int(preset["height"])
    ratio_matches = abs(width / height - expected_width / expected_height) <= 0.001
    exact_matches = width == expected_width and height == expected_height
    passed = ratio_matches if args.aspect_only else exact_matches
    requirement = f"aspect {expected_ratio_label}" if args.aspect_only else f"{expected_width}x{expected_height}"
    result = "PASS" if passed else "FAIL"
    print(f"{result}: {args.image} is {width}x{height}; {target_name} requires {requirement}.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
