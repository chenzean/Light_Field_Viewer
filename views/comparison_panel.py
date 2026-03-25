"""
右侧多方法对比展示面板 — 三个标签页

Tab 1 — SAI 全图网格: 支持同步缩放 + 鼠标拖拽平移 + 右键画框
Tab 2 — 局部放大对比: 每个矩形框的裁剪区域, 所有方法并排
Tab 3 — EPI 对比: 所有方法的 EPI 并排
"""

from PyQt5.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QSizePolicy, QApplication, QRubberBand, QTabWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QPoint, QRect
from PyQt5.QtGui import QPixmap, QFont, QCursor


# ===========================================================================
# SAI 标签 — 支持缩放后的视口裁剪显示 + 鼠标拖拽平移 + 右键画框
# ===========================================================================
class SAILabel(QLabel):
    """SAI 图像标签, 显示指定视口区域。

    缩放/平移由父面板统一管理, 本 Label 只负责:
      - 根据 viewport 裁剪显示
      - 转发滚轮事件 (缩放)
      - 左键拖拽 → 平移
      - 右键拖拽 → 画矩形框
    """
    wheel_signal = pyqtSignal(int)
    drag_delta = pyqtSignal(float, float)       # 平移增量 (原图像素)
    rect_drawn = pyqtSignal(int, int, int, int)  # 画框 (原图坐标)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: 1px solid #999; background: white;")
        self.setMinimumSize(80, 80)
        self._original_pixmap = None
        # 当前显示的 viewport (原图坐标)
        self._vx = 0
        self._vy = 0
        self._vw = 0
        self._vh = 0
        # 拖拽
        self._dragging = False
        self._drag_start = None
        # 画框
        self._drawing = False
        self._draw_start = None
        self._rubber_band = None

    def set_original_pixmap(self, pixmap):
        self._original_pixmap = pixmap

    def apply_viewport(self, vx, vy, vw, vh):
        """显示原图中 (vx, vy, vw, vh) 区域, 填满整个 Label。"""
        self._vx, self._vy, self._vw, self._vh = vx, vy, vw, vh
        if self._original_pixmap is None or self._original_pixmap.isNull():
            return
        ow, oh = self._original_pixmap.width(), self._original_pixmap.height()
        vx = max(0, min(vx, ow - 1))
        vy = max(0, min(vy, oh - 1))
        vw = max(1, min(vw, ow - vx))
        vh = max(1, min(vh, oh - vy))
        cropped = self._original_pixmap.copy(vx, vy, vw, vh)
        super().setPixmap(cropped.scaled(
            self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))

    def show_full(self):
        if self._original_pixmap and not self._original_pixmap.isNull():
            self._vx, self._vy = 0, 0
            self._vw = self._original_pixmap.width()
            self._vh = self._original_pixmap.height()
            super().setPixmap(self._original_pixmap.scaled(
                self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))

    def wheelEvent(self, event):
        self.wheel_signal.emit(event.angleDelta().y())
        event.accept()

    # ---- 左键: 拖拽平移 ----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = event.pos()
            self.setCursor(QCursor(Qt.ClosedHandCursor))
        elif event.button() == Qt.RightButton and self._original_pixmap:
            self._drawing = True
            self._draw_start = event.pos()
            if self._rubber_band is None:
                self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
            self._rubber_band.setGeometry(QRect(self._draw_start, QSize()))
            self._rubber_band.show()

    def mouseMoveEvent(self, event):
        if self._dragging and self._drag_start is not None:
            delta = event.pos() - self._drag_start
            self._drag_start = event.pos()
            # Label 像素 → 原图像素
            pm = self.pixmap()
            if pm and not pm.isNull() and pm.width() > 0:
                scale = self._vw / pm.width() if self._vw > 0 else 1.0
                dx = -delta.x() * scale
                dy = -delta.y() * scale
                self.drag_delta.emit(dx, dy)
        elif self._drawing and self._rubber_band:
            self._rubber_band.setGeometry(
                QRect(self._draw_start, event.pos()).normalized())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(QCursor(Qt.ArrowCursor))
        elif event.button() == Qt.RightButton and self._drawing:
            self._drawing = False
            if self._rubber_band:
                self._rubber_band.hide()
            s = self._map_to_orig(self._draw_start)
            e = self._map_to_orig(event.pos())
            if s and e:
                x = min(s[0], e[0])
                y = min(s[1], e[1])
                w = abs(e[0] - s[0])
                h = abs(e[1] - s[1])
                if w > 3 and h > 3:
                    self.rect_drawn.emit(x, y, w, h)

    def mouseDoubleClickEvent(self, event):
        pass  # 面板处理

    def _map_to_orig(self, label_pos):
        """Label 坐标 → 原图坐标 (考虑当前 viewport)。"""
        pm = self.pixmap()
        if pm is None or pm.isNull():
            return None
        pw, ph = pm.width(), pm.height()
        lw, lh = self.width(), self.height()
        x_off = (lw - pw) // 2
        y_off = (lh - ph) // 2
        rx = label_pos.x() - x_off
        ry = label_pos.y() - y_off
        if rx < 0 or ry < 0 or rx >= pw or ry >= ph:
            return None
        # viewport 内的比例
        img_x = self._vx + int(rx * self._vw / pw)
        img_y = self._vy + int(ry * self._vh / ph)
        return (img_x, img_y)

    def resizeEvent(self, event):
        if self._original_pixmap and self._vw > 0:
            self.apply_viewport(self._vx, self._vy, self._vw, self._vh)
        elif self._original_pixmap:
            self.show_full()
        super().resizeEvent(event)


