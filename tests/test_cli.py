from limpaper import cli


def test_list(library, capsys):
    assert cli.main(["-l"]) == 0
    out = capsys.readouterr().out
    assert "abstract (2)" in out and "night/city_rain.mp4" in out


def test_current_none(library, capsys):
    assert cli.main(["-c"]) == 0
    assert capsys.readouterr().out.strip() == "none"


def test_add(library, tmp_path, capsys):
    f = tmp_path / "x.webm"
    f.write_bytes(b"x")
    assert cli.main(["add", str(f), "-c", "new"]) == 0
    assert (library / "new" / "x.webm").exists()


def test_apply_without_backend(library, monkeypatch, capsys):
    from limpaper.backends import BackendError
    from limpaper.backends.mpvpaper import MpvpaperBackend

    def boom(self, path):
        raise BackendError("mpvpaper is not installed.")

    monkeypatch.setattr(MpvpaperBackend, "apply", boom)
    import limpaper.backends.windows as win
    monkeypatch.setattr(win.WindowsBackend, "apply", boom)
    assert cli.main(["apply", "neon grid"]) == 1
    assert "not installed" in capsys.readouterr().err


def test_apply_records_current(library, monkeypatch, capsys):
    import limpaper.backends.windows as win
    from limpaper.backends.mpvpaper import MpvpaperBackend

    calls = []
    monkeypatch.setattr(MpvpaperBackend, "apply", lambda self, p: calls.append(p))
    monkeypatch.setattr(win.WindowsBackend, "apply", lambda self, p: calls.append(p))
    assert cli.main(["apply", "neon grid"]) == 0
    assert calls and calls[0].name == "neon-grid.1920x1080.mp4"
    cli.main(["current"])
    assert "neon-grid" in capsys.readouterr().out


def test_sources_lists_warning(capsys):
    assert cli.main(["sources"]) == 0
    out = capsys.readouterr().out
    assert "MotionBGs" in out and "malicious" in out


def test_mpv_args():
    from limpaper.backends.base import mpv_args

    assert mpv_args("no-audio loop panscan=1.0") == ["--no-audio", "--loop", "--panscan=1.0"]


def test_mpvpaper_command(tmp_path, monkeypatch):
    from limpaper.backends import mpvpaper
    from limpaper.config import Settings

    calls = []
    monkeypatch.setattr(mpvpaper, "which", lambda name: "/usr/bin/mpvpaper")
    monkeypatch.setattr(mpvpaper, "run", lambda cmd, **kw: calls.append(cmd) or type("R", (), {"returncode": 1})())
    monkeypatch.setattr(mpvpaper.time, "sleep", lambda s: None)
    monkeypatch.setattr(mpvpaper.subprocess, "Popen", lambda cmd, **kw: calls.append(cmd))
    video, still = tmp_path / "a.mp4", tmp_path / "b.png"
    video.write_bytes(b"x")
    still.write_bytes(b"x")
    backend = mpvpaper.MpvpaperBackend(Settings(output="DP-1", mpv_opts="no-audio loop"))
    backend.apply(video)
    assert calls[0] == ["pkill", "-x", "mpvpaper"]
    assert calls[1] == ["mpvpaper", "-f", "-o", "no-audio loop", "DP-1", str(video)]
    backend.apply(still)
    assert calls[-1][3] == "no-audio loop image-display-duration=inf"
