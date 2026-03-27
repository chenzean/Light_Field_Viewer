"""
左侧设置面板 — 数据目录、角度分辨率、场景/帧选择、方法选择、矩形框管理、EPI 设置
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QSpinBox, QComboBox, QCheckBox, QRadioButton, QPushButton,
    QButtonGroup, QListWidget, QListWidgetItem, QFileDialog,
    QLineEdit, QScrollArea, QAbstractItemView
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor, QIcon, QPixmap

import config as cfg


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

    def _init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(6)

        # ---- 可视化模式选择 ----
        grp_vis = QGroupBox("可视化模式")
        hbox_vis = QHBoxLayout()
        self.radio_sai = QRadioButton("子孔径图像 (SAI)")
        self.radio_mli = QRadioButton("微透镜图像 (MLI)")
        self.radio_sai.setChecked(True)
        self.btn_grp_vis = QButtonGroup()
        self.btn_grp_vis.addButton(self.radio_sai, 0)
        self.btn_grp_vis.addButton(self.radio_mli, 1)
        self.btn_grp_vis.buttonClicked.connect(self._on_vis_mode_changed)
        hbox_vis.addWidget(self.radio_sai)
        hbox_vis.addWidget(self.radio_mli)
        grp_vis.setLayout(hbox_vis)
        layout.addWidget(grp_vis)

        # ---- 数据类型选择 ----
        grp_mode = QGroupBox("数据类型")
        hbox_mode = QHBoxLayout()
        self.radio_image = QRadioButton("光场图像")
        self.radio_video = QRadioButton("光场视频")
        self.radio_video.setChecked(True)
        self.btn_grp_mode = QButtonGroup()
        self.btn_grp_mode.addButton(self.radio_image, 0)
        self.btn_grp_mode.addButton(self.radio_video, 1)
        self.btn_grp_mode.buttonClicked.connect(self._on_mode_changed)
        hbox_mode.addWidget(self.radio_image)
        hbox_mode.addWidget(self.radio_video)
        grp_mode.setLayout(hbox_mode)
        layout.addWidget(grp_mode)

        # ---- 数据目录 ----
        grp_dir = QGroupBox("数据目录")
        vbox = QVBoxLayout()
        # 数据根目录
        hbox = QHBoxLayout()
        self.txt_data_root = QLineEdit()
        self.txt_data_root.setPlaceholderText("选择数据根目录...")
        self.txt_data_root.setReadOnly(True)
        btn_browse_data = QPushButton("浏览")
        btn_browse_data.clicked.connect(self._browse_data_root)
        hbox.addWidget(QLabel("数据:"))
        hbox.addWidget(self.txt_data_root)
        hbox.addWidget(btn_browse_data)
        vbox.addLayout(hbox)
        # 导出目录
        hbox2 = QHBoxLayout()
        self.txt_export_dir = QLineEdit()
        self.txt_export_dir.setPlaceholderText("选择导出目录...")
        self.txt_export_dir.setReadOnly(True)
        btn_browse_export = QPushButton("浏览")
        btn_browse_export.clicked.connect(self._browse_export_dir)
        hbox2.addWidget(QLabel("导出:"))
        hbox2.addWidget(self.txt_export_dir)
        hbox2.addWidget(btn_browse_export)
        vbox.addLayout(hbox2)
        grp_dir.setLayout(vbox)
        layout.addWidget(grp_dir)

        # ---- 角度分辨率 (MLI 模式下隐藏) ----
        self.grp_angular = QGroupBox("角度分辨率")
        grp_angular = self.grp_angular
        hbox3 = QHBoxLayout()
        self.spin_u_max = QSpinBox()
        self.spin_u_max.setRange(1, 20)
        self.spin_u_max.setValue(cfg.DEFAULT_ANGULAR_U)
        self.spin_v_max = QSpinBox()
        self.spin_v_max.setRange(1, 20)
        self.spin_v_max.setValue(cfg.DEFAULT_ANGULAR_V)
        hbox3.addWidget(QLabel("U:"))
        hbox3.addWidget(self.spin_u_max)
        hbox3.addWidget(QLabel("V:"))
        hbox3.addWidget(self.spin_v_max)
        self.spin_u_max.valueChanged.connect(self._on_angular_changed)
        self.spin_v_max.valueChanged.connect(self._on_angular_changed)
        grp_angular.setLayout(hbox3)
        layout.addWidget(grp_angular)

        # ---- 场景 / 帧 / 角度坐标 ----
        grp_sel = QGroupBox("数据选择")
        vbox2 = QVBoxLayout()
        # 场景
        hbox_scene = QHBoxLayout()
        hbox_scene.addWidget(QLabel("场景:"))
        self.combo_scene = QComboBox()
        self.combo_scene.currentTextChanged.connect(self._on_scene_changed)
        hbox_scene.addWidget(self.combo_scene)
        vbox2.addLayout(hbox_scene)
        # 帧 (光场视频时可用, 光场图像时隐藏)
        self.hbox_frame_widget = QWidget()
        hbox_frame = QHBoxLayout(self.hbox_frame_widget)
        hbox_frame.setContentsMargins(0, 0, 0, 0)
        hbox_frame.addWidget(QLabel("帧:"))
        self.combo_frame = QComboBox()
        self.combo_frame.currentIndexChanged.connect(self._on_frame_changed)
        hbox_frame.addWidget(self.combo_frame)
        vbox2.addWidget(self.hbox_frame_widget)
        # 角度坐标 (MLI 模式下隐藏)
        self.widget_uv = QWidget()
        hbox_uv = QHBoxLayout(self.widget_uv)
        hbox_uv.setContentsMargins(0, 0, 0, 0)
        hbox_uv.addWidget(QLabel("u:"))
        self.spin_u = QSpinBox()
        self.spin_u.setRange(1, cfg.DEFAULT_ANGULAR_U)
        self.spin_u.setValue(1)
        hbox_uv.addWidget(self.spin_u)
        hbox_uv.addWidget(QLabel("v:"))
        self.spin_v = QSpinBox()
        self.spin_v.setRange(1, cfg.DEFAULT_ANGULAR_V)
        self.spin_v.setValue(1)
        hbox_uv.addWidget(self.spin_v)
        self.spin_u.valueChanged.connect(self._on_uv_changed)
        self.spin_v.valueChanged.connect(self._on_uv_changed)
        vbox2.addWidget(self.widget_uv)
        grp_sel.setLayout(vbox2)
        layout.addWidget(grp_sel)

        # ---- 方法选择 ----
        grp_methods = QGroupBox("方法选择")
        vbox3 = QVBoxLayout()
        hbox_btn = QHBoxLayout()
        btn_select_all = QPushButton("全选")
        btn_select_all.clicked.connect(self._select_all_methods)
        btn_deselect_all = QPushButton("全不选")
        btn_deselect_all.clicked.connect(self._deselect_all_methods)
        hbox_btn.addWidget(btn_select_all)
        hbox_btn.addWidget(btn_deselect_all)
        vbox3.addLayout(hbox_btn)
        self.list_methods = QListWidget()
        self.list_methods.setSelectionMode(QAbstractItemView.NoSelection)
        self.list_methods.itemChanged.connect(self._on_methods_changed)
        vbox3.addWidget(self.list_methods)
        grp_methods.setLayout(vbox3)
        layout.addWidget(grp_methods)

        # ---- 矩形框管理 ----
        grp_rect = QGroupBox("矩形框管理")
        vbox4 = QVBoxLayout()
        hbox_rect_btn = QHBoxLayout()
        btn_add_rect = QPushButton("+ 添加框")
        btn_add_rect.clicked.connect(lambda: self.rect_added.emit())
        btn_del_rect = QPushButton("- 删除框")
        btn_del_rect.clicked.connect(self._on_remove_rect)
        btn_clear_rect = QPushButton("清空全部")
        btn_clear_rect.clicked.connect(lambda: self.rects_cleared.emit())
        hbox_rect_btn.addWidget(btn_add_rect)
        hbox_rect_btn.addWidget(btn_del_rect)
        hbox_rect_btn.addWidget(btn_clear_rect)
        vbox4.addLayout(hbox_rect_btn)
        # 框列表
        self.list_rects = QListWidget()
        self.list_rects.currentRowChanged.connect(self._on_rect_selected)
        vbox4.addWidget(self.list_rects)
        # 选中框参数
        vbox4.addWidget(QLabel("选中框参数:"))
        grid_rect = QVBoxLayout()
        for name, attr, default in [
            ("X:", 'spin_rect_x', cfg.DEFAULT_RECT_X),
            ("Y:", 'spin_rect_y', cfg.DEFAULT_RECT_Y),
            ("W:", 'spin_rect_w', cfg.DEFAULT_RECT_W),
            ("H:", 'spin_rect_h', cfg.DEFAULT_RECT_H),
        ]:
            hb = QHBoxLayout()
            hb.addWidget(QLabel(name))
            spin = QSpinBox()
            spin.setRange(0, 4096)
            spin.setValue(default)
            spin.valueChanged.connect(self._on_rect_params_changed)
            setattr(self, attr, spin)
            hb.addWidget(spin)
            grid_rect.addLayout(hb)
        # 粗细
        hb_thick = QHBoxLayout()
        hb_thick.addWidget(QLabel("粗细:"))
        self.spin_rect_thickness = QSpinBox()
        self.spin_rect_thickness.setRange(1, 20)
        self.spin_rect_thickness.setValue(cfg.DEFAULT_RECT_THICKNESS)
        self.spin_rect_thickness.valueChanged.connect(self._on_rect_params_changed)
        hb_thick.addWidget(self.spin_rect_thickness)
        grid_rect.addLayout(hb_thick)
        # RGB 颜色输入
        hb_color = QHBoxLayout()
        hb_color.addWidget(QLabel("颜色 R:"))
        self.spin_rect_r = QSpinBox()
        self.spin_rect_r.setRange(0, 255)
        self.spin_rect_r.setValue(255)
        self.spin_rect_r.valueChanged.connect(self._on_rect_params_changed)
        hb_color.addWidget(self.spin_rect_r)
        hb_color.addWidget(QLabel("G:"))
        self.spin_rect_g = QSpinBox()
        self.spin_rect_g.setRange(0, 255)
        self.spin_rect_g.setValue(0)
        self.spin_rect_g.valueChanged.connect(self._on_rect_params_changed)
        hb_color.addWidget(self.spin_rect_g)
        hb_color.addWidget(QLabel("B:"))
        self.spin_rect_b = QSpinBox()
        self.spin_rect_b.setRange(0, 255)
        self.spin_rect_b.setValue(0)
        self.spin_rect_b.valueChanged.connect(self._on_rect_params_changed)
        hb_color.addWidget(self.spin_rect_b)
        grid_rect.addLayout(hb_color)
        vbox4.addLayout(grid_rect)
        grp_rect.setLayout(vbox4)
        layout.addWidget(grp_rect)

        # ---- 残差图设置 ----
        grp_residual = QGroupBox("残差图")
        vbox_res = QVBoxLayout()
        self.chk_residual = QCheckBox("显示残差图 (与 Ground_Truth 对比)")
        self.chk_residual.setChecked(False)
        self.chk_residual.stateChanged.connect(self._on_residual_changed)
        vbox_res.addWidget(self.chk_residual)
        grp_residual.setLayout(vbox_res)
        layout.addWidget(grp_residual)

        # ---- EPI 设置 (MLI 模式下隐藏) ----
        self.grp_epi = QGroupBox("EPI 设置")
        grp_epi = self.grp_epi
        vbox5 = QVBoxLayout()
        self.chk_epi = QCheckBox("显示 EPI")
        self.chk_epi.setChecked(False)
        self.chk_epi.stateChanged.connect(self._on_epi_changed)
        vbox5.addWidget(self.chk_epi)
        # 方向单选
        hbox_orient = QHBoxLayout()
        self.radio_h_epi = QRadioButton("水平")
        self.radio_v_epi = QRadioButton("垂直")
        self.radio_h_epi.setChecked(True)
        self.btn_grp_epi = QButtonGroup()
        self.btn_grp_epi.addButton(self.radio_h_epi, 0)
        self.btn_grp_epi.addButton(self.radio_v_epi, 1)
        self.btn_grp_epi.buttonClicked.connect(self._on_epi_changed)
        hbox_orient.addWidget(self.radio_h_epi)
        hbox_orient.addWidget(self.radio_v_epi)
        vbox5.addLayout(hbox_orient)
        # EPI 参数
        for name, attr, default, max_val in [
            ("角度索引:", 'spin_epi_angular', cfg.DEFAULT_EPI_ANGULAR_IDX, 20),
            ("空间位置:", 'spin_epi_spatial', cfg.DEFAULT_EPI_SPATIAL_POS, 4096),
            ("裁剪起始:", 'spin_epi_crop_start', cfg.DEFAULT_EPI_CROP_START, 4096),
            ("裁剪结束:", 'spin_epi_crop_end', cfg.DEFAULT_EPI_CROP_END, 4096),
            ("高度拉伸:", 'spin_epi_stretch', cfg.DEFAULT_EPI_STRETCH, 20),
        ]:
            hb = QHBoxLayout()
            hb.addWidget(QLabel(name))
            spin = QSpinBox()
            spin.setRange(1, max_val)
            spin.setValue(default)
            spin.valueChanged.connect(self._on_epi_changed)
            setattr(self, attr, spin)
            hb.addWidget(spin)
            vbox5.addLayout(hb)
        grp_epi.setLayout(vbox5)
        layout.addWidget(grp_epi)

        # ---- 导出 DPI 设置 ----
        grp_dpi = QGroupBox("导出 DPI")
        hbox_dpi = QHBoxLayout()
        hbox_dpi.addWidget(QLabel("颜色条 DPI:"))
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(50, 600)
        self.spin_dpi.setValue(150)
        self.spin_dpi.setSingleStep(50)
        hbox_dpi.addWidget(self.spin_dpi)
        grp_dpi.setLayout(hbox_dpi)
        layout.addWidget(grp_dpi)

        # ---- 按钮 ----
        hbox_actions = QHBoxLayout()
        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(lambda: self.refresh_requested.emit())
        btn_export = QPushButton("导出")
        btn_export.clicked.connect(lambda: self.export_requested.emit())
        hbox_actions.addWidget(btn_refresh)
        hbox_actions.addWidget(btn_export)
        layout.addLayout(hbox_actions)

        layout.addStretch()
        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

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
        self._building = False

    def set_frames(self, frames: list):
        self._building = True
        self.combo_frame.clear()
        self.combo_frame.addItems(frames)
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
            color = r['color']
            label = f"框{i+1} ({r['x']},{r['y']},{r['w']},{r['h']})"
            item = QListWidgetItem(label)
            # 用颜色块作为图标
            pix = QPixmap(16, 16)
            pix.fill(QColor(*color))
            item.setIcon(QIcon(pix))
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
