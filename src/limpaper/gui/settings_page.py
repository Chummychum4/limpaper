"""Settings page."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, autostart
from ..config import DEFAULT_MPV_OPTS, IS_WINDOWS
from ..util import open_in_file_manager, which
from . import style


def _card(title: str, subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(22, 18, 22, 20)
    lay.setSpacing(12)
    t = QLabel(title)
    t.setObjectName("cardTitle")
    lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("muted")
        s.setWordWrap(True)
        lay.addWidget(s)
    return card, lay


class SettingsPage(QWidget):
    toast = Signal(str, str)
    changed = Signal()

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.lp = window.lp
        s = self.lp.settings

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(16)

        t = QLabel("Settings")
        t.setObjectName("pageTitle")
        root.addWidget(t)

        # Library
        card, lay = _card("Library", "Every folder inside the wallpaper folder is a category.")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)
        row = QHBoxLayout()
        self.folder = QLineEdit(s.wallpaper_dir)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._pick_folder)
        open_ = QPushButton("Open")
        open_.clicked.connect(lambda: open_in_file_manager(self.lp.library.root))
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        row.addWidget(open_)
        form.addRow("Wallpaper folder", row)
        self.download_cat = QLineEdit(s.download_category)
        form.addRow("Downloads go to", self.download_cat)
        lay.addLayout(form)
        root.addWidget(card)

        # Playback
        card, lay = _card("Playback", "Videos are played by mpv"
                          + (" behind your desktop icons." if IS_WINDOWS else " through mpvpaper (wlroots compositors)."))
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)
        self.mpv_opts = QLineEdit(s.mpv_opts)
        self.mpv_opts.setPlaceholderText(DEFAULT_MPV_OPTS)
        self.mpv_opts.setToolTip("mpv options, e.g. 'no-audio loop panscan=1.0 hwdec=auto'. "
                                 "panscan=1.0 fills the screen instead of letterboxing.")
        form.addRow("mpv options", self.mpv_opts)
        self.output = QLineEdit(s.output)
        self.mpv_path = QLineEdit(s.mpv_path)
        if IS_WINDOWS:
            row = QHBoxLayout()
            self.mpv_path.setPlaceholderText("auto-detect (bundled mpv, PATH, scoop, Program Files)")
            pick = QPushButton("Browse…")
            pick.clicked.connect(self._pick_mpv)
            row.addWidget(self.mpv_path, 1)
            row.addWidget(pick)
            form.addRow("mpv.exe", row)
        else:
            self.output.setToolTip("mpvpaper output, e.g. DP-1. * plays on every monitor.")
            form.addRow("Monitor (output)", self.output)
        lay.addLayout(form)
        self.backend_status = QLabel("")
        self.backend_status.setWordWrap(True)
        lay.addWidget(self.backend_status)
        self.autostart = QCheckBox("Restore my wallpaper when I log in")
        self.autostart.setToolTip(
            "Adds limpaper to Windows startup." if IS_WINDOWS else
            "Writes an XDG autostart entry. On Hyprland/Sway add `exec-once = limpaper restore` instead."
        )
        try:
            self.autostart.setChecked(autostart.is_enabled())
        except OSError:
            self.autostart.setEnabled(False)
        lay.addWidget(self.autostart)
        root.addWidget(card)

        # Theming (Linux / caelestia)
        if not IS_WINDOWS:
            card, lay = _card("Desktop colours",
                              "Recolour your desktop from each wallpaper through caelestia's dynamic scheme. "
                              "Needs caelestia-cli and ffmpeg; skipped quietly when they are missing.")
            self.theme = QCheckBox("Match desktop colours to the wallpaper")
            self.theme.setChecked(s.theme)
            lay.addWidget(self.theme)
            form = QFormLayout()
            self.frame_at = QLineEdit(s.frame_at)
            self.frame_at.setPlaceholderText("first frame")
            self.frame_at.setToolTip("Seconds into the video to take colours from")
            form.addRow("Sample colours at (s)", self.frame_at)
            lay.addLayout(form)
            ok = bool(which("caelestia"))
            note = QLabel("caelestia found ✓" if ok else "caelestia not found — colours will be left alone.")
            note.setStyleSheet(f"color: {style.GOOD if ok else style.MUTED};")
            lay.addWidget(note)
            root.addWidget(card)
        else:
            self.theme = None
            self.frame_at = None

        # Online
        card, lay = _card("Discover", "Wallpapers from MotionBGs, MoeWalls and Wallhaven. "
                          "None of them are made or checked by limpaper.")
        self.safe = QCheckBox("Safe search (Wallhaven: SFW only)")
        self.safe.setChecked(s.safe_search)
        self.previews = QCheckBox("Play animated previews")
        self.previews.setChecked(s.animated_previews)
        lay.addWidget(self.safe)
        lay.addWidget(self.previews)
        reset = QPushButton("Show the third-party warning again")
        reset.setObjectName("ghost")
        reset.clicked.connect(self._reset_warning)
        lay.addWidget(reset, 0, Qt.AlignLeft)
        root.addWidget(card)

        # Save
        row = QHBoxLayout()
        row.addStretch()
        save = QPushButton("Save settings")
        save.setObjectName("primary")
        save.clicked.connect(self.save)
        row.addWidget(save)
        root.addLayout(row)

        about = QLabel(
            f"limpaper {__version__} · GPL-3.0-or-later · "
            "<a style='color:#8b6cff' href='https://github.com/Chummychum4/limpaper'>github.com/Chummychum4/limpaper</a>"
        )
        about.setOpenExternalLinks(True)
        about.setObjectName("muted")
        root.addWidget(about)
        root.addStretch()
        self.refresh_status()

    def refresh_status(self) -> None:
        ok, why = self.lp.backend.available()
        if ok:
            self.backend_status.setText("● Playback ready")
            self.backend_status.setStyleSheet(f"color: {style.GOOD};")
        else:
            self.backend_status.setText(f"● {why}")
            self.backend_status.setStyleSheet(f"color: {style.WARN};")

    def _pick_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Wallpaper folder", self.folder.text())
        if d:
            self.folder.setText(d)

    def _pick_mpv(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Find mpv.exe", "", "mpv (mpv.exe);;All files (*)")
        if f:
            self.mpv_path.setText(f)

    def _reset_warning(self) -> None:
        self.lp.settings.online_warning_accepted = False
        self.lp.settings.save()
        self.toast.emit("You'll see the warning next time you open Discover.", "info")

    def save(self) -> None:
        s = self.lp.settings
        s.wallpaper_dir = self.folder.text().strip() or s.wallpaper_dir
        s.download_category = self.download_cat.text().strip() or "downloads"
        s.mpv_opts = self.mpv_opts.text().strip() or DEFAULT_MPV_OPTS
        s.output = self.output.text().strip() or "*"
        s.mpv_path = self.mpv_path.text().strip()
        if self.theme is not None:
            s.theme = self.theme.isChecked()
            s.frame_at = self.frame_at.text().strip()
        s.safe_search = self.safe.isChecked()
        s.animated_previews = self.previews.isChecked()
        try:
            self.lp.save_settings()
        except OSError as exc:
            self.toast.emit(f"Could not save settings: {exc}", "error")
            return
        try:
            if self.autostart.isEnabled() and self.autostart.isChecked() != autostart.is_enabled():
                autostart.set_enabled(self.autostart.isChecked())
        except OSError as exc:
            self.toast.emit(f"Could not change login startup: {exc}", "error")
        self.refresh_status()
        self.changed.emit()
        self.toast.emit("Settings saved", "good")
