"""Wallhaven (wallhaven.cc) - still wallpapers through its public API."""

from __future__ import annotations

import urllib.parse

from .base import OnlineWallpaper, Page, Source, get_json

API = "https://wallhaven.cc/api/v1/search"


def parse(data: dict) -> Page:
    items = []
    for w in data.get("data", []):
        items.append(
            OnlineWallpaper(
                source=Wallhaven.id,
                id=w["id"],
                title=f"wallhaven {w['id']}",
                page_url=w.get("url", ""),
                thumb_url=w.get("thumbs", {}).get("large", ""),
                download_url=w.get("path", ""),
                kind="image",
                resolution=w.get("resolution", ""),
            )
        )
    meta = data.get("meta", {})
    return Page(items, meta.get("current_page", 1) < meta.get("last_page", 1))


class Wallhaven(Source):
    id = "wallhaven"
    name = "Wallhaven"
    homepage = "https://wallhaven.cc"
    kind = "Still"
    description = "A huge library of still wallpapers. Uses the official API."
    download_hosts = ("wallhaven.cc",)

    def _query(self, page: int, safe: bool, **params) -> Page:
        params.update(
            categories="111",
            purity="100" if safe else "110",
            atleast="1920x1080",
            page=str(page),
        )
        return parse(get_json(API + "?" + urllib.parse.urlencode(params)))

    def browse(self, page: int = 1, safe: bool = True) -> Page:
        return self._query(page, safe, sorting="toplist", topRange="1M")

    def search(self, query: str, page: int = 1, safe: bool = True) -> Page:
        return self._query(page, safe, q=query, sorting="relevance")
