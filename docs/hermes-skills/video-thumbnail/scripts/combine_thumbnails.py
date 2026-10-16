#!/usr/bin/env python3
"""
Combine multiple thumbnail images into a 2x2 comparison grid.

Usage:
    python3 combine_thumbnails.py \
        --images thumb1.png thumb2.png thumb3.png thumb4.png \
        --output comparison.png \
        --labels "A" "B" "C" "D"
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def parse_args():
    parser = argparse.ArgumentParser(description="Combine thumbnails into comparison grid")
    parser.add_argument(
        "--images", required=True, nargs="+",
        help="Paths to thumbnail images (expects 4 for a 2x2 grid)"
    )
    parser.add_argument(
        "--output", required=True,
        help="Output file path for the combined grid image"
    )
    parser.add_argument(
        "--labels", nargs="*", default=["A", "B", "C", "D"],
        help="Labels for each thumbnail (default: A B C D)"
    )
    return parser.parse_args()


def add_label(img, label):
    """Add a label badge to the top-left corner of an image."""
    draw = ImageDraw.Draw(img)
    font_size = max(28, img.width // 20)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    padding = 12
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    badge_w = text_w + padding * 2
    badge_h = text_h + padding * 2
    margin = 16

    draw.rounded_rectangle(
        [margin, margin, margin + badge_w, margin + badge_h],
        radius=8,
        fill=(0, 0, 0, 200),
    )
    draw.text(
        (margin + padding, margin + padding - bbox[1]),
        label, fill="white", font=font,
    )
    return img


def main():
    args = parse_args()

    images = []
    for path in args.images:
        if not Path(path).exists():
            print(f"Error: Image not found: {path}", file=sys.stderr)
            sys.exit(1)
        images.append(Image.open(path).convert("RGBA"))

    if len(images) != 4:
        print(f"Warning: Expected 4 images, got {len(images)}. Grid may look uneven.", file=sys.stderr)

    # Normalize all images to the same size (use the first image's dimensions)
    target_w, target_h = images[0].size
    resized = []
    for img in images:
        if img.size != (target_w, target_h):
            img = img.resize((target_w, target_h), Image.LANCZOS)
        resized.append(img)

    # Add labels
    labels = args.labels[:len(resized)]
    for i, (img, label) in enumerate(zip(resized, labels)):
        resized[i] = add_label(img, label)

    # Build 2x2 grid with gap
    gap = 8
    grid_w = target_w * 2 + gap
    grid_h = target_h * 2 + gap
    grid = Image.new("RGBA", (grid_w, grid_h), (20, 20, 20, 255))

    positions = [
        (0, 0),
        (target_w + gap, 0),
        (0, target_h + gap),
        (target_w + gap, target_h + gap),
    ]

    for img, pos in zip(resized, positions):
        grid.paste(img, pos)

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    grid.convert("RGB").save(str(output_path), quality=95)
    print(f"Comparison grid saved to: {output_path}")


if __name__ == "__main__":
    main()
