"""The limpaper GUI: sidebar navigation, Library, Discover and Settings."""

from __future__ import annotations

import random
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core import Limpaper
from ..library import pretty
from ..media import thumbnail_for
from . import style
from .discover_page import DiscoverPage, WarningDialog
from .library_page import LibraryPage
from .settings_page import SettingsPage
from .widgets import GradientLabel, Toast
from .workers import Pool, load_image

ASSETS = Path(__file__).resolve().parent.parent / "assets"
# Sidebar is 232 wide with 20px padding and a 10px card margin each side
THUMB_W, THUMB_H = 172, 97


class NowPlaying(QFrame):
    """Sidebar card showing the current wallpaper with quick controls."""

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.setObjectName("nowCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 12)
        lay.setSpacing(8)
        self.thumb = QLabel()
        self.thumb.setFixedSize(THUMB_W, THUMB_H)
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setStyleSheet(f"background: {style.SURFACE_3}; border-radius: 10px; color: {style.FAINT};")
        lay.addWidget(self.thumb)
        self.label = QLabel("NOW PLAYING")
        self.label.setObjectName("sectionLabel")
        self.title = QLabel("Nothing")
        self.title.setObjectName("nowTitle")
        self.title.setWordWrap(True)
        lay.addWidget(self.label)
        lay.addWidget(self.title)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.shuffle = QPushButton("⤨")
        self.shuffle.setToolTip("Random wallpaper (Ctrl+R)")
        self.stop = QPushButton("■  Stop")
        self.stop.setToolTip("Stop the wallpaper")
        self.shuffle.clicked.connect(lambda: window.play_random(None))
        self.stop.clicked.connect(window.stop)
        row.addWidget(self.stop, 1)
        row.addWidget(self.shuffle)
        lay.addLayout(row)
        self._shown: str | None = None

    def refresh(self) -> None:
        lp = self.win.lp
        current = lp.current
        active = current is not None and lp.is_active()
        self.label.setText("NOW PLAYING" if active else "NOT PLAYING")
        self.title.setText(pretty(str(current)) if active else "Pick a wallpaper to start")
        self.stop.setEnabled(active)
        key = str(current) if active else None
        if key == self._shown:
            return
        self._shown = key
        self.thumb.setPixmap(QPixmap())
        self.thumb.setText("—" if not active else "")
        if not active:
            return
        mpv = lp.mpv_binary()

        def work():
            still = thumbnail_for(current, mpv)
            return None if still is None else load_image(still, QSize(376, 212))

        def done(image):
            if image is None or self._shown != key:
                return
            pix = QPixmap.fromImage(image).scaled(QSize(THUMB_W, THUMB_H), Qt.KeepAspectRatioByExpanding,
                                                  Qt.SmoothTransformation)
            x = (pix.width() - THUMB_W) // 2
            y = (pix.height() - THUMB_H) // 2
            self.thumb.setPixmap(pix.copy(x, y, THUMB_W, THUMB_H))

        self.win.pool.run(work, done=done)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.lp = Limpaper()
        try:
            self.lp.library.ensure()
        except OSError:
            pass  # e.g. an unplugged drive; the Library page explains
        self.pool = Pool()
        # Discover's listings and thumbnails; cleared whenever the query changes
        self.net_pool = Pool(6)
        self.setWindowTitle("limpaper")
        self.resize(1320, 840)
        self.setMinimumSize(980, 640)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Sidebar
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(20, 24, 20, 20)
        sl.setSpacing(6)
        brand = QHBoxLayout()
        brand.addWidget(GradientLabel("limpaper", 28))
        brand.addStretch()
        sl.addLayout(brand)
        tag = QLabel("live wallpapers")
        tag.setObjectName("muted")
        tag.setStyleSheet("font-size: 11px; padding-left: 3px;")
        sl.addWidget(tag)
        sl.addSpacing(22)
        nav_label = QLabel("BROWSE")
        nav_label.setObjectName("sectionLabel")
        sl.addWidget(nav_label)
        sl.addSpacing(4)

        self.nav = QButtonGroup(self)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, label, shortcut in (("library", "▦   Library", "Ctrl+1"),
                                     ("discover", "✦   Discover", "Ctrl+2"),
                                     ("settings", "⚙   Settings", "Ctrl+3")):
            b = QPushButton(label)
            b.setObjectName("navButton")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(shortcut)
            b.clicked.connect(lambda _=False, k=key: self.show_page(k))
            self.nav.addButton(b)
            self.nav_buttons[key] = b
            sl.addWidget(b)
            QShortcut(QKeySequence(shortcut), self, activated=lambda k=key: self.show_page(k))
        sl.addStretch()
        self.now = NowPlaying(self)
        sl.addWidget(self.now)
        h.addWidget(side)

        # Pages
        self.stack = QStackedWidget()
        self.library = LibraryPage(self)
        self.discover = DiscoverPage(self)
        self.settings = SettingsPage(self)
        self.pages = {"library": self.library, "discover": self.discover, "settings": self.settings}
        for page in self.pages.values():
            self.stack.addWidget(page)
            page.toast.connect(self.toast)
        h.addWidget(self.stack, 1)

        self.library.applyRequested.connect(self.apply)
        self.library.randomRequested.connect(self.play_random)
        self.discover.applyRequested.connect(self.apply)
        self.discover.downloaded.connect(self.library.refresh)
        self.settings.changed.connect(self._settings_changed)

        self.toaster = Toast(self)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=lambda: self.play_random(None))
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_search)
        QShortcut(QKeySequence("F5"), self, activated=self.refresh_all)

        self.show_page("library")
        self.refresh_all()
        # Folders change behind our back (file manager, downloads); keep in sync
        self._watch = QTimer(self, interval=4000)
        self._watch.timeout.connect(self._poll)
        self._watch.start()
        self._last_snapshot = self._snapshot()

        ok, why = self.lp.backend.available()
        if not ok:
            QTimer.singleShot(600, lambda: self.toast(why, "warn"))

    # ── Navigation ──────────────────────────────────────────────────────────
    def show_page(self, key: str) -> None:
        if key == "discover" and not self.lp.settings.online_warning_accepted:
            if WarningDialog(self).exec() != WarningDialog.Accepted:
                current = next((k for k, p in self.pages.items() if p is self.stack.currentWidget()), "library")
                self.nav_buttons[current].setChecked(True)
                return
            self.lp.settings.online_warning_accepted = True
            self.lp.settings.save()
        if self.stack.currentWidget() is self.discover and key != "discover":
            self.discover.deactivate()
        self.stack.setCurrentWidget(self.pages[key])
        self.nav_buttons[key].setChecked(True)
        if key == "discover":
            self.discover.activate()
        elif key == "settings":
            self.settings.refresh_status()

    def _focus_search(self) -> None:
        page = self.stack.currentWidget()
        if hasattr(page, "search"):
            page.search.setFocus()
            page.search.selectAll()

    def toast(self, text: str, kind: str = "info") -> None:
        self.toaster.show_message(text, kind)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.toaster.isVisible():
            self.toaster._reposition()

    # ── State ───────────────────────────────────────────────────────────────
    def refresh_all(self) -> None:
        self.library.refresh()
        self.now.refresh()

    def _snapshot(self):
        lib = self.lp.library
        return tuple((c, lib.count(c)) for c in lib.categories())

    def _poll(self) -> None:
        snap = self._snapshot()
        if snap != self._last_snapshot:
            self._last_snapshot = snap
            self.library.refresh()
        self.now.refresh()

    def _settings_changed(self) -> None:
        self.library._thumbs.clear()
        self.refresh_all()

    # ── Playback ────────────────────────────────────────────────────────────
    def apply(self, path: Path) -> None:
        path = Path(path)
        self.toast(f"Setting {pretty(str(path))}…", "info")

        def done(notes):
            extra = f"  ·  {notes[0]}" if notes else ""
            self.toast(f"Now playing {pretty(str(path))}{extra}", "good")
            self.now.refresh()
            self.library.refresh_grid()

        self.pool.run(self.lp.apply, path, done=done, failed=lambda e: self.toast(e, "error"))

    def play_random(self, pool) -> None:
        pool = pool or self.lp.library.wallpapers()
        if not pool:
            self.toast("No wallpapers to pick from yet.", "warn")
            return
        choices = [w for w in pool if w.path != self.lp.current] or pool
        self.apply(random.choice(choices).path)

    def stop(self) -> None:
        def done(result):
            was_running, _notes = result
            self.toast("Wallpaper stopped" if was_running else "No wallpaper was running", "info")
            self.now.refresh()
            self.library.refresh_grid()

        self.pool.run(self.lp.stop, done=done, failed=lambda e: self.toast(e, "error"))

    def closeEvent(self, event) -> None:
        self.discover.deactivate()
        self.discover._cancel()
        super().closeEvent(event)


def run() -> int:
    if sys.platform == "win32":
        # Own taskbar identity, so Windows shows our icon rather than Python's
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("limpaper.limpaper")
        except (AttributeError, OSError):
            pass
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("limpaper")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("limpaper")
    app.setStyle("Fusion")
    app.setStyleSheet(style.QSS)
    icon = ASSETS / "icon.png"
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    win = MainWindow()
    win.show()
    return app.exec()
