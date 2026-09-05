"""
主窗口 — 组装左侧设置面板和右侧对比面板
"""

from PyQt5.QtWidgets import QMainWindow, QSplitter, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QMenu, QActionGroup
from PyQt5.QtGui import QPalette, QColor, QPixmap, QPainter, QPen, QIcon
from PyQt5.QtCore import Qt

from views.settings_panel import SettingsPanel
from views.comparison_panel import ComparisonPanel
from views.theme import LIGHT_THEME, DARK_THEME, interface_font, typography_stylesheet
from views.glass_background import GlassBackground
from views.appearance import Appearance
from views.controls import SelectionBox


class MainWindow(QMainWindow):
    """光场图像查看器主窗口。"""

    def __init__(self, settings=None):
        super().__init__()
        self.setWindowTitle("Light Field Viewer V1 — 光场图像查看器")
        self.setMinimumSize(800, 600)
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
        self.settings_panel.setMinimumWidth(390)
        self.settings_panel.setMaximumWidth(480)

        # 左右分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.settings_panel)
        splitter.addWidget(self.comparison_panel)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(12)
        splitter.setSizes([390, 1000])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        workspace = GlassBackground()
        workspace.setObjectName("workspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        header = QWidget()
        header.setObjectName("appHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(10)
        self.sidebar_button = QPushButton()
        self.sidebar_button.setAccessibleName("显示或隐藏设置侧栏")
        self.sidebar_button.setFixedWidth(38)
        self.sidebar_button.setCheckable(True)
        self.sidebar_button.setChecked(True)
        self.sidebar_button.setShortcut("Ctrl+B")
        self.sidebar_button.setToolTip("显示或隐藏设置侧栏 (Ctrl+B)")
        self.sidebar_button.toggled.connect(self.settings_panel.setVisible)
        header_layout.addWidget(self.sidebar_button)
        title = QLabel("Light Field Viewer")
        title.setObjectName("appTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()
        self.settings_button = QPushButton("设置")
        self.settings_button.setAccessibleName("设置")
        self.settings_button.setCursor(Qt.PointingHandCursor)
        settings_menu = QMenu(self.settings_button)
        appearance_menu = settings_menu.addMenu("外观")
        self.appearance_actions = QActionGroup(self)
        for label, mode in [("跟随系统", "system"), ("浅色", "light"), ("深色", "dark")]:
            action = appearance_menu.addAction(label)
            action.setCheckable(True)
            action.setData(mode)
            action.setChecked(mode == self.appearance.mode)
            self.appearance_actions.addAction(action)
        self.appearance_actions.triggered.connect(
            lambda action: self.appearance.set_mode(action.data()))
        self.settings_button.setMenu(settings_menu)
        self.open_button = QPushButton("打开数据…")
        self.open_button.setShortcut("Ctrl+O")
        self.open_button.setToolTip("打开数据目录 (Ctrl+O)")
        self.open_button.clicked.connect(self.settings_panel._browse_data_root)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setShortcut("F5")
        self.refresh_button.clicked.connect(self.settings_panel.refresh_requested.emit)
        self.export_button = QPushButton("导出结果")
        self.export_button.setObjectName("primaryAction")
        self.export_button.clicked.connect(self.settings_panel.export_requested.emit)
        for button in (self.open_button, self.refresh_button, self.export_button):
            button.setCursor(Qt.PointingHandCursor)
            header_layout.addWidget(button)
        header_layout.addWidget(self.settings_button)
        self.comparison_panel.open_requested.connect(self.settings_panel._browse_data_root)
        layout.addWidget(header)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(workspace)

        # 状态栏
        self.statusBar().showMessage("就绪 — 请选择数据根目录")
        self.appearance.changed.connect(self._apply_appearance)
        self._apply_appearance(self.appearance.dark)

    def _apply_appearance(self, dark):
        icon = QPixmap(40, 40)
        icon.fill(Qt.transparent)
        painter = QPainter(icon)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#eef0f5" if dark else "#424957"), 2.5))
        painter.drawRoundedRect(5, 7, 30, 26, 4, 4)
        painter.drawLine(16, 8, 16, 32)
        painter.end()
        self.sidebar_button.setIcon(QIcon(icon))
        palette = QPalette(self._light_palette)
        if dark:
            for role, color in [(QPalette.Window, "#252b36"), (QPalette.WindowText, "#eef0f5"),
                                (QPalette.Base, "#252b36"), (QPalette.AlternateBase, "#303744"),
                                (QPalette.Text, "#eef0f5"), (QPalette.Button, "#353d4b"),
                                (QPalette.ButtonText, "#eef0f5"), (QPalette.Highlight, "#007aff"),
                                (QPalette.HighlightedText, "#ffffff")]:
                palette.setColor(role, QColor(color))
        self.setPalette(palette)
        self.setStyleSheet(
            typography_stylesheet()
            + (DARK_THEME if dark else LIGHT_THEME))
        self.centralWidget().dark = dark
        self.centralWidget().update()
        for combo in self.findChildren(SelectionBox):
            combo.set_dark(dark)
