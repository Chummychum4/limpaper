"""Parsers are tested against trimmed copies of each site's markup."""

from limpaper.sources import SOURCES, moewalls, motionbgs, wallhaven
from limpaper.sources.base import OnlineWallpaper

MOTIONBGS_HTML = """
<div class=tmb><a title="A Galaxy Within live wallpaper" href=/a-galaxy-within> <figure><picture>
<source srcset=/i/c/364x205/media/10270/a-galaxy-within.3840x2160.jpg type=image/jpeg>
<img alt="a galaxy within live wallpaper" height=205 src=/i/c/364x205/media/10270/a-galaxy-within.3840x2160.jpg width=364>
</picture></figure> <span class=ttl>A Galaxy Within</span> <span class=frm> 4K </span> </a>
<a title="Tall Phone animated wallpaper" href=/tall-phone><img src=/i/c/205x364/media/1/tall.1080x1920.jpg></a>
<a title="Lich King Winter&#8217;s Wrath live wallpaper" href=/lich-king><img height=205
src=/i/c/364x205/media/10208/lich-king.3840x2160.jpg width=364></a>
<a href=/2/>next</a>
"""

MOEWALLS_HTML = """
<article class="entry-tpl-grid entry-tpl-grid-m g1-card post-21558 post type-post resolutions-3840x2160">
<div class="entry-featured-media"><a title="Crimson Blackhole Abyss Live Wallpaper" class="g1-frame"
href="https://moewalls.com/sci-fi/crimson-blackhole-abyss-live-wallpaper/"><div class="g1-frame-inner">
<img width="364" height="205" src="https://moewalls.com/wp-content/uploads/2026/10/crimson-thumb-364x205.jpg" class="x" alt="" />
</div></a></div>
<div class="entry-resolutions"><a href="https://moewalls.com/resolution/3840x2160/" rel="tag">3840x2160</a></div>
<h3 class="g1-gamma g1-gamma-1st entry-title"><a href="https://moewalls.com/sci-fi/crimson-blackhole-abyss-live-wallpaper/" rel="bookmark">Crimson Blackhole Abyss Live Wallpaper</a></h3>
</article>
<a href="https://moewalls.com/page/2/">2</a>
"""

MOEWALLS_DETAIL = """
<video id="player" poster="/x.jpg"><source src="/wp-content/uploads/preview/2026/crimson-preview.webm" type="video/webm"></video>
<a id="moe-download" data-id ="21558" data-url="VJJr%2BIh%3D" rel="nofollow" class="g1-button lcc-wall" href="#">Download</a>
"""


def test_motionbgs_parse():
    items = motionbgs.parse(MOTIONBGS_HTML)
    assert [i.title for i in items] == ["A Galaxy Within", "Lich King Winter’s Wrath"]
    first = items[0]
    assert first.id == "10270"
    assert first.page_url == "https://motionbgs.com/a-galaxy-within"
    assert first.preview_url == "https://motionbgs.com/media/10270/a-galaxy-within.960x540.mp4"
    assert first.download_url == "https://motionbgs.com/dl/hd/10270/"
    assert first.thumb_url.startswith("https://motionbgs.com/i/c/546x308/media/10270/")


def test_motionbgs_paging(monkeypatch):
    monkeypatch.setattr(motionbgs, "get_text", lambda url: MOTIONBGS_HTML)
    page = SOURCES["motionbgs"].browse(1)
    assert page.has_more and len(page.items) == 2
    assert SOURCES["motionbgs"].search("rain", 2).items == []


def test_moewalls_parse_and_resolve(monkeypatch):
    items = moewalls.parse(MOEWALLS_HTML)
    assert len(items) == 1
    it = items[0]
    assert it.title == "Crimson Blackhole Abyss"
    assert it.resolution == "3840x2160"
    assert it.thumb_url.endswith("crimson-thumb-728x410.jpg")
    assert it.download_url == ""
    monkeypatch.setattr(moewalls, "get_text", lambda url: MOEWALLS_DETAIL)
    SOURCES["moewalls"].resolve(it)
    assert it.download_url == "https://go.moewalls.com/download.php?video=VJJr%2BIh%3D"
    assert it.preview_url == "https://moewalls.com/wp-content/uploads/preview/2026/crimson-preview.webm"


def test_wallhaven_parse():
    data = {
        "data": [{"id": "abc123", "url": "https://wallhaven.cc/w/abc123", "resolution": "3840x2160",
                  "path": "https://w.wallhaven.cc/full/ab/wallhaven-abc123.jpg",
                  "thumbs": {"large": "https://th.wallhaven.cc/lg/ab/abc123.jpg"}}],
        "meta": {"current_page": 1, "last_page": 3},
    }
    page = wallhaven.parse(data)
    assert page.has_more
    assert page.items[0].kind == "image"
    assert page.items[0].download_url.endswith("wallhaven-abc123.jpg")


def test_wallhaven_safe_search(monkeypatch):
    seen = []
    monkeypatch.setattr(wallhaven, "get_json", lambda url: seen.append(url) or {"data": [], "meta": {}})
    SOURCES["wallhaven"].search("forest", 1, safe=True)
    SOURCES["wallhaven"].search("forest", 1, safe=False)
    assert "purity=100" in seen[0] and "purity=110" in seen[1]


def test_allowed_hosts():
    mb = SOURCES["motionbgs"]
    assert mb.allows_host("motionbgs.com")
    assert mb.allows_host("cdn.motionbgs.com")
    assert not mb.allows_host("evilmotionbgs.com")
    assert not mb.allows_host("motionbgs.com.evil.net")
    assert SOURCES["moewalls"].allows_host("go.moewalls.com")
    assert SOURCES["wallhaven"].allows_host("w.wallhaven.cc")


def test_every_source_is_described():
    for s in SOURCES.values():
        assert s.name and s.homepage.startswith("https://") and s.download_hosts
        assert isinstance(OnlineWallpaper(s.id, "1", "t", "p", "t"), OnlineWallpaper)
