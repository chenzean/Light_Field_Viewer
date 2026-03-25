"""
主控制器 — 连接 models 和 views, 处理所有交互逻辑

三个标签页:
  Tab 1 — SAI 全图: 同步缩放/平移, 右键画框
  Tab 2 — 局部放大: 所有方法的裁剪区域并排
  Tab 3 — EPI: 所有方法的 EPI 并排
"""

import numpy as np
from PyQt5.QtCore import QTimer

from models.light_field_data import LightFieldData
from models.rect_annotator import draw_multiple_rectangles, crop_region
from models.epi_extractor import (
    horizontal_epi, vertical_epi, crop_epi, draw_epi_region
)
from utils.image_utils import ndarray_to_qpixmap, ensure_rgb, scale_epi

import config as cfg


class AppController:
    """主控制器。"""

    def __init__(self, main_window):
        self.window = main_window
        self.settings = main_window.settings_panel
        self.comparison = main_window.comparison_panel

        self.lf_data = LightFieldData()

        # 当前状态
        self.mode = 'video'
        self.data_root = ""
        self.export_dir = ""
        self.selected_methods = []
        self.current_scene = ""
        self.current_frame_index = 0
        self.current_u = 1
        self.current_v = 1
        self.u_max = cfg.DEFAULT_ANGULAR_U
        self.v_max = cfg.DEFAULT_ANGULAR_V

        self.rects = []

        self.epi_params = {
            'enabled': False,
            'orientation': 'horizontal',
            'angular_idx': cfg.DEFAULT_EPI_ANGULAR_IDX,
            'spatial_pos': cfg.DEFAULT_EPI_SPATIAL_POS,
            'crop_start': cfg.DEFAULT_EPI_CROP_START,
            'crop_end': cfg.DEFAULT_EPI_CROP_END,
            'stretch': cfg.DEFAULT_EPI_STRETCH,
        }

        self._lf_cache = {}
        self._lf_cache_keys = []

        # SAI 缓存: {(method, scene, frame_index, u, v): np.ndarray}
        self._sai_cache = {}

        # 延迟刷新定时器 (防抖: 参数快速变化时只刷新最后一次)
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(100)  # 100ms 防抖
        self._refresh_timer.timeout.connect(self._do_refresh)

        self._connect_signals()

    def _connect_signals(self):
        s = self.settings
        s.mode_changed.connect(self.on_mode_changed)
        s.data_root_changed.connect(self.on_data_root_changed)
        s.export_dir_changed.connect(self.on_export_dir_changed)
        s.angular_resolution_changed.connect(self.on_angular_changed)
        s.scene_changed.connect(self.on_scene_changed)
        s.frame_changed.connect(self.on_frame_changed)
        s.uv_changed.connect(self.on_uv_changed)
        s.methods_changed.connect(self.on_methods_changed)
        s.rect_added.connect(self.on_rect_added)
        s.rect_removed.connect(self.on_rect_removed)
        s.rects_cleared.connect(self.on_rects_cleared)
        s.rect_selected.connect(self.on_rect_selected)
        s.rect_params_changed.connect(self.on_rect_params_changed)
        s.epi_params_changed.connect(self.on_epi_params_changed)
        s.refresh_requested.connect(self.refresh_all)

        self.comparison.rect_drawn_on_sai.connect(self.on_rect_drawn_on_sai)

    # ==== 模式 ====
    def on_mode_changed(self, mode):
        self.mode = mode
        if self.data_root:
            self.on_data_root_changed(self.data_root)

    # ==== 数据目录 ====
    def on_data_root_changed(self, path):
        self.data_root = path
        self.window.statusBar().showMessage(f"正在扫描: {path} ...")

        self.lf_data.scan_root(path)
        methods = self.lf_data.get_methods()
        scenes = self.lf_data.get_scenes()
        u_max, v_max = self.lf_data.detect_angular_resolution()
        self.u_max, self.v_max = u_max, v_max

        # Ground_Truth 排第一
        if 'Ground_Truth' in methods:
            methods.remove('Ground_Truth')
            methods.insert(0, 'Ground_Truth')

        self.settings.set_methods(methods)
        self.settings.set_scenes(scenes)
        self.settings.set_angular_resolution(u_max, v_max)
        self.selected_methods = methods.copy()

        if scenes:
            self.current_scene = scenes[0]
            self._update_frame_list()

        self.window.statusBar().showMessage(
            f"已加载: {len(methods)} 个方法, {len(scenes)} 个场景, "
            f"角度分辨率 {u_max}×{v_max}")
        self.refresh_all()

    def _update_frame_list(self):
        if self.mode == 'image':
            self.settings.set_frames(["(无帧)"])
            self.current_frame_index = 0
        else:
            display_list = self.lf_data.get_frame_display_list(self.current_scene)
            self.settings.set_frames(display_list if display_list else [])
            self.current_frame_index = 0

    def on_export_dir_changed(self, path):
        self.export_dir = path

    def on_angular_changed(self, u_max, v_max):
        self.u_max, self.v_max = u_max, v_max
        self._lf_cache.clear()
        self._lf_cache_keys.clear()
        self.refresh_all()

    def on_scene_changed(self, scene):
        self.current_scene = scene
        self._sai_cache.clear()
        self._update_frame_list()
        self.refresh_all()

    def on_frame_changed(self, frame_index):
        self.current_frame_index = frame_index
        self._sai_cache.clear()
        self.refresh_all()

    def on_uv_changed(self, u, v):
        self.current_u, self.current_v = u, v
        self._sai_cache.clear()
        self.refresh_all()

    def on_methods_changed(self, methods):
        self.selected_methods = methods
        self.comparison.set_methods(methods)
        self.refresh_all()

    # ==== 矩形框 ====
    def on_rect_added(self):
        idx = len(self.rects)
        color = cfg.RECT_COLOR_CYCLE[idx % len(cfg.RECT_COLOR_CYCLE)]
        self.rects.append({
            'x': cfg.DEFAULT_RECT_X, 'y': cfg.DEFAULT_RECT_Y,
            'w': cfg.DEFAULT_RECT_W, 'h': cfg.DEFAULT_RECT_H,
            'color': color, 'thickness': cfg.DEFAULT_RECT_THICKNESS,
        })
        self.settings.update_rect_list(self.rects)
        self.refresh_all()

    def on_rect_removed(self, idx):
        if 0 <= idx < len(self.rects):
            self.rects.pop(idx)
            self.settings.update_rect_list(self.rects)
            self.refresh_all()

    def on_rects_cleared(self):
        self.rects.clear()
        self.settings.update_rect_list(self.rects)
        self.refresh_all()

    def on_rect_selected(self, idx):
        if 0 <= idx < len(self.rects):
            self.settings.set_rect_params(self.rects[idx])

    def on_rect_params_changed(self, idx, params):
        if 0 <= idx < len(self.rects):
            self.rects[idx].update(params)
            self.settings.update_rect_list(self.rects)
            self.refresh_all()

    def on_rect_drawn_on_sai(self, x, y, w, h):
        idx = len(self.rects)
        color = cfg.RECT_COLOR_CYCLE[idx % len(cfg.RECT_COLOR_CYCLE)]
        self.rects.append({
            'x': x, 'y': y, 'w': w, 'h': h,
            'color': color, 'thickness': cfg.DEFAULT_RECT_THICKNESS,
        })
        self.settings.update_rect_list(self.rects)
        self.refresh_all()

    # ==== EPI ====
    def on_epi_params_changed(self, params):
        self.epi_params = params
        self.refresh_all()

    # ==== 核心刷新 (防抖) ====
    def refresh_all(self):
        """触发延迟刷新 (100ms 防抖)。"""
        self._refresh_timer.start()

    def _do_refresh(self):
        """实际执行刷新。"""
        if not self.selected_methods or not self.current_scene:
            return

        self.comparison.set_methods(self.selected_methods)

        # 从左侧面板读取最新 EPI 参数 (确保同步)
        self.epi_params = self.settings.get_epi_params()

        # Tab 1: SAI 全图
        for method in self.selected_methods:
            sai = self._load_sai(method)
            if sai is None:
                continue
            annotated = draw_multiple_rectangles(sai, self.rects) if self.rects else sai.copy()
            if self.epi_params.get('enabled', False):
                annotated = draw_epi_region(
                    annotated,
                    self.epi_params['spatial_pos'],
                    self.epi_params['crop_start'],
                    self.epi_params['crop_end'],
                    self.epi_params['orientation'],
                    line_color=(0, 0, 255),
                    thickness=2)
            self.comparison.update_method_sai(method, ndarray_to_qpixmap(annotated))

        # Tab 2: 局部放大
        crop_data = {}  # {method: [QPixmap, ...]}
        for method in self.selected_methods:
            sai = self._load_sai(method)
            if sai is None:
                crop_data[method] = []
                continue
            crops = []
            for r in self.rects:
                crop = crop_region(sai, r['x'], r['y'], r['w'], r['h'])
                crops.append(ndarray_to_qpixmap(crop))
            crop_data[method] = crops
        self.comparison.update_all_zooms(self.selected_methods, self.rects, crop_data)

        # Tab 3: EPI
        epi_data = {}  # {method: QPixmap or None}
        if self.epi_params.get('enabled', False):
            for method in self.selected_methods:
                epi_data[method] = self._extract_epi_pixmap(method)
        self.comparison.update_all_epis(self.selected_methods, epi_data)

    def _load_sai(self, method):
        key = (method, self.current_scene, self.current_frame_index,
               self.current_u, self.current_v)
        if key in self._sai_cache:
            return self._sai_cache[key]
        sai = self.lf_data.load_sai(
            method, self.current_scene, self.current_frame_index,
            self.current_u, self.current_v)
        if sai is not None:
            sai = ensure_rgb(sai)
            self._sai_cache[key] = sai
            # 限制缓存大小 (最多 50 张)
            if len(self._sai_cache) > 50:
                oldest = next(iter(self._sai_cache))
                del self._sai_cache[oldest]
        return sai

    def _extract_epi_pixmap(self, method):
        lf = self._get_light_field(method)
        if lf is None:
            return None
        orient = self.epi_params['orientation']
        ang_idx = self.epi_params['angular_idx'] - 1
        spatial_pos = self.epi_params['spatial_pos']
        ang_idx = max(0, min(ang_idx, lf.shape[0] - 1))

        if orient == 'horizontal':
            spatial_pos = max(0, min(spatial_pos, lf.shape[2] - 1))
            epi = horizontal_epi(lf, ang_idx, spatial_pos)
        else:
            spatial_pos = max(0, min(spatial_pos, lf.shape[3] - 1))
            epi = vertical_epi(lf, ang_idx, spatial_pos)

        epi_cropped = crop_epi(epi,
                               self.epi_params['crop_start'],
                               self.epi_params['crop_end'])
        stretch = self.epi_params.get('stretch', 1)
        if stretch > 1:
            epi_cropped = scale_epi(epi_cropped, stretch)
        return ndarray_to_qpixmap(epi_cropped)

    def _get_light_field(self, method):
        key = (method, self.current_scene, self.current_frame_index)
        if key in self._lf_cache:
            return self._lf_cache[key]
        lf = self.lf_data.load_light_field(
            method, self.current_scene, self.current_frame_index,
            self.u_max, self.v_max)
        if lf is not None:
            if len(self._lf_cache_keys) >= cfg.LF_CACHE_SIZE:
                oldest = self._lf_cache_keys.pop(0)
                self._lf_cache.pop(oldest, None)
            self._lf_cache[key] = lf
            self._lf_cache_keys.append(key)
        return lf

    # ==== 导出参数 ====
    def get_export_params(self):
        return {
            'data_root': self.data_root,
            'export_dir': self.export_dir,
            'mode': self.mode,
            'angular_u': self.u_max,
            'angular_v': self.v_max,
            'scene': self.current_scene,
            'frame_index': self.current_frame_index,
            'u': self.current_u,
            'v': self.current_v,
            'methods': self.selected_methods.copy(),
            'rects': [r.copy() for r in self.rects],
            'epi_enabled': self.epi_params.get('enabled', False),
            'epi_orientation': self.epi_params.get('orientation', 'horizontal'),
            'epi_angular_idx': self.epi_params.get('angular_idx', 3),
            'epi_spatial_pos': self.epi_params.get('spatial_pos', 256),
            'epi_crop_start': self.epi_params.get('crop_start', 100),
            'epi_crop_end': self.epi_params.get('crop_end', 200),
            'epi_stretch': self.epi_params.get('stretch', 1),
        }
