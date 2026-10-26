"""Background work for the GUI: a thread pool with results delivered on the UI thread."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QImage, QImageReader

from ..config import cache_dir


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    # object, not int: byte counts can pass 2**31
    progress = Signal(object, object)


class Task(QRunnable):
    def __init__(self, fn: Callable, *args, with_progress: bool = False):
        super().__init__()
        self.fn, self.args, self.with_progress = fn, args, with_progress
        # Created on the UI thread, so emits from the worker are queued to it
        self.signals = _Signals()

    def run(self) -> None:
        try:
            if self.with_progress:
                result = self.fn(*self.args, progress=self.signals.progress.emit)
            else:
                result = self.fn(*self.args)
        except Exception as exc:  # reported to the UI rather than lost in a thread
            self.signals.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.signals.done.emit(result)


class Pool:
    """Runs callables off the UI thread and keeps their tasks alive until done."""

    def __init__(self, threads: int = 6):
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(threads)
        self._live: set[Task] = set()

    def run(
        self,
        fn: Callable,
        *args,
        done: Callable[[Any], None] | None = None,
        failed: Callable[[str], None] | None = None,
        progress: Callable[[int, int], None] | None = None,
    ) -> Task:
        task = Task(fn, *args, with_progress=progress is not None)
        task.setAutoDelete(False)
        self._live.add(task)

        def finish(*_):
            self._live.discard(task)

        if done:
            task.signals.done.connect(done)
        if failed:
            task.signals.failed.connect(failed)
        if progress:
            task.signals.progress.connect(progress)
        task.signals.done.connect(finish)
        task.signals.failed.connect(finish)
        self.pool.start(task)
        return task

    def clear(self) -> None:
        """Drop queued (not yet started) work, e.g. thumbnails of a stale page."""
        for task in list(self._live):
            # tryTake only succeeds for tasks still waiting in the queue
            if self.pool.tryTake(task):
                self._live.discard(task)


def load_image(path: Path | str, size: QSize) -> QImage:
    """Read an image scaled to cover `size`; runs fine on a worker thread."""
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    original = reader.size()
    if original.isValid():
        scaled = original.scaled(size, Qt.KeepAspectRatioByExpanding)
        reader.setScaledSize(scaled)
    image = reader.read()
    if image.isNull():
        raise OSError(reader.errorString())
    return image


def fetch_online_thumb(url: str, size: QSize) -> QImage:
    """Download (or read from cache) a remote thumbnail."""
    from ..sources.base import http_get

    folder = cache_dir() / "online"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".img")
    if not path.is_file() or not path.stat().st_size:
        data = http_get(url)
        image = QImage.fromData(data)
        if image.isNull():
            raise OSError("not an image")
        path.write_bytes(data)
    return load_image(path, size)
