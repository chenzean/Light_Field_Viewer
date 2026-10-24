"""
右侧多方法对比展示面板 — 三个标签页

Tab 1 — SAI 全图网格: 支持同步缩放 + 鼠标拖拽平移 + 右键画框
Tab 2 — 局部放大对比: 每个矩形框的裁剪区域, 所有方法并排
Tab 3 — EPI 对比: 所有方法的 EPI 并排

图块使用完整矩形显示，所有交互均使用原图像素坐标。
"""

from PyQt5.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QSizePolicy, QRubberBand, QTabWidget, QStackedWidget, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QPointF, QRect, QRectF, QTimer
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QCursor

from views import theme

PLATE_RADIUS = 0
GRID_SPACING = 10


# ===========================================================================
# 图块基类 — 圆角裁切 + 发丝描边
# ===========================================================================
class ImagePlate(QLabel):
    """Neutral image bed; image corners remain visible for pixel inspection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self._edge = None        # 覆盖色 (矩形框配色), None 时用主题描边
        self._edge_width = 0.0

    def set_edge(self, color, width=1.4):
        self._edge = QColor(*color) if color is not None else None
        self._edge_width = width
        self.update()

    def paintEvent(self, event):
        if self.pixmap() is None or self.pixmap().isNull():
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, PLATE_RADIUS, PLATE_RADIUS)

        pixmap = self.pixmap()
        covers = (pixmap is not None and not pixmap.isNull()
                  and pixmap.width() >= self.width()
                  and pixmap.height() >= self.height())
        if not covers:
            painter.fillPath(path, theme.color("image_bed"))
        if pixmap is not None and not pixmap.isNull():
            painter.save()
            painter.setClipPath(path)
            ratio = pixmap.devicePixelRatio() or 1.0
            painter.drawPixmap(
                self._pixmap_origin(rect, pixmap.width() / ratio,
                                    pixmap.height() / ratio), pixmap)
            painter.restore()

        if self._edge_width <= 0:
            return
        painter.setPen(QPen(self._edge if self._edge is not None
                            else theme.color("border_soft"), self._edge_width))
        painter.setBrush(Qt.NoBrush)
        inset = self._edge_width / 2.0
        painter.drawRoundedRect(rect.adjusted(inset, inset, -inset, -inset),
                                PLATE_RADIUS, PLATE_RADIUS)

    def _pixmap_origin(self, rect, width, height):
        """Honour the label's alignment the way QLabel would."""
        flags = self.alignment()
        if flags & Qt.AlignLeft:
            x = 0.0
        elif flags & Qt.AlignRight:
            x = rect.width() - width
        else:
            x = (rect.width() - width) / 2.0
        if flags & Qt.AlignTop:
            y = 0.0
        elif flags & Qt.AlignBottom:
            y = rect.height() - height
        else:
            y = (rect.height() - height) / 2.0
        return QPointF(x, y)


