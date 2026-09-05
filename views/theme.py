"""Apple-inspired light appearance using locally installed fonts."""

from PyQt5.QtGui import QFont, QFontDatabase
import re


def interface_font():
    families = set(QFontDatabase().families())
    for family in ("PingFang SC", "Microsoft YaHei UI", "Segoe UI"):
        if family in families:
            font = QFont(family)
            font.setPointSizeF(11)
            font.setWeight(QFont.Normal)
            font.setStyleHint(QFont.SansSerif)
            return font
    return QFontDatabase.systemFont(QFontDatabase.GeneralFont)


def typography_stylesheet():
    available = set(QFontDatabase().families())
    body = interface_font().family()
    latin = "Segoe UI" if "Segoe UI" in available else body
    return (
        f"QWidget {{ font-family: '{body}'; font-size: 15px; font-weight: 400; }}\n"
        f"QLabel#appTitle, QSpinBox {{ font-family: '{latin}'; }}\n"
    )

LIGHT_THEME = """
QWidget { color: #242426; }
QMainWindow { background: #e9edf5; }
QWidget#glassSidebar { background: rgba(255, 255, 255, 145);
    border: 1px solid rgba(255, 255, 255, 210); border-radius: 16px; }
QWidget#glassCanvas { background: rgba(255, 255, 255, 105);
    border: 1px solid rgba(255, 255, 255, 180); border-radius: 16px; }
QWidget#settingsContent { background: transparent; }
QWidget#appHeader { background: rgba(255, 255, 255, 150);
    border: 1px solid rgba(255, 255, 255, 220); border-radius: 14px; }
QLabel#appTitle { font-size: 19px; font-weight: 600; }
QLabel#sidebarHeading { font-size: 13px; font-weight: 600; color: #77777d; padding: 0 20px 8px; }
QLabel#emptyTitle { font-size: 27px; font-weight: 600; }
QLabel#emptyDescription { color: #85858b; font-size: 15px; padding-bottom: 12px; }
QLabel#interactionHint { color: #85858b; font-size: 13px; padding-top: 8px; }
QLabel[typography="method"] { font-size: 15px; font-weight: 600; }
QWidget#emptyCanvas { background: transparent; }
QScrollArea { border: none; background: transparent; }
QGroupBox { background: transparent; border: none; border-top: 1px solid rgba(130, 147, 170, 45);
    margin-top: 17px; padding: 12px 0 0; }
QGroupBox::title { subcontrol-origin: margin; left: 0; padding: 0 6px 0 0;
    color: #77777d; font-size: 13px; font-weight: 600; }
QPushButton { background: rgba(255, 255, 255, 175); border: 1px solid rgba(255, 255, 255, 235); border-radius: 7px;
    padding: 5px 12px; min-height: 20px; }
QPushButton:hover { background: #f4f4f6; border-color: #b6b6bf; }
QPushButton:pressed, QPushButton:checked { background: #e4e4e9; border-color: #c4c4cd; }
QPushButton:focus { border-color: #007aff; }
QPushButton:disabled { background: #eeeef0; color: #aaaab0; border-color: #dedee2; }
QPushButton#primaryAction { background: #007aff; color: white; border-color: #007aff; font-weight: 600; }
QPushButton#primaryAction:hover { background: #0070eb; border-color: #0070eb; }
QPushButton#primaryAction:pressed { background: #005ec4; border-color: #005ec4; }
QPushButton#primaryAction:focus { border-color: #003e85; }
QPushButton#primaryAction:disabled { background: #b7d8ff; border-color: #b7d8ff; }
QPushButton[destructive="true"] { color: #c63731; }
QPushButton[destructive="true"]:disabled { color: #aaaab0; }
QRadioButton[segmented="true"] { background: rgba(145, 160, 190, 35); border: 1px solid transparent;
    border-radius: 6px; padding: 5px 6px; color: #686870; }
QRadioButton[segmented="true"]::indicator { width: 0; height: 0; border: none; background: transparent; }
QRadioButton[segmented="true"]:checked { background: white; border-color: #d8d8dc; color: #242426; }
QRadioButton[segmented="true"]:hover { background: #ededf0; }
QRadioButton[segmented="true"]:focus { border-color: #007aff; }
QRadioButton, QCheckBox { spacing: 6px; }
QLineEdit, QSpinBox, QComboBox { background: rgba(255, 255, 255, 185); border: 1px solid rgba(160, 175, 195, 90);
    border-radius: 6px; padding: 4px 6px; min-height: 20px; selection-background-color: #007aff; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #007aff; }
QComboBox { border-radius: 8px; padding: 5px 36px 5px 10px; min-height: 22px; }
QComboBox:hover { background: #fcfcfe; border-color: #b8b8c0; }
QComboBox:on { background: #f2f6ff; border-color: #007aff; }
QComboBox::drop-down { subcontrol-origin: border; subcontrol-position: top right;
    width: 32px; border: none; background: transparent; }
QComboBox::down-arrow { image: none; border: none; width: 0; height: 0; }
NumberBox { border-radius: 8px; padding: 5px 36px 5px 10px; min-height: 22px; }
NumberBox::up-button { subcontrol-origin: border; subcontrol-position: top right;
    width: 32px; height: 16px; border: none; background: transparent; }
NumberBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right;
    width: 32px; height: 16px; border: none; background: transparent; }
NumberBox::up-arrow, NumberBox::down-arrow { image: none; width: 0; height: 0; }
QLineEdit:read-only { color: #77777d; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled { color: #aaaab0; background: #eeeef0; }
QListWidget { background: rgba(255, 255, 255, 150); border: 1px solid rgba(255, 255, 255, 210); border-radius: 7px; padding: 4px; }
QListWidget::item { padding: 5px; border-radius: 4px; }
QListWidget::item:selected { background: #dceaff; color: #005bbf; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: rgba(145, 160, 190, 35); color: #6e6e73; padding: 7px 20px;
    margin: 0 2px 8px 0; border: 1px solid transparent; border-radius: 6px; }
QTabBar::tab:selected { background: rgba(255, 255, 255, 220); color: #242426; border-color: #d8d8dc; font-weight: 600; }
QTabBar::tab:hover { color: #007aff; }
QTabWidget#inspectorTabs { background: transparent; }
QTabWidget#inspectorTabs::pane { background: transparent; }
QTabWidget#inspectorTabs::tab-bar { alignment: center; }
QSplitter::handle { background: transparent; }
QSplitter::handle:hover { background: rgba(255, 255, 255, 75); border-radius: 5px; }
QStatusBar { background: #f8f8fa; color: #85858b; border-top: 1px solid rgba(130, 147, 170, 45); font-size: 13px; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px 0; }
QScrollBar::handle:vertical { background: #c7c7cc; border-radius: 4px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: #aeaeb2; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { background: #ffffff; color: #242426; border: 1px solid #d8d8dc; padding: 6px; }
QMenu { background: #fafbfe; color: #242426; border: 1px solid #d8d8dc; padding: 5px; }
QMenu::item { padding: 7px 24px; border-radius: 5px; }
QMenu::item:selected { background: #007aff; color: white; }
"""

