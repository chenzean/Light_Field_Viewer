"""
Light Field Viewer — 光场图像查看器

入口文件: 创建 QApplication, 启动主窗口

用法:
    python main.py
"""

import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from views.main_window import MainWindow
from controllers.app_controller import AppController
from controllers.export_controller import ExportController
from utils.resources import app_icon

APP_ID = "chenzean.LightFieldViewer.V1"


def _claim_taskbar_identity():
    """让任务栏使用本程序的图标, 而不是 python.exe 的。

    Windows 按 AppUserModelID 归组任务栏按钮; 不显式设置的话, 源码运行时
    整个窗口会被归到 Python 名下, setWindowIcon 也就看不出效果。
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except (AttributeError, OSError):
        pass


def main():
    # 高 DPI 支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    _claim_taskbar_identity()

    app = QApplication(sys.argv)
    app.setApplicationName("Light Field Viewer")
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())

    # 创建主窗口
    window = MainWindow()

    # 创建控制器
    app_ctrl = AppController(window)
    export_ctrl = ExportController(app_ctrl)

    # 连接导出按钮
    window.settings_panel.export_requested.connect(export_ctrl.export)

    # 显示窗口
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