# ===========================================================================
# SAI 标签 — 支持缩放后的视口裁剪显示 + 鼠标拖拽平移 + 右键画框
# ===========================================================================
class SAILabel(ImagePlate):
    """SAI 图像标签, 显示指定视口区域。

    缩放/平移由父面板统一管理, 本 Label 只负责:
      - 根据 viewport 裁剪显示
      - 转发滚轮事件 (缩放)
      - 左键拖拽 → 平移
      - 右键拖拽 → 画矩形框
    """
    wheel_signal = pyqtSignal(int, float, float)  # delta, rel_x(0~1), rel_y(0~1)
    drag_delta = pyqtSignal(float, float)       # 平移增量 (原图像素)
    rect_drawn = pyqtSignal(int, int, int, int)  # 画框 (原图坐标)
    focus_request = pyqtSignal()                 # 请求父面板获取焦点

    def __init__(self, parent=None):
        super().__init__(parent)
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
        self._smooth = True

    def set_original_pixmap(self, pixmap):
        self._original_pixmap = pixmap if pixmap and not pixmap.isNull() else None
        self.clear()
        self._dragging = self._drawing = False
        if self._rubber_band:
            self._rubber_band.hide()
        if self._original_pixmap is None:
            self._vw = self._vh = 0
            self.setText("缺少当前帧 / 视角")
        else:
            self.setPixmap(self._original_pixmap)
        self.update()

    def sizeHint(self):
        # The retained full-resolution pixmap must not size the window.
        return QSize(240, 180)

    def minimumSizeHint(self):
        return QSize(80, 80)

    def apply_viewport(self, vx, vy, vw, vh, smooth=True):
        """Draw a floating-point source rectangle with one uniform scale.

        Keeping the source rectangle unrounded avoids pixel-aspect drift at
        high zoom and gives painting, wheel, pan and ROI the same transform.
        """
        if self._original_pixmap is None:
            return
        ow, oh = self._original_pixmap.width(), self._original_pixmap.height()
        self._vw, self._vh = max(1e-6, min(vw, ow)), max(1e-6, min(vh, oh))
        self._vx = max(0.0, min(vx, ow - self._vw))
        self._vy = max(0.0, min(vy, oh - self._vh))
        self._smooth = smooth
        self.update()

    def show_full(self, smooth=True):
        if self._original_pixmap:
            self.apply_viewport(0, 0, self._original_pixmap.width(),
                                self._original_pixmap.height(), smooth=smooth)

    def display_rect(self):
        """Image bounds in widget coordinates, excluding the letterbox."""
        if self._original_pixmap is None or self._vw <= 0 or self._vh <= 0:
            return QRectF()
        scale = min(self.width() / self._vw, self.height() / self._vh)
        width, height = self._vw * scale, self._vh * scale
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2,
                      width, height)

    def paintEvent(self, event):
        if self._original_pixmap is None or self._vw <= 0:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), theme.color("image_bed"))
        painter.setRenderHint(QPainter.SmoothPixmapTransform, self._smooth)
        painter.drawPixmap(self.display_rect(), self._original_pixmap,
                           QRectF(self._vx, self._vy, self._vw, self._vh))

    def wheelEvent(self, event):
        pos = event.pos()
        rect = self.display_rect()
        if not rect.isEmpty() and rect.contains(QPointF(pos)):
            self.wheel_signal.emit(event.angleDelta().y(),
                                   (pos.x() - rect.x()) / rect.width(),
                                   (pos.y() - rect.y()) / rect.height())
        event.accept()

    # ---- 左键: 拖拽平移 ----
    def mousePressEvent(self, event):
        self.focus_request.emit()
        if self._map_to_orig(event.pos()) is None:
            return
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
            rect = self.display_rect()
            if not rect.isEmpty():
                dx = -delta.x() * self._vw / rect.width()
                dy = -delta.y() * self._vh / rect.height()
                self.drag_delta.emit(dx, dy)
        elif self._drawing and self._rubber_band:
            self._rubber_band.setGeometry(
                QRect(self._draw_start, event.pos()).normalized().intersected(
                    self.display_rect().toAlignedRect()))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(QCursor(Qt.ArrowCursor))
        elif event.button() == Qt.RightButton and self._drawing:
            self._drawing = False
            if self._rubber_band:
                self._rubber_band.hide()
            s = self._map_to_orig(self._draw_start)
            e = self._map_to_orig(event.pos(), clamp=True)
            if s and e:
                x = min(s[0], e[0])
                y = min(s[1], e[1])
                w = abs(e[0] - s[0])
                h = abs(e[1] - s[1])
                if w > 3 and h > 3:
                    self.rect_drawn.emit(x, y, w, h)

    def mouseDoubleClickEvent(self, event):
        pass  # 面板处理

    def _map_to_orig(self, label_pos, clamp=False):
        """Label 坐标 → 原图坐标 (考虑当前 viewport)。"""
        rect = self.display_rect()
        if rect.isEmpty():
            return None
        if not clamp and not rect.contains(QPointF(label_pos)):
            return None
        rx = max(0.0, min(1.0, (label_pos.x() - rect.x()) / rect.width()))
        ry = max(0.0, min(1.0, (label_pos.y() - rect.y()) / rect.height()))
        return (int(self._vx + rx * self._vw), int(self._vy + ry * self._vh))

    def resizeEvent(self, event):
        if self._original_pixmap and self._vw <= 0:
            self.show_full()
        self.update()
        super().resizeEvent(event)


