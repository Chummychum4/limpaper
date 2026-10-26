"""Downloading wallpapers from online sources, defensively.

Third-party files can be anything, so a download is only kept when:

* it was fetched over HTTPS from a host the source is known to serve from,
* the server did not label it as a web page or a program,
* its first bytes are those of a real video or image container, and
* it is not absurdly large.

Anything else is deleted before it ever reaches the wallpaper folder. These
checks reduce the risk; they do not make third-party files safe.
"""

from __future__ import annotations

import os
import re
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from .library import Library, _unique
from .sources.base import USER_AGENT, OnlineWallpaper, Source

MAX_BYTES = 2 * 1024**3
CHUNK = 256 * 1024

ProgressFn = Callable[[int, int], None]  # (received, total or 0)


class DownloadError(Exception):
    pass


class Cancelled(DownloadError):
    pass


def sniff(head: bytes) -> str | None:
    """File extension implied by a file's first bytes, or None if unknown."""
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12]
        return "mov" if brand == b"qt  " else "mp4"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "webm" if b"webm" in head[:64] else "mkv"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return "avi"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:3] == b"\xff\xd8\xff":
        return "jpg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if head[:2] == b"BM":
        return "bmp"
    return None


_BAD_TYPES = ("text/", "application/x-msdownload", "application/x-dosexec",
              "application/zip", "application/x-msi", "application/javascript",
              "application/x-sh", "application/vnd.microsoft.portable-executable")


def _filename(resp, url: str) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.I) or re.search(r'filename="?([^";]+)"?', cd, re.I)
    name = urllib.parse.unquote(m.group(1)) if m else ""
    if not name:
        name = urllib.parse.unquote(Path(urllib.parse.urlsplit(url).path).name)
    # Never trust a server-supplied path: keep the last component only
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip(" .")
    return name or "wallpaper"


def safe_name(title: str, ext: str) -> str:
    stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", title).strip(" .")[:100] or "wallpaper"
    return f"{stem}.{ext}"


def download(
    item: OnlineWallpaper,
    source: Source,
    library: Library,
    category: str,
    progress: ProgressFn | None = None,
    cancel: threading.Event | None = None,
) -> Path:
    """Fetch an online wallpaper into a category; returns the saved path."""
    item = source.resolve(item)
    url = item.download_url
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https":
        raise DownloadError("Refusing a download that is not over HTTPS.")
    if not source.allows_host(parts.hostname or ""):
        raise DownloadError(f"Refusing a download from an unexpected host: {parts.hostname}")

    category = library.create_category(category)
    folder = library.root / category
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **item.headers})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
    except Exception as exc:
        raise DownloadError(f"Download failed: {exc}") from exc

    part = folder / f".limpaper-{item.source}-{item.id}.part"
    try:
        with resp:
            final = urllib.parse.urlsplit(resp.geturl())
            # Redirects must stay on the source's own hosts too
            if final.scheme != "https" or not source.allows_host(final.hostname or ""):
                raise DownloadError(f"Download was redirected to an unexpected host: {final.hostname}")
            ctype = resp.headers.get("Content-Type", "").lower()
            if ctype.startswith(_BAD_TYPES):
                raise DownloadError(f"The site sent {ctype.split(';')[0]} instead of a wallpaper.")
            total = int(resp.headers.get("Content-Length") or 0)
            if total > MAX_BYTES:
                raise DownloadError("File is larger than 2 GB; refusing it.")
            server_name = _filename(resp, url)

            received, head = 0, b""
            with open(part, "wb") as fh:
                while True:
                    if cancel is not None and cancel.is_set():
                        raise Cancelled("Download cancelled.")
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    if not head:
                        head = chunk[:64]
                        if sniff(head) is None:
                            raise DownloadError("The file is not a recognised video or image; it was discarded.")
                    fh.write(chunk)
                    received += len(chunk)
                    if received > MAX_BYTES:
                        raise DownloadError("File is larger than 2 GB; refusing it.")
                    if progress:
                        progress(received, total)
            if total and received < total:
                raise DownloadError("Download ended early; try again.")

        ext = sniff(head)
        if ext is None:
            raise DownloadError("Empty download.")
        title = item.title if item.kind == "video" else Path(server_name).stem
        dest = _unique(folder / safe_name(title, ext))
        os.replace(part, dest)
        return dest
    except BaseException:
        part.unlink(missing_ok=True)
        raise
