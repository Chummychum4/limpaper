"""Pick the playback backend for this platform."""

from __future__ import annotations

from ..config import IS_WINDOWS, Settings
from .base import Backend, BackendError

__all__ = ["Backend", "BackendError", "get_backend"]


def get_backend(settings: Settings) -> Backend:
    if IS_WINDOWS:
        from .windows import WindowsBackend

        return WindowsBackend(settings)
    from .mpvpaper import MpvpaperBackend

    return MpvpaperBackend(settings)
