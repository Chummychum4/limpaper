"""The wallpaper library: category folders under one root.

Every non-hidden folder directly under the root is a category; anything with a
recognised extension inside it, at any depth, is a wallpaper of that category.
There is nothing to register, so folders made in a file manager show up too.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import IMAGE_EXTS, VIDEO_EXTS, WALLPAPER_EXTS

_RESOLUTION = re.compile(r"[._-]\d{3,5}x\d{3,5}$")
# Credit suffixes download sites append to file names
_SITE_SUFFIX = re.compile(r"[._-](moewalls[._-]com|motionbgs[._-]com|wallhaven)$", re.I)


def pretty(name: str) -> str:
    """Human-readable wallpaper name from a file name or relative path."""
    n = name.replace("\\", "/").rsplit("/", 1)[-1]
    stem, dot, ext = n.rpartition(".")
    if dot and ext.lower() in WALLPAPER_EXTS:
        n = stem
    n = _SITE_SUFFIX.sub("", n)
    n = _RESOLUTION.sub("", n)
    n = re.sub(r"[-_]+", " ", n).strip()
    return n or name


def ext_of(path: Path | str) -> str:
    return str(path).rsplit(".", 1)[-1].lower() if "." in str(path) else ""


def is_wallpaper_file(path: Path | str) -> bool:
    return ext_of(path) in WALLPAPER_EXTS and not Path(path).name.startswith(".")


def is_video(path: Path | str) -> bool:
    return ext_of(path) in VIDEO_EXTS


def is_image(path: Path | str) -> bool:
    return ext_of(path) in IMAGE_EXTS


@dataclass(frozen=True)
class Wallpaper:
    path: Path
    category: str
    # Path relative to the category folder, with forward slashes
    rel: str

    @property
    def name(self) -> str:
        return pretty(self.rel)

    @property
    def subfolder(self) -> str:
        return self.rel.rsplit("/", 1)[0] if "/" in self.rel else ""

    @property
    def is_video(self) -> bool:
        return is_video(self.path)

    @property
    def kind(self) -> str:
        return "video" if self.is_video else "image"


class LibraryError(Exception):
    pass


def clean_category(name: str) -> str:
    """Validate a category name typed by a user; returns the cleaned name."""
    name = name.strip()
    if not name or name in (".", "..") or name.startswith("."):
        raise LibraryError("Category names cannot be empty or start with a dot.")
    if re.search(r'[/\\:*?"<>|\x00-\x1f]', name):
        raise LibraryError('Category names cannot contain / \\ : * ? " < > |')
    return name


def _unique(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    i = 2
    while True:
        candidate = dest.with_name(f"{stem} ({i}){suffix}")
        if not candidate.exists():
            return candidate
        i += 1


class Library:
    def __init__(self, root: Path | str):
        self.root = Path(root).expanduser()

    def exists(self) -> bool:
        return self.root.is_dir()

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    # ── Discovery ────────────────────────────────────────────────────────────
    def categories(self) -> list[str]:
        try:
            entries = list(os.scandir(self.root))
        except OSError:
            return []
        return sorted(
            (e.name for e in entries if not e.name.startswith(".") and e.is_dir()),
            key=str.casefold,
        )

    def _walk(self, category: str) -> Iterable[str]:
        base = self.root / category
        seen: set[str] = set()
        for dirpath, dirnames, filenames in os.walk(base, followlinks=True):
            real = os.path.realpath(dirpath)
            if real in seen:  # symlink loop
                dirnames[:] = []
                continue
            seen.add(real)
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            rel_dir = os.path.relpath(dirpath, base).replace(os.sep, "/")
            for f in filenames:
                if is_wallpaper_file(f):
                    yield f if rel_dir == "." else f"{rel_dir}/{f}"

    def wallpapers(self, category: str | None = None) -> list[Wallpaper]:
        """Wallpapers of one category, or of every category when None.

        Loose files come before sub-folders, alphabetical within each depth,
        which keeps the numbering of 1.x menus.
        """
        cats = self.categories() if category is None else [category]
        out: list[Wallpaper] = []
        for cat in cats:
            rels = sorted(self._walk(cat), key=lambda r: (r.count("/"), r.casefold()))
            out.extend(Wallpaper(self.root / cat / r, cat, r) for r in rels)
        return out

    def count(self, category: str) -> int:
        return sum(1 for _ in self._walk(category))

    def find(self, query: str) -> Wallpaper | None:
        """Resolve a path, "category/name" or a (partial) name to a wallpaper."""
        p = Path(query).expanduser()
        if p.is_file():
            try:
                rel = p.resolve().relative_to(self.root.resolve())
                cat, _, rest = rel.as_posix().partition("/")
                return Wallpaper(p, cat, rest)
            except ValueError:
                return Wallpaper(p, "", p.name)
        q = query.casefold()
        everything = self.wallpapers()
        for w in everything:
            if f"{w.category}/{w.rel}".casefold() == q or w.name.casefold() == q:
                return w
        matches = [w for w in everything if q in w.name.casefold()]
        return matches[0] if len(matches) == 1 else None

    # ── Changes ──────────────────────────────────────────────────────────────
    def create_category(self, name: str) -> str:
        name = clean_category(name)
        self.ensure()
        (self.root / name).mkdir(exist_ok=True)
        return name

    def rename_category(self, old: str, new: str) -> str:
        new = clean_category(new)
        if (self.root / new).exists():
            raise LibraryError(f'A category called "{new}" already exists.')
        (self.root / old).rename(self.root / new)
        return new

    def delete_category(self, name: str) -> None:
        """Remove a category; refuses while it still holds wallpapers."""
        if self.count(name):
            raise LibraryError(f'"{name}" still has wallpapers in it.')
        shutil.rmtree(self.root / name)

    def add(self, files: Iterable[Path | str], category: str, move: bool = False) -> list[Path]:
        """Copy (or move) files into a category, skipping unsupported formats."""
        sources = [Path(f).expanduser() for f in files]
        sources = [s for s in sources if s.is_file() and is_wallpaper_file(s)]
        if not sources:
            return []
        category = self.create_category(category)
        added = []
        for src in sources:
            dest = _unique(self.root / category / src.name)
            if move:
                shutil.move(str(src), dest)
            else:
                shutil.copy2(src, dest)
            added.append(dest)
        return added

    def move(self, wallpaper: Wallpaper, category: str) -> Path:
        category = self.create_category(category)
        dest = _unique(self.root / category / wallpaper.path.name)
        shutil.move(str(wallpaper.path), dest)
        return dest

    def delete(self, wallpaper: Wallpaper) -> None:
        wallpaper.path.unlink()
