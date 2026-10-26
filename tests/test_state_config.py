import json
from pathlib import Path

from limpaper.config import Settings
from limpaper.state import State


def test_state_current_history_favorites(tmp_path):
    s = State(tmp_path / "st")
    assert s.current is None
    a, b = Path("/w/a.mp4"), Path("/w/b.mp4")
    s.set_current(a)
    s.set_current(b)
    s.set_current(a)
    assert s.current == a
    assert s.history() == [str(a), str(b)]
    assert s.toggle_favorite(a) is True
    assert s.is_favorite(a)
    s.forget(a, Path("/w/moved.mp4"))
    assert s.favorites() == {str(Path("/w/moved.mp4"))}
    assert s.current == Path("/w/moved.mp4")
    assert s.toggle_favorite(Path("/w/moved.mp4")) is False


def test_current_file_compatible_with_1x(tmp_path):
    s = State(tmp_path)
    (tmp_path / "current").write_text("/home/me/wallpapers/animated/cars/r31.mp4\n")
    assert s.current == Path("/home/me/wallpapers/animated/cars/r31.mp4")


def test_settings_roundtrip(tmp_path):
    path = tmp_path / "c.json"
    s = Settings.load(path)
    s.download_category = "fresh"
    s.save(path)
    assert Settings.load(path).download_category == "fresh"


def test_env_overrides_are_not_saved(tmp_path, monkeypatch):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"wallpaper_dir": "/from/file"}))
    monkeypatch.setenv("LIMPAPER_DIR", "/from/env")
    monkeypatch.setenv("LIMPAPER_THEME", "0")
    s = Settings.load(path)
    assert s.wallpaper_dir == "/from/env" and s.theme is False
    s.safe_search = False
    s.save(path)
    saved = json.loads(path.read_text())
    assert saved["wallpaper_dir"] == "/from/file"
    assert saved["theme"] is True
    assert saved["safe_search"] is False


def test_unknown_keys_ignored(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"bogus": 1, "output": "DP-1"}))
    assert Settings.load(path).output == "DP-1"
