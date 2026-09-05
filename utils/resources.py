"""
资源路径解析 — 源码运行和 PyInstaller 打包后都能找到 assets/
"""

import os
import sys


def resource_path(*parts):
    """返回随程序分发的资源文件的绝对路径。

    PyInstaller 会把打包的数据解压到 ``sys._MEIPASS``, 该目录和源码目录不同,
    所以两种情况要分开处理。
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def app_icon():
    """应用图标; 缺失时返回空 QIcon, 不影响启动。"""
    from PyQt5.QtGui import QIcon

    path = resource_path("assets", "icon.ico")
    return QIcon(path) if os.path.exists(path) else QIcon()
