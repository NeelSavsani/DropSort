"""Modern QSS stylesheets and aesthetic design tokens for the PySide6 GUI."""

import re

THEME_COLORS = {
    "bg_darkest": "#0b0e14",
    "bg_main": "#0f141c",
    "bg_card": "#18202c",
    "bg_card_hover": "#212c3d",
    "bg_input": "#131b26",
    "border": "#283548",
    "border_focus": "#6366f1",
    "text_primary": "#f3f4f6",
    "text_secondary": "#9ca3af",
    "text_muted": "#6b7280",
    "primary": "#6366f1",
    "primary_hover": "#4f46e5",
    "primary_light": "rgba(99, 102, 241, 0.15)",
    "success": "#10b981",
    "success_hover": "#059669",
    "success_light": "rgba(16, 185, 129, 0.15)",
    "warning": "#f59e0b",
    "warning_light": "rgba(245, 158, 11, 0.15)",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "danger_light": "rgba(239, 68, 68, 0.15)",
    "info": "#06b6d4",
    "info_light": "rgba(6, 182, 212, 0.15)",
}

MAIN_STYLESHEET = """
/* Global Reset & Base */
QWidget {
    background-color: #0f141c;
    color: #f3f4f6;
    font-family: 'Segoe UI', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13px;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
}

QMainWindow {
    background-color: #0b0e14;
}

/* Sidebar & Navigation */
#sidebar {
    background-color: #0b0e14;
    border-right: 1px solid #283548;
    min-width: 220px;
    max-width: 220px;
}

#sidebarHeader {
    padding: 20px 16px 12px 16px;
}

QPushButton#themeToggle {
    background-color: #131b26;
    color: #cbd5e1;
    border: 1px solid #2e3d52;
    border-radius: 9px;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 600;
    text-align: left;
}

QPushButton#themeToggle:hover {
    background-color: #212c3d;
    color: #ffffff;
    border-color: #6366f1;
}

#navBtn {
    background-color: transparent;
    color: #9ca3af;
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 500;
    text-align: left;
    margin: 3px 12px;
}

#navBtn:hover {
    background-color: #18202c;
    color: #ffffff;
}

#navBtn:checked {
    background-color: #6366f1;
    color: #ffffff;
    font-weight: 600;
}

/* Content Area */
#contentArea {
    background-color: #0f141c;
}

/* Card Containers */
.CardWidget {
    background-color: #18202c;
    border: 1px solid #283548;
    border-radius: 12px;
    padding: 16px;
}

.CardWidget:hover {
    border-color: #3b4d66;
}

/* Push Buttons */
QPushButton {
    background-color: #212c3d;
    color: #f3f4f6;
    border: 1px solid #283548;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
    min-height: 28px;
}

QPushButton:hover {
    background-color: #2b394f;
    border-color: #4f607d;
}

QPushButton:pressed {
    background-color: #1a2332;
}

QPushButton:disabled {
    background-color: #131b26;
    color: #4b5563;
    border-color: #1f2937;
}

/* Primary Action Buttons */
QPushButton#primaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #4f46e5);
    color: #ffffff;
    border: 1px solid #4f46e5;
    font-weight: 700;
    padding: 8px 18px;
}

QPushButton#primaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #4338ca);
    border-color: #4338ca;
}

QPushButton#primaryBtn:pressed {
    background-color: #3730a3;
}

/* Success Buttons */
QPushButton#successBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
    color: #ffffff;
    border: 1px solid #059669;
    font-weight: 700;
    padding: 8px 18px;
}

QPushButton#successBtn:hover {
    background-color: #059669;
    border-color: #047857;
}

QPushButton#successBtn:pressed {
    background-color: #065f46;
}

/* Danger Buttons */
QPushButton#dangerBtn {
    background-color: #ef4444;
    color: #ffffff;
    border: 1px solid #dc2626;
    font-weight: 600;
    padding: 6px 14px;
}

QPushButton#dangerBtn:hover {
    background-color: #dc2626;
}

QPushButton#dangerBtn:pressed {
    background-color: #b91c1c;
}

/* Subtle Secondary Buttons */
QPushButton#subtleBtn {
    background-color: #161f2c;
    color: #cbd5e1;
    border: 1px solid #2e3d52;
    padding: 6px 14px;
}

QPushButton#subtleBtn:hover {
    background-color: #212d3e;
    color: #ffffff;
    border-color: #4f607d;
}

/* Line Edits & Inputs */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #131b26;
    color: #f3f4f6;
    border: 1px solid #283548;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    min-height: 22px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #6366f1;
    background-color: #182333;
}

/* ComboBox */
QComboBox {
    padding-right: 20px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px;
    border-left: none;
}

QComboBox QAbstractItemView {
    background-color: #18202c;
    color: #f3f4f6;
    border: 1px solid #283548;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
    border-radius: 8px;
    padding: 4px;
}

/* Table View */
QTableWidget, QTableView {
    background-color: #131b26;
    color: #f3f4f6;
    gridline-color: #1e293b;
    border: 1px solid #283548;
    border-radius: 10px;
    alternate-background-color: #101721;
}

QTableWidget::item, QTableView::item {
    padding: 8px 10px;
    border-bottom: 1px solid #1e293b;
}

QTableWidget::item:selected, QTableView::item:selected {
    background-color: #24324a;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #18202c;
    color: #9ca3af;
    padding: 10px;
    font-weight: 600;
    font-size: 12px;
    border: none;
    border-bottom: 1px solid #283548;
    text-transform: uppercase;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #0f141c;
    width: 8px;
    margin: 0;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #283548;
    min-height: 25px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #3b4d66;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #0f141c;
    height: 8px;
    margin: 0;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #283548;
    min-width: 25px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #3b4d66;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* CheckBox */
QCheckBox {
    color: #f3f4f6;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #283548;
    background-color: #131b26;
}

QCheckBox::indicator:hover {
    border-color: #6366f1;
}

QCheckBox::indicator:checked {
    background-color: #6366f1;
    border-color: #6366f1;
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><polyline points='20 6 9 17 4 12'></polyline></svg>");
}

/* Progress Bar */
QProgressBar {
    background-color: #131b26;
    border: 1px solid #283548;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    color: #f3f4f6;
    font-size: 11px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #38bdf8);
    border-radius: 5px;
}

/* Group Box */
QGroupBox {
    border: 1px solid #283548;
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 16px;
    font-weight: 600;
    color: #f3f4f6;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #9ca3af;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #283548;
    border-radius: 10px;
    background-color: #18202c;
    padding: 12px;
}

QTabBar::tab {
    background-color: #131b26;
    color: #9ca3af;
    border: 1px solid #283548;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #18202c;
    color: #ffffff;
    border-bottom: 2px solid #6366f1;
    font-weight: 600;
}

QTabBar::tab:hover:!selected {
    background-color: #1b2535;
    color: #f3f4f6;
}
"""

