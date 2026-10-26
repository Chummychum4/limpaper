"""MoeWalls (moewalls.com) - live wallpapers, mostly anime and games."""

from __future__ import annotations

import html
import re
import urllib.parse

from .base import OnlineWallpaper, Page, Source, SourceError, get_text

BASE = "https://moewalls.com"
DOWNLOAD = "https://go.moewalls.com/download.php?video="

_ARTICLE = re.compile(r'<article class="entry-tpl-grid[^"]*\bpost-(?P<id>\d+)\b[^"]*">(?P<body>.*?)</article>', re.S)
_TITLE = re.compile(r'entry-title"><a href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>', re.S)
_IMG = re.compile(r'<img[^>]*\ssrc="(?P<src>[^"]+)"')
_RES = re.compile(r"/resolution/(\d+x\d+)/")
_SUFFIX = re.compile(r"\s+live\s+wallpaper$", re.I)
_PREVIEW = re.compile(r'src="(?P<src>[^"]+\.(?:webm|mp4))"')
_DOWNLOAD = re.compile(r'id="moe-download"[^>]*data-url="(?P<key>[^"]+)"')


def parse(page_html: str) -> list[OnlineWallpaper]:
    items = []
    for art in _ARTICLE.finditer(page_html):
        body = art["body"]
        title = _TITLE.search(body)
        img = _IMG.search(body)
        if not title or not img:
            continue
        res = _RES.search(body)
        items.append(
            OnlineWallpaper(
                source=MoeWalls.id,
                id=art["id"],
                title=_SUFFIX.sub("", html.unescape(title["title"]).strip()),
                page_url=title["url"],
                # The grid serves 364px thumbs; the 728px size is listed in srcset
                thumb_url=img["src"].replace("-364x205.", "-728x410."),
                kind="video",
                resolution=res.group(1) if res else "",
                headers={"Referer": BASE + "/"},
            )
        )
    return items


def parse_detail(item: OnlineWallpaper, page_html: str) -> OnlineWallpaper:
    preview = _PREVIEW.search(page_html)
    if preview:
        item.preview_url = urllib.parse.urljoin(BASE, html.unescape(preview["src"]))
    key = _DOWNLOAD.search(page_html)
    if not key:
        raise SourceError("MoeWalls page has no download link (the site may have changed).")
    # The key is already URL-encoded in the page
    item.download_url = DOWNLOAD + html.unescape(key["key"])
    return item


class MoeWalls(Source):
    id = "moewalls"
    name = "MoeWalls"
    homepage = BASE
    kind = "Live"
    description = "Live wallpapers, mostly anime and games. Downloads are the original MP4."
    download_hosts = ("moewalls.com",)

    def _page(self, page: int, query: str = "") -> Page:
        path = f"{BASE}/" if page <= 1 else f"{BASE}/page/{page}/"
        if query:
            path += "?" + urllib.parse.urlencode({"s": query})
        doc = get_text(path)
        return Page(parse(doc), f"/page/{page + 1}/" in doc)

    def browse(self, page: int = 1, safe: bool = True) -> Page:
        return self._page(page)

    def search(self, query: str, page: int = 1, safe: bool = True) -> Page:
        return self._page(page, query)

    def resolve(self, item: OnlineWallpaper) -> OnlineWallpaper:
        if item.download_url:
            return item
        return parse_detail(item, get_text(item.page_url))
