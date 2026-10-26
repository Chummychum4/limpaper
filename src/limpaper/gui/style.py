"""Colours and the Qt stylesheet for the GUI."""

BG = "#0b0d12"
SURFACE = "#12151c"
SURFACE_2 = "#181c25"
SURFACE_3 = "#202532"
BORDER = "#252b38"
TEXT = "#e8ebf2"
MUTED = "#8a93a6"
FAINT = "#5b6375"
ACCENT = "#8b6cff"
ACCENT_2 = "#3fd0ff"
GOOD = "#3ddc97"
WARN = "#ffb547"
WARN_BG = "#2a1f0a"
DANGER = "#ff5c7a"

QSS = f"""
* {{
    font-size: 13px;
    color: {TEXT};
    outline: none;
}}
QMainWindow, #root {{ background: {BG}; }}
QToolTip {{
    background: {SURFACE_3}; color: {TEXT};
    border: 1px solid {BORDER}; padding: 6px 8px; border-radius: 6px;
}}

/* ── Sidebar ─────────────────────────────────────────────── */
#sidebar {{
    background: {SURFACE};
    border-right: 1px solid {BORDER};
}}
#navButton {{
    text-align: left;
    padding: 10px 14px;
    border: none;
    border-radius: 10px;
    color: {MUTED};
    font-size: 14px;
    font-weight: 500;
    background: transparent;
}}
#navButton:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
#navButton:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(139,108,255,0.28), stop:1 rgba(63,208,255,0.10));
    color: {TEXT};
}}
#sectionLabel {{
    color: {FAINT}; font-size: 11px; font-weight: 700;
    letter-spacing: 1px; padding: 0 6px;
}}
#nowCard {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
#nowTitle {{ font-weight: 600; font-size: 13px; }}
#nowSub {{ color: {MUTED}; font-size: 11px; }}

/* ── Page chrome ─────────────────────────────────────────── */
#pageTitle {{ font-size: 24px; font-weight: 700; }}
#pageSub {{ color: {MUTED}; font-size: 13px; }}
#muted {{ color: {MUTED}; }}

QLineEdit, QComboBox, QSpinBox {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 12px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; border: 1px solid {BORDER};
    selection-background-color: {SURFACE_3}; padding: 4px;
}}

QPushButton {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 500;
}}
QPushButton:hover {{ background: {SURFACE_3}; border-color: #323a4c; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {FAINT}; background: {SURFACE}; }}
QPushButton#primary {{
    border: none;
    color: white;
    font-weight: 600;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT}, stop:1 #5b8cff);
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9d82ff, stop:1 #6f9bff);
}}
QPushButton#primary:disabled {{ background: {SURFACE_3}; color: {FAINT}; }}
QPushButton#danger {{ color: {DANGER}; }}
QPushButton#ghost {{ background: transparent; border: none; color: {MUTED}; }}
QPushButton#ghost:hover {{ color: {TEXT}; }}

#chip {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 15px;
    padding: 5px 14px;
    color: {MUTED};
}}
#chip:hover {{ color: {TEXT}; border-color: #323a4c; }}
#chip:checked {{
    color: white;
    border: 1px solid {ACCENT};
    background: rgba(139,108,255,0.22);
}}

#segment {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    padding: 8px 16px;
    border-radius: 0;
    color: {MUTED};
}}
#segment[first="true"] {{ border-top-left-radius: 10px; border-bottom-left-radius: 10px; }}
#segment[last="true"] {{ border-top-right-radius: 10px; border-bottom-right-radius: 10px; }}
#segment:checked {{ background: {SURFACE_3}; color: {TEXT}; border-color: {ACCENT}; }}

/* ── Grids ───────────────────────────────────────────────── */
QListView {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {SURFACE_3}; border-radius: 4px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: #343b4d; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: none; height: 0;
}}
QScrollBar:horizontal {{ height: 0; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ── Discover ────────────────────────────────────────────── */
#warningBanner {{
    background: {WARN_BG};
    border: 1px solid #6b4c12;
    border-radius: 12px;
}}
#warningText {{ color: {WARN}; }}
#detail {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
#detailTitle {{ font-size: 17px; font-weight: 700; }}
#badge {{
    background: {SURFACE_3};
    border-radius: 8px;
    padding: 3px 8px;
    color: {MUTED};
    font-size: 11px;
    font-weight: 600;
}}
QProgressBar {{
    background: {SURFACE_2};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    border-radius: 4px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 {ACCENT_2});
}}

/* ── Settings ────────────────────────────────────────────── */
#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
#cardTitle {{ font-size: 15px; font-weight: 700; }}
QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{
    width: 18px; height: 18px; border-radius: 5px;
    border: 1px solid #3a4256; background: {SURFACE_2};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

/* ── Dialogs & toasts ────────────────────────────────────── */
QDialog {{ background: {SURFACE}; }}
QMenu {{
    background: {SURFACE_2}; border: 1px solid {BORDER};
    border-radius: 10px; padding: 6px;
}}
QMenu::item {{ padding: 7px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {SURFACE_3}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
QMessageBox {{ background: {SURFACE}; }}
#toast {{
    background: {SURFACE_3};
    border: 1px solid #343b4d;
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: 500;
}}
#emptyTitle {{ font-size: 18px; font-weight: 700; }}
"""