# ===========================================================================
# 通用图像 Label (用于放大图和 EPI)
# ===========================================================================
class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: 1px solid #ccc; background: white;")
        self.setScaledContents(False)
        self.setMinimumSize(40, 40)
        self._pixmap = None

    def set_image(self, pixmap):
        self._pixmap = pixmap
        if pixmap:
            super().setPixmap(pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            super().setPixmap(QPixmap())

    def resizeEvent(self, event):
        if self._pixmap and not self._pixmap.isNull():
            super().setPixmap(self._pixmap.scaled(
                event.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        super().resizeEvent(event)


# ===========================================================================
# Tab 1: SAI 全图网格
# ===========================================================================
class SAIGridTab(QWidget):
    """SAI 全图网格 — 所有方法并排, 同步缩放/平移。"""
    rect_drawn = pyqtSignal(int, int, int, int)

    COLUMN_MIN_WIDTH = 150   # 每列最小宽度
    PAN_STEP = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = {}          # {method: SAILabel}
        self._method_order = []
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._img_w = 512
        self._img_h = 512

        self.setFocusPolicy(Qt.StrongFocus)
        self._init_ui()

    def _init_ui(self):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(4)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.scroll.setWidget(self.container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

    def set_methods(self, methods):
        # 移除旧的
        for name in list(self.labels.keys()):
            if name not in methods:
                lbl = self.labels.pop(name)
                self.grid.removeWidget(lbl)
                lbl.deleteLater()
        # 添加新的
        for m in methods:
            if m not in self.labels:
                # 容器: 标题 + SAILabel
                container = QWidget()
                vbox = QVBoxLayout(container)
                vbox.setSpacing(2)
                vbox.setContentsMargins(0, 0, 0, 0)
                title = QLabel(m)
                title.setAlignment(Qt.AlignCenter)
                font = QFont()
                font.setBold(True)
                font.setPointSize(9)
                title.setFont(font)
                title.setMaximumHeight(20)
                vbox.addWidget(title)
                sai_lbl = SAILabel()
                sai_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                sai_lbl.wheel_signal.connect(self._on_wheel)
                sai_lbl.drag_delta.connect(self._on_drag)
                sai_lbl.rect_drawn.connect(lambda x, y, w, h: self.rect_drawn.emit(x, y, w, h))
                vbox.addWidget(sai_lbl)
                container._sai_label = sai_lbl
                container._title = title
                self.labels[m] = container

        self._method_order = methods
        self._relayout()

    def _relayout(self):
        while self.grid.count():
            self.grid.takeAt(0)

        n = len(self._method_order)
        if n == 0:
            return

        panel_width = self.scroll.viewport().width()
        panel_height = self.scroll.viewport().height()

        # 自动选择最优列数
        best_cols = 1
        best_score = 0
        for c in range(1, n + 1):
            rows = (n + c - 1) // c
            cell_w = panel_width / c
            cell_h = panel_height / rows
            if cell_w < self.COLUMN_MIN_WIDTH:
                continue
            aspect = min(cell_w, cell_h) / max(cell_w, cell_h) if max(cell_w, cell_h) > 0 else 0
            area = cell_w * cell_h
            score = area * aspect
            if score > best_score:
                best_score = score
                best_cols = c

        num_rows = (n + best_cols - 1) // best_cols

        for i, m in enumerate(self._method_order):
            if m in self.labels:
                self.grid.addWidget(self.labels[m], i // best_cols, i % best_cols)

        # 强制所有列等宽、所有行等高
        for c in range(best_cols):
            self.grid.setColumnStretch(c, 1)
        for r in range(num_rows):
            self.grid.setRowStretch(r, 1)
        # 清除多余的 stretch
        for c in range(best_cols, self.grid.columnCount()):
            self.grid.setColumnStretch(c, 0)
        for r in range(num_rows, self.grid.rowCount()):
            self.grid.setRowStretch(r, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._method_order:
            self._relayout()

    def set_sai(self, method, pixmap):
        if method in self.labels:
            sai_lbl = self.labels[method]._sai_label
            sai_lbl.set_original_pixmap(pixmap)
            if pixmap and not pixmap.isNull():
                self._img_w = pixmap.width()
                self._img_h = pixmap.height()
            self._apply_viewport_one(method)

    def _on_wheel(self, delta):
        if delta > 0:
            self._zoom = min(self._zoom * 1.25, 20.0)
        else:
            self._zoom = max(self._zoom / 1.25, 1.0)
        if self._zoom <= 1.0:
            self._pan_x = 0
            self._pan_y = 0
        self._apply_viewport_all()

    def _on_drag(self, dx, dy):
        self._pan_x += dx
        self._pan_y += dy
        self._apply_viewport_all()

    def keyPressEvent(self, event):
        step = self.PAN_STEP / self._zoom
        moved = False
        if event.key() == Qt.Key_Left:
            self._pan_x -= step; moved = True
        elif event.key() == Qt.Key_Right:
            self._pan_x += step; moved = True
        elif event.key() == Qt.Key_Up:
            self._pan_y -= step; moved = True
        elif event.key() == Qt.Key_Down:
            self._pan_y += step; moved = True
        elif event.key() == Qt.Key_Home:
            self._zoom = 1.0; self._pan_x = 0; self._pan_y = 0; moved = True
        if moved:
            self._apply_viewport_all()
            event.accept()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._apply_viewport_all()

    def _apply_viewport_all(self):
        for m in self._method_order:
            self._apply_viewport_one(m)

    def _apply_viewport_one(self, method):
        if method not in self.labels:
            return
        sai_lbl = self.labels[method]._sai_label
        if self._zoom <= 1.0:
            sai_lbl.show_full()
        else:
            vw = self._img_w / self._zoom
            vh = self._img_h / self._zoom
            max_px = max(0, self._img_w - vw)
            max_py = max(0, self._img_h - vh)
            self._pan_x = max(0, min(self._pan_x, max_px))
            self._pan_y = max(0, min(self._pan_y, max_py))
            sai_lbl.apply_viewport(
                int(self._pan_x), int(self._pan_y), int(vw), int(vh))


# ===========================================================================
# Tab 2: 局部放大对比
# ===========================================================================
class ZoomCompareTab(QWidget):
    """局部放大对比 — 每个矩形框一组, 所有方法自适应网格排列。"""

    COLUMN_MIN_WIDTH = 150

    def __init__(self, parent=None):
        super().__init__(parent)
        self._methods = []
        self._rects = []
        self._crop_data = {}
        self._init_ui()

    def _init_ui(self):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setSpacing(12)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.scroll.setWidget(self.container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

        self._groups = []  # [(title_label, grid_widget, {method: ImageLabel})]

    def resizeEvent(self, event):
        """窗口大小变化时重新排列。"""
        super().resizeEvent(event)
        if self._methods and self._rects:
            self._rebuild()

    def update_zooms(self, methods, rects, crop_data):
        """更新数据并重建布局。"""
        self._methods = methods
        self._rects = rects
        self._crop_data = crop_data
        self._rebuild()

    def _rebuild(self):
        """根据当前面板宽度重建所有内容。"""
        # 清除旧的
        for title, grid_w, _ in self._groups:
            self.main_layout.removeWidget(title)
            self.main_layout.removeWidget(grid_w)
            title.deleteLater()
            grid_w.deleteLater()
        self._groups.clear()
        # 移除 stretch
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        methods = self._methods
        rects = self._rects
        crop_data = self._crop_data

        if not rects or not methods:
            return

        n = len(methods)
        panel_width = self.scroll.viewport().width()
        panel_height = self.scroll.viewport().height()

        # 每个框组占用的高度 = panel_height / 框数 (大致)
        num_rects = len(rects)
        group_height = max(200, panel_height // max(1, num_rects) - 30)

        # 自动选择最优列数 (跟 SAI Tab 相同逻辑)
        best_cols = 1
        best_score = 0
        for c in range(1, n + 1):
            rows = (n + c - 1) // c
            cell_w = panel_width / c
            cell_h = group_height / rows
            if cell_w < self.COLUMN_MIN_WIDTH:
                continue
            aspect = min(cell_w, cell_h) / max(cell_w, cell_h) if max(cell_w, cell_h) > 0 else 0
            score = cell_w * cell_h * aspect
            if score > best_score:
                best_score = score
                best_cols = c

        for i, r in enumerate(rects):
            color = r['color']
            # 标题
            title = QLabel(f"  矩形框 {i+1}  ({r['x']}, {r['y']}, {r['w']}, {r['h']})")
            title.setStyleSheet(
                f"color: rgb({color[0]},{color[1]},{color[2]}); "
                f"font-weight: bold; font-size: 11px;")
            title.setMaximumHeight(20)
            self.main_layout.addWidget(title)

            # 网格
            grid_w = QWidget()
            grid = QGridLayout(grid_w)
            grid.setSpacing(4)
            grid.setContentsMargins(0, 0, 0, 0)

            num_rows = (n + best_cols - 1) // best_cols
            labels = {}
            for j, m in enumerate(methods):
                cell = QWidget()
                vbox = QVBoxLayout(cell)
                vbox.setSpacing(1)
                vbox.setContentsMargins(0, 0, 0, 0)
                name_lbl = QLabel(m)
                name_lbl.setAlignment(Qt.AlignCenter)
                name_lbl.setMaximumHeight(16)
                font = QFont()
                font.setPointSize(8)
                name_lbl.setFont(font)
                vbox.addWidget(name_lbl)
                img_lbl = ImageLabel()
                img_lbl.setStyleSheet(
                    f"border: 2px solid rgb({color[0]},{color[1]},{color[2]});")
                img_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                vbox.addWidget(img_lbl)
                grid.addWidget(cell, j // best_cols, j % best_cols)
                labels[m] = img_lbl

                if m in crop_data and i < len(crop_data[m]):
                    img_lbl.set_image(crop_data[m][i])

            # 等宽等高
            for c in range(best_cols):
                grid.setColumnStretch(c, 1)
            for r_idx in range(num_rows):
                grid.setRowStretch(r_idx, 1)

            self.main_layout.addWidget(grid_w, 1)  # stretch=1 让网格均分空间
            self._groups.append((title, grid_w, labels))

        self.main_layout.addStretch(0)


# ===========================================================================
# Tab 3: EPI 对比
# ===========================================================================
class EPICompareTab(QWidget):
    """EPI 对比 — 所有方法的 EPI 竖向排列, 统一宽度, 方便上下对比线性结构。"""

    EPI_DISPLAY_HEIGHT = 40  # 每条 EPI 的固定显示高度

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.vbox = QVBoxLayout(self.container)
        self.vbox.setSpacing(2)
        self.vbox.setContentsMargins(4, 4, 4, 4)
        self.scroll.setWidget(self.container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

        self._rows = []  # [(label_widget, name_lbl, img_lbl)]

    def update_epis(self, methods, epi_data):
        """更新 EPI 显示 — 竖向排列, 每个方法一行, 统一宽度。"""
        # 清除旧的
        for row_w, _, _ in self._rows:
            self.vbox.removeWidget(row_w)
            row_w.deleteLater()
        self._rows.clear()

        if not methods or not epi_data:
            return

        # 找到所有 EPI 的最大宽度, 用于统一显示
        max_w = 1
        for m in methods:
            pix = epi_data.get(m)
            if pix and not pix.isNull():
                max_w = max(max_w, pix.width())

        for m in methods:
            row_w = QWidget()
            hbox = QHBoxLayout(row_w)
            hbox.setSpacing(4)
            hbox.setContentsMargins(0, 0, 0, 0)

            # 方法名 (固定宽度, 左对齐)
            name_lbl = QLabel(m)
            name_lbl.setFixedWidth(120)
            name_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            font = QFont()
            font.setBold(True)
            font.setPointSize(9)
            name_lbl.setFont(font)
            hbox.addWidget(name_lbl)

            # EPI 图像
            img_lbl = QLabel()
            img_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            img_lbl.setStyleSheet("border: 1px solid #999; background: white;")
            img_lbl.setFixedHeight(self.EPI_DISPLAY_HEIGHT)
            img_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            pix = epi_data.get(m)
            if pix and not pix.isNull():
                # 统一缩放: 高度固定, 宽度按比例
                scaled = pix.scaledToHeight(self.EPI_DISPLAY_HEIGHT, Qt.SmoothTransformation)
                img_lbl.setPixmap(scaled)

            hbox.addWidget(img_lbl)
            self.vbox.addWidget(row_w)
            self._rows.append((row_w, name_lbl, img_lbl))

        self.vbox.addStretch()


# ===========================================================================
# 主面板: 三个标签页
# ===========================================================================
class ComparisonPanel(QWidget):
    """右侧对比面板 — 三个标签页。"""
    rect_drawn_on_sai = pyqtSignal(int, int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.sai_tab = SAIGridTab()
        self.zoom_tab = ZoomCompareTab()
        self.epi_tab = EPICompareTab()

        self.tabs.addTab(self.sai_tab, "SAI 全图")
        self.tabs.addTab(self.zoom_tab, "局部放大")
        self.tabs.addTab(self.epi_tab, "EPI 对比")

        layout.addWidget(self.tabs)

        # 转发信号
        self.sai_tab.rect_drawn.connect(
            lambda x, y, w, h: self.rect_drawn_on_sai.emit(x, y, w, h))

    def set_methods(self, methods):
        self.sai_tab.set_methods(methods)

    def update_method_sai(self, method, pixmap):
        self.sai_tab.set_sai(method, pixmap)

    def update_all_zooms(self, methods, rects, crop_data):
        """批量更新局部放大标签页。"""
        self.zoom_tab.update_zooms(methods, rects, crop_data)

    def update_all_epis(self, methods, epi_data):
        """批量更新 EPI 标签页。"""
        self.epi_tab.update_epis(methods, epi_data)
