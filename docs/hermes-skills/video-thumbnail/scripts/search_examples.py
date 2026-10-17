#!/usr/bin/env python3
"""
Search YouTube for high-performing videos on a topic and download their thumbnails
as style examples for thumbnail generation.

Uses the Scrape Creators API to find videos, sorts by view count, and downloads
the top thumbnails.

Usage:
    python3 search_examples.py --query "claude code tutorial" --top 5
    python3 search_examples.py --query "AI agents" --top 3 --min-views 50000

Environment:
    SCRAPECREATORS_API_KEY must be set (or present in .env).

Output:
    Downloads thumbnails to youtube-thumbnails/examples/ and prints a JSON manifest
    to stdout with metadata about each downloaded thumbnail.
"""

import argparse
import io
import json
import os
import re
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

from PIL import Image

# Enable AVIF support — YouTube serves AVIF thumbnails
try:
    import pillow_avif  # noqa: F401
except ImportError:
    pass


def load_dotenv():
    """Load .env file from project root if it exists."""
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        env_path = Path.cwd() / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


def search_youtube(query, api_key):
    """Search YouTube via Scrape Creators API."""
    encoded_query = urllib.parse.quote(query)
    url = f"https://api.scrapecreators.com/v1/youtube/search?query={encoded_query}&includeExtras=true"

    req = urllib.request.Request(url, headers={"x-api-key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"Error: API returned {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: API request failed: {e}", file=sys.stderr)
        sys.exit(1)


def get_best_thumbnail_url(thumbnail_data):
    """Extract the highest-resolution thumbnail URL from the API response.

    The thumbnail field can be a string URL or a list of objects with url/width/height.
    """
    if isinstance(thumbnail_data, str):
        return thumbnail_data
    if isinstance(thumbnail_data, list):
        best = max(thumbnail_data, key=lambda t: t.get("width", 0) * t.get("height", 0), default=None)
        if best:
            return best.get("url", "")
    if isinstance(thumbnail_data, dict):
        return thumbnail_data.get("url", "")
    return ""


def download_thumbnail(url, output_path):
    """Download a thumbnail image, convert to JPEG via Pillow.

    YouTube often serves WebP which Claude's Read tool can't display.
    Converting through Pillow ensures the output is always a real JPEG.
    """
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()

        if b"<!DOCTYPE" in data[:256] or b"<html" in data[:256]:
            print(f"  Warning: Got HTML instead of image from {url}", file=sys.stderr)
            return False

        if len(data) < 100:
            print(f"  Warning: File too small ({len(data)} bytes) from {url}", file=sys.stderr)
            return False

        # Open with Pillow and re-save as JPEG to normalize the format
        # (YouTube serves WebP which some tools can't read)
        img = Image.open(io.BytesIO(data))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), "JPEG", quality=90)
        return True

    except Exception as e:
        print(f"  Warning: Failed to download {url}: {e}", file=sys.stderr)
        return False


def slugify(text, max_len=40):
    """Convert text to a filename-safe slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    return text[:max_len]


def main():
    parser = argparse.ArgumentParser(description="Search YouTube for high-performing thumbnail examples")
    parser.add_argument("--query", required=True, help="Search query (video topic)")
    parser.add_argument("--top", type=int, default=5, help="Number of top thumbnails to download (default: 5)")
    parser.add_argument("--min-views", type=int, default=0, help="Minimum view count filter (default: 0)")
    parser.add_argument("--output-dir", default="youtube-thumbnails/examples", help="Output directory")
    args = parser.parse_args()

    load_dotenv()

    api_key = os.environ.get("SCRAPECREATORS_API_KEY")
    if not api_key:
        print("Error: SCRAPECREATORS_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    print(f"Searching YouTube for: {args.query}", file=sys.stderr)
    data = search_youtube(args.query, api_key)

    videos = data.get("videos", [])
    if not videos:
        print("No videos found for this query.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(videos)} videos", file=sys.stderr)

    # Parse view counts and filter
    for v in videos:
        v["_views"] = v.get("viewCountInt", 0) or 0
    videos = [v for v in videos if v["_views"] >= args.min_views]
    videos.sort(key=lambda v: v["_views"], reverse=True)

    if not videos:
        print(f"No videos found with >= {args.min_views} views.", file=sys.stderr)
        sys.exit(1)

    top_videos = videos[:args.top]

    print(f"\nTop {len(top_videos)} videos by views:", file=sys.stderr)
    for i, v in enumerate(top_videos):
        print(f"  {i+1}. [{v['_views']:,} views] {v.get('title', 'Untitled')}", file=sys.stderr)

    # Download thumbnails
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    query_slug = slugify(args.query)

    manifest = []
    for i, v in enumerate(top_videos):
        thumb_url = get_best_thumbnail_url(v.get("thumbnail", ""))
        if not thumb_url:
            print(f"  Skipping video {i+1}: no thumbnail URL", file=sys.stderr)
            continue

        filename = f"{query_slug}-{i+1}.jpg"
        output_path = output_dir / filename

        print(f"  Downloading thumbnail {i+1}: {v.get('title', '')[:60]}...", file=sys.stderr)
        if download_thumbnail(thumb_url, output_path):
            manifest.append({
                "path": str(output_path),
                "title": v.get("title", ""),
                "views": v["_views"],
                "channel": v.get("channel", {}).get("title", ""),
                "url": v.get("url", ""),
            })

    if not manifest:
        print("Error: Failed to download any thumbnails.", file=sys.stderr)
        sys.exit(1)

    print(f"\nDownloaded {len(manifest)} thumbnails to {output_dir}/", file=sys.stderr)

    # Print manifest to stdout (machine-readable for the skill to parse)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
