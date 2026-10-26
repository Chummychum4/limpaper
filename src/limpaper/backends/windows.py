"""Windows: mpv rendered into the desktop's WorkerW window, behind the icons.

Explorer creates a WorkerW window between the wallpaper and the desktop icons
when Progman receives the undocumented 0x052C message. mpv is then told to draw
into that window with --wid. This is the same technique Lively Wallpaper and
weebp use. Still images go through the regular Windows wallpaper setting.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

from ..config import Settings, state_dir
from ..library import is_image
from ..util import app_dir, which
from .base import Backend, BackendError, mpv_args

SPI_GETDESKWALLPAPER = 0x0073
SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02
SMTO_NORMAL = 0x0000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


def _user32():
    u = ctypes.WinDLL("user32", use_last_error=True)
    u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    u.FindWindowW.restype = wintypes.HWND
    u.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    u.FindWindowExW.restype = wintypes.HWND
    u.SendMessageTimeoutW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
    ]
    u.SendMessageTimeoutW.restype = ctypes.c_size_t
    u.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
    u.SystemParametersInfoW.restype = wintypes.BOOL
    return u


def find_workerw() -> int:
    """HWND of the window that sits between the wallpaper and the icons."""
    user32 = _user32()
    progman = user32.FindWindowW("Progman", None)
    if not progman:
        raise BackendError("Could not find the desktop window (Progman).")

    result = ctypes.c_size_t()
    # Ask Explorer to spawn the WorkerW (both argument forms are seen in the wild)
    user32.SendMessageTimeoutW(progman, 0x052C, 0xD, 0x1, SMTO_NORMAL, 1000, ctypes.byref(result))
    user32.SendMessageTimeoutW(progman, 0x052C, 0, 0, SMTO_NORMAL, 1000, ctypes.byref(result))

    # Windows 11 24H2 and later: the WorkerW is a child of Progman, behind the icons
    workerw = user32.FindWindowExW(progman, None, "WorkerW", None)

    if not workerw:
        # Earlier versions: it is the top-level sibling right after the icons' host
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd, _lparam):
            nonlocal workerw
            if user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
                workerw = user32.FindWindowExW(None, hwnd, "WorkerW", None)
            return True

        user32.EnumWindows(enum_proc(callback), 0)
    if not workerw:
        raise BackendError("Could not find the desktop WorkerW window.")
    return int(workerw)


def _process_image(pid: int) -> str:
    """Executable path of a running process, or "" if it is gone."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def locate_mpv(settings: Settings) -> str | None:
    candidates = [settings.mpv_path] if settings.mpv_path else []
    here = app_dir()
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    candidates += [
        str(here / "mpv" / "mpv.exe"),
        str(here / "mpv.exe"),
        which("mpv") or "",
        str(local / "limpaper" / "mpv" / "mpv.exe"),
        str(Path.home() / "scoop" / "apps" / "mpv" / "current" / "mpv.exe"),
        str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "mpv" / "mpv.exe"),
        str(local / "Programs" / "mpv" / "mpv.exe"),
    ]
    for c in candidates:
        if c and Path(c).is_file():
            # PATH may resolve to mpv.com, the console wrapper; launch the GUI binary
            exe = Path(c).with_suffix(".exe")
            return str(exe) if exe.is_file() else c
    return None


class WindowsBackend(Backend):
    name = "windows"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.pid_file = state_dir() / "mpv.pid"

    def available(self) -> tuple[bool, str]:
        if not locate_mpv(self.settings):
            return False, (
                "mpv was not found. The Windows download bundles it; otherwise install it "
                "(e.g. `winget install mpv` or `scoop install mpv`) or set its path in Settings."
            )
        return True, ""

    # ── Static images: the native wallpaper setting ──────────────────────────
    def _set_system_wallpaper(self, path: str | None) -> None:
        user32 = _user32()
        buf = ctypes.create_unicode_buffer(path) if path else None
        user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, buf, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
        )

    def _get_system_wallpaper(self) -> str:
        user32 = _user32()
        buf = ctypes.create_unicode_buffer(1024)
        user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, len(buf), buf, 0)
        return buf.value

    # ── Video ────────────────────────────────────────────────────────────────
    def apply(self, path: Path) -> None:
        if not path.is_file():
            raise BackendError(f"File no longer exists: {path}")
        self.stop()

        if is_image(path):
            self._set_system_wallpaper(str(path.resolve()))
            return

        mpv = locate_mpv(self.settings)
        if not mpv:
            raise BackendError(self.available()[1])
        time.sleep(0.2)
        hwnd = find_workerw()
        cmd = [
            mpv,
            f"--wid={hwnd}",
            "--title=limpaper-wallpaper",
            "--no-osc",
            "--osd-level=0",
            "--no-input-default-bindings",
            "--input-vo-keyboard=no",
            "--cursor-autohide=always",
            "--force-window=yes",
            *mpv_args(self.settings.mpv_opts),
            str(path),
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
                close_fds=True,
            )
        except OSError as exc:
            raise BackendError(f"Could not start mpv: {exc}") from exc
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(proc.pid), encoding="utf-8")

    def _pid(self) -> int | None:
        try:
            pid = int(self.pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None
        # Only ever touch the pid if it is still an mpv we started
        return pid if _process_image(pid).lower().endswith("mpv.exe") else None

    def stop(self) -> bool:
        pid = self._pid()
        if pid is None:
            return False
        try:
            os.kill(pid, 15)  # TerminateProcess on Windows
        except OSError:
            pass
        self.pid_file.unlink(missing_ok=True)
        # Repaint the desktop so the last video frame does not linger
        self._set_system_wallpaper(self._get_system_wallpaper() or None)
        return True

    def is_running(self) -> bool:
        return self._pid() is not None
