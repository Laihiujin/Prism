import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        v = int(value)
        return v
    except Exception:
        return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        v = float(value)
        return v if math.isfinite(v) and v > 0 else None
    except Exception:
        return None


def _reduce_ratio(width: int, height: int) -> Optional[str]:
    try:
        if width <= 0 or height <= 0:
            return None
        g = math.gcd(int(width), int(height))
        if g <= 0:
            return None
        return f"{int(width) // g}:{int(height) // g}"
    except Exception:
        return None


def cover_aspect_ratio_for_orientation(orientation: Optional[str]) -> str:
    """
    Douyin cover ratio defaults (observed):
    - portrait: 3:4
    - landscape: 4:3
    - square/unknown: 1:1
    """
    if orientation == "portrait":
        return "3:4"
    if orientation == "landscape":
        return "4:3"
    return "1:1"


def probe_video_metadata(file_path: str, *, timeout_sec: int = 10) -> dict:
    """
    Best-effort probe video metadata via ffprobe.
    Returns keys: duration, width, height, rotation, aspect_ratio, orientation, cover_aspect_ratio.
    """
    p = Path(str(file_path))
    if not p.exists() or not p.is_file():
        return {
            "duration": None,
            "width": None,
            "height": None,
            "rotation": 0,
            "aspect_ratio": None,
            "orientation": None,
            "cover_aspect_ratio": "1:1",
        }

    if not shutil.which("ffprobe"):
        return {
            "duration": None,
            "width": None,
            "height": None,
            "rotation": 0,
            "aspect_ratio": None,
            "orientation": None,
            "cover_aspect_ratio": "1:1",
        }

    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height:stream_tags=rotate:format=duration",
                "-of",
                "json",
                str(p),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        if proc.returncode != 0 or not proc.stdout:
            raise RuntimeError("ffprobe failed")

        data = json.loads(proc.stdout)
        streams = data.get("streams") or []
        stream0 = streams[0] if streams else {}
        width = _safe_int(stream0.get("width"))
        height = _safe_int(stream0.get("height"))
        tags = stream0.get("tags") or {}
        rotate = _safe_int(tags.get("rotate")) or 0

        # Normalize rotation to [0, 360)
        rotate = rotate % 360
        if rotate in (90, 270) and width and height:
            width, height = height, width

        duration = _safe_float((data.get("format") or {}).get("duration"))
        aspect_ratio = _reduce_ratio(width, height) if width and height else None

        orientation: Optional[str] = None
        if width and height:
            if width == height:
                orientation = "square"
            elif height > width:
                orientation = "portrait"
            else:
                orientation = "landscape"

        return {
            "duration": duration,
            "width": width,
            "height": height,
            "rotation": rotate,
            "aspect_ratio": aspect_ratio,
            "orientation": orientation,
            "cover_aspect_ratio": cover_aspect_ratio_for_orientation(orientation),
        }
    except Exception:
        return {
            "duration": None,
            "width": None,
            "height": None,
            "rotation": 0,
            "aspect_ratio": None,
            "orientation": None,
            "cover_aspect_ratio": "1:1",
        }

