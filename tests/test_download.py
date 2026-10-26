import io
import threading

import pytest

from limpaper import download as dl
from limpaper.download import Cancelled, DownloadError, download, safe_name, sniff
from limpaper.library import Library
from limpaper.sources import SOURCES
from limpaper.sources.base import OnlineWallpaper

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 20 + b"webm" + b"\x00" * 100


def test_sniff():
    assert sniff(MP4) == "mp4"
    assert sniff(b"\x00\x00\x00\x14ftypqt  ") == "mov"
    assert sniff(WEBM) == "webm"
    assert sniff(b"\x1a\x45\xdf\xa3" + b"\x00" * 60) == "mkv"
    assert sniff(b"GIF89a....") == "gif"
    assert sniff(b"\xff\xd8\xff\xe0") == "jpg"
    assert sniff(b"\x89PNG\r\n\x1a\n") == "png"
    assert sniff(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert sniff(b"MZ\x90\x00") is None
    assert sniff(b"PK\x03\x04") is None
    assert sniff(b"<!DOCTYPE html>") is None


def test_safe_name():
    assert safe_name('a/b\\c:d*?"<>|', "mp4") == "abcd.mp4"
    assert safe_name("...", "png") == "wallpaper.png"


class FakeResponse(io.BytesIO):
    def __init__(self, body, url, headers):
        super().__init__(body)
        self._url, self.headers = url, headers

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def fake_urlopen(body, final_url=None, ctype="video/mp4", disposition=""):
    def opener(req, timeout=None):
        headers = {"Content-Type": ctype, "Content-Length": str(len(body))}
        if disposition:
            headers["Content-Disposition"] = disposition
        return FakeResponse(body, final_url or req.full_url, headers)
    return opener


def item(url="https://motionbgs.com/dl/hd/1/", title="Neon Rain"):
    return OnlineWallpaper("motionbgs", "1", title, "https://motionbgs.com/x", "", download_url=url)


@pytest.fixture
def lib(tmp_path):
    return Library(tmp_path / "walls")


def test_download_ok(lib, monkeypatch):
    monkeypatch.setattr(dl.urllib.request, "urlopen", fake_urlopen(MP4))
    seen = []
    path = download(item(), SOURCES["motionbgs"], lib, "downloads", lambda a, b: seen.append((a, b)))
    assert path.name == "Neon Rain.mp4" and path.read_bytes() == MP4
    assert seen[-1] == (len(MP4), len(MP4))
    assert not list(path.parent.glob("*.part"))


def test_extension_follows_content(lib, monkeypatch):
    monkeypatch.setattr(dl.urllib.request, "urlopen", fake_urlopen(WEBM))
    assert download(item(), SOURCES["motionbgs"], lib, "d").suffix == ".webm"


@pytest.mark.parametrize("body,ctype", [
    (b"MZ\x90\x00" + b"\x00" * 100, "application/octet-stream"),   # a Windows program
    (b"PK\x03\x04" + b"\x00" * 100, "application/octet-stream"),   # an archive
    (MP4, "text/html"),                                            # labelled as a page
    (MP4, "application/x-msdownload"),
])
def test_rejects_non_media(lib, monkeypatch, body, ctype):
    monkeypatch.setattr(dl.urllib.request, "urlopen", fake_urlopen(body, ctype=ctype))
    with pytest.raises(DownloadError):
        download(item(), SOURCES["motionbgs"], lib, "downloads")
    assert not [p for p in (lib.root / "downloads").iterdir()]


def test_rejects_http_and_foreign_hosts(lib, monkeypatch):
    monkeypatch.setattr(dl.urllib.request, "urlopen", fake_urlopen(MP4))
    with pytest.raises(DownloadError, match="HTTPS"):
        download(item("http://motionbgs.com/dl/hd/1/"), SOURCES["motionbgs"], lib, "d")
    with pytest.raises(DownloadError, match="unexpected host"):
        download(item("https://evil.example/x.mp4"), SOURCES["motionbgs"], lib, "d")


def test_rejects_redirect_elsewhere(lib, monkeypatch):
    monkeypatch.setattr(dl.urllib.request, "urlopen", fake_urlopen(MP4, final_url="https://evil.example/a.mp4"))
    with pytest.raises(DownloadError, match="redirected"):
        download(item(), SOURCES["motionbgs"], lib, "d")


def test_cancel_cleans_up(lib, monkeypatch):
    monkeypatch.setattr(dl, "CHUNK", 16)
    monkeypatch.setattr(dl.urllib.request, "urlopen", fake_urlopen(MP4))
    ev = threading.Event()
    with pytest.raises(Cancelled):
        download(item(), SOURCES["motionbgs"], lib, "d", lambda a, b: ev.set(), ev)
    assert list((lib.root / "d").iterdir()) == []


def test_still_named_after_server_file(lib, monkeypatch):
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    monkeypatch.setattr(dl.urllib.request, "urlopen",
                        fake_urlopen(png, ctype="image/png", disposition='attachment; filename="../../wallhaven-abc.png"'))
    it = OnlineWallpaper("wallhaven", "abc", "wallhaven abc", "", "", kind="image",
                         download_url="https://w.wallhaven.cc/full/ab/wallhaven-abc.png")
    path = download(it, SOURCES["wallhaven"], lib, "stills")
    assert path.name == "wallhaven-abc.png" and path.parent == lib.root / "stills"
