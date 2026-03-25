"""
主窗口 — 组装左侧设置面板和右侧对比面板
"""

from PyQt5.QtWidgets import QMainWindow, QSplitter, QWidget, QHBoxLayout
from PyQt5.QtCore import Qt

from views.settings_panel import SettingsPanel
from views.comparison_panel import ComparisonPanel


class MainWindow(QMainWindow):
    """光场图像查看器主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Light Field Viewer V1 — 光场图像查看器")
        self.setMinimumSize(800, 600)
        # 默认最大化, 减少手动调整窗口
        self.showMaximized()

        # 创建左右面板
        self.settings_panel = SettingsPanel()
        self.comparison_panel = ComparisonPanel()

        # 左右分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.settings_panel)
        splitter.addWidget(self.comparison_panel)
        # 左侧固定宽度约 300, 右侧自适应
        splitter.setSizes([300, 900])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

        # 状态栏
        self.statusBar().showMessage("就绪 — 请选择数据根目录")
