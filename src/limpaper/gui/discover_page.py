"""Discover page: browse, preview and download wallpapers from other websites."""

from __future__ import annotations

import threading
import webbrowser

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QPixmap, QStandardItem
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..download import download
from ..sources import SOURCES, THIRD_PARTY_WARNING, OnlineWallpaper
from ..util import human_size
from . import style
from .widgets import BADGE, KEY, PAYLOAD, PIXMAP, SUBTITLE, CardGrid
from .workers import fetch_online_thumb

THUMB = QSize(640, 360)

try:  # QtMultimedia ships in PySide6-Addons; previews are optional
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget

    HAVE_VIDEO = True
except ImportError:  # pragma: no cover - depends on the install
    HAVE_VIDEO = False


class WarningDialog(QDialog):
    """Shown before Discover is first opened; must be explicitly accepted."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Before you browse")
        self.setModal(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 26, 28, 22)
        lay.setSpacing(14)

        head = QHBoxLayout()
        icon = QLabel("⚠")
        icon.setStyleSheet(f"font-size: 30px; color: {style.WARN};")
        title = QLabel("These wallpapers are not ours")
        title.setStyleSheet("font-size: 19px; font-weight: 700;")
        head.addWidget(icon)
        head.addWidget(title, 1)
        lay.addLayout(head)

        body = QLabel(THIRD_PARTY_WARNING)
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {style.WARN};")
        lay.addWidget(body)

        checks = QLabel(
            "What limpaper does to reduce the risk:\n"
            "  •  only downloads over HTTPS from each site's own servers\n"
            "  •  refuses web pages, programs and archives\n"
            "  •  keeps a file only if its contents are a real video or image\n"
            "  •  never runs anything it downloads"
        )
        checks.setObjectName("muted")
        lay.addWidget(checks)

        self.agree = QCheckBox("I understand that these files come from third parties and may be unsafe")
        lay.addWidget(self.agree)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Go back")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("Continue to Discover")
        self.ok.setObjectName("primary")
        self.ok.setEnabled(False)
        self.ok.clicked.connect(self.accept)
        self.agree.toggled.connect(self.ok.setEnabled)
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay.addLayout(row)

        # Wrapped labels only report a correct height once the width is fixed
        self.ensurePolished()
        width = 580
        self.setFixedSize(width, lay.totalHeightForWidth(width))


class DetailPanel(QFrame):
    downloadRequested = Signal(object, bool)  # item, apply afterwards
    cancelRequested = Signal()

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.setObjectName("detail")
        self.setMinimumWidth(320)
        self.setMaximumWidth(460)
        self.item: OnlineWallpaper | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        self.stack = QStackedWidget()
        self.stack.setMinimumHeight(180)
        self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.still = QLabel("Select a wallpaper to preview it")
        self.still.setAlignment(Qt.AlignCenter)
        self.still.setObjectName("muted")
        self.still.setStyleSheet(f"background: {style.SURFACE_2}; border-radius: 12px;")
        self.stack.addWidget(self.still)
        self.player = None
        if HAVE_VIDEO:
            self.video = QVideoWidget()
            self.video.setStyleSheet("background: black;")
            self.stack.addWidget(self.video)
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.audio.setMuted(True)
            self.player.setAudioOutput(self.audio)
            self.player.setVideoOutput(self.video)
            self.player.setLoops(QMediaPlayer.Infinite)
            self.player.errorOccurred.connect(lambda *_: self.stack.setCurrentWidget(self.still))
            self.player.mediaStatusChanged.connect(self._media_status)
        lay.addWidget(self.stack)

        self.title = QLabel("")
        self.title.setObjectName("detailTitle")
        self.title.setWordWrap(True)
        lay.addWidget(self.title)

        self.badges = QHBoxLayout()
        self.badges.setSpacing(6)
        lay.addLayout(self.badges)

        save_row = QHBoxLayout()
        lbl = QLabel("Save to")
        lbl.setObjectName("muted")
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.setToolTip("Category folder the download goes into (type a new name to create one)")
        save_row.addWidget(lbl)
        save_row.addWidget(self.category, 1)
        lay.addLayout(save_row)

        self.get_apply = QPushButton("⬇  Download && set as wallpaper")
        self.get_apply.setObjectName("primary")
        self.get_apply.clicked.connect(lambda: self._request(True))
        self.get_only = QPushButton("Download to library")
        self.get_only.clicked.connect(lambda: self._request(False))
        self.open_site = QPushButton("Open on website ↗")
        self.open_site.setObjectName("ghost")
        self.open_site.clicked.connect(lambda: self.item and webbrowser.open(self.item.page_url))
        lay.addWidget(self.get_apply)
        lay.addWidget(self.get_only)
        lay.addWidget(self.open_site)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(8)
        self.progress.hide()
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        self.cancel = QPushButton("Cancel download")
        self.cancel.setObjectName("ghost")
        self.cancel.hide()
        self.cancel.clicked.connect(self.cancelRequested.emit)
        lay.addWidget(self.progress)
        lay.addWidget(self.status)
        lay.addWidget(self.cancel)
        lay.addStretch()

        note = QLabel("Third-party content — download at your own risk.")
        note.setStyleSheet(f"color: {style.WARN}; font-size: 11px;")
        note.setWordWrap(True)
        lay.addWidget(note)
        self.set_item(None)

    def _media_status(self, status) -> None:
        if status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia):
            self.stack.setCurrentWidget(self.video)

    def _request(self, apply: bool) -> None:
        if self.item:
            self.downloadRequested.emit(self.item, apply)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.stack.setFixedHeight(int((self.width() - 32) * 9 / 16))

    def set_categories(self, cats: list[str], default: str) -> None:
        current = self.category.currentText() or default
        self.category.clear()
        names = sorted(set(cats) | {default}, key=str.casefold)
        self.category.addItems(names)
        self.category.setCurrentText(current)

    def set_item(self, item: OnlineWallpaper | None, pixmap: QPixmap | None = None) -> None:
        self.item = item
        for b in (self.get_apply, self.get_only, self.open_site):
            b.setEnabled(item is not None)
        while self.badges.count():
            w = self.badges.takeAt(0).widget()
            if w:
                w.deleteLater()
        if self.player:
            self.player.stop()
        self.stack.setCurrentWidget(self.still)
        if item is None:
            self.title.setText("Nothing selected")
            self.still.setPixmap(QPixmap())
            self.still.setText("Select a wallpaper to preview it")
            return
        self.title.setText(item.title)
        source = SOURCES[item.source]
        for text in (source.name, "LIVE" if item.kind == "video" else "STILL", item.resolution):
            if text:
                b = QLabel(text)
                b.setObjectName("badge")
                self.badges.addWidget(b)
        self.badges.addStretch()
        self.set_still(pixmap)
        self.set_preview(item)

    def set_still(self, pixmap: QPixmap | None) -> None:
        if pixmap and not pixmap.isNull():
            size = self.stack.size()
            scaled = pixmap.scaled(size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (scaled.width() - size.width()) // 2
            y = (scaled.height() - size.height()) // 2
            self.still.setPixmap(scaled.copy(x, y, size.width(), size.height()))
        else:
            self.still.setPixmap(QPixmap())
            self.still.setText("Loading preview…")

    def set_preview(self, item: OnlineWallpaper) -> None:
        if (self.player and item is self.item and item.preview_url
                and self.win.lp.settings.animated_previews):
            self.player.setSource(QUrl(item.preview_url))
            self.player.play()

    def stop_preview(self) -> None:
        if self.player:
            self.player.stop()


class DiscoverPage(QWidget):
    applyRequested = Signal(object)
    toast = Signal(str, str)
    downloaded = Signal()

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.lp = window.lp
        self.source = next(iter(SOURCES.values()))
        self.query = ""
        self.page = 0
        self.has_more = False
        self.loading = False
        self.gen = 0
        self._thumbs: dict[str, QPixmap] = {}
        self.cancel_event: threading.Event | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 20)
        root.setSpacing(14)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        t = QLabel("Discover")
        t.setObjectName("pageTitle")
        self.sub = QLabel("Live wallpapers from around the web")
        self.sub.setObjectName("pageSub")
        titles.addWidget(t)
        titles.addWidget(self.sub)
        head.addLayout(titles)
        head.addStretch()
        root.addLayout(head)

        banner = QFrame()
        banner.setObjectName("warningBanner")
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(14, 10, 14, 10)
        icon = QLabel("⚠")
        icon.setStyleSheet(f"font-size: 20px; color: {style.WARN};")
        text = QLabel(
            "<b>Not our content.</b> These wallpapers come from other websites and may contain "
            "malicious software. limpaper checks that downloads are real video or image files, "
            "but cannot guarantee they are safe — download at your own risk."
        )
        text.setObjectName("warningText")
        text.setWordWrap(True)
        bl.addWidget(icon)
        bl.addWidget(text, 1)
        root.addWidget(banner)

        bar = QHBoxLayout()
        bar.setSpacing(0)
        self.source_group = QButtonGroup(self)
        ids = list(SOURCES)
        for i, sid in enumerate(ids):
            s = SOURCES[sid]
            b = QPushButton(f"{s.name}  ·  {s.kind}")
            b.setObjectName("segment")
            b.setProperty("first", i == 0)
            b.setProperty("last", i == len(ids) - 1)
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setToolTip(f"{s.description}\n{s.homepage}")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=sid: self.set_source(k))
            self.source_group.addButton(b)
            bar.addWidget(b)
        bar.addSpacing(14)
        self.search = QLineEdit(placeholderText="Search (e.g. rain, cyberpunk, forest)…")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self.run_search)
        bar.addWidget(self.search, 1)
        bar.addSpacing(8)
        go = QPushButton("Search")
        go.setObjectName("primary")
        go.clicked.connect(self.run_search)
        bar.addWidget(go)
        bar.addSpacing(6)
        browse = QPushButton("Latest")
        browse.setToolTip("Clear the search and show the newest wallpapers")
        browse.clicked.connect(self.browse_latest)
        bar.addWidget(browse)
        root.addLayout(bar)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(14)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.grid = CardGrid()
        self.grid.selectionModel().currentChanged.connect(self._selected)
        self.grid.nearBottom.connect(self.load_more)
        empty = QLabel("")
        empty.setObjectName("muted")
        empty.setAlignment(Qt.AlignCenter)
        self.empty_label = empty
        self.grid.set_empty_widget(empty)
        ll.addWidget(self.grid, 1)
        self.state_label = QLabel("")
        self.state_label.setObjectName("muted")
        ll.addWidget(self.state_label)
        split.addWidget(left)

        self.detail = DetailPanel(window)
        self.detail.downloadRequested.connect(self._download)
        self.detail.cancelRequested.connect(self._cancel)
        split.addWidget(self.detail)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([900, 360])
        root.addWidget(split, 1)

        self._started = False

    # ── Loading ─────────────────────────────────────────────────────────────
    def activate(self) -> None:
        """Called whenever the page is shown."""
        self.detail.set_categories(self.lp.library.categories(), self.lp.settings.download_category)
        if not self._started:
            self._started = True
            self.reload()
        elif self.detail.item:
            self.detail.set_preview(self.detail.item)

    def deactivate(self) -> None:
        self.detail.stop_preview()

    def set_source(self, sid: str) -> None:
        for b, key in zip(self.source_group.buttons(), SOURCES):
            b.setChecked(key == sid)
        if SOURCES[sid] is not self.source:
            self.source = SOURCES[sid]
            self.reload()

    def run_search(self) -> None:
        self.query = self.search.text().strip()
        self.reload()

    def browse_latest(self) -> None:
        self.search.clear()
        self.query = ""
        self.reload()

    def reload(self) -> None:
        self.gen += 1
        self.page = 0
        self.has_more = False
        self.loading = False
        # Drop queued listings/thumbnails of the previous query (downloads use another pool)
        self.win.net_pool.clear()
        self.grid.model_.clear()
        self.detail.set_item(None)
        self.load_more(force=True)

    def load_more(self, force: bool = False) -> None:
        if self.loading or (not force and not self.has_more):
            return
        self.loading = True
        self.page += 1
        gen, source, query, page = self.gen, self.source, self.query, self.page
        safe = self.lp.settings.safe_search
        what = f"“{query}”" if query else ("top this month" if source.kind == "Still" else "newest")
        self.state_label.setText(f"Loading {what} from {source.name}…")
        self.empty_label.setText(f"Loading {source.name}…")
        self.grid.update_empty()

        def work():
            return source.search(query, page, safe) if query else source.browse(page, safe)

        self.win.net_pool.run(work, done=lambda res: self._loaded(gen, res),
                              failed=lambda err: self._failed(gen, err))

    def _failed(self, gen: int, err: str) -> None:
        if gen != self.gen:
            return
        self.loading = False
        self.state_label.setText(err)
        self.empty_label.setText(f"Couldn't load {self.source.name}.\n{err}")
        self.grid.update_empty()
        self.toast.emit(err, "error")

    def _loaded(self, gen: int, result) -> None:
        if gen != self.gen:
            return
        self.loading = False
        self.has_more = result.has_more
        m = self.grid.model_
        for item in result.items:
            it = QStandardItem(item.title)
            it.setEditable(False)
            it.setData(item.resolution or self.source.name, SUBTITLE)
            it.setData("LIVE" if item.kind == "video" else "STILL", BADGE)
            it.setData(item, PAYLOAD)
            it.setData(item.thumb_url, KEY)
            if item.thumb_url in self._thumbs:
                it.setData(self._thumbs[item.thumb_url], PIXMAP)
            else:
                self._load_thumb(gen, item.thumb_url)
            m.appendRow(it)
        n = m.rowCount()
        more = "  ·  scroll for more" if self.has_more else ""
        self.state_label.setText(f"{n} wallpapers from {self.source.name}{more}")
        self.empty_label.setText("No results. Try another search or source.")
        self.grid.update_empty()
        if n and not self.grid.currentIndex().isValid():
            self.grid.setCurrentIndex(m.index(0, 0))

    def _load_thumb(self, gen: int, url: str) -> None:
        if not url:
            return

        def done(image):
            pix = QPixmap.fromImage(image)
            self._thumbs[url] = pix
            m = self.grid.model_
            for i in range(m.rowCount()):
                if m.item(i).data(KEY) == url:
                    m.item(i).setData(pix, PIXMAP)
            item = self.detail.item
            if item and item.thumb_url == url:
                self.detail.set_still(pix)

        def failed(_err: str) -> None:
            item = self.detail.item
            if item and item.thumb_url == url:
                self.detail.still.setText("No preview available")

        self.win.net_pool.run(fetch_online_thumb, url, THUMB, done=done, failed=failed)

    # ── Selection & preview ─────────────────────────────────────────────────
    def _selected(self, current, _previous) -> None:
        item = current.data(PAYLOAD) if current.isValid() else None
        self.detail.set_item(item, self._thumbs.get(item.thumb_url) if item else None)
        if item and not item.preview_url and item.kind == "video":
            source = SOURCES[item.source]

            def done(resolved):
                if self.detail.item is item:
                    self.detail.set_preview(resolved)

            self.win.pool.run(source.resolve, item, done=done)

    # ── Downloads ───────────────────────────────────────────────────────────
    def _download(self, item: OnlineWallpaper | None, apply: bool) -> None:
        if item is None:
            return
        if self.cancel_event is not None:
            self.toast.emit("A download is already running.", "warn")
            return
        category = self.detail.category.currentText().strip() or self.lp.settings.download_category
        source = SOURCES[item.source]
        self.cancel_event = threading.Event()
        cancel = self.cancel_event
        d = self.detail
        d.progress.setRange(0, 0)
        d.progress.show()
        d.cancel.show()
        d.status.setText(f"Downloading {item.title}…")
        d.get_apply.setEnabled(False)
        d.get_only.setEnabled(False)

        def work(progress):
            return download(item, source, self.lp.library, category, progress, cancel)

        def on_progress(got: int, total: int) -> None:
            if total:
                d.progress.setRange(0, 1000)
                d.progress.setValue(int(got * 1000 / total))
                d.status.setText(f"Downloading {item.title}…  {human_size(got)} of {human_size(total)}")
            else:
                d.status.setText(f"Downloading {item.title}…  {human_size(got)}")

        def finish() -> None:
            self.cancel_event = None
            d.progress.hide()
            d.cancel.hide()
            d.get_apply.setEnabled(d.item is not None)
            d.get_only.setEnabled(d.item is not None)

        def done(path) -> None:
            finish()
            d.status.setText(f"Saved to {path}")
            self.toast.emit(f"Downloaded {item.title} to {category}", "good")
            self.downloaded.emit()
            d.set_categories(self.lp.library.categories(), category)
            if apply:
                self.applyRequested.emit(path)

        def failed(err: str) -> None:
            finish()
            d.status.setText(err)
            self.toast.emit(err, "warn" if "cancel" in err.lower() else "error")

        self.win.pool.run(work, done=done, failed=failed, progress=on_progress)

    def _cancel(self) -> None:
        if self.cancel_event:
            self.cancel_event.set()
