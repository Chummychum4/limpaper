"""MotionBGs (motionbgs.com) - live wallpapers, mostly games and anime."""

from __future__ import annotations

import html
import re
import urllib.parse

from .base import OnlineWallpaper, Page, Source, get_text

BASE = "https://motionbgs.com"

_CARD = re.compile(r'<a title="(?P<title>[^"]*)" href=/(?P<slug>[^ >]+)>(?P<body>.*?)</a>', re.S)
_THUMB = re.compile(
    r"src=/i/c/(?P<size>\d+x\d+)/media/(?P<id>\d+)/(?P<file>[^ >/]+?)\.(?P<res>\d+x\d+)\.jpg"
)
_NAME = re.compile(r"<span class=ttl>(.*?)</span>", re.S)
_SUFFIX = re.compile(r"\s+(live|animated)\s+wallpaper$", re.I)


def parse(page_html: str) -> list[OnlineWallpaper]:
    items, seen = [], set()
    for card in _CARD.finditer(page_html):
        thumb = _THUMB.search(card["body"])
        if not thumb or thumb["id"] in seen:
            continue
        w, h = (int(x) for x in thumb["size"].split("x"))
        if h > w:  # phone wallpapers share the listing pages
            continue
        seen.add(thumb["id"])
        name = _NAME.search(card["body"])
        title = html.unescape(name.group(1).strip() if name else _SUFFIX.sub("", card["title"]))
        mid, file = thumb["id"], thumb["file"]
        items.append(
            OnlineWallpaper(
                source=MotionBGs.id,
                id=mid,
                title=title,
                page_url=f"{BASE}/{card['slug']}",
                thumb_url=f"{BASE}/i/c/546x308/media/{mid}/{file}.{thumb['res']}.jpg",
                preview_url=f"{BASE}/media/{mid}/{file}.960x540.mp4",
                download_url=f"{BASE}/dl/hd/{mid}/",
                kind="video",
                resolution="1920x1080",
            )
        )
    return items


class MotionBGs(Source):
    id = "motionbgs"
    name = "MotionBGs"
    homepage = BASE
    kind = "Live"
    description = "Live wallpapers from games, anime and films. Downloads are 1080p MP4."
    download_hosts = ("motionbgs.com",)

    def browse(self, page: int = 1, safe: bool = True) -> Page:
        url = f"{BASE}/" if page <= 1 else f"{BASE}/{page}/"
        doc = get_text(url)
        return Page(parse(doc), f"href=/{page + 1}/" in doc)

    def search(self, query: str, page: int = 1, safe: bool = True) -> Page:
        if page > 1:  # the site returns a single page of matches
            return Page([], False)
        doc = get_text(f"{BASE}/search?" + urllib.parse.urlencode({"q": query}))
        return Page(parse(doc), False)
