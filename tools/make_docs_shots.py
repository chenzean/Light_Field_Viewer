"""
使用说明配图生成器 — 输出到 docs/images/

配图用 Demo数据格式/ 里的真实数据、走真实控制器生成, 所以截图里的内容就是
用户实际会看到的东西。界面改了以后重跑一次即可, 不用手动截图。

用法:
    python tools/make_docs_shots.py
"""

import os
import sys
import tempfile
import time

from PyQt5.QtCore import Qt, QRect, QSettings, QCoreApplication, QEvent
from PyQt5.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from views.main_window import MainWindow          # noqa: E402
from controllers.app_controller import AppController      # noqa: E402
from controllers.export_controller import ExportController  # noqa: E402

OUT = os.path.join(ROOT, "docs", "images")

# 优先用本机上方法数量真实的对比数据集; 没有则退回仓库内的 Demo 数据,
# 这样别人克隆下来也能重新生成配图。
DATA_CANDIDATES = (
    # 正斜杠在 Windows 上一样能用, 也省得纠结反斜杠转义
    "D:/Light_Field_Video/7_Results_of_different_comparison_methods",
    os.path.join(ROOT, "Demo数据格式", "SAI", "光场视频"),
)

# 数据集里方法很多, 画布上全塞进去每块就太小了; 截图只展示有代表性的一组,
# 侧栏的方法列表里仍然能看到全部方法。
FEATURED = ("Ground_Truth", "RIFE", "EPIT", "DistgSSR", "LFSloMo", "Proposed_v1")

WINDOW = (1500, 940)
FULL_WIDTH = 1200        # 全窗口截图在仓库里的宽度
SIDEBAR = QRect(0, 46, 384, 894)


def pick_data_root():
    for candidate in DATA_CANDIDATES:
        if os.path.isdir(candidate):
            return candidate
    raise SystemExit("找不到可用的数据目录: " + " / ".join(DATA_CANDIDATES))


def settle(app, seconds=0.5):
    """刷新是 200ms 防抖的, processEvents 一次跑不到, 这里等它真正触发。"""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        # 取消勾选方法后旧图块是 deleteLater() 删除的, processEvents 不处理
        # DeferredDelete, 不显式送一次的话旧图块会留在画面上和新布局重叠
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def save(window, name, rect=None, width=None):
    shot = window.grab(rect) if rect else window.grab()
    if width and shot.width() > width:
        shot = shot.scaledToWidth(width, Qt.SmoothTransformation)
    path = os.path.join(OUT, f"{name}.png")
    shot.save(path)
    print(f"  {name}.png  {shot.width()}x{shot.height()}")
    return path


def main():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    os.makedirs(OUT, exist_ok=True)

    settings = QSettings(os.path.join(tempfile.mkdtemp(), "a.ini"),
                         QSettings.IniFormat)
    window = MainWindow(settings=settings)
    controller = AppController(window)
    exporter = ExportController(controller)
    window.settings_panel.export_requested.connect(exporter.export)
    window.appearance.set_mode("light")
    window.setAttribute(Qt.WA_DontShowOnScreen)
    window.showNormal()
    window.resize(*WINDOW)
    app.processEvents()

    panel = window.settings_panel
    comparison = window.comparison_panel

    print("writing", OUT)
    save(window, "empty-state", width=FULL_WIDTH)

    data_root = pick_data_root()
    print("data root:", data_root)
    panel.txt_data_root.setText(data_root)
    panel.data_root_changed.emit(data_root)
    settle(app)

    methods = [panel.list_methods.item(i).text()
               for i in range(panel.list_methods.count())]
    print(f"扫描到 {len(methods)} 个方法")
    featured = [m for m in FEATURED if m in methods]
    if len(featured) >= 2:
        for i in range(panel.list_methods.count()):
            item = panel.list_methods.item(i)
            item.setCheckState(Qt.Checked if item.text() in featured
                               else Qt.Unchecked)
        print("画布展示:", ", ".join(featured))
        settle(app)
    save(window, "overview", width=FULL_WIDTH)
    save(window, "sidebar-data", SIDEBAR)

    # 一个矩形框 + 残差, 让「局部放大」页有内容可看
    panel.rect_added.emit()
    panel.spin_rect_x.setValue(150)
    panel.spin_rect_y.setValue(96)
    panel.spin_rect_w.setValue(150)
    panel.spin_rect_h.setValue(150)
    panel.chk_residual.setChecked(True)
    settle(app)

    panel.sections.setCurrentIndex(1)
    app.processEvents()
    save(window, "sidebar-annotate", SIDEBAR)

    comparison.tabs.setCurrentIndex(1)
    settle(app, 3)
    save(window, "tab-zoom", width=FULL_WIDTH)

    panel.chk_epi.setChecked(True)
    comparison.tabs.setCurrentIndex(2)
    # EPI 需要把每个方法的整组角度视角都读进来, 比其它页慢得多
    settle(app, 8)
    save(window, "tab-epi", width=FULL_WIDTH)

    panel.sections.setCurrentIndex(2)
    panel.txt_export_dir.setText(r"D:\LF_export\Scene_0001")
    comparison.tabs.setCurrentIndex(0)
    settle(app)
    save(window, "sidebar-export", SIDEBAR)

    panel.sections.setCurrentIndex(0)
    window.appearance.set_mode("dark")
    settle(app)
    save(window, "dark-appearance", width=FULL_WIDTH)

    window.close()
    print("done")


if __name__ == "__main__":
    main()
