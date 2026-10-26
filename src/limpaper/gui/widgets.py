"""Custom widgets: the wallpaper card grid, toasts, the logo."""

from __future__ import annotations

import hashlib

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGraphicsOpacityEffect,
    QLabel,
    QListView,
    QStyle,
    QStyledItemDelegate,
    QWidget,
)

from . import style

TITLE = Qt.DisplayRole
SUBTITLE = Qt.UserRole + 1
PIXMAP = Qt.UserRole + 2
BADGE = Qt.UserRole + 3
FAV = Qt.UserRole + 4
ACTIVE = Qt.UserRole + 5
PAYLOAD = Qt.UserRole + 6
KEY = Qt.UserRole + 7

CARD_MIN_WIDTH = 250
GAP = 7  # half the space between cards
RADIUS = 14


def _placeholder_colors(seed: str) -> tuple[QColor, QColor]:
    h = int(hashlib.md5(seed.encode()).hexdigest()[:6], 16)
    hue = h % 360
    return QColor.fromHsl(hue, 120, 70), QColor.fromHsl((hue + 50) % 360, 140, 35)


class CardDelegate(QStyledItemDelegate):
    """Paints a wallpaper as a rounded 16:9 card with its title over the image."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scaled: dict[tuple, QPixmap] = {}

    def invalidate(self) -> None:
        self._scaled.clear()

    def sizeHint(self, option, index) -> QSize:
        view = self.parent()
        return view.gridSize() if isinstance(view, QListView) else QSize(260, 160)

    def _cover(self, pix: QPixmap, size: QSize, key) -> QPixmap:
        ck = (key, size.width(), size.height(), pix.cacheKey())
        cached = self._scaled.get(ck)
        if cached is None:
            if len(self._scaled) > 600:
                self._scaled.clear()
            scaled = pix.scaled(size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (scaled.width() - size.width()) // 2
            y = (scaled.height() - size.height()) // 2
            cached = scaled.copy(x, y, size.width(), size.height())
            self._scaled[ck] = cached
        return cached

    def paint(self, p: QPainter, option, index) -> None:
        r = option.rect.adjusted(GAP, GAP, -GAP, -GAP)
        rf = QRectF(r)
        hover = bool(option.state & QStyle.State_MouseOver)
        selected = bool(option.state & QStyle.State_Selected)
        title = index.data(TITLE) or ""

        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        clip = QPainterPath()
        clip.addRoundedRect(rf, RADIUS, RADIUS)
        p.setClipPath(clip)

        pix = index.data(PIXMAP)
        if isinstance(pix, QPixmap) and not pix.isNull():
            dpr = p.device().devicePixelRatioF() if p.device() else 1.0
            target = QSize(int(r.width() * dpr), int(r.height() * dpr))
            cover = self._cover(pix, target, index.data(KEY))
            cover.setDevicePixelRatio(dpr)
            p.drawPixmap(r.topLeft(), cover)
        else:
            c1, c2 = _placeholder_colors(title)
            g = QLinearGradient(rf.topLeft(), rf.bottomRight())
            g.setColorAt(0, c1)
            g.setColorAt(1, c2)
            p.fillRect(r, g)
            p.setPen(QColor(255, 255, 255, 60))
            f = QFont(option.font)
            f.setPixelSize(int(r.height() * 0.45))
            f.setBold(True)
            p.setFont(f)
            p.drawText(r.adjusted(0, -16, 0, -16), Qt.AlignCenter, (title[:1] or "?").upper())

        # Legibility gradient under the text
        shade = QLinearGradient(QPointF(0, r.bottom()), QPointF(0, r.bottom() - 84))
        shade.setColorAt(0, QColor(5, 6, 10, 225))
        shade.setColorAt(1, QColor(5, 6, 10, 0))
        p.fillRect(QRect(r.left(), r.bottom() - 84, r.width(), 85), shade)
        if hover:
            p.fillRect(r, QColor(255, 255, 255, 16))

        pad = 12
        f = QFont(option.font)
        f.setPixelSize(14)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(style.TEXT))
        fm = QFontMetrics(f)
        subtitle = index.data(SUBTITLE) or ""
        title_y = r.bottom() - pad - (18 if subtitle else 0)
        p.drawText(QPoint(r.left() + pad, title_y),
                   fm.elidedText(title, Qt.ElideRight, r.width() - 2 * pad))
        if subtitle:
            f2 = QFont(option.font)
            f2.setPixelSize(11)
            p.setFont(f2)
            p.setPen(QColor(200, 205, 218, 170))
            p.drawText(QPoint(r.left() + pad, r.bottom() - pad),
                       QFontMetrics(f2).elidedText(subtitle, Qt.ElideRight, r.width() - 2 * pad))

        # Pills along the top
        fb = QFont(option.font)
        fb.setPixelSize(10)
        fb.setBold(True)
        fb.setLetterSpacing(QFont.AbsoluteSpacing, 0.6)
        p.setFont(fb)
        x = r.left() + 10
        badge = index.data(BADGE)
        if badge:
            x = self._pill(p, x, r.top() + 10, badge, QColor(10, 12, 18, 170), QColor(style.TEXT))
        if index.data(ACTIVE):
            self._pill(p, x, r.top() + 10, "● PLAYING", QColor(61, 220, 151, 230), QColor("#06140d"))
        if index.data(FAV):
            fs = QFont(option.font)
            fs.setPixelSize(16)
            p.setFont(fs)
            p.setPen(QColor("#ffd166"))
            p.drawText(QRect(r.right() - 34, r.top() + 6, 28, 24), Qt.AlignCenter, "★")

        # Play hint on hover
        if hover:
            cx, cy = r.center().x(), r.center().y() - 12
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 215))
            p.drawEllipse(QPoint(cx, cy), 22, 22)
            tri = QPainterPath()
            tri.moveTo(cx - 6, cy - 9)
            tri.lineTo(cx - 6, cy + 9)
            tri.lineTo(cx + 10, cy)
            tri.closeSubpath()
            p.setBrush(QColor(15, 17, 24))
            p.drawPath(tri)

        p.setClipping(False)
        if selected:
            pen = QPen(QColor(style.ACCENT), 2.5)
        elif hover:
            pen = QPen(QColor(255, 255, 255, 70), 1)
        else:
            pen = QPen(QColor(255, 255, 255, 22), 1)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rf.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)
        p.restore()

    @staticmethod
    def _pill(p: QPainter, x: int, y: int, text: str, bg: QColor, fg: QColor) -> int:
        fm = QFontMetrics(p.font())
        w = fm.horizontalAdvance(text) + 14
        rect = QRectF(x, y, w, 20)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(rect, 10, 10)
        p.setPen(fg)
        p.drawText(rect, Qt.AlignCenter, text)
        return x + w + 6


class CardGrid(QListView):
    """Responsive grid of cards that fills its width with equal columns."""

    nearBottom = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(24)
        self.setMouseTracking(True)
        self.setSpacing(0)
        self.setFrameShape(QListView.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.delegate = CardDelegate(self)
        self.setItemDelegate(self.delegate)
        self.model_ = QStandardItemModel(self)
        self.setModel(self.model_)
        self.verticalScrollBar().valueChanged.connect(self._scrolled)

        self.empty = QWidget(self.viewport())
        self.empty.hide()

    def set_empty_widget(self, widget: QWidget) -> None:
        self.empty = widget
        widget.setParent(self.viewport())
        self._place_empty()

    def update_empty(self) -> None:
        self.empty.setVisible(self.model_.rowCount() == 0)
        self._place_empty()

    def _place_empty(self) -> None:
        vp = self.viewport().rect()
        hint = self.empty.sizeHint()
        w = min(vp.width() - 40, max(hint.width(), 420))
        h = hint.height()
        self.empty.setGeometry((vp.width() - w) // 2, max(20, (vp.height() - h) // 3), w, h)

    def _scrolled(self, value: int) -> None:
        bar = self.verticalScrollBar()
        if bar.maximum() > 0 and value >= bar.maximum() - 200:
            self.nearBottom.emit()

    def resizeEvent(self, event) -> None:
        # Leave room for the scrollbar up front, so its arrival never wraps a column
        width = self.width() - self.verticalScrollBar().sizeHint().width() - 8
        cols = max(1, width // CARD_MIN_WIDTH)
        w = width // cols
        h = int((w - 2 * GAP) * 9 / 16) + 2 * GAP
        if self.gridSize() != QSize(w, h):
            self.setGridSize(QSize(w, h))
            self.delegate.invalidate()
        super().resizeEvent(event)
        self._place_empty()


class Toast(QLabel):
    """Short-lived message at the bottom of the window."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignCenter)
        self.hide()
        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)
        self._anim = QPropertyAnimation(self._fx, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._timer = QTimer(self, singleShot=True)
        self._timer.timeout.connect(self._fade_out)

    def show_message(self, text: str, kind: str = "info", ms: int = 3200) -> None:
        colors = {"info": style.ACCENT_2, "good": style.GOOD, "warn": style.WARN, "error": style.DANGER}
        self.setStyleSheet(f"#toast {{ border-left: 4px solid {colors.get(kind, style.ACCENT_2)}; }}")
        self.setText(text)
        self._reposition()
        self.show()
        self.raise_()
        self._anim.stop()
        try:
            self._anim.finished.disconnect(self.hide)
        except (RuntimeError, TypeError):
            pass
        self._anim.setStartValue(self._fx.opacity() if self.isVisible() else 0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(ms)

    def _fade_out(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.hide)
        self._anim.start()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if not parent:
            return
        w = min(560, parent.width() - 80)
        self.setFixedWidth(w)
        self.adjustSize()
        self.move((parent.width() - w) // 2 + 120, parent.height() - self.height() - 28)


class GradientLabel(QWidget):
    """The word mark, painted with the accent gradient."""

    def __init__(self, text: str, size: int = 26, parent=None):
        super().__init__(parent)
        self.text = text
        self.font_ = QFont()
        self.font_.setPixelSize(size)
        self.font_.setWeight(QFont.Black)
        self.font_.setLetterSpacing(QFont.AbsoluteSpacing, -0.5)
        fm = QFontMetrics(self.font_)
        self.setFixedSize(fm.horizontalAdvance(text) + 6, fm.height() + 4)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        fm = QFontMetrics(self.font_)
        path.addText(2, fm.ascent() + 1, self.font_, self.text)
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0, QColor(style.ACCENT))
        g.setColorAt(1, QColor(style.ACCENT_2))
        p.fillPath(path, g)