# ===========================================================================
# 通用图像 Label (用于放大图和 EPI)
# ===========================================================================
class ImageLabel(ImagePlate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScaledContents(False)
        self.setMinimumSize(40, 40)
        self._pixmap = None

    def sizeHint(self):
        return QSize(180, 120)

    def minimumSizeHint(self):
        return QSize(40, 40)

    def set_image(self, pixmap):
        self._pixmap = pixmap
        if pixmap and not pixmap.isNull():
            super().setPixmap(pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.clear()
            self.setText("缺少当前帧 / 视角")

    def resizeEvent(self, event):
        if self._pixmap and not self._pixmap.isNull():
            super().setPixmap(self._pixmap.scaled(
                event.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        super().resizeEvent(event)


class _ElidedLabel(QLabel):
    """Keep method names within their column, with the full name on hover."""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self.setToolTip(text)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def resizeEvent(self, event):
        self.setText(self.fontMetrics().elidedText(
            self._full_text, Qt.ElideMiddle, self.contentsRect().width()))
        super().resizeEvent(event)


def _method_caption(text):
    """The small semibold name that sits above every tile."""
    label = _ElidedLabel(text)
    label.setAlignment(Qt.AlignCenter)
    label.setProperty("typography", "method")
    label.setMinimumHeight(22)
    return label


def _group_caption(color, text):
    """Rect heading: a colour chip in the rect's colour, then neutral text."""
    label = QLabel(
        f'<span style="color: rgb({color[0]},{color[1]},{color[2]});">■</span>'
        f'&nbsp;&nbsp;{text}')
    label.setProperty("typography", "method")
    label.setMinimumHeight(24)
    return label


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
        self._pixmaps = {}
        self._method_order = []
        self._reference_method = None
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._img_w = 512
        self._img_h = 512

        # 交互期间 (拖拽/缩放/键盘平移) 用快速插值, 停下后再做一次高质量重绘
        self._fast_mode = False
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.setInterval(140)
        self._settle_timer.timeout.connect(self._on_interaction_settled)

        self.setFocusPolicy(Qt.StrongFocus)
        self._init_ui()

    def _begin_interaction(self):
        """标记进入交互状态 (使用快速插值), 并重启停顿计时器。"""
        self._fast_mode = True
        self._settle_timer.start()

    def _on_interaction_settled(self):
        """交互停顿后, 用高质量插值重绘一次。"""
        self._fast_mode = False
        self._apply_viewport_all()

    def _init_ui(self):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(GRID_SPACING)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.scroll.setWidget(self.container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

    def set_methods(self, methods):
        # 方法列表未变化时直接返回, 避免每次刷新都重建网格
        if methods == self._method_order and all(m in self.labels for m in methods):
            return
        # 移除旧的
        for name in list(self.labels.keys()):
            if name not in methods:
                lbl = self.labels.pop(name)
                self.grid.removeWidget(lbl)
                lbl.deleteLater()
                self._pixmaps.pop(name, None)
        # 添加新的
        for m in methods:
            if m not in self.labels:
                # 容器: 标题 + SAILabel
                container = QWidget()
                vbox = QVBoxLayout(container)
                vbox.setSpacing(5)
                vbox.setContentsMargins(0, 0, 0, 0)
                title = _method_caption(m)
                vbox.addWidget(title)
                sai_lbl = SAILabel()
                sai_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                sai_lbl.wheel_signal.connect(self._on_wheel)
                sai_lbl.drag_delta.connect(self._on_drag)
                sai_lbl.rect_drawn.connect(lambda x, y, w, h: self.rect_drawn.emit(x, y, w, h))
                sai_lbl.focus_request.connect(self.setFocus)
                vbox.addWidget(sai_lbl)
                container._sai_label = sai_lbl
                container._title = title
                self.labels[m] = container

        self._method_order = list(methods)
        self._relayout()
        self._sync_reference_geometry()

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
            available_w = max(1, cell_w - GRID_SPACING)
            available_h = max(1, cell_h - 30 - GRID_SPACING)
            scale = min(available_w / self._img_w, available_h / self._img_h)
            score = scale * scale
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
            QTimer.singleShot(0, self._apply_viewport_all)

    def set_sai(self, method, pixmap):
        if method in self.labels:
            self._pixmaps[method] = pixmap if pixmap and not pixmap.isNull() else None
            self._sync_reference_geometry()

    def _sync_reference_geometry(self):
        """Share pixel coordinates only between images of the same size.

        Ground Truth anchors the grid when available; otherwise the first
        loaded method in display order does. Incompatible images are blocked,
        never stretched or silently mapped into another method's coordinates.
        """
        valid = [m for m in self._method_order if self._pixmaps.get(m)]
        reference = 'Ground_Truth' if 'Ground_Truth' in valid else (valid[0] if valid else None)
        self._reference_method = reference
        if reference is not None:
            pixmap = self._pixmaps[reference]
            size = (pixmap.width(), pixmap.height())
            if size != (self._img_w, self._img_h):
                self._img_w, self._img_h = size
                self._zoom = 1.0
                self._pan_x = self._pan_y = 0.0
                self._relayout()
        for method in self._method_order:
            label = self.labels[method]._sai_label
            pixmap = self._pixmaps.get(method)
            if pixmap and (pixmap.width(), pixmap.height()) != (self._img_w, self._img_h):
                label.set_original_pixmap(None)
                label.setText(f"尺寸不一致 · 无法同步比较\n{pixmap.width()}×{pixmap.height()}，参考 {self._img_w}×{self._img_h}")
            else:
                label.set_original_pixmap(pixmap)
        self._apply_viewport_all()
        QTimer.singleShot(0, self._apply_viewport_all)

    def reset_view(self):
        self._zoom = 1.0
        self._pan_x = self._pan_y = 0.0
        self._apply_viewport_all()

    def _on_wheel(self, delta, rel_x, rel_y):
        if delta == 0:
            return
        self._begin_interaction()
        old_zoom = self._zoom
        if delta > 0:
            self._zoom = min(self._zoom * 1.25, 20.0)
        else:
            self._zoom = max(self._zoom / 1.25, 1.0)

        if self._zoom <= 1.0:
            self._pan_x = 0
            self._pan_y = 0
        else:
            # 鼠标在原图中的坐标 (缩放前)
            old_vw = self._img_w / old_zoom if old_zoom > 1.0 else self._img_w
            old_vh = self._img_h / old_zoom if old_zoom > 1.0 else self._img_h
            img_x = self._pan_x + rel_x * old_vw
            img_y = self._pan_y + rel_y * old_vh
            # 新视口大小
            new_vw = self._img_w / self._zoom
            new_vh = self._img_h / self._zoom
            # 让鼠标位置保持不变
            self._pan_x = img_x - rel_x * new_vw
            self._pan_y = img_y - rel_y * new_vh
        self._apply_viewport_all()

    def _on_drag(self, dx, dy):
        self._begin_interaction()
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
            self.reset_view()
            event.accept()
            return
        if moved:
            self._begin_interaction()
            self._apply_viewport_all()
            event.accept()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.reset_view()

    def _apply_viewport_all(self):
        vw = self._img_w / max(1.0, self._zoom)
        vh = self._img_h / max(1.0, self._zoom)
        self._pan_x = max(0.0, min(self._pan_x, self._img_w - vw))
        self._pan_y = max(0.0, min(self._pan_y, self._img_h - vh))
        for m in self._method_order:
            self._apply_viewport_one(m)

    def _apply_viewport_one(self, method):
        if method not in self.labels:
            return
        sai_lbl = self.labels[method]._sai_label
        smooth = not self._fast_mode
        sai_lbl.apply_viewport(self._pan_x, self._pan_y,
                               self._img_w / max(1.0, self._zoom),
                               self._img_h / max(1.0, self._zoom),
                               smooth=smooth)


# ===========================================================================
# Tab 2: 局部放大对比
# ===========================================================================
class ZoomCompareTab(QWidget):
    """局部放大对比 — 每个矩形框一组, 所有方法自适应网格排列。"""

    COLUMN_MIN_WIDTH = 180

    def __init__(self, parent=None):
        super().__init__(parent)
        self._methods = []
        self._rects = []
        self._crop_data = {}
        self._residual_data = None
        self._colorbar_pixmap = None
        self._init_ui()

    def _init_ui(self):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll.setWidget(self.container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

        self._groups = []  # [[widget, ...], ...]  每组的所有 widget 列表
        self._last_cols = -1  # 上次重建时采用的列数, 用于判断 resize 是否需要重建

        # resize 防抖定时器 (避免拖拽窗口时频繁重建)
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(150)
        self._resize_timer.timeout.connect(self._on_resize_done)

    def resizeEvent(self, event):
        """窗口大小变化时防抖重排。"""
        super().resizeEvent(event)
        if self._methods and self._rects:
            self._resize_timer.start()

    def _on_resize_done(self):
        if not (self._methods and self._rects):
            return
        # 列数不变时, 现有 widget 会随 layout stretch 自动缩放, 无需销毁重建
        if self._compute_best_cols() == self._last_cols:
            return
        self._rebuild()

    def _compute_best_cols(self):
        """根据当前面板尺寸与数据量, 计算最优列数 (与 _rebuild 中逻辑一致)。"""
        n = len(self._methods)
        if n == 0:
            return 1
        panel_width = self.scroll.viewport().width()
        panel_height = self.scroll.viewport().height()
        num_rects = len(self._rects)
        has_residual = self._residual_data is not None
        if has_residual:
            panel_width -= 74
        image_rows = 2 if has_residual else 1
        group_height = max(250, panel_height // max(1, num_rects) - 32)
        aspect = self._rects[0]['w'] / max(1, self._rects[0]['h']) if self._rects else 1

        best_cols = 1
        best_score = 0
        for c in range(1, n + 1):
            rows = (n + c - 1) // c
            cell_w = panel_width / c - GRID_SPACING
            cell_h = (group_height / rows - 50) / image_rows
            if cell_w < self.COLUMN_MIN_WIDTH:
                continue
            score = min(cell_w / aspect, max(1, cell_h)) ** 2
            if score > best_score:
                best_score = score
                best_cols = c
        return best_cols

    def update_zooms(self, methods, rects, crop_data,
                     residual_data=None, colorbar_pixmap=None):
        """更新数据并重建布局。"""
        self._methods = methods
        self._rects = rects
        self._crop_data = crop_data
        self._residual_data = residual_data
        self._colorbar_pixmap = colorbar_pixmap
        self._rebuild()

    def _tile_grid(self, methods, best_cols, color, source, rect_index):
        """Each method keeps its crop and residual in the same grid cell."""
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setSpacing(GRID_SPACING)
        grid.setContentsMargins(0, 0, 0, 0)
        for j, m in enumerate(methods):
            cell = QWidget()
            cell.setObjectName("methodComparison")
            cell.setProperty("method", m)
            vbox = QVBoxLayout(cell)
            vbox.setSpacing(4)
            vbox.setContentsMargins(0, 0, 0, 0)
            vbox.addWidget(_method_caption(m))
            img_lbl = ImageLabel()
            img_lbl.setObjectName("cropImage")
            img_lbl.setMinimumHeight(96)
            img_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            vbox.addWidget(img_lbl, 1)
            grid.addWidget(cell, j // best_cols, j % best_cols)
            pixmap = source[m][rect_index] if source and m in source and rect_index < len(source[m]) else None
            img_lbl.set_image(pixmap)
            if self._residual_data is not None:
                residual_caption = QLabel("参考图" if m == 'Ground_Truth' else "绝对残差 · RGB 均值")
                residual_caption.setProperty("typography", "caption")
                residual_caption.setAlignment(Qt.AlignCenter)
                vbox.addWidget(residual_caption)
                residual = ImageLabel()
                residual.setObjectName("residualImage")
                residual.setMinimumHeight(96)
                residual.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                if m == 'Ground_Truth':
                    residual.setText("Ground Truth\n作为残差计算参考")
                else:
                    values = self._residual_data.get(m, [])
                    residual.set_image(values[rect_index] if rect_index < len(values) else None)
                    if residual._pixmap is None:
                        residual.setText("无可用残差")
                vbox.addWidget(residual, 1)
        for c in range(best_cols):
            grid.setColumnStretch(c, 1)
        for r_idx in range((len(methods) + best_cols - 1) // best_cols):
            grid.setRowStretch(r_idx, 1)
        return holder

    def _rebuild(self):
        """根据当前面板宽度重建所有内容。"""
        # 清除旧的所有内容 (widget + stretch spacer)
        self._groups.clear()
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        methods = self._methods
        rects = self._rects
        crop_data = self._crop_data
        residual_data = self._residual_data

        if not rects or not methods:
            return

        has_residual = residual_data is not None

        # 自动选择最优列数 (并记录, 供 resize 时判断是否需要重建)
        best_cols = self._compute_best_cols()
        self._last_cols = best_cols

        for i, r in enumerate(rects):
            color = r['color']
            group_widgets = []

            # 标题
            title = _group_caption(
                color, f"矩形框 {i+1}　({r['x']}, {r['y']})　{r['w']}×{r['h']}")
            self.main_layout.addWidget(title)
            group_widgets.append(title)

            # The color scale occupies its own column; method columns never shift.
            group_row = QWidget()
            row_layout = QHBoxLayout(group_row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(GRID_SPACING)
            grid_w = self._tile_grid(methods, best_cols, color, crop_data, i)
            row_layout.addWidget(grid_w, 1)
            if has_residual:
                scale_column = QWidget()
                scale_column.setFixedWidth(64)
                scale_layout = QVBoxLayout(scale_column)
                scale_layout.setContentsMargins(0, 0, 0, 0)
                scale_title = QLabel("残差\n共享色标")
                scale_title.setAlignment(Qt.AlignCenter)
                scale_title.setProperty("typography", "caption")
                scale_layout.addWidget(scale_title)
                if self._colorbar_pixmap and not self._colorbar_pixmap.isNull():
                    cb_lbl = ImageLabel()
                    cb_lbl.setObjectName("residualColorbar")
                    cb_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    cb_lbl.setFixedSize(64, 320)
                    cb_lbl.set_edge(None, 0.0)
                    cb_lbl.set_image(self._colorbar_pixmap)
                    scale_layout.addWidget(cb_lbl)
                scale_layout.addStretch()
                row_layout.addWidget(scale_column)
            self.main_layout.addWidget(group_row, 1)
            group_widgets.append(group_row)

            self._groups.append(group_widgets)

        self.main_layout.addStretch(0)


# ===========================================================================
# Tab 3: EPI 对比
# ===========================================================================
class EPICompareTab(QWidget):
    """EPI 对比 — 所有方法的 EPI 竖向排列, 统一宽度, 方便上下对比线性结构。"""

    EPI_DISPLAY_HEIGHT = 44  # 每条 EPI 的固定显示高度

    def __init__(self, parent=None):
        super().__init__(parent)
        self._methods = []
        self._epi_data = {}
        self._scale = None
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(120)
        self._resize_timer.timeout.connect(self._refresh_fit)
        self._init_ui()

    def _init_ui(self):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.vbox = QVBoxLayout(self.container)
        self.vbox.setSpacing(6)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.scroll.setWidget(self.container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

        self._rows = []  # [(label_widget, name_lbl, img_lbl)]

    def update_epis(self, methods, epi_data):
        """One common scale for every EPI, without stretching to fill a row."""
        self._methods = list(methods)
        self._epi_data = epi_data or {}
        self._scale = self._fit_scale()
        self._rebuild()
        self._resize_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._methods:
            # Recompute after the scroll viewport has its final size. Only
            # parent resizes schedule this; rebuilding rows cannot loop it.
            self._resize_timer.start()

    def _refresh_fit(self):
        scale = self._fit_scale()
        if self._scale is None or abs(scale - self._scale) > 1e-9:
            self._scale = scale
            self._rebuild()
        else:
            # An all-missing EPI set has no image scale change on resize.
            # Its placeholders must still shrink with the viewport.
            width = max(40, min(240, self.scroll.viewport().width() - 146))
            for method, (_, _, label) in zip(self._methods, self._rows):
                pixmap = self._epi_data.get(method)
                if not pixmap or pixmap.isNull():
                    label.setFixedWidth(width)

    def _fit_scale(self):
        pixmaps = [p for p in self._epi_data.values() if p and not p.isNull()]
        if not pixmaps:
            return 1.0
        max_width = max(p.width() for p in pixmaps)
        max_height = max(p.height() for p in pixmaps)
        return max(0.01, min(max(40, self.scroll.viewport().width() - 146) / max_width,
                             self.EPI_DISPLAY_HEIGHT / max_height))

    def _rebuild(self):
        # 清除旧内容 (含 addStretch 产生的 spacer)
        while self.vbox.count():
            item = self.vbox.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._rows.clear()

        if not self._methods:
            return

        for m in self._methods:
            row_w = QWidget()
            hbox = QHBoxLayout(row_w)
            hbox.setSpacing(10)
            hbox.setContentsMargins(0, 0, 0, 0)

            # 方法名 (固定宽度, 右对齐, 与图像基线对齐)
            name_lbl = _ElidedLabel(m)
            name_lbl.setFixedWidth(118)
            name_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            name_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            name_lbl.setProperty("typography", "method")
            hbox.addWidget(name_lbl)

            # EPI 图像
            img_lbl = ImagePlate()
            img_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            img_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            pix = self._epi_data.get(m)
            if pix and not pix.isNull():
                # A shared multiplier preserves slope relationships even if
                # methods have different EPI heights; never scale each alone.
                scaled = pix.scaled(max(1, round(pix.width() * self._scale)),
                                    max(1, round(pix.height() * self._scale)),
                                    Qt.KeepAspectRatio, Qt.SmoothTransformation)
                img_lbl.setPixmap(scaled)
                img_lbl.setFixedSize(scaled.size())
            else:
                img_lbl.setText("缺少当前帧 / 视角的 EPI")
                width = max(40, min(240, self.scroll.viewport().width() - 146))
                img_lbl.setFixedSize(width, self.EPI_DISPLAY_HEIGHT)

            hbox.addWidget(img_lbl)
            hbox.addStretch()
            self.vbox.addWidget(row_w)
            self._rows.append((row_w, name_lbl, img_lbl))

        self.vbox.addStretch()


# ===========================================================================
# 主面板: 三个标签页
# ===========================================================================
class ComparisonPanel(QWidget):
    """右侧对比面板 — 三个标签页。"""
    rect_drawn_on_sai = pyqtSignal(int, int, int, int)
    open_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("canvasTabs")
        self.tabs.setDocumentMode(True)
        self.sai_tab = SAIGridTab()
        self.zoom_tab = ZoomCompareTab()
        self.epi_tab = EPICompareTab()

        self.tabs.addTab(self.sai_tab, "SAI 全图")
        self.tabs.addTab(self.zoom_tab, "局部放大")
        self.tabs.addTab(self.epi_tab, "EPI 对比")

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self._build_empty_state())
        self.content_stack.addWidget(self.tabs)
        layout.addWidget(self.content_stack)

        self.interaction_hint = QLabel()
        self.interaction_hint.setObjectName("interactionHint")
        self.interaction_hint.setAlignment(Qt.AlignCenter)
        self.interaction_hint.hide()
        layout.addWidget(self.interaction_hint)
        self.tabs.currentChanged.connect(self._update_hint)
        self._update_hint()

        # 转发信号
        self.sai_tab.rect_drawn.connect(
            lambda x, y, w, h: self.rect_drawn_on_sai.emit(x, y, w, h))

    def _build_empty_state(self):
        empty = QWidget()
        empty.setObjectName("emptyCanvas")
        empty_layout = QVBoxLayout(empty)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_layout.setSpacing(10)

        self.empty_glyph = QLabel()
        self.empty_glyph.setAlignment(Qt.AlignCenter)
        self.empty_glyph.setFixedHeight(64)

        empty_title = QLabel("打开光场数据")
        empty_title.setObjectName("emptyTitle")
        empty_title.setAlignment(Qt.AlignCenter)
        empty_description = QLabel("选择包含各方法结果的数据目录，\n然后选择场景、帧与视角进行同步比较。")
        empty_description.setObjectName("emptyDescription")
        empty_description.setAlignment(Qt.AlignCenter)
        open_button = QPushButton("打开数据目录…")
        open_button.setObjectName("primaryAction")
        open_button.setCursor(Qt.PointingHandCursor)
        open_button.clicked.connect(self.open_requested.emit)

        empty_layout.addWidget(self.empty_glyph)
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_description)
        empty_layout.addSpacing(6)
        empty_layout.addWidget(open_button, 0, Qt.AlignHCenter)
        self._paint_empty_glyph()
        return empty

    def _paint_empty_glyph(self):
        """A 2×2 grid of plates — the app's own subject, drawn simply."""
        scale = 2
        size = 60
        pixmap = QPixmap(size * scale, size * scale)
        pixmap.fill(Qt.transparent)
        pixmap.setDevicePixelRatio(scale)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        stroke = theme.color("text_3")
        fill = QColor(stroke)
        fill.setAlpha(28)
        painter.setPen(QPen(stroke, 1.4))
        painter.setBrush(fill)
        side, gap = 24, 5
        origin = (size - side * 2 - gap) / 2.0
        for row in range(2):
            for col in range(2):
                painter.drawRoundedRect(
                    QRectF(origin + col * (side + gap),
                           origin + row * (side + gap), side, side), 5, 5)
        painter.end()
        self.empty_glyph.setPixmap(pixmap)

    def set_dark(self, dark):
        """外观切换 — 重绘所有自绘图块与空状态图标。"""
        theme.set_active(dark)
        self._paint_empty_glyph()
        for plate in self.findChildren(ImagePlate):
            plate.update()

    def set_methods(self, methods):
        self.sai_tab.set_methods(methods)
        self.content_stack.setCurrentIndex(1 if methods else 0)
        self._update_hint()

    def _update_hint(self, *_):
        self.interaction_hint.setVisible(self.content_stack.currentIndex() == 1)
        hints = {
            self.sai_tab: "滚轮缩放  ·  拖动平移  ·  右键拖动添加选区  ·  Home 复位",
            self.zoom_tab: "在全图中添加选区，或前往侧栏「标注」设置局部放大与残差",
            self.epi_tab: "前往侧栏「标注」开启 EPI，并调整方向与采样位置",
        }
        self.interaction_hint.setText(hints.get(self.tabs.currentWidget(), ""))

    def update_method_sai(self, method, pixmap):
        self.sai_tab.set_sai(method, pixmap)

    def update_all_zooms(self, methods, rects, crop_data,
                         residual_data=None, colorbar_pixmap=None):
        """批量更新局部放大标签页。"""
        self.zoom_tab.update_zooms(
            methods, rects, crop_data, residual_data, colorbar_pixmap)

    def update_all_epis(self, methods, epi_data):
        """批量更新 EPI 标签页。"""
        self.epi_tab.update_epis(methods, epi_data)

    def set_epi_tab_visible(self, visible: bool):
        """显示或隐藏 EPI 标签页。"""
        idx = self.tabs.indexOf(self.epi_tab)
        if visible and idx < 0:
            self.tabs.addTab(self.epi_tab, "EPI 对比")
        elif not visible and idx >= 0:
            self.tabs.removeTab(idx)
