"""Library page: your wallpapers as a grid, filtered by category chips."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QPixmap, QStandardItem
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..config import WALLPAPER_EXTS
from ..library import LibraryError, Wallpaper
from ..media import thumbnail_for
from ..util import open_in_file_manager
from .widgets import ACTIVE, BADGE, FAV, KEY, PAYLOAD, PIXMAP, SUBTITLE, CardGrid
from .workers import load_image

ALL, FAVORITES, RECENT = "\x00all", "\x00favorites", "\x00recent"
THUMB = QSize(640, 360)


class LibraryPage(QWidget):
    applyRequested = Signal(object)  # Path
    randomRequested = Signal(object)  # list[Wallpaper]
    toast = Signal(str, str)
    changed = Signal()

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.lp = window.lp
        self.view = ALL
        self._thumbs: dict[str, QPixmap] = {}
        self._pending: set[str] = set()
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 16)
        root.setSpacing(16)

        # Header
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        t = QLabel("Library")
        t.setObjectName("pageTitle")
        self.sub = QLabel("")
        self.sub.setObjectName("pageSub")
        titles.addWidget(t)
        titles.addWidget(self.sub)
        head.addLayout(titles)
        head.addStretch()
        self.search = QLineEdit(placeholderText="Search wallpapers…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(self.refresh_grid)
        head.addWidget(self.search)
        shuffle = QPushButton("⤨  Shuffle")
        shuffle.setToolTip("Play a random wallpaper from this view")
        shuffle.clicked.connect(lambda: self.randomRequested.emit(self.visible()))
        head.addWidget(shuffle)
        add = QPushButton("＋  Add wallpapers")
        add.setObjectName("primary")
        add.clicked.connect(self.add_files)
        head.addWidget(add)
        root.addLayout(head)

        # Category chips
        self.chip_area = QScrollArea()
        self.chip_area.setWidgetResizable(True)
        self.chip_area.setFixedHeight(44)
        self.chip_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chip_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        chip_host = QWidget()
        self.chips = QHBoxLayout(chip_host)
        self.chips.setContentsMargins(0, 4, 0, 4)
        self.chips.setSpacing(8)
        self.chip_area.setWidget(chip_host)
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        root.addWidget(self.chip_area)

        # Grid
        self.grid = CardGrid()
        # activated covers double-click (or single, per platform) and Enter
        self.grid.activated.connect(self._activated)
        self.grid.customContextMenuRequested.connect(self._context_menu)
        self.grid.set_empty_widget(self._empty_state())
        root.addWidget(self.grid, 1)

        hint = QLabel("Double-click to play · right-click for more · drop video or image files anywhere to import")
        hint.setObjectName("muted")
        hint.setStyleSheet("font-size: 11px;")
        root.addWidget(hint)

    def _empty_state(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        icon = QLabel("🎞")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 44px;")
        self.empty_title = QLabel("No wallpapers here yet")
        self.empty_title.setObjectName("emptyTitle")
        self.empty_title.setAlignment(Qt.AlignCenter)
        self.empty_text = QLabel(
            "Drop videos or images onto this window, use “Add wallpapers”,\n"
            "or grab some from the Discover tab."
        )
        self.empty_text.setObjectName("muted")
        self.empty_text.setAlignment(Qt.AlignCenter)
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignCenter)
        add = QPushButton("Add wallpapers")
        add.setObjectName("primary")
        add.clicked.connect(self.add_files)
        disc = QPushButton("Open Discover")
        disc.clicked.connect(lambda: self.win.show_page("discover"))
        row.addWidget(add)
        row.addWidget(disc)
        for x in (icon, self.empty_title, self.empty_text):
            lay.addWidget(x)
        lay.addSpacing(8)
        lay.addLayout(row)
        return w

    # ── Data ────────────────────────────────────────────────────────────────
    def refresh(self) -> None:
        self.refresh_chips()
        self.refresh_grid()

    def refresh_chips(self) -> None:
        while self.chips.count():
            item = self.chips.takeAt(0)
            if item.widget():
                self.chip_group.removeButton(item.widget())
                item.widget().deleteLater()
        cats = self.lp.library.categories()
        if self.view not in (ALL, FAVORITES, RECENT, *cats):
            self.view = ALL
        entries = [(ALL, "All"), (FAVORITES, "★ Favourites"), (RECENT, "Recent")]
        entries += [(c, c) for c in cats]
        for key, label in entries:
            b = QPushButton(label)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(key == self.view)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.set_view(k))
            if key not in (ALL, FAVORITES, RECENT):
                b.setContextMenuPolicy(Qt.CustomContextMenu)
                b.customContextMenuRequested.connect(lambda _pos, k=key, btn=b: self._category_menu(k, btn))
            self.chip_group.addButton(b)
            self.chips.addWidget(b)
        new = QPushButton("＋ New category")
        new.setObjectName("ghost")
        new.setCursor(Qt.PointingHandCursor)
        new.clicked.connect(self.new_category)
        self.chips.addWidget(new)
        self.chips.addStretch()

    def set_view(self, key: str) -> None:
        self.view = key
        self.refresh_grid()

    def _items(self) -> list[Wallpaper]:
        lib, state = self.lp.library, self.lp.state
        if self.view == FAVORITES:
            favs = state.favorites()
            return [w for w in lib.wallpapers() if str(w.path) in favs]
        if self.view == RECENT:
            by_path = {str(w.path): w for w in lib.wallpapers()}
            return [by_path[h] for h in state.history() if h in by_path]
        return lib.wallpapers(None if self.view == ALL else self.view)

    def visible(self) -> list[Wallpaper]:
        m = self.grid.model_
        return [m.item(i).data(PAYLOAD) for i in range(m.rowCount())]

    def refresh_grid(self) -> None:
        items = self._items()
        needle = self.search.text().strip().casefold()
        if needle:
            items = [w for w in items if needle in w.name.casefold() or needle in w.category.casefold()]
        favs = self.lp.state.favorites()
        current = self.lp.current
        active = self.lp.is_active()
        m = self.grid.model_
        m.clear()
        for w in items:
            it = QStandardItem(w.name)
            it.setEditable(False)
            key = str(w.path)
            sub = w.category + (f" / {w.subfolder}" if w.subfolder else "")
            it.setData(sub, SUBTITLE)
            it.setData("LIVE" if w.is_video else "STILL", BADGE)
            it.setData(key in favs, FAV)
            it.setData(active and w.path == current, ACTIVE)
            it.setData(w, PAYLOAD)
            it.setData(key, KEY)
            if key in self._thumbs:
                it.setData(self._thumbs[key], PIXMAP)
            else:
                self._load_thumb(w)
            m.appendRow(it)
        total = sum(self.lp.library.count(c) for c in self.lp.library.categories())
        cats = len(self.lp.library.categories())
        self.sub.setText(f"{total} wallpapers in {cats} categories  ·  {self.lp.library.root}")
        if not self.lp.library.exists():
            self.empty_title.setText("Your wallpaper folder doesn't exist yet")
        elif needle:
            self.empty_title.setText(f"Nothing matches “{needle}”")
        else:
            self.empty_title.setText("No wallpapers here yet")
        self.grid.update_empty()

    def _load_thumb(self, w: Wallpaper) -> None:
        key = str(w.path)
        if key in self._pending:
            return
        self._pending.add(key)
        mpv = self.lp.mpv_binary()

        def work():
            still = thumbnail_for(w.path, mpv)
            return None if still is None else load_image(still, THUMB)

        def done(image):
            self._pending.discard(key)
            if image is None:
                return
            pix = QPixmap.fromImage(image)
            self._thumbs[key] = pix
            m = self.grid.model_
            for i in range(m.rowCount()):
                if m.item(i).data(KEY) == key:
                    m.item(i).setData(pix, PIXMAP)

        self.win.pool.run(work, done=done, failed=lambda _e: self._pending.discard(key))

    # ── Interaction ─────────────────────────────────────────────────────────
    def _activated(self, index) -> None:
        w = index.data(PAYLOAD)
        if w:
            self.applyRequested.emit(w.path)

    def _context_menu(self, pos) -> None:
        index = self.grid.indexAt(pos)
        if not index.isValid():
            return
        w: Wallpaper = index.data(PAYLOAD)
        menu = QMenu(self)
        menu.addAction("▶  Set as wallpaper", lambda: self.applyRequested.emit(w.path))
        fav = self.lp.state.is_favorite(w.path)
        menu.addAction("☆  Remove from favourites" if fav else "★  Add to favourites",
                       lambda: self.toggle_favorite(w))
        menu.addAction("📂  Show in folder", lambda: open_in_file_manager(w.path))
        move = menu.addMenu("➜  Move to")
        for cat in self.lp.library.categories():
            if cat != w.category:
                act = QAction(cat, move)
                act.triggered.connect(lambda _=False, c=cat: self.move(w, c))
                move.addAction(act)
        move.addSeparator()
        move.addAction("New category…", lambda: self.move(w, None))
        menu.addSeparator()
        menu.addAction("🗑  Delete from disk", lambda: self.delete(w))
        menu.exec(self.grid.viewport().mapToGlobal(pos))

    def toggle_favorite(self, w: Wallpaper) -> None:
        now = self.lp.state.toggle_favorite(w.path)
        self.toast.emit(f"{'Added to' if now else 'Removed from'} favourites: {w.name}", "info")
        self.refresh_grid()

    def move(self, w: Wallpaper, cat: str | None) -> None:
        if cat is None:
            cat, ok = QInputDialog.getText(self, "New category", "Category name:")
            if not ok or not cat.strip():
                return
        try:
            new = self.lp.library.move(w, cat)
        except (LibraryError, OSError) as exc:
            self.toast.emit(str(exc), "error")
            return
        self.lp.state.forget(w.path, new)
        self._thumbs.pop(str(w.path), None)
        self.toast.emit(f"Moved {w.name} to {cat}", "good")
        self.refresh()

    def delete(self, w: Wallpaper) -> None:
        answer = QMessageBox.question(
            self, "Delete wallpaper", f"Delete “{w.name}” from disk?\n\n{w.path}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.lp.library.delete(w)
        except OSError as exc:
            self.toast.emit(str(exc), "error")
            return
        self.lp.state.forget(w.path)
        self.toast.emit(f"Deleted {w.name}", "info")
        self.refresh()

    def _target_category(self) -> str:
        return self.view if not self.view.startswith("\x00") else "misc"

    def add_files(self) -> None:
        patterns = " ".join(f"*.{e}" for e in WALLPAPER_EXTS)
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add wallpapers", str(Path.home()), f"Wallpapers ({patterns});;All files (*)"
        )
        if files:
            self.import_files([Path(f) for f in files])

    def import_files(self, paths: list[Path]) -> None:
        files: list[Path] = []
        for p in paths:
            files += sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p]
        cat = self._target_category()
        try:
            added = self.lp.library.add(files, cat)
        except (LibraryError, OSError) as exc:
            self.toast.emit(str(exc), "error")
            return
        if added:
            self.toast.emit(f"Added {len(added)} wallpaper{'s' if len(added) != 1 else ''} to {cat}", "good")
        else:
            self.toast.emit("No supported video or image files found.", "warn")
        self.refresh()

    def new_category(self) -> None:
        name, ok = QInputDialog.getText(self, "New category", "Category name:")
        if not ok or not name.strip():
            return
        try:
            name = self.lp.library.create_category(name)
        except (LibraryError, OSError) as exc:
            self.toast.emit(str(exc), "error")
            return
        self.view = name
        self.refresh()

    def _category_menu(self, cat: str, button: QPushButton) -> None:
        menu = QMenu(self)
        menu.addAction("Open folder", lambda: open_in_file_manager(self.lp.library.root / cat))
        menu.addAction("Rename…", lambda: self._rename_category(cat))
        menu.addAction("Delete (only if empty)", lambda: self._delete_category(cat))
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _rename_category(self, cat: str) -> None:
        name, ok = QInputDialog.getText(self, "Rename category", "New name:", text=cat)
        if not ok or not name.strip() or name == cat:
            return
        try:
            self.view = self.lp.library.rename_category(cat, name)
        except (LibraryError, OSError) as exc:
            self.toast.emit(str(exc), "error")
            return
        self._thumbs.clear()
        self.refresh()

    def _delete_category(self, cat: str) -> None:
        try:
            self.lp.library.delete_category(cat)
        except (LibraryError, OSError) as exc:
            self.toast.emit(str(exc), "error")
            return
        self.refresh()

    # ── Drag and drop ───────────────────────────────────────────────────────
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.import_files(paths)
