"""What every playback backend provides."""

from __future__ import annotations

import shlex
from pathlib import Path


class BackendError(Exception):
    pass


class Backend:
    name = "backend"

    def available(self) -> tuple[bool, str]:
        """(usable, human-readable reason when it is not)."""
        raise NotImplementedError

    def apply(self, path: Path) -> None:
        """Show a wallpaper, replacing whatever is playing. Raises BackendError."""
        raise NotImplementedError

    def stop(self) -> bool:
        """Stop the wallpaper; returns whether one was running."""
        raise NotImplementedError

    def is_running(self) -> bool:
        raise NotImplementedError


def mpv_args(opts: str) -> list[str]:
    """Turn "no-audio loop panscan=1.0" into ["--no-audio", "--loop", ...]."""
    args = []
    for opt in shlex.split(opts):
        args.append(opt if opt.startswith("--") else f"--{opt}")
    return args
