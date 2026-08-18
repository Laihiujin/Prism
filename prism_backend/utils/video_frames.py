from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
import glob
import sys


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def find_ffmpeg() -> str | None:
    """
    Prefer bundled Playwright ffmpeg under repo-root `.playwright-browsers`,
    then fall back to PATH.
    """
    root = _repo_root()
    bundled = root / ".playwright-browsers"
    if bundled.exists():
        if sys.platform == "win32":
            patterns = [
                str(bundled / "ffmpeg-*" / "ffmpeg.exe"),
                str(bundled / "ffmpeg-*" / "ffmpeg-win64" / "ffmpeg.exe"),
            ]
        else:
            patterns = [
                str(bundled / "ffmpeg-*" / "ffmpeg"),
                str(bundled / "ffmpeg-*" / "ffmpeg-linux" / "ffmpeg"),
                str(bundled / "ffmpeg-*" / "ffmpeg-mac" / "ffmpeg"),
            ]
        for p in patterns:
            matches = sorted(glob.glob(p))
            if matches:
                exe = matches[-1]
                if Path(exe).exists():
                    return exe

    return shutil.which("ffmpeg")


def extract_first_frame(video_path: str, out_path: str, *, overwrite: bool = True) -> None:
    """
    Extract the first representative frame from a video as a PNG.
    Uses ffmpeg (bundled if available).
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found (bundled Playwright ffmpeg missing and ffmpeg not on PATH)")

    src = Path(video_path)
    dst = Path(out_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not overwrite:
        return

    # -ss 0.1 to avoid black first frame in some codecs
    cmd = [
        ffmpeg,
        "-y" if overwrite else "-n",
        "-ss",
        "0.1",
        "-i",
        str(src),
        "-frames:v",
        "1",
        "-vf",
        "scale=iw:ih",
        str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0 or not dst.exists():
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f"ffmpeg extract_first_frame failed: {stderr[:4000]}")