# Shared geometry keeps the two appearances identical in layout.
_DARK_COLORS = {
    "#242426": "#eef0f5", "#e9edf5": "#151922", "#77777d": "#b5bfce",
    "#85858b": "#b5bfce", "#686870": "#b5bfce", "#6e6e73": "#b5bfce",
    "#ffffff": "#303846", "#fafbfe": "#292f3b", "#f8f8fa": "#202632",
    "#f4f4f6": "#414b5c", "#e4e4e9": "#414b5c", "#ededf0": "#414b5c",
    "#fcfcfe": "#414b5c", "#f2f6ff": "#34475e", "#dceaff": "#34475e",
    "#005bbf": "#a6cfff", "#c63731": "#ff8b85", "#aaaab0": "#8d97a7",
    "#eeeef0": "#303744", "#dedee2": "#485363", "#d8d8dc": "#596474",
    "#b6b6bf": "#657185", "#b8b8c0": "#657185", "#c4c4cd": "#657185",
    "#c7c7cc": "#657185", "#aeaeb2": "#8693a7", "#b7d8ff": "#35587c",
}
DARK_THEME = re.sub(r"#[0-9a-fA-F]{6}",
                    lambda match: _DARK_COLORS.get(match[0], match[0]), LIGHT_THEME)
DARK_THEME = DARK_THEME.replace("rgba(255, 255, 255,", "rgba(35, 43, 57,")
DARK_THEME = DARK_THEME.replace("background: white;", "background: #414b5c;")
DARK_THEME += """
QWidget#glassSidebar, QWidget#glassCanvas, QWidget#appHeader {
    border: 1px solid rgba(180, 202, 235, 45); }
QGroupBox { border-top: 1px solid rgba(180, 202, 235, 40); }
QPushButton { border-color: rgba(180, 202, 235, 65); }
QPushButton:focus { border-color: #409cff; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #409cff; }
"""

