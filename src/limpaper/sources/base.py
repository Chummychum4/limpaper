"""Online wallpaper sources: shared types and a tiny HTTP helper."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from .. import __version__

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    f"Chrome/130.0 Safari/537.36 limpaper/{__version__}"
)
TIMEOUT = 20


class SourceError(Exception):
    pass


def http_get(url: str, headers: dict | None = None, timeout: float = TIMEOUT) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # URLError, HTTPError, timeouts, SSL errors
        raise SourceError(f"Could not reach {urllib.parse.urlsplit(url).netloc}: {exc}") from exc


def get_text(url: str, headers: dict | None = None) -> str:
    return http_get(url, headers).decode("utf-8", "replace")


def get_json(url: str, headers: dict | None = None) -> dict:
    try:
        return json.loads(http_get(url, headers))
    except ValueError as exc:
        raise SourceError(f"Unexpected response from {url}") from exc


@dataclass
class OnlineWallpaper:
    source: str
    id: str
    title: str
    page_url: str
    thumb_url: str
    # Short animated clip for previews (live sources only)
    preview_url: str = ""
    # Filled in by Source.resolve() when it needs the detail page
    download_url: str = ""
    kind: str = "video"  # "video" or "image"
    resolution: str = ""
    # Extra request headers the download needs (e.g. a Referer)
    headers: dict = field(default_factory=dict)


@dataclass
class Page:
    items: list[OnlineWallpaper]
    has_more: bool


class Source:
    id = ""
    name = ""
    homepage = ""
    kind = "Live"  # shown as a badge: "Live" or "Still"
    description = ""
    # Hosts downloads may come from; anything else is refused
    download_hosts: tuple[str, ...] = ()

    def browse(self, page: int = 1, safe: bool = True) -> Page:
        """Newest or most popular wallpapers."""
        raise NotImplementedError

    def search(self, query: str, page: int = 1, safe: bool = True) -> Page:
        raise NotImplementedError

    def resolve(self, item: OnlineWallpaper) -> OnlineWallpaper:
        """Make sure download_url (and preview_url where possible) are set."""
        return item

    def allows_host(self, host: str) -> bool:
        host = host.lower()
        return any(host == h or host.endswith("." + h) for h in self.download_hosts)
