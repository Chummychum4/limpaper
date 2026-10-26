"""Restore the last wallpaper at login.

Windows: a value under HKCU\\...\\Run. Linux: an XDG autostart entry, which most
desktops and session managers honour. Hyprland and Sway ignore XDG autostart
unless a helper runs it, so the README also shows the exec-once line.
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys
from pathlib import Path

from .config import IS_WINDOWS

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "limpaper"


def restore_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "restore"]
    exe = shutil.which("limpaper")
    if exe:
        return [exe, "restore"]
    python = sys.executable
    if IS_WINDOWS and python.lower().endswith("python.exe"):
        python = python[: -len("python.exe")] + "pythonw.exe"
    return [python, "-m", "limpaper", "restore"]


def _desktop_file() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "autostart" / "limpaper-restore.desktop"


def is_enabled() -> bool:
    if IS_WINDOWS:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, VALUE)
            return True
        except OSError:
            return False
    return _desktop_file().is_file()


def set_enabled(on: bool) -> None:
    cmd = restore_command()
    if IS_WINDOWS:
        import subprocess
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, VALUE, 0, winreg.REG_SZ, subprocess.list2cmdline(cmd))
            else:
                try:
                    winreg.DeleteValue(key, VALUE)
                except OSError:
                    pass
        return
    path = _desktop_file()
    if not on:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=limpaper (restore wallpaper)\n"
        f"Exec={shlex.join(cmd)}\n"
        "NoDisplay=true\n"
        "X-GNOME-Autostart-enabled=true\n",
        encoding="utf-8",
    )
