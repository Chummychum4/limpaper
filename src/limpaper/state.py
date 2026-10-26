"""Small pieces of persistent state: current wallpaper, history, favourites."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .config import state_dir

HISTORY_LIMIT = 50


class State:
    def __init__(self, directory: Path | None = None):
        self.dir = directory or state_dir()
        # Same file name as limpaper 1.x, so --restore survives the upgrade
        self.current_file = self.dir / "current"
        self.baseline_file = self.dir / "baseline"
        self.history_file = self.dir / "history.json"
        self.favorites_file = self.dir / "favorites.json"

    def _write(self, path: Path, text: str) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    def _read_list(self, path: Path) -> list[str]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [str(x) for x in data] if isinstance(data, list) else []

    # ── Current ──────────────────────────────────────────────────────────────
    @property
    def current(self) -> Path | None:
        try:
            text = self.current_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return Path(text) if text else None

    def set_current(self, path: Path) -> None:
        self._write(self.current_file, f"{path}\n")
        history = [str(path)] + [h for h in self.history() if h != str(path)]
        self._write(self.history_file, json.dumps(history[:HISTORY_LIMIT], indent=1))

    def history(self) -> list[str]:
        return self._read_list(self.history_file)

    # ── Favourites ───────────────────────────────────────────────────────────
    def favorites(self) -> set[str]:
        return set(self._read_list(self.favorites_file))

    def is_favorite(self, path: Path) -> bool:
        return str(path) in self.favorites()

    def toggle_favorite(self, path: Path) -> bool:
        """Flip the favourite flag; returns the new value."""
        favs = self.favorites()
        key = str(path)
        now = key not in favs
        if now:
            favs.add(key)
        else:
            favs.discard(key)
        self._write(self.favorites_file, json.dumps(sorted(favs), indent=1))
        return now

    def forget(self, path: Path, new: Path | None = None) -> None:
        """Drop (or rename) a path everywhere, after a delete or move."""
        key = str(path)
        favs = self.favorites()
        if key in favs:
            favs.discard(key)
            if new:
                favs.add(str(new))
            self._write(self.favorites_file, json.dumps(sorted(favs), indent=1))
        if self.current == path and new:
            self._write(self.current_file, f"{new}\n")
