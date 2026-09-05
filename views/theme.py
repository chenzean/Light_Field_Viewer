"""Apple-style appearance: one geometry, two colour palettes.

The stylesheet below is a ``string.Template``. Geometry (radii, padding,
metrics) is written once; only the ``$token`` colours differ between the light
and dark appearances, so the two can never drift apart.
"""

from string import Template

from PyQt5.QtGui import QColor, QFont, QFontDatabase

# Radii, in the spirit of macOS: small controls 6, containers 10, panels 12.
RADIUS_CONTROL = 6
RADIUS_CARD = 10

# Latin first, CJK second: Qt falls through per glyph, so Chinese picks up
# YaHei while Latin and digits keep the tighter UI face. The Segoe UI Variable
# faces are deliberately absent — Qt 5 renders them with loose, almost
# monospaced spacing, which reads nothing like SF.
_LATIN_FACES = ("Segoe UI", "Helvetica Neue", "Arial")
_CJK_FACES = ("PingFang SC", "Microsoft YaHei UI", "Microsoft YaHei", "Yu Gothic UI")


def _families():
    available = set(QFontDatabase().families())
    stack = [f for f in _LATIN_FACES if f in available][:1]
    stack += [f for f in _CJK_FACES if f in available][:1]
    return stack


def interface_font():
    """Base application font used by every widget unless it says otherwise."""
    font = QFont()
    stack = _families()
    if stack:
        font.setFamily(stack[0])
    font.setPointSizeF(10)
    font.setWeight(QFont.Normal)
    font.setStyleHint(QFont.SansSerif)
    return font


def apply_interface_font(app):
    """Set the font on the application, not just the window.

    Any ``font-size`` rule in a style sheet makes Qt rebuild that widget's font
    from the *application* font, so a font set only on the main window is
    silently dropped and the UI falls back to the locale default (SimSun here).
    """
    if app is not None:
        app.setFont(interface_font())


def typography_stylesheet():
    """Sizes and weights. The family is repeated here for the same reason."""
    stack = _families()
    family = f'font-family: "{stack[0]}"; ' if stack else ""
    return (
        f"QWidget {{ {family}font-size: 13px; font-weight: 400; }}\n"
        "QToolTip, QStatusBar, QLabel#interactionHint { font-size: 12px; }\n"
    )


# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------
LIGHT = {
    "window": "#e6e6e9",
    "toolbar": "#f5f5f7",
    "sidebar": "rgba(250, 250, 252, 170)",
    "canvas": "#ffffff",
    "card": "rgba(255, 255, 255, 235)",
    "control": "#ffffff",
    "control_hover": "#f4f4f6",
    "control_press": "#e9e9ec",
    "track": "rgba(120, 120, 128, 30)",
    "track_hover": "rgba(120, 120, 128, 52)",
    "thumb": "#ffffff",
    "menu": "#fbfbfd",
    "image_bed": "#f2f2f4",
    "text": "#1d1d1f",
    "text_2": "#6e6e73",
    "text_3": "#8e8e93",
    "text_off": "#b4b4ba",
    "line": "rgba(0, 0, 0, 26)",
    "border": "#d4d4d9",
    "border_soft": "rgba(0, 0, 0, 20)",
    "accent": "#007aff",
    "accent_hover": "#0a6fe4",
    "accent_press": "#005ec4",
    "on_accent": "#ffffff",
    "accent_off": "#a8d2ff",
    "danger": "#d70015",
    "scroll": "rgba(0, 0, 0, 55)",
    "scroll_hover": "rgba(0, 0, 0, 95)",
}

