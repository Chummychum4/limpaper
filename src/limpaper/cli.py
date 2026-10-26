"""Command line entry point.

`limpaper` with no arguments opens the TUI in a terminal and the GUI anywhere
else (a desktop launcher, the Windows .exe). Everything the menus can do is also
a subcommand, so keybinds and autostart lines need no interface at all.
"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

from . import __version__

# limpaper 1.x flags, still accepted
LEGACY = {
    "-l": "list", "--list": "list",
    "-r": "restore", "--restore": "restore",
    "-R": "random", "--random": "random",
    "-s": "stop", "--stop": "stop",
    "-c": "current", "--current": "current",
}

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
GREEN, YELLOW, RED, CYAN = "\033[32m", "\033[33m", "\033[31m", "\033[36m"


def _color() -> bool:
    return sys.stdout is not None and sys.stdout.isatty()


def say(text: str, color: str = "") -> None:
    if sys.stdout is None:  # windowed .exe
        return
    print(f"{color}{text}{RESET}" if color and _color() else text)


def fail(text: str) -> int:
    if sys.stderr is not None:
        msg = f"{RED}{text}{RESET}" if _color() else text
        print(msg, file=sys.stderr)
    return 1


def _app():
    from .core import Limpaper

    return Limpaper()


# ── Commands ─────────────────────────────────────────────────────────────────
def cmd_gui(_args) -> int:
    try:
        from .gui.app import run
    except ImportError as exc:
        return fail(
            f"The GUI needs PySide6 ({exc}).\n"
            "Install it with:  pip install 'limpaper[gui]'  (or re-run the installer)."
        )
    return run()


def cmd_tui(_args) -> int:
    try:
        from .tui.app import run
    except ImportError as exc:
        return fail(
            f"The TUI needs Textual ({exc}).\n"
            "Install it with:  pip install 'limpaper[tui]'  (or re-run the installer)."
        )
    return run()


def cmd_list(args) -> int:
    lp = _app()
    cats = [args.category] if args.category else lp.library.categories()
    if not lp.library.exists():
        return fail(f"Wallpaper folder not found: {lp.library.root}")
    for cat in cats:
        walls = lp.library.wallpapers(cat)
        say(f"{cat} ({len(walls)})", BOLD)
        for w in walls:
            say(f"  {w.rel}")
    return 0


def _apply(lp, path: Path) -> None:
    notes = lp.apply(path)
    from .library import pretty

    say(f"✓ Now playing: {pretty(str(path))}", GREEN)
    say(f"  {path}", DIM)
    for n in notes:
        say(f"  {n}", DIM)


def cmd_apply(args) -> int:
    from .backends import BackendError

    lp = _app()
    w = lp.library.find(args.target)
    if not w:
        return fail(f"No single wallpaper matches {args.target!r}. Try `limpaper list`.")
    try:
        _apply(lp, w.path)
    except BackendError as exc:
        return fail(str(exc))
    return 0


def cmd_random(args) -> int:
    from .backends import BackendError

    lp = _app()
    try:
        pick = lp.random(args.category)
    except BackendError as exc:
        return fail(str(exc))
    say(f"✓ Now playing: {pick.name}", GREEN)
    say(f"  {pick.path}", DIM)
    return 0


def cmd_restore(_args) -> int:
    from .backends import BackendError

    lp = _app()
    current = lp.current
    if not current:
        return fail("No saved wallpaper.")
    try:
        _apply(lp, current)
    except BackendError as exc:
        return fail(str(exc))
    return 0


def cmd_stop(_args) -> int:
    lp = _app()
    was_running, notes = lp.stop()
    say("✓ Wallpaper stopped." if was_running else "No wallpaper is running.",
        GREEN if was_running else YELLOW)
    for n in notes:
        say(f"  {n}", DIM)
    return 0


def cmd_current(_args) -> int:
    current = _app().current
    say(str(current) if current else "none")
    return 0


def cmd_add(args) -> int:
    from .library import LibraryError

    lp = _app()
    try:
        added = lp.library.add(args.files, args.category, move=args.move)
    except (LibraryError, OSError) as exc:
        return fail(str(exc))
    skipped = len(args.files) - len(added)
    for p in added:
        say(f"✓ {p}", GREEN)
    if skipped:
        say(f"Skipped {skipped} file(s) that are missing or not a supported format.", YELLOW)
    return 0 if added else 1


def cmd_sources(_args) -> int:
    from .sources import SOURCES, THIRD_PARTY_WARNING

    for s in SOURCES.values():
        say(f"{s.id:<10} {s.name} [{s.kind}]  {s.homepage}", BOLD)
        say(f"           {s.description}", DIM)
    say("")
    say(THIRD_PARTY_WARNING, YELLOW)
    return 0


def cmd_online(args) -> int:
    from .download import DownloadError, download
    from .sources import SOURCES, THIRD_PARTY_WARNING, SourceError
    from .util import human_size

    source = SOURCES.get(args.source)
    if not source:
        return fail(f"Unknown source {args.source!r}. Choose from: {', '.join(SOURCES)}")
    lp = _app()
    say("⚠ " + THIRD_PARTY_WARNING, YELLOW)
    say("")
    try:
        query = " ".join(args.query)
        page = source.search(query, args.page, lp.settings.safe_search) if query \
            else source.browse(args.page, lp.settings.safe_search)
    except SourceError as exc:
        return fail(str(exc))
    if not page.items:
        return fail("No results.")

    if args.get is None:
        for i, item in enumerate(page.items, 1):
            res = f"  {item.resolution}" if item.resolution else ""
            say(f"{CYAN if _color() else ''}{i:>3}{RESET if _color() else ''}  {item.title}{res}")
        cmd = " ".join(filter(None, ["limpaper online", args.source, query, "--get N"]))
        more = f"  (next page: --page {args.page + 1})" if page.has_more else ""
        say(f"\nDownload one with:  {cmd}{more}", DIM)
        return 0

    if not 1 <= args.get <= len(page.items):
        return fail(f"Pick 1-{len(page.items)}.")
    item = page.items[args.get - 1]
    category = args.category or lp.settings.download_category

    def progress(got: int, total: int) -> None:
        if sys.stdout is not None and sys.stdout.isatty():
            pct = f"{got * 100 // total:3d}%" if total else ""
            print(f"\r  downloading {human_size(got)} {pct}   ", end="", flush=True)

    try:
        path = download(item, source, lp.library, category, progress, threading.Event())
    except (DownloadError, SourceError, OSError) as exc:
        say("")
        return fail(str(exc))
    say("")
    say(f"✓ Saved {path}", GREEN)
    if args.apply:
        from .backends import BackendError

        try:
            _apply(lp, path)
        except BackendError as exc:
            return fail(str(exc))
    return 0


def cmd_doctor(_args) -> int:
    from .config import CONFIG_FILE, IS_WINDOWS
    from .util import which

    lp = _app()
    ok, why = lp.backend.available()
    rows = [
        ("version", __version__, True),
        ("config", str(CONFIG_FILE), True),
        ("wallpaper folder", str(lp.library.root), lp.library.exists()),
        (f"playback ({lp.backend.name})", "ready" if ok else why, ok),
        ("ffmpeg (thumbnails, theming)", which("ffmpeg") or "not found", bool(which("ffmpeg"))),
    ]
    if not IS_WINDOWS:
        rows.append(("caelestia (theming)", which("caelestia") or "not found", bool(which("caelestia"))))
    for mod, label in (("textual", "Textual (TUI)"), ("PySide6", "PySide6 (GUI)")):
        try:
            __import__(mod)
            rows.append((label, "installed", True))
        except ImportError:
            rows.append((label, "not installed", False))
    for name, value, good in rows:
        mark = f"{GREEN}✓{RESET}" if good else f"{YELLOW}!{RESET}"
        if not _color():
            mark = "ok" if good else "!!"
        say(f" {mark} {name:<30} {value}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="limpaper",
        description="Animated wallpaper manager. Run without arguments for the "
        "TUI (in a terminal) or the GUI.",
        epilog="1.x flags still work: -l list, -r restore, -R random, -s stop, -c current.",
    )
    p.add_argument("-V", "--version", action="version", version=f"limpaper {__version__}")
    sub = p.add_subparsers(dest="command", metavar="command")

    sub.add_parser("gui", help="open the graphical app").set_defaults(func=cmd_gui)
    sub.add_parser("tui", help="open the terminal app").set_defaults(func=cmd_tui)

    s = sub.add_parser("list", help="print categories and wallpapers")
    s.add_argument("category", nargs="?")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("apply", help="play a wallpaper by path or name")
    s.add_argument("target", help='a file path, "category/file" or part of a name')
    s.set_defaults(func=cmd_apply)

    s = sub.add_parser("random", help="play a random wallpaper")
    s.add_argument("category", nargs="?", help="limit to one category")
    s.set_defaults(func=cmd_random)

    sub.add_parser("restore", help="re-apply the last wallpaper (for autostart)").set_defaults(func=cmd_restore)
    sub.add_parser("stop", help="stop the wallpaper and restore colours").set_defaults(func=cmd_stop)
    sub.add_parser("current", help="print the current wallpaper's path").set_defaults(func=cmd_current)

    s = sub.add_parser("add", help="copy files into the library")
    s.add_argument("files", nargs="+")
    s.add_argument("-c", "--category", default="misc", help="target category (created if needed)")
    s.add_argument("-m", "--move", action="store_true", help="move instead of copy")
    s.set_defaults(func=cmd_add)

    sub.add_parser("sources", help="list online wallpaper sources").set_defaults(func=cmd_sources)

    s = sub.add_parser("online", help="browse or search an online source")
    s.add_argument("source", help="motionbgs, moewalls or wallhaven")
    s.add_argument("query", nargs="*", help="search words; omit to browse")
    s.add_argument("-p", "--page", type=int, default=1)
    s.add_argument("-g", "--get", type=int, metavar="N", help="download result N")
    s.add_argument("-c", "--category", help="category to save into")
    s.add_argument("-a", "--apply", action="store_true", help="play it after downloading")
    s.set_defaults(func=cmd_online)

    sub.add_parser("doctor", help="check dependencies and setup").set_defaults(func=cmd_doctor)
    return p


def _interactive_default() -> int:
    tty = sys.stdin is not None and sys.stdout is not None and sys.stdin.isatty() and sys.stdout.isatty()
    return cmd_tui(None) if tty else cmd_gui(None)


def _safe_streams() -> None:
    # A Windows console or pipe may not encode ✓ and ⚠; degrade instead of crashing
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _safe_streams()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in LEGACY:
        argv[0] = LEGACY[argv[0]]
    if not argv:
        return _interactive_default()
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        return _interactive_default()
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        return 130


def main_gui() -> int:
    """Entry point for launchers and the Windows .exe: GUI unless told otherwise."""
    if len(sys.argv) > 1:
        return main()
    return cmd_gui(None)
