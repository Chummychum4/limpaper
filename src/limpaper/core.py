"""One object the CLI, TUI and GUI all drive."""

from __future__ import annotations

import random
from pathlib import Path

from . import theming
from .backends import BackendError, get_backend
from .config import IS_WINDOWS, Settings
from .library import Library, Wallpaper, is_image
from .state import State
from .util import which


class Limpaper:
    def __init__(self, settings: Settings | None = None, state: State | None = None):
        self.settings = settings or Settings.load()
        self.state = state or State()
        self.reload()

    def reload(self) -> None:
        """Pick up changed settings (wallpaper folder, mpv path, ...)."""
        self.library = Library(self.settings.root)
        self.backend = get_backend(self.settings)

    def save_settings(self) -> None:
        self.settings.save()
        self.reload()

    # ── Playback ─────────────────────────────────────────────────────────────
    def apply(self, path: Path) -> list[str]:
        """Play a wallpaper; returns status lines. Raises BackendError."""
        path = Path(path)
        self.backend.apply(path)
        self.state.set_current(path)
        notes = []
        summary = theming.apply(path, self.settings, self.state)
        if summary:
            notes.append(summary)
        return notes

    def stop(self) -> tuple[bool, list[str]]:
        was_running = self.backend.stop()
        notes = []
        # The current file is kept so restore still works after a stop
        summary = theming.restore(self.settings, self.state)
        if summary:
            notes.append(summary)
        return was_running, notes

    def restore(self) -> Path:
        current = self.state.current
        if not current:
            raise BackendError("No saved wallpaper.")
        self.apply(current)
        return current

    def random(self, category: str | None = None) -> Wallpaper:
        pool = self.library.wallpapers(category)
        if not pool:
            where = f'"{category}"' if category else str(self.library.root)
            raise BackendError(f"No wallpapers found in {where}.")
        current = self.state.current
        choices = [w for w in pool if w.path != current] or pool
        pick = random.choice(choices)
        self.apply(pick.path)
        return pick

    def mpv_binary(self) -> str | None:
        """mpv, for grabbing thumbnails when ffmpeg is missing."""
        if IS_WINDOWS:
            from .backends.windows import locate_mpv

            return locate_mpv(self.settings)
        return which("mpv")

    @property
    def current(self) -> Path | None:
        return self.state.current

    def is_active(self) -> bool:
        if self.backend.is_running():
            return True
        # Windows shows stills through its own wallpaper setting, not mpv
        current = self.state.current
        return IS_WINDOWS and current is not None and is_image(current)