# A calm, high-contrast daytime palette.  Keeping the component geometry the
# same in both themes makes switching instant and avoids visual jumps.
_LIGHT_REPLACEMENTS = {
    "#0b0e14": "#f4f7fb", "#0f141c": "#f8fafc", "#18202c": "#ffffff",
    "#212c3d": "#edf2f7", "#131b26": "#f7f9fc", "#141b24": "#f8fafc",
    "#101721": "#f1f5f9", "#1a2332": "#dfe7f1", "#1b2535": "#eef2f7",
    "#1c2534": "#f8fafc", "#1e293b": "#e2e8f0", "#24324a": "#e0e7ff",
    "#283548": "#d7e0ea", "#2e3d52": "#c7d2e1", "#3b4d66": "#aebfd2",
    "#4f607d": "#94a9c0", "#4b5563": "#64748b", "#6b7280": "#64748b",
    "#9ca3af": "#52657a", "#cbd5e1": "#334155", "#e5e7eb": "#1e293b",
    "#f3f4f6": "#10213a", "#ffffff": "#ffffff", "#182333": "#eef2ff",
}


def get_stylesheet(dark_mode: bool = True) -> str:
    """Return the application stylesheet for the requested appearance."""
    if dark_mode:
        return MAIN_STYLESHEET
    return translate_inline_stylesheet(MAIN_STYLESHEET, dark_mode=False)


def translate_inline_stylesheet(stylesheet: str, dark_mode: bool) -> str:
    """Translate legacy, widget-local colours to the requested palette.

    Several specialised widgets intentionally have local QSS.  This lets the
    appearance switch update them too, without weakening their component styles.
    """
    if dark_mode:
        return stylesheet
    # Regex performs a one-pass substitution, so a new light value can never
    # be substituted again if it happens to resemble a dark palette token.
    matcher = re.compile("|".join(re.escape(color) for color in _LIGHT_REPLACEMENTS))
    return matcher.sub(lambda match: _LIGHT_REPLACEMENTS[match.group(0)], stylesheet)
