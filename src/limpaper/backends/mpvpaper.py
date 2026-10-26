"""Linux: mpvpaper draws mpv on a wlr-layer-shell background surface.

Works on wlroots-based compositors (Hyprland, Sway, river, ...). GNOME and KDE
do not implement wlr-layer-shell.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from ..config import Settings
from ..library import is_image
from ..util import run, which
from .base import Backend, BackendError


class MpvpaperBackend(Backend):
    name = "mpvpaper"

    def __init__(self, settings: Settings):
        self.settings = settings

    def available(self) -> tuple[bool, str]:
        if not which("mpvpaper"):
            return False, "mpvpaper is not installed (see the README for Arch/Debian commands)."
        if not os.environ.get("WAYLAND_DISPLAY"):
            return False, "No Wayland session found; mpvpaper needs a wlroots compositor such as Hyprland or Sway."
        return True, ""

    def apply(self, path: Path) -> None:
        if not which("mpvpaper"):
            raise BackendError("mpvpaper is not installed.")
        if not path.is_file():
            raise BackendError(f"File no longer exists: {path}")
        opts = self.settings.mpv_opts
        if is_image(path):
            # Without this mpv shows a still for one second and moves on
            opts += " image-display-duration=inf"
        self.stop()
        time.sleep(0.2)
        try:
            subprocess.Popen(
                ["mpvpaper", "-f", "-o", opts, self.settings.output or "*", str(path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise BackendError(f"Could not start mpvpaper: {exc}") from exc

    def stop(self) -> bool:
        return run(["pkill", "-x", "mpvpaper"]).returncode == 0

    def is_running(self) -> bool:
        return run(["pgrep", "-x", "mpvpaper"]).returncode == 0
