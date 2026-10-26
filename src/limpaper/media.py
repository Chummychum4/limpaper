"""Stills from videos: thumbnails for the GUI and frames for theming.

ffmpeg is preferred; mpv can grab a frame too, which matters on Windows where
mpv is bundled but ffmpeg usually is not installed.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from .config import cache_dir
from .library import is_image
from .util import run, which

THUMB_WIDTH = 480


def _key(path: Path, *extra: str) -> str:
    try:
        mtime = str(int(path.stat().st_mtime))
    except OSError:
        mtime = "0"
    return hashlib.sha256(" ".join([str(path), mtime, *extra]).encode()).hexdigest()[:32]


def _duration(video: Path) -> float:
    if not which("ffprobe"):
        return 0.0
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", str(video)], timeout=20).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def _ffmpeg_frame(video: Path, out: Path, at: str | None, width: int | None) -> bool:
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if at:
        cmd += ["-ss", at]
    cmd += ["-i", str(video), "-frames:v", "1", "-update", "1"]
    if width:
        cmd += ["-vf", f"scale={width}:-2"]
    cmd.append(str(out))
    return run(cmd, timeout=60).returncode == 0 and out.is_file() and out.stat().st_size > 0


def _mpv_frame(mpv: str, video: Path, out: Path, at: str | None, width: int | None) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [mpv, "--no-config", "--really-quiet", "--ao=null", "--frames=1",
               "--vo=image", f"--vo-image-outdir={tmp}", "--vo-image-format=png"]
        if at:
            cmd.append(f"--start={at}")
        if width:
            cmd.append(f"--vf=scale={width}:-2")
        cmd.append(str(video))
        run(cmd, timeout=60)
        shots = sorted(Path(tmp).glob("*.png"))
        if not shots:
            return False
        out.write_bytes(shots[0].read_bytes())
        return True


def _grab(video: Path, out: Path, at: str | None, width: int | None, mpv: str | None) -> bool:
    if which("ffmpeg") and _ffmpeg_frame(video, out, at, width):
        return True
    return bool(mpv) and _mpv_frame(mpv, video, out, at, width)


def frame_is_blank(image: Path) -> bool:
    """A uniformly dark frame means the video fades in from black."""
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return False
    try:
        im = Image.open(image).convert("L")
        im.thumbnail((64, 64))
        st = ImageStat.Stat(im)
        return st.mean[0] < 6 and st.stddev[0] < 6
    except OSError:
        return False


def frame_for(video: Path, at: str = "", mpv: str | None = None) -> Path | None:
    """Full-size still of a video (cached), re-sampled further in if blank."""
    out = cache_dir() / "frames" / f"{_key(video, at)}.png"
    if out.is_file() and out.stat().st_size:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    if not _grab(video, out, at or None, None, mpv):
        return None
    if frame_is_blank(out):
        dur = _duration(video)
        later = min(max(dur * 0.15, 0.5), 10.0)
        _grab(video, out, f"{later:.2f}", None, mpv)
    return out if out.is_file() else None


def thumbnail_for(path: Path, mpv: str | None = None) -> Path | None:
    """Small still for grids. Images are returned as-is; the GUI scales them."""
    if is_image(path):
        return path
    out = cache_dir() / "thumbs" / f"{_key(path, str(THUMB_WIDTH))}.jpg"
    if out.is_file() and out.stat().st_size:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    # One second in skips most fade-ins; very short clips fall back to frame 0
    for at in ("1", None):
        if _grab(path, out, at, THUMB_WIDTH, mpv):
            return out
    return None
