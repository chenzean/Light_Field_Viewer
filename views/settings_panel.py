"""
左侧设置面板 — 数据目录、角度分辨率、场景/帧选择、方法选择、矩形框管理、EPI 设置

布局参照 macOS 系统设置: 每组是一张圆角卡片, 卡片内是「左标签 / 右控件」的
等高行, 行与行之间用一条内缩的发丝线分隔。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QPushButton, QButtonGroup, QListWidget, QListWidgetItem,
    QFileDialog, QScrollArea, QAbstractItemView, QSizePolicy,
    QStackedWidget, QFrame, QColorDialog
)
from PyQt5.QtCore import pyqtSignal, Qt, QRectF, QSize
from PyQt5.QtGui import QColor, QIcon, QPixmap, QPainter, QPen

import config as cfg
from views.controls import (
    SelectionBox, NumberBox, CheckBox, RadioButton, PushButton, TextField,
    SegmentedControl, CheckListDelegate
)

# Row metrics shared by every card, so all pages line up vertically.
ROW_MARGINS = (12, 5, 12, 5)
STEPPER_WIDTH = 94
COMBO_MIN_WIDTH = 132
COMBO_MAX_WIDTH = 236
SMALL_STEPPER_WIDTH = 80
LABEL_WIDTH = 62


def _separator():
    line = QFrame()
    line.setObjectName("rowSeparator")
    line.setFrameShape(QFrame.NoFrame)
    line.setFixedHeight(1)
    return line


def _row(label, widgets, expand=False, label_width=None, fill=False):
    """One card row: label on the left, control(s) on the right.

    ``expand`` lets the first control take the free space (text fields);
    ``fill`` splits the row evenly between the controls (button clusters).
    """
    if not isinstance(widgets, (list, tuple)):
        widgets = [widgets]
    row = QWidget()
    row.setObjectName("formRow")
    box = QHBoxLayout(row)
    box.setContentsMargins(*ROW_MARGINS)
    box.setSpacing(8)
    if label is not None:
        caption = QLabel(label) if isinstance(label, str) else label
        caption.setObjectName("rowLabel")
        if label_width:
            caption.setFixedWidth(label_width)
        box.addWidget(caption)
    if fill:
        for widget in widgets:
            box.addWidget(widget, 1)
    elif expand:
        for index, widget in enumerate(widgets):
            box.addWidget(widget, 1 if index == 0 else 0)
    else:
        box.addStretch(1)
        for widget in widgets:
            box.addWidget(widget)
    return row


def _stack(*items):
    """Group rows and separators into one widget that can be hidden together."""
    holder = QWidget()
    holder.setObjectName("formRow")
    box = QVBoxLayout(holder)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(0)
    for item in items:
        box.addWidget(item)
    return holder


def _card(title, items):
    """A titled rounded card; separators are inserted between the rows."""
    group = QGroupBox(title)
    box = QVBoxLayout(group)
    box.setContentsMargins(0, 4, 0, 4)
    box.setSpacing(0)
    for index, item in enumerate(items):
        if index:
            box.addWidget(_separator())
        box.addWidget(item)
    return group


def _segmented(buttons):
    """Two or more radios rendered as one recessed segmented control."""
    return SegmentedControl(buttons)


def _selector(placeholder):
    """Pop-up button sized to its content, as macOS sizes one.

    Stretching it across the row is what made the control column look ragged
    next to the narrow steppers, so it grows with its text between a floor and
    a ceiling instead.
    """
    combo = SelectionBox()
    combo.setPlaceholderText(placeholder)
    combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
    combo.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    combo.setMinimumWidth(COMBO_MIN_WIDTH)
    combo.setMaximumWidth(COMBO_MAX_WIDTH)
    combo.currentTextChanged.connect(
        lambda text, box=combo: box.setToolTip(text))
    return combo


def _stepper(minimum, maximum, value, width=STEPPER_WIDTH, step=1):
    spin = NumberBox()
    spin.setRange(minimum, maximum)
    spin.setSingleStep(step)
    spin.setValue(value)
    spin.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    spin.setFixedWidth(width)
    return spin


def _flat_list(minimum, maximum):
    """A list that sits inside a card without a second border around it."""
    widget = QListWidget()
    widget.setObjectName("cardList")
    widget.setMinimumHeight(minimum)
    widget.setMaximumHeight(maximum)
    widget.setFrameShape(QFrame.NoFrame)
    widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    return widget


def _rounded_chip(color, width, height, radius):
    scale = 2
    pixmap = QPixmap(width * scale, height * scale)
    pixmap.fill(Qt.transparent)
    pixmap.setDevicePixelRatio(scale)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(0, 0, 0, 40), 1))
    painter.setBrush(color)
    painter.drawRoundedRect(
        QRectF(0.5, 0.5, width - 1, height - 1), radius, radius)
    painter.end()
    return QIcon(pixmap)


def _swatch(color, size=12):
    """Rounded colour chip, the way macOS shows a tag colour."""
    return _rounded_chip(QColor(*color), size, size, 3.5)


def _swatch_bar(color):
    """Wider chip used inside the colour-well button."""
    return _rounded_chip(color, 40, 14, 4)


class SettingsPanel(QWidget):
    """左侧设置面板。"""

    # ---- 信号 ----
    mode_changed = pyqtSignal(str)             # 'image' 或 'video'
    vis_mode_changed = pyqtSignal(str)         # 'sai' 或 'mli'
    data_root_changed = pyqtSignal(str)
    export_dir_changed = pyqtSignal(str)
    angular_resolution_changed = pyqtSignal(int, int)
    scene_changed = pyqtSignal(str)
    frame_changed = pyqtSignal(int)            # 帧位置索引 (0-based)
    uv_changed = pyqtSignal(int, int)
    methods_changed = pyqtSignal(list)         # 选中的方法列表
    rect_added = pyqtSignal()
    rect_removed = pyqtSignal(int)             # 删除第 i 个框
    rects_cleared = pyqtSignal()               # 清空所有框
    rect_selected = pyqtSignal(int)            # 选中第 i 个框
    rect_params_changed = pyqtSignal(int, dict)  # 第 i 个框参数变化
    epi_params_changed = pyqtSignal(dict)
    residual_changed = pyqtSignal(bool)        # 残差图开关
    refresh_requested = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._building = True  # 防止初始化时触发信号
        self._init_ui()
        self._building = False

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------
    def _init_ui(self):
        # A QTabBar always spans its parent's full width, which would stretch
        # the pill across the sidebar; a stack behind a segmented control gives
        # the macOS inspector shape while keeping count/setCurrentIndex/widget.
        self.sections = QStackedWidget()
        self.sections.setObjectName("inspectorTabs")
        self.section_buttons = QButtonGroup(self)
        tabs = []
        for index, (title, groups) in enumerate([
            ("数据", self._data_groups()),
            ("标注", self._annotation_groups()),
            ("导出", self._export_groups()),
        ]):
            self.sections.addWidget(self._page(groups))
            button = RadioButton(title)
            button.setChecked(index == 0)
            self.section_buttons.addButton(button, index)
            tabs.append(button)
        self.section_buttons.buttonClicked.connect(
            lambda button: self.sections.setCurrentIndex(
                self.section_buttons.id(button)))
        self.sections.currentChanged.connect(self._sync_section_buttons)

        picker = QWidget()
        picker_layout = QHBoxLayout(picker)
        picker_layout.setContentsMargins(14, 0, 14, 0)
        picker_layout.addStretch(1)
        picker_layout.addWidget(_segmented(tabs))
        picker_layout.addStretch(1)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 12, 0, 0)
        main_layout.setSpacing(10)
        main_layout.addWidget(picker)
        main_layout.addWidget(self.sections, 1)
        for button in self.findChildren(QPushButton):
            button.setCursor(Qt.PointingHandCursor)

    def _sync_section_buttons(self, index):
        button = self.section_buttons.button(index)
        if button is not None:
            button.setChecked(True)

    def _page(self, groups):
        page = QWidget()
        page.setObjectName("settingsContent")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(14, 10, 14, 16)
        page_layout.setSpacing(14)
        for group in groups:
            page_layout.addWidget(group)
        page_layout.addStretch()
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(page)
        return area

    # ---- 「数据」页 ----
    def _data_groups(self):
        # 数据根目录
        self.txt_data_root = TextField()
        self.txt_data_root.setPlaceholderText("尚未选择")
        self.txt_data_root.setReadOnly(True)
        browse_data = PushButton("浏览…")
        browse_data.clicked.connect(self._browse_data_root)
        grp_dir = _card("数据目录", [
            _row("数据", [self.txt_data_root, browse_data], expand=True,
                 label_width=34),
        ])

        # 可视化模式 / 数据类型 — 两个分段控件
        self.radio_sai = RadioButton("子孔径图像 (SAI)")
        self.radio_mli = RadioButton("微透镜图像 (MLI)")
        self.radio_sai.setChecked(True)
        self.btn_grp_vis = QButtonGroup(self)
        self.btn_grp_vis.addButton(self.radio_sai, 0)
        self.btn_grp_vis.addButton(self.radio_mli, 1)
        self.btn_grp_vis.buttonClicked.connect(self._on_vis_mode_changed)

        self.radio_image = RadioButton("光场图像")
        self.radio_video = RadioButton("光场视频")
        self.radio_video.setChecked(True)
        self.btn_grp_mode = QButtonGroup(self)
        self.btn_grp_mode.addButton(self.radio_image, 0)
        self.btn_grp_mode.addButton(self.radio_video, 1)
        self.btn_grp_mode.buttonClicked.connect(self._on_mode_changed)

        for button, short in [(self.radio_sai, "SAI"), (self.radio_mli, "MLI"),
                              (self.radio_image, "图像"), (self.radio_video, "视频")]:
            button.setToolTip(button.text())
            button.setText(short)

        display_group = _card("显示方式", [
            _row("模式", _segmented([self.radio_sai, self.radio_mli]),
                 label_width=34),
            _row("类型", _segmented([self.radio_image, self.radio_video]),
                 label_width=34),
        ])

        # 角度分辨率 (MLI 模式下隐藏)
        self.spin_u_max = _stepper(1, 20, cfg.DEFAULT_ANGULAR_U)
        self.spin_v_max = _stepper(1, 20, cfg.DEFAULT_ANGULAR_V)
        self.spin_u_max.valueChanged.connect(self._on_angular_changed)
        self.spin_v_max.valueChanged.connect(self._on_angular_changed)
        self.grp_angular = _card("角度分辨率", [
            _row("U 方向", self.spin_u_max),
            _row("V 方向", self.spin_v_max),
        ])

        # 场景 / 帧 / 视角
        self.combo_scene = _selector("尚未载入场景")
        self.combo_scene.currentTextChanged.connect(self._on_scene_changed)
        scene_row = _row("场景", self.combo_scene, label_width=34)

        self.combo_frame = _selector("尚未载入帧")
        self.combo_frame.currentIndexChanged.connect(self._on_frame_changed)
        self.hbox_frame_widget = _stack(
            _separator(), _row("帧", self.combo_frame, label_width=34))

        self.spin_u = _stepper(1, cfg.DEFAULT_ANGULAR_U, 1)
        self.spin_v = _stepper(1, cfg.DEFAULT_ANGULAR_V, 1)
        self.spin_u.valueChanged.connect(self._on_uv_changed)
        self.spin_v.valueChanged.connect(self._on_uv_changed)
        self.widget_uv = _stack(
            _separator(), _row("视角 u", self.spin_u),
            _separator(), _row("视角 v", self.spin_v))

        grp_sel = _card("数据选择", [scene_row])
        grp_sel.layout().addWidget(self.hbox_frame_widget)
        grp_sel.layout().addWidget(self.widget_uv)

        # 方法选择
        select_all = PushButton("全选")
        select_all.clicked.connect(self._select_all_methods)
        deselect_all = PushButton("取消全选")
        deselect_all.clicked.connect(self._deselect_all_methods)
        self.list_methods = _flat_list(104, 168)
        self.list_methods.setSelectionMode(QAbstractItemView.NoSelection)
        self.list_methods.setItemDelegate(CheckListDelegate(self.list_methods))
        self.list_methods.itemChanged.connect(self._on_methods_changed)
        grp_methods = _card("方法选择", [
            _row(None, [select_all, deselect_all], fill=True),
            self.list_methods,
        ])

        return [grp_dir, display_group, self.grp_angular, grp_sel, grp_methods]

    # ---- 「标注」页 ----
    def _annotation_groups(self):
        add_rect = PushButton("添加")
        add_rect.clicked.connect(lambda: self.rect_added.emit())
        del_rect = PushButton("删除")
        del_rect.setProperty("destructive", True)
        del_rect.clicked.connect(self._on_remove_rect)
        clear_rect = PushButton("清空")
        clear_rect.setProperty("destructive", True)
        clear_rect.clicked.connect(lambda: self.rects_cleared.emit())

        self.list_rects = _flat_list(84, 124)
        self.list_rects.currentRowChanged.connect(self._on_rect_selected)

        self.spin_rect_x = _stepper(0, 4096, cfg.DEFAULT_RECT_X, SMALL_STEPPER_WIDTH)
        self.spin_rect_y = _stepper(0, 4096, cfg.DEFAULT_RECT_Y, SMALL_STEPPER_WIDTH)
        self.spin_rect_w = _stepper(0, 4096, cfg.DEFAULT_RECT_W, SMALL_STEPPER_WIDTH)
        self.spin_rect_h = _stepper(0, 4096, cfg.DEFAULT_RECT_H, SMALL_STEPPER_WIDTH)
        self.spin_rect_thickness = _stepper(1, 20, cfg.DEFAULT_RECT_THICKNESS)
        # 颜色改用色板按钮 (QColorDialog), 三个分量仍作为取值来源保留
        self.spin_rect_r = _stepper(0, 255, 255)
        self.spin_rect_g = _stepper(0, 255, 0)
        self.spin_rect_b = _stepper(0, 255, 0)
        for spin in (self.spin_rect_r, self.spin_rect_g, self.spin_rect_b):
            spin.setParent(self)
            spin.hide()
            spin.valueChanged.connect(self._sync_color_well)
        for spin in (self.spin_rect_x, self.spin_rect_y, self.spin_rect_w,
                     self.spin_rect_h, self.spin_rect_thickness,
                     self.spin_rect_r, self.spin_rect_g, self.spin_rect_b):
            spin.valueChanged.connect(self._on_rect_params_changed)

        self.btn_rect_color = PushButton()
        self.btn_rect_color.setObjectName("colorWell")
        self.btn_rect_color.setAccessibleName("矩形框颜色")
        self.btn_rect_color.setToolTip("选择矩形框颜色")
        self.btn_rect_color.setFixedSize(54, 24)
        self.btn_rect_color.setIconSize(QSize(40, 14))
        self.btn_rect_color.clicked.connect(self._pick_rect_color)
        self._sync_color_well()

        self.grp_rect = _card("矩形框管理", [
            _row(None, [add_rect, del_rect, clear_rect], fill=True),
            self.list_rects,
            _row("位置", [self._mini("X", self.spin_rect_x),
                          self._mini("Y", self.spin_rect_y)], label_width=34),
            _row("大小", [self._mini("宽", self.spin_rect_w),
                          self._mini("高", self.spin_rect_h)], label_width=34),
            _row("线宽", self.spin_rect_thickness, label_width=34),
            _row("颜色", self.btn_rect_color, label_width=34),
        ])
        grp_rect = self.grp_rect

        self.chk_residual = CheckBox("显示残差图 (与 Ground_Truth 对比)")
        self.chk_residual.setChecked(False)
        self.chk_residual.stateChanged.connect(self._on_residual_changed)
        grp_residual = _card("残差图", [
            _row(None, self.chk_residual, expand=True),
        ])

        self.chk_epi = CheckBox("显示 EPI")
        self.chk_epi.setChecked(False)
        self.chk_epi.stateChanged.connect(self._on_epi_changed)
        self.radio_h_epi = RadioButton("水平")
        self.radio_v_epi = RadioButton("垂直")
        self.radio_h_epi.setChecked(True)
        self.btn_grp_epi = QButtonGroup(self)
        self.btn_grp_epi.addButton(self.radio_h_epi, 0)
        self.btn_grp_epi.addButton(self.radio_v_epi, 1)
        self.btn_grp_epi.buttonClicked.connect(self._on_epi_changed)

        epi_rows = [
            _row(None, self.chk_epi, expand=True),
            _row("方向", _segmented([self.radio_h_epi, self.radio_v_epi]),
                 label_width=LABEL_WIDTH),
        ]
        for caption, attr, default, maximum in [
            ("角度索引", 'spin_epi_angular', cfg.DEFAULT_EPI_ANGULAR_IDX, 20),
            ("空间位置", 'spin_epi_spatial', cfg.DEFAULT_EPI_SPATIAL_POS, 4096),
            ("裁剪起始", 'spin_epi_crop_start', cfg.DEFAULT_EPI_CROP_START, 4096),
            ("裁剪结束", 'spin_epi_crop_end', cfg.DEFAULT_EPI_CROP_END, 4096),
            ("高度拉伸", 'spin_epi_stretch', cfg.DEFAULT_EPI_STRETCH, 20),
        ]:
            spin = _stepper(1, maximum, default)
            spin.valueChanged.connect(self._on_epi_changed)
            setattr(self, attr, spin)
            epi_rows.append(_row(caption, spin, label_width=LABEL_WIDTH))
        self.grp_epi = _card("EPI 设置", epi_rows)

        return [grp_rect, grp_residual, self.grp_epi]

    # ---- 「导出」页 ----
    def _export_groups(self):
        self.txt_export_dir = TextField()
        self.txt_export_dir.setPlaceholderText("尚未选择")
        self.txt_export_dir.setReadOnly(True)
        browse_export = PushButton("浏览…")
        browse_export.clicked.connect(self._browse_export_dir)
        export_group = _card("保存位置", [
            _row("目录", [self.txt_export_dir, browse_export], expand=True,
                 label_width=34),
        ])

        self.spin_dpi = _stepper(50, 600, 150, step=50)
        grp_dpi = _card("导出 DPI", [
            _row("颜色条", self.spin_dpi, label_width=LABEL_WIDTH),
        ])
        return [export_group, grp_dpi]

    # ---- 颜色色板 ----
    def _rect_color(self):
        return QColor(self.spin_rect_r.value(), self.spin_rect_g.value(),
                      self.spin_rect_b.value())

    def _sync_color_well(self, *_):
        self.btn_rect_color.setIcon(_swatch_bar(self._rect_color()))

    def _pick_rect_color(self):
        chosen = QColorDialog.getColor(
            self._rect_color(), self, "选择矩形框颜色")
        if not chosen.isValid():
            return
        self._building = True
        self.spin_rect_r.setValue(chosen.red())
        self.spin_rect_g.setValue(chosen.green())
        self.spin_rect_b.setValue(chosen.blue())
        self._building = False
        self._sync_color_well()
        self._on_rect_params_changed()

    @staticmethod
    def _mini(caption, spin):
        """A stepper with a one-character caption in front of it."""
        holder = QWidget()
        holder.setObjectName("formRow")
        box = QHBoxLayout(holder)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(5)
        label = QLabel(caption)
        label.setProperty("typography", "caption")
        box.addWidget(label)
        box.addWidget(spin)
        return holder

    # ---- 可视化模式切换 ----
    def _on_vis_mode_changed(self):
        if self._building:
            return
        is_mli = self.radio_mli.isChecked()
        # MLI 模式下隐藏角度分辨率、角度坐标和 EPI 设置
        self.grp_angular.setVisible(not is_mli)
        self.widget_uv.setVisible(not is_mli)
        self.grp_epi.setVisible(not is_mli)
        vis_mode = 'mli' if is_mli else 'sai'
        self.vis_mode_changed.emit(vis_mode)

    # ---- 残差开关 ----
    def _on_residual_changed(self):
        if self._building:
            return
        self.residual_changed.emit(self.chk_residual.isChecked())

    # ---- 模式切换 ----
    def _on_mode_changed(self):
        if self._building:
            return
        is_video = self.radio_video.isChecked()
        self.hbox_frame_widget.setVisible(is_video)
        mode = 'video' if is_video else 'image'
        self.mode_changed.emit(mode)

    # ---- 目录浏览 ----
    def _browse_data_root(self):
        path = QFileDialog.getExistingDirectory(self, "选择数据根目录")
        if path:
            self.txt_data_root.setText(path)
            self.data_root_changed.emit(path)

    def _browse_export_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if path:
            self.txt_export_dir.setText(path)
            self.export_dir_changed.emit(path)

    # ---- 回调 ----
    def _on_angular_changed(self):
        if self._building:
            return
        u_max = self.spin_u_max.value()
        v_max = self.spin_v_max.value()
        self.spin_u.setMaximum(u_max)
        self.spin_v.setMaximum(v_max)
        self.spin_epi_angular.setMaximum(max(u_max, v_max))
        self.angular_resolution_changed.emit(u_max, v_max)

    def _on_scene_changed(self, text):
        if not self._building and text:
            self.scene_changed.emit(text)

    def _on_frame_changed(self, index):
        if not self._building and index >= 0:
            self.frame_changed.emit(index)

    def _on_uv_changed(self):
        if not self._building:
            self.uv_changed.emit(self.spin_u.value(), self.spin_v.value())

    def _on_methods_changed(self, item):
        if self._building:
            return
        selected = []
        for i in range(self.list_methods.count()):
            it = self.list_methods.item(i)
            if it.checkState() == Qt.Checked:
                selected.append(it.text())
        self.methods_changed.emit(selected)

    def _select_all_methods(self):
        self._building = True
        for i in range(self.list_methods.count()):
            self.list_methods.item(i).setCheckState(Qt.Checked)
        self._building = False
        self._on_methods_changed(None)

    def _deselect_all_methods(self):
        self._building = True
        for i in range(self.list_methods.count()):
            self.list_methods.item(i).setCheckState(Qt.Unchecked)
        self._building = False
        self._on_methods_changed(None)

    def _on_remove_rect(self):
        row = self.list_rects.currentRow()
        if row >= 0:
            self.rect_removed.emit(row)

    def _on_rect_selected(self, row):
        if row >= 0:
            self.rect_selected.emit(row)

    def _on_rect_params_changed(self):
        if self._building:
            return
        row = self.list_rects.currentRow()
        if row >= 0:
            params = {
                'x': self.spin_rect_x.value(),
                'y': self.spin_rect_y.value(),
                'w': self.spin_rect_w.value(),
                'h': self.spin_rect_h.value(),
                'thickness': self.spin_rect_thickness.value(),
                'color': (self.spin_rect_r.value(),
                          self.spin_rect_g.value(),
                          self.spin_rect_b.value()),
            }
            self.rect_params_changed.emit(row, params)

    def _on_epi_changed(self, *args):
        if self._building:
            return
        self.epi_params_changed.emit(self.get_epi_params())

    # ---- 外部接口 ----
    def set_methods(self, methods: list):
        """设置方法列表 (带复选框)。"""
        self._building = True
        self.list_methods.clear()
        for m in methods:
            item = QListWidgetItem(m)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.list_methods.addItem(item)
        self._building = False

    def set_scenes(self, scenes: list):
        self._building = True
        self.combo_scene.clear()
        self.combo_scene.addItems(scenes)
        # A placeholder keeps QComboBox on index -1 after insertion, and the
        # controller reads get_current_scene(), so select the first entry back.
        if scenes:
            self.combo_scene.setCurrentIndex(0)
        self._building = False

    def set_frames(self, frames: list):
        self._building = True
        self.combo_frame.clear()
        self.combo_frame.addItems(frames)
        if frames:
            self.combo_frame.setCurrentIndex(0)
        self._building = False

    def set_angular_resolution(self, u_max: int, v_max: int):
        self._building = True
        self.spin_u_max.setValue(u_max)
        self.spin_v_max.setValue(v_max)
        self.spin_u.setMaximum(u_max)
        self.spin_v.setMaximum(v_max)
        self.spin_epi_angular.setMaximum(max(u_max, v_max))
        self._building = False

    def update_rect_list(self, rects: list):
        """更新矩形框列表显示。"""
        self._building = True
        current = self.list_rects.currentRow()
        self.list_rects.clear()
        for i, r in enumerate(rects):
            label = f"框 {i+1}   {r['x']}, {r['y']}   {r['w']}×{r['h']}"
            item = QListWidgetItem(label)
            item.setIcon(_swatch(r['color']))
            self.list_rects.addItem(item)
        if 0 <= current < self.list_rects.count():
            self.list_rects.setCurrentRow(current)
        elif self.list_rects.count() > 0:
            self.list_rects.setCurrentRow(self.list_rects.count() - 1)
        self._building = False

    def set_rect_params(self, rect_dict: dict):
        """从 rect_dict 填充参数到 SpinBox。"""
        self._building = True
        self.spin_rect_x.setValue(rect_dict.get('x', 0))
        self.spin_rect_y.setValue(rect_dict.get('y', 0))
        self.spin_rect_w.setValue(rect_dict.get('w', 128))
        self.spin_rect_h.setValue(rect_dict.get('h', 128))
        self.spin_rect_thickness.setValue(rect_dict.get('thickness', 3))
        color = rect_dict.get('color', (255, 0, 0))
        self.spin_rect_r.setValue(color[0])
        self.spin_rect_g.setValue(color[1])
        self.spin_rect_b.setValue(color[2])
        self._sync_color_well()
        self._building = False

    def get_selected_methods(self) -> list:
        selected = []
        for i in range(self.list_methods.count()):
            it = self.list_methods.item(i)
            if it.checkState() == Qt.Checked:
                selected.append(it.text())
        return selected

    def get_epi_params(self) -> dict:
        return {
            'enabled': self.chk_epi.isChecked(),
            'orientation': 'horizontal' if self.radio_h_epi.isChecked() else 'vertical',
            'angular_idx': self.spin_epi_angular.value(),
            'spatial_pos': self.spin_epi_spatial.value(),
            'crop_start': self.spin_epi_crop_start.value(),
            'crop_end': self.spin_epi_crop_end.value(),
            'stretch': self.spin_epi_stretch.value(),
        }

    def get_export_dpi(self) -> int:
        return self.spin_dpi.value()

    def get_vis_mode(self) -> str:
        return 'mli' if self.radio_mli.isChecked() else 'sai'

    def get_residual_enabled(self) -> bool:
        return self.chk_residual.isChecked()

    def get_mode(self) -> str:
        return 'video' if self.radio_video.isChecked() else 'image'

    def get_current_scene(self) -> str:
        return self.combo_scene.currentText()

    def get_current_frame_index(self) -> int:
        return max(0, self.combo_frame.currentIndex())

    def get_uv(self) -> tuple:
        return (self.spin_u.value(), self.spin_v.value())

    def get_angular_resolution(self) -> tuple:
        return (self.spin_u_max.value(), self.spin_v_max.value())
