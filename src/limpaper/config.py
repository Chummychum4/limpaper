"""Paths and user settings.

Settings live in a small JSON file so the GUI, the TUI and the CLI share them.
Environment variables from limpaper 1.x still work and win over the file, so
existing keybinds and autostart lines keep behaving the same.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"

VIDEO_EXTS = ("mp4", "mkv", "webm", "gif", "mov", "avi", "m4v")
IMAGE_EXTS = ("jpg", "jpeg", "png", "webp", "bmp")
WALLPAPER_EXTS = VIDEO_EXTS + IMAGE_EXTS

DEFAULT_MPV_OPTS = "no-audio loop panscan=1.0 hwdec=auto"


def _xdg(var: str, fallback: str) -> Path:
    value = os.environ.get(var)
    return Path(value) if value else Path.home() / fallback


def config_dir() -> Path:
    if IS_WINDOWS:
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "limpaper"
    return _xdg("XDG_CONFIG_HOME", ".config") / "limpaper"


def state_dir() -> Path:
    if IS_WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "limpaper"
    return _xdg("XDG_STATE_HOME", ".local/state") / "limpaper"


def cache_dir() -> Path:
    if IS_WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "limpaper" / "cache"
    return _xdg("XDG_CACHE_HOME", ".cache") / "limpaper"


def default_wallpaper_dir() -> Path:
    if IS_WINDOWS:
        return Path.home() / "Videos" / "limpaper"
    return Path.home() / "wallpapers" / "animated"


CONFIG_FILE = config_dir() / "config.json"

# limpaper 1.x environment variables -> setting they override
_ENV_VARS = {
    "LIMPAPER_DIR": "wallpaper_dir",
    "LIMPAPER_OUTPUT": "output",
    "LIMPAPER_THEME": "theme",
    "LIMPAPER_FRAME_AT": "frame_at",
    "LIMPAPER_MPV_OPTS": "mpv_opts",
    "LIMPAPER_MPV": "mpv_path",
}


@dataclass
class Settings:
    wallpaper_dir: str = field(default_factory=lambda: str(default_wallpaper_dir()))
    # mpvpaper output name (Linux), "*" means every monitor
    output: str = "*"
    mpv_opts: str = DEFAULT_MPV_OPTS
    # Full path to mpv.exe on Windows when it is not on PATH or bundled
    mpv_path: str = ""
    # Recolour the desktop through caelestia (Linux only)
    theme: bool = True
    # Seconds into the video to sample for theming; empty = first frame
    frame_at: str = ""
    # Category that downloads from the Discover tab land in
    download_category: str = "downloads"
    # Set once the user has acknowledged the third-party content warning
    online_warning_accepted: bool = False
    # Only safe-for-work results from sources that support a filter
    safe_search: bool = True
    # Play a muted animated preview of online wallpapers in the GUI
    animated_previews: bool = True

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or CONFIG_FILE
        data: dict = {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        known = {f.name for f in fields(cls)}
        settings = cls(**{k: v for k, v in data.items() if k in known})
        settings._apply_env()
        return settings

    def _apply_env(self) -> None:
        # Remember what the file said, so saving never bakes an env override in
        self._file_values = {}
        for var, name in _ENV_VARS.items():
            value = os.environ.get(var)
            if not value:
                continue
            env_value = value != "0" if name == "theme" else value
            self._file_values[name] = (getattr(self, name), env_value)
            setattr(self, name, env_value)

    def save(self, path: Path | None = None) -> None:
        path = path or CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        for name, (file_value, env_value) in getattr(self, "_file_values", {}).items():
            # Untouched since load: keep the file's own value
            if data[name] == env_value:
                data[name] = file_value
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    @property
    def root(self) -> Path:
        return Path(os.path.expanduser(self.wallpaper_dir))
