# PyInstaller spec: two executables sharing one folder.
#   limpaper.exe      windowed, opens the GUI
#   limpaper-cli.exe  console, for `limpaper-cli tui` and the other commands
# Build from the repository root:  pyinstaller packaging/windows/limpaper.spec

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent.parent
ICON = str(ROOT / "src" / "limpaper" / "assets" / "icon.ico")

PKG = ROOT / "src" / "limpaper"
# Listed explicitly so the build works whether or not limpaper is pip-installed
datas = [
    (str(PKG / "assets"), "limpaper/assets"),
    (str(PKG / "tui" / "app.tcss"), "limpaper/tui"),
] + collect_data_files("textual")
hidden = collect_submodules("limpaper") + collect_submodules("textual.widgets")
# Large Qt pieces limpaper never touches
excludes = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtQuick3D", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtGraphs", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtDesigner", "PySide6.QtBluetooth", "PySide6.QtLocation", "PySide6.QtPositioning",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtTextToSpeech", "PySide6.QtWebSockets",
    "tkinter",
]


def analysis(script):
    return Analysis(
        [str(ROOT / "packaging" / "windows" / script)],
        pathex=[str(ROOT / "src")],
        datas=datas,
        hiddenimports=hidden,
        excludes=excludes,
        noarchive=False,
    )


gui = analysis("entry_gui.py")
cli = analysis("entry_cli.py")

gui_exe = EXE(
    PYZ(gui.pure), gui.scripts, [],
    exclude_binaries=True, name="limpaper", icon=ICON,
    console=False, upx=False,
)
cli_exe = EXE(
    PYZ(cli.pure), cli.scripts, [],
    exclude_binaries=True, name="limpaper-cli", icon=ICON,
    console=True, upx=False,
)

coll = COLLECT(
    gui_exe, gui.binaries, gui.datas,
    cli_exe, cli.binaries, cli.datas,
    name="limpaper", upx=False,
)
