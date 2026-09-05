"""
主窗口 — 组装左侧设置面板和右侧对比面板

窗口结构参照 macOS: 顶部统一工具栏, 左侧半透明侧栏, 右侧内容区,
三者之间只用 1px 分隔线, 不做浮层卡片。
"""

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QWidget, QVBoxLayout, QLabel,
    QHBoxLayout, QMenu, QActionGroup, QSizePolicy
)
from PyQt5.QtGui import QPalette, QColor, QPixmap, QPainter, QPen, QIcon
from PyQt5.QtCore import Qt, QSize, QPointF, QRectF

from views import theme
from views import controls
from views.settings_panel import SettingsPanel
from views.comparison_panel import ComparisonPanel
from views.theme import (
    LIGHT_THEME, DARK_THEME, interface_font, typography_stylesheet
)
from views.glass_background import GlassBackground
from views.appearance import Appearance
from views.controls import PushButton, SelectionBox
from utils.resources import app_icon

TOOLBAR_HEIGHT = 46


class MainWindow(QMainWindow):
    """光场图像查看器主窗口。"""

    def __init__(self, settings=None):
        super().__init__()
        self.setWindowTitle("Light Field Viewer V1 — 光场图像查看器")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(800, 600)
        theme.apply_interface_font(QApplication.instance())
        self.setFont(interface_font())
        self.appearance = Appearance(self, settings)
        self._light_palette = QPalette(self.palette())
        self.setStyleSheet(typography_stylesheet() + LIGHT_THEME)
        # 默认最大化, 减少手动调整窗口
        self.showMaximized()

        # 创建左右面板
        self.settings_panel = SettingsPanel()
        self.comparison_panel = ComparisonPanel()
        self.settings_panel.setObjectName("glassSidebar")
        self.settings_panel.setAttribute(Qt.WA_StyledBackground, True)
        self.comparison_panel.setObjectName("glassCanvas")
        self.comparison_panel.setAttribute(Qt.WA_StyledBackground, True)
        self.settings_panel.setMinimumWidth(360)
        self.settings_panel.setMaximumWidth(460)

        # 左右分割器 — 只留一条发丝线的间隙
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.settings_panel)
        splitter.addWidget(self.comparison_panel)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)
        splitter.setSizes([380, 1000])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        workspace = GlassBackground()
        workspace.setObjectName("workspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_toolbar())
        layout.addWidget(splitter, 1)
        self.comparison_panel.open_requested.connect(
            self.settings_panel._browse_data_root)
        self.setCentralWidget(workspace)

        # 状态栏
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().showMessage("就绪 — 请选择数据根目录")
        self.appearance.changed.connect(self._apply_appearance)
        self._apply_appearance(self.appearance.dark)

    # ---- 顶部统一工具栏 ----
    def _build_toolbar(self):
        header = QWidget()
        header.setObjectName("appHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header.setFixedHeight(TOOLBAR_HEIGHT)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        header_layout.setSpacing(6)

        self.sidebar_button = PushButton()
        self.sidebar_button.setObjectName("sidebarToggle")
        self.sidebar_button.setAccessibleName("显示或隐藏设置侧栏")
        self.sidebar_button.setIconSize(QSize(18, 18))
        self.sidebar_button.setFixedWidth(34)
        self.sidebar_button.setCheckable(True)
        self.sidebar_button.setChecked(True)
        self.sidebar_button.setShortcut("Ctrl+B")
        self.sidebar_button.setToolTip("显示或隐藏设置侧栏 (Ctrl+B)")
        self.sidebar_button.toggled.connect(self.settings_panel.setVisible)
        header_layout.addWidget(self.sidebar_button)

        title = QLabel("Light Field Viewer")
        title.setObjectName("appTitle")
        header_layout.addSpacing(2)
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self.open_button = PushButton("打开数据…")
        self.open_button.setShortcut("Ctrl+O")
        self.open_button.setToolTip("打开数据目录 (Ctrl+O)")
        self.open_button.clicked.connect(self.settings_panel._browse_data_root)
        self.refresh_button = PushButton("刷新")
        self.refresh_button.setShortcut("F5")
        self.refresh_button.setToolTip("重新载入当前数据 (F5)")
        self.refresh_button.clicked.connect(
            self.settings_panel.refresh_requested.emit)

        self.settings_button = PushButton("设置")
        self.settings_button.setAccessibleName("设置")
        settings_menu = QMenu(self.settings_button)
        # Flat rather than nested: a submenu would cost a second click and a
        # marker arrow that style sheets cannot draw as anything but a box.
        # Fusion renders addSection() as a bare rule with no caption, so the
        # three appearance choices simply stand on their own.
        self.appearance_actions = QActionGroup(self)
        for label, mode in [("跟随系统", "system"), ("浅色", "light"), ("深色", "dark")]:
            action = settings_menu.addAction(label)
            action.setCheckable(True)
            action.setData(mode)
            action.setChecked(mode == self.appearance.mode)
            self.appearance_actions.addAction(action)
        self.appearance_actions.triggered.connect(
            lambda action: self.appearance.set_mode(action.data()))
        self.settings_button.setMenu(settings_menu)

        self.export_button = PushButton("导出结果")
        self.export_button.setObjectName("primaryAction")
        self.export_button.setToolTip("导出当前对比结果")
        self.export_button.clicked.connect(
            self.settings_panel.export_requested.emit)

        # 主操作放在最右, 与 macOS 工具栏一致
        for button in (self.open_button, self.refresh_button,
                       self.settings_button, self.export_button):
            button.setCursor(Qt.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            header_layout.addWidget(button)
        return header

    # ---- 侧栏开关图标 ----
    def _sidebar_icon(self, dark):
        scale = 2
        pixmap = QPixmap(18 * scale, 18 * scale)
        pixmap.fill(Qt.transparent)
        pixmap.setDevicePixelRatio(scale)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = theme.DARK if dark else theme.LIGHT
        stroke = QColor(palette["text_2"])
        painter.setPen(QPen(stroke, 1.4))
        body = QRectF(1.7, 3.2, 14.6, 11.6)
        painter.drawRoundedRect(body, 3.0, 3.0)
        fill = QColor(stroke)
        fill.setAlpha(60)
        painter.fillRect(QRectF(1.7, 3.2, 5.0, 11.6), fill)
        painter.drawLine(QPointF(6.7, 3.2), QPointF(6.7, 14.8))
        painter.end()
        return QIcon(pixmap)

    def _apply_appearance(self, dark):
        controls.set_dark(dark)
        self.sidebar_button.setIcon(self._sidebar_icon(dark))
        palette = QPalette(self._light_palette)
        tokens = theme.DARK if dark else theme.LIGHT
        for role, token in [(QPalette.Window, "window"), (QPalette.WindowText, "text"),
                            (QPalette.Base, "control"), (QPalette.AlternateBase, "card"),
                            (QPalette.Text, "text"), (QPalette.Button, "control"),
                            (QPalette.ButtonText, "text"), (QPalette.Highlight, "accent"),
                            (QPalette.HighlightedText, "on_accent"),
                            (QPalette.PlaceholderText, "text_3"),
                            (QPalette.ToolTipBase, "menu"), (QPalette.ToolTipText, "text")]:
            palette.setColor(role, QColor(tokens[token]))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(tokens["text_off"]))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(tokens["text_off"]))
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(tokens["text_off"]))
        self.setPalette(palette)
        self.setStyleSheet(
            typography_stylesheet() + (DARK_THEME if dark else LIGHT_THEME))
        self.centralWidget().dark = dark
        self.centralWidget().update()
        for combo in self.findChildren(SelectionBox):
            combo.set_dark(dark)
        self.comparison_panel.set_dark(dark)
