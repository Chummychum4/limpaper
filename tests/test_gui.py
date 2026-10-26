import os

import pytest

pytest.importorskip("PySide6.QtWidgets")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_main_window_builds(library, qapp):
    from limpaper.gui.app import MainWindow

    win = MainWindow()
    win.show()
    qapp.processEvents()
    assert win.library.grid.model_.rowCount() == 5
    win.library.search.setText("rain")
    assert win.library.grid.model_.rowCount() == 1
    win.show_page("settings")
    assert win.stack.currentWidget() is win.settings
    win.close()


def test_discover_needs_warning_acceptance(library, qapp, monkeypatch):
    from limpaper.gui import app as gapp

    win = gapp.MainWindow()
    monkeypatch.setattr(gapp.WarningDialog, "exec", lambda self: gapp.WarningDialog.Rejected)
    win.show_page("discover")
    assert win.stack.currentWidget() is win.library
    assert not win.lp.settings.online_warning_accepted
    win.close()