DARK = {
    "window": "#1c1c1e",
    "toolbar": "#282829",
    "sidebar": "rgba(46, 46, 49, 175)",
    "canvas": "#1e1e20",
    "card": "rgba(52, 52, 55, 215)",
    "control": "#3a3a3c",
    "control_hover": "#464648",
    "control_press": "#525254",
    "track": "rgba(120, 120, 128, 64)",
    "track_hover": "rgba(120, 120, 128, 96)",
    "thumb": "#5d5d61",
    "menu": "#2c2c2e",
    "image_bed": "#2a2a2c",
    "text": "#f2f2f7",
    "text_2": "#a1a1a6",
    "text_3": "#8e8e93",
    "text_off": "#5f5f63",
    "line": "rgba(255, 255, 255, 30)",
    "border": "#4b4b4e",
    "border_soft": "rgba(255, 255, 255, 24)",
    "accent": "#0a84ff",
    "accent_hover": "#3b9bff",
    "accent_press": "#0069d9",
    "on_accent": "#ffffff",
    "accent_off": "rgba(10, 132, 255, 90)",
    "danger": "#ff453a",
    "scroll": "rgba(255, 255, 255, 60)",
    "scroll_hover": "rgba(255, 255, 255, 105)",
}

# Backdrop colours for GlassBackground, kept beside the palettes they match.
BACKDROP = {False: LIGHT["window"], True: DARK["window"]}

# The appearance currently on screen. Widgets that paint their own glyphs read
# from here instead of each keeping a copy of the palette.
_ACTIVE = dict(LIGHT)


def set_active(dark):
    _ACTIVE.clear()
    _ACTIVE.update(DARK if dark else LIGHT)


def color(token):
    """QColor for a palette token in the appearance currently on screen.

    QColor's string constructor does not understand CSS ``rgba()`` — it returns
    an invalid (opaque black) colour — so the functional form the style sheet
    needs has to be parsed here by hand.
    """
    value = _ACTIVE[token].strip()
    if not value.startswith(("rgb(", "rgba(")):
        return QColor(value)
    parts = [int(float(p)) for p in
             value[value.index("(") + 1:value.rindex(")")].split(",")]
    red, green, blue = parts[:3]
    return QColor(red, green, blue, parts[3] if len(parts) > 3 else 255)


