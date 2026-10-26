"""Render assets/icon.svg to icon.png (app/desktop) and icon.ico (Windows).

Run after changing the SVG:  python packaging/make_icons.py
Needs PySide6 and Pillow.
"""

import io
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parent.parent / "src" / "limpaper" / "assets"


def render(size: int) -> Image.Image:
    renderer = QSvgRenderer(str(ASSETS / "icon.svg"))
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data())))


def main() -> None:
    QGuiApplication(sys.argv)
    render(256).save(ASSETS / "icon.png")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    big = render(256)
    big.save(ASSETS / "icon.ico", sizes=[(s, s) for s in sizes])
    print("wrote", ASSETS / "icon.png", ASSETS / "icon.ico")


if __name__ == "__main__":
    main()
