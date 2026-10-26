"""Recolour the desktop to match the wallpaper through caelestia (Linux only).

Colours are handed to caelestia's own "dynamic" scheme rather than written by
hand, so foot / quickshell / gtk / qt / fuzzel / btop all follow one source of
truth. caelestia only accepts still images, so a frame is extracted first.
"""

from __future__ import annotations

from pathlib import Path

from .config import IS_WINDOWS, Settings
from .library import is_image
from .media import frame_for
from .state import State
from .util import run, which


def available(settings: Settings) -> bool:
    return (
        not IS_WINDOWS
        and settings.theme
        and bool(which("caelestia"))
        and bool(which("ffmpeg"))
    )


def _save_baseline(state: State) -> None:
    """Remember the pre-limpaper scheme once, so "stop" can go back to it."""
    if state.baseline_file.is_file():
        return
    props = run(["caelestia", "scheme", "get", "-n", "-f", "-m", "-v"]).stdout.splitlines()
    if len(props) != 4 or props[0] == "dynamic":
        # Already dynamic: whatever it was derived from is not recoverable
        return
    wallpaper = run(["caelestia", "wallpaper"]).stdout.strip()
    state.dir.mkdir(parents=True, exist_ok=True)
    state.baseline_file.write_text(
        f"name={props[0]}\nflavour={props[1]}\nmode={props[2]}\n"
        f"variant={props[3]}\nwallpaper={wallpaper}\n",
        encoding="utf-8",
    )


def apply(path: Path, settings: Settings, state: State) -> str:
    """Theme from a wallpaper; returns a one-line summary ("" when skipped)."""
    if not available(settings):
        return ""
    _save_baseline(state)
    still = path if is_image(path) else frame_for(path, settings.frame_at)
    if not still:
        return "Could not extract a frame; colours left unchanged."
    # "scheme set -n dynamic" is a no-op when already dynamic, in which case the
    # wallpaper call has already recomputed the palette.
    run(["caelestia", "wallpaper", "-f", str(still)])
    run(["caelestia", "scheme", "set", "-n", "dynamic"])
    mode = run(["caelestia", "scheme", "get", "-m"]).stdout.strip()
    variant = run(["caelestia", "scheme", "get", "-v"]).stdout.strip()
    return f"colours: dynamic {mode} {variant}".strip()


def restore(settings: Settings, state: State) -> str:
    if not available(settings):
        return ""
    try:
        lines = state.baseline_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return "No saved baseline scheme; colours left as they are."
    base = dict(line.split("=", 1) for line in lines if "=" in line)
    name = base.get("name")
    if not name:
        return ""
    # Scheme first: once it is no longer dynamic, restoring the still wallpaper
    # cannot pull the palette back off the image.
    run(["caelestia", "scheme", "set", "-n", name, "-f", base.get("flavour", ""),
         "-m", base.get("mode", ""), "-v", base.get("variant", "")])
    wp = base.get("wallpaper", "")
    if wp and Path(wp).is_file():
        run(["caelestia", "wallpaper", "-f", wp])
    return f"colours: {name} {base.get('flavour', '')} {base.get('mode', '')}".strip()