_STYLESHEET = Template("""
/* ---- surfaces ------------------------------------------------------- */
QWidget { color: $text; }
QMainWindow { background: $window; }
QWidget#workspace { background: transparent; }
QWidget#appHeader { background: $toolbar; border: none;
    border-bottom: 1px solid $line; }
QWidget#glassSidebar { background: $sidebar; border: none;
    border-right: 1px solid $line; }
QWidget#glassCanvas { background: $canvas; border: none; }
QWidget#settingsContent, QWidget#emptyCanvas { background: transparent; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QSplitter::handle { background: $canvas; }

/* ---- typography ----------------------------------------------------- */
QLabel#appTitle { font-size: 14px; font-weight: 600; }
QLabel#rowLabel { color: $text; }
QLabel#emptyTitle { font-size: 22px; font-weight: 600; }
QLabel#emptyDescription { color: $text_2; font-size: 13px; }
QLabel#interactionHint { color: $text_3; padding-top: 6px; }
QLabel[typography="method"] { font-size: 12px; font-weight: 600; color: $text; }
QLabel[typography="caption"] { font-size: 11px; font-weight: 600; color: $text_2; }
QLabel:disabled { color: $text_off; }

/* ---- grouped cards -------------------------------------------------- */
QGroupBox { background: $card; border: 1px solid $border_soft;
    border-radius: ${card_radius}px; margin-top: 19px; padding: 0; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
    left: 2px; padding: 0 0 5px 0; color: $text_2;
    font-size: 11px; font-weight: 600; background: transparent; }
QFrame#rowSeparator { background: $line; border: none; margin-left: 12px; }
QWidget#formRow { background: transparent; }

/* ---- buttons -------------------------------------------------------- */
QPushButton { background: $control; border: 1px solid $border;
    border-radius: ${control_radius}px; padding: 4px 12px; min-height: 21px;
    color: $text; }
QPushButton:hover { background: $control_hover; }
QPushButton:pressed, QPushButton:checked { background: $control_press; }
QPushButton:focus { border-color: $accent; }
QPushButton:disabled { background: $control; color: $text_off;
    border-color: $border_soft; }
QPushButton#primaryAction { background: $accent; color: $on_accent;
    border-color: $accent; font-weight: 600; }
QPushButton#primaryAction:hover { background: $accent_hover;
    border-color: $accent_hover; }
QPushButton#primaryAction:pressed { background: $accent_press;
    border-color: $accent_press; }
QPushButton#primaryAction:disabled { background: $accent_off;
    border-color: $accent_off; color: $on_accent; }
QPushButton[destructive="true"] { color: $danger; }
QPushButton[destructive="true"]:disabled { color: $text_off; }

/* Toolbar buttons are borderless until hovered, as in a unified titlebar. */
QWidget#appHeader QPushButton { background: transparent;
    border: 1px solid transparent; padding: 4px 11px; }
QWidget#appHeader QPushButton:hover { background: $track; }
QWidget#appHeader QPushButton:pressed,
QWidget#appHeader QPushButton:checked { background: $track_hover; }
QWidget#appHeader QPushButton:focus { border-color: $accent; }
QWidget#appHeader QPushButton#primaryAction { background: $accent;
    border-color: $accent; color: $on_accent; }
QWidget#appHeader QPushButton#primaryAction:hover { background: $accent_hover;
    border-color: $accent_hover; }
QWidget#appHeader QPushButton#primaryAction:pressed { background: $accent_press;
    border-color: $accent_press; }
QWidget#appHeader QPushButton#primaryAction:disabled { background: $accent_off;
    border-color: $accent_off; color: $on_accent; }
QPushButton#sidebarToggle { padding: 4px 6px; }
QPushButton#colorWell { padding: 2px 6px; }
QPushButton::menu-indicator { image: none; width: 0; height: 0; }

/* ---- segmented controls ---------------------------------------------
   The selected segment's thumb is painted by SegmentedControl so it can
   slide; leaving a :checked background here would flash under the animation,
   and a heavier :checked font would move the thumb's target mid-flight. */
QWidget#segmented { background: $track; border-radius: 8px; }
QRadioButton[segmented="true"] { background: transparent;
    border: none; border-radius: ${control_radius}px;
    padding: 3px 8px; color: $text_2; }
QRadioButton[segmented="true"]:hover { color: $text; }
QRadioButton[segmented="true"]:checked { background: transparent; color: $text; }
QRadioButton[segmented="true"]:disabled { color: $text_off; }
QRadioButton[segmented="true"]::indicator { width: 0; height: 0;
    border: none; background: transparent; margin: 0; }

/* ---- checkboxes and radios ------------------------------------------
   The left padding is room for the focus halo, which Qt would otherwise
   clip against the widget's own edge. */
QCheckBox, QRadioButton { spacing: 7px; background: transparent;
    padding: 3px 0 3px 4px; }
QCheckBox::indicator, QRadioButton::indicator { width: 14px; height: 14px;
    border: 1px solid $border; background: $control; }
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: $text_3; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: $accent; border-color: $accent; }
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {
    background: $control; border-color: $border_soft; }
QCheckBox::indicator:checked:disabled,
QRadioButton::indicator:checked:disabled { background: $accent_off;
    border-color: $accent_off; }
QCheckBox:disabled, QRadioButton:disabled { color: $text_off; }

/* ---- text fields, steppers, pop-up buttons -------------------------- */
QLineEdit, QSpinBox, QComboBox, NumberBox { background: $control;
    border: 1px solid $border; border-radius: ${control_radius}px;
    padding: 3px 8px; min-height: 21px; color: $text;
    selection-background-color: $accent; selection-color: $on_accent; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, NumberBox:focus {
    border-color: $accent; }
QLineEdit:read-only { color: $text_2; background: $control; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled,
NumberBox:disabled { color: $text_off; background: $control;
    border-color: $border_soft; }
/* The drop-down / stepper sub-controls already reserve their own width, so the
   trailing padding here stays small or the edit field is squeezed to nothing. */
QComboBox, NumberBox { padding: 3px 7px 3px 9px; min-height: 22px; }
QComboBox:hover, NumberBox:hover { background: $control_hover; }
QComboBox:on { border-color: $accent; }
QComboBox::drop-down { subcontrol-origin: border;
    subcontrol-position: top right; width: 26px; border: none;
    background: transparent; }
QComboBox::down-arrow { image: none; border: none; width: 0; height: 0; }
NumberBox::up-button { subcontrol-origin: border;
    subcontrol-position: top right; width: 26px; height: 14px; border: none;
    background: transparent; }
NumberBox::down-button { subcontrol-origin: border;
    subcontrol-position: bottom right; width: 26px; height: 14px;
    border: none; background: transparent; }
NumberBox::up-arrow, NumberBox::down-arrow { image: none; width: 0; height: 0; }

/* ---- lists ----------------------------------------------------------- */
QListWidget { background: $control; border: 1px solid $border;
    border-radius: 8px; padding: 3px; outline: none; }
QListWidget::item { padding: 4px 6px; border-radius: 5px; min-height: 20px;
    color: $text; }
QListWidget::item:hover { background: $track; }
QListWidget::item:selected { background: $accent; color: $on_accent; }
/* Lists that live inside a grouped card carry no border of their own. */
QListWidget#cardList { background: transparent; border: none; border-radius: 0;
    padding: 0 6px; }
QListWidget#cardList::item { padding: 4px 6px; }
QListWidget::indicator { width: 14px; height: 14px; border-radius: 4px;
    border: 1px solid $border; background: $control; margin-right: 2px; }
QListWidget::indicator:checked { background: $accent; border-color: $accent; }

/* ---- tabs ------------------------------------------------------------
   A QTabBar always spans the full width of its QTabWidget, so painting a
   track on it would stretch the pill across the panel. The canvas tabs stay
   borderless; the sidebar builds a real segmented control instead. */
QTabWidget::pane { border: none; background: transparent; }
QTabBar { background: transparent; qproperty-drawBase: 0; }
QTabBar::tab { background: transparent; border: 1px solid transparent;
    border-radius: ${control_radius}px; padding: 4px 13px; margin: 0 3px 0 0;
    color: $text_2; }
QTabBar::tab:hover { color: $text; background: $track; }
QTabBar::tab:selected { background: $track_hover; border-color: transparent;
    color: $text; font-weight: 600; }
QTabWidget#canvasTabs::tab-bar { alignment: left; }

/* ---- scrollbars ------------------------------------------------------ */
QScrollBar:vertical { background: transparent; width: 11px; margin: 2px 0; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 3px;
    min-height: 30px; margin: 0 4px; }
QScrollBar::handle:vertical:hover { background: $scroll_hover; }
QScrollBar:horizontal { background: transparent; height: 11px; margin: 0 2px; }
QScrollBar::handle:horizontal { background: $scroll; border-radius: 3px;
    min-width: 30px; margin: 4px 0; }
QScrollBar::handle:horizontal:hover { background: $scroll_hover; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ---- chrome ---------------------------------------------------------- */
QStatusBar { background: transparent; color: $text_3;
    border-top: 1px solid $line; }
QStatusBar::item { border: none; }
QToolTip { background: $menu; color: $text; border: 1px solid $border_soft;
    border-radius: ${control_radius}px; padding: 5px 8px; }
QMenu { background: $menu; color: $text; border: 1px solid $border_soft;
    border-radius: 8px; padding: 4px; }
QMenu::item { padding: 5px 26px 5px 20px; border-radius: 5px; }
QMenu::item:selected { background: $accent; color: $on_accent; }
QMenu::separator { height: 1px; background: $line; margin: 4px 8px; }
QMenu::indicator { width: 12px; height: 12px; left: 6px; }
""")


def stylesheet(dark=False):
    palette = dict(DARK if dark else LIGHT)
    palette.update(control_radius=RADIUS_CONTROL, card_radius=RADIUS_CARD)
    return _STYLESHEET.substitute(palette)


LIGHT_THEME = stylesheet(False)
DARK_THEME = stylesheet(True)
