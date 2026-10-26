# limpaper.exe: opens the GUI; with arguments it runs that command silently
# (e.g. `limpaper.exe restore` from the login startup entry).
import sys

from limpaper.cli import main_gui

sys.exit(main_gui())
