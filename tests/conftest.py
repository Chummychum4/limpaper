import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Keep every test away from the real config, state, cache and wallpapers."""
    for var in ("LIMPAPER_DIR", "LIMPAPER_OUTPUT", "LIMPAPER_THEME", "LIMPAPER_FRAME_AT",
                "LIMPAPER_MPV_OPTS", "LIMPAPER_MPV"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    import limpaper.config as config

    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config" / "limpaper" / "config.json")
    yield tmp_path


@pytest.fixture
def library(tmp_path, monkeypatch):
    root = tmp_path / "walls"
    for rel in ("abstract/neon-grid.1920x1080.mp4", "abstract/b.webm", "cars/r31.mkv",
                "scenery/night/city_rain.mp4", "scenery/sunset.png", "scenery/notes.txt",
                "scenery/.hidden.mp4", ".trash/x.mp4"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    monkeypatch.setenv("LIMPAPER_DIR", str(root))
    return root
