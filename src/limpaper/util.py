"""Process helpers shared by the backends, thumbnails and theming."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .config import IS_WINDOWS

# Keep console windows from flashing up when the GUI spawns tools on Windows
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0


def run(cmd: list[str], timeout: float = 60, **kw) -> subprocess.CompletedProcess:
    """Run a command quietly, capturing its output as text. Never raises."""
    try:
        return subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=NO_WINDOW,
            **kw,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def which(name: str) -> str | None:
    return shutil.which(name)


def app_dir() -> Path:
    """Folder of the running executable (PyInstaller) or of the package."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def open_in_file_manager(path: Path) -> None:
    """Reveal a file, or open a folder, in the platform file manager."""
    if IS_WINDOWS:
        if path.is_file():
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            subprocess.Popen(["explorer", str(path)])
        return
    target = path.parent if path.is_file() else path
    opener = which("xdg-open") or which("gio")
    if opener:
        args = [opener, "open", str(target)] if opener.endswith("gio") else [opener, str(target)]
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
