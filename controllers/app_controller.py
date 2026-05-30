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
from models.rect_annotator import (
    draw_multiple_rectangles, crop_region, crop_with_border
)
from models.epi_extractor import (
    horizontal_epi, vertical_epi, crop_epi, draw_epi_region
)
from models.residual import (
    compute_residual, residual_to_colormap, generate_colorbar
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
        self.vis_mode = 'sai'        # 'sai' 或 'mli'
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
        self.residual_enabled = False

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
        # MLI 缓存: {(method, scene): np.ndarray}
        self._mli_cache = {}

        # 延迟刷新定时器 (防抖: 参数快速变化时只刷新最后一次)
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(200)  # 200ms 防抖
        self._refresh_timer.timeout.connect(self._do_refresh)

        self._connect_signals()

    def _connect_signals(self):
        s = self.settings
        s.mode_changed.connect(self.on_mode_changed)
        s.vis_mode_changed.connect(self.on_vis_mode_changed)
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
        s.residual_changed.connect(self.on_residual_changed)
        s.refresh_requested.connect(self.refresh_all)

        self.comparison.rect_drawn_on_sai.connect(self.on_rect_drawn_on_sai)
        # 切换 tab 时触发刷新, 避免懒加载导致切换后看到旧数据
        self.comparison.tabs.currentChanged.connect(self.refresh_all)

    # ==== 可视化模式 ====
    def on_vis_mode_changed(self, vis_mode):
        self.vis_mode = vis_mode
        self._mli_cache.clear()
        self._sai_cache.clear()
        # MLI 模式下隐藏 EPI tab, 更新场景列表
        self.comparison.set_epi_tab_visible(vis_mode == 'sai')
        if vis_mode == 'mli' and self.data_root:
            mli_scenes = self.lf_data.get_mli_scenes(self.mode)
            self.settings.set_scenes(mli_scenes)
            if mli_scenes:
                self.current_scene = mli_scenes[0]
                self._update_mli_frame_list()
            else:
                self.current_scene = ""
        elif vis_mode == 'sai' and self.data_root:
            scenes = self.lf_data.get_scenes()
            self.settings.set_scenes(scenes)
            if scenes:
                self.current_scene = scenes[0]
                self._update_frame_list()
            else:
                self.current_scene = ""
        self.refresh_all()

    # ==== 残差开关 ====
    def on_residual_changed(self, enabled):
        self.residual_enabled = enabled
        self.refresh_all()

    # ==== 模式 ====
    def on_mode_changed(self, mode):
        self.mode = mode
        # image/video 切换会改变同一 (method, scene, frame_index) 解析到的文件,
        # 而 SAI/光场缓存 key 不含 mode, 故需全部清空
        self._mli_cache.clear()
        self._sai_cache.clear()
        self._lf_cache.clear()
        self._lf_cache_keys.clear()
        if self.data_root:
            self.on_data_root_changed(self.data_root)

    # ==== 数据目录 ====
    def on_data_root_changed(self, path):
        self.data_root = path
        # 缓存 key 不含根目录, 换目录后必须清空, 否则同名 method/scene 会命中旧数据
        self._sai_cache.clear()
        self._mli_cache.clear()
        self._lf_cache.clear()
        self._lf_cache_keys.clear()
        self.window.statusBar().showMessage(f"正在扫描: {path} ...")

        self.lf_data.scan_root(path)
        methods = self.lf_data.get_methods()

        # 根据可视化模式选择场景列表
        self.vis_mode = self.settings.get_vis_mode()
        if self.vis_mode == 'mli':
            scenes = self.lf_data.get_mli_scenes(self.mode)
        else:
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
            if self.vis_mode == 'mli':
                self._update_mli_frame_list()
            else:
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

    def _update_mli_frame_list(self):
        """更新 MLI 模式下的帧列表。"""
        if self.mode == 'image':
            self.settings.set_frames(["(无帧)"])
            self.current_frame_index = 0
        else:
            # 找到有数据的第一个方法来获取帧列表
            for m in self.selected_methods:
                frames = self.lf_data.get_mli_frame_list(m, self.current_scene)
                if frames:
                    self.settings.set_frames(frames)
                    self.current_frame_index = 0
                    return
            self.settings.set_frames([])
            self.current_frame_index = 0

    def on_export_dir_changed(self, path):
        self.export_dir = path

    def on_angular_changed(self, u_max, v_max):
        self.u_max, self.v_max = u_max, v_max
        self._lf_cache.clear()
        self._lf_cache_keys.clear()
        self.refresh_all()

    def on_scene_changed(self, scene):
        # scene 已包含在缓存 key 中, 无需清空缓存 (来回切换可命中缓存, 免读盘)
        self.current_scene = scene
        if self.vis_mode == 'mli':
            self._update_mli_frame_list()
        else:
            self._update_frame_list()
        self.refresh_all()

    def on_frame_changed(self, frame_index):
        # frame_index 已包含在缓存 key 中, 无需清空缓存
        self.current_frame_index = frame_index
        self.refresh_all()

    def on_uv_changed(self, u, v):
        # u, v 已包含在 SAI 缓存 key 中, 无需清空缓存 (浏览视角时免重复读盘)
        self.current_u, self.current_v = u, v
        self.window.statusBar().showMessage(f"切换视角: u={u}, v={v}")
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
        """触发延迟刷新 (200ms 防抖)。"""
        self._refresh_timer.start()

    def _do_refresh(self):
        """实际执行刷新。"""
        if not self.selected_methods or not self.current_scene:
            return

        self.comparison.set_methods(self.selected_methods)

        # 从左侧面板读取最新参数 (确保同步)
        self.epi_params = self.settings.get_epi_params()
        self.residual_enabled = self.settings.get_residual_enabled()
        self.vis_mode = self.settings.get_vis_mode()

        if self.vis_mode == 'mli':
            self._do_refresh_mli()
        else:
            self._do_refresh_sai()

    def _current_tab_index(self):
        """获取当前可见的标签页索引。"""
        return self.comparison.tabs.currentIndex()

    def _do_refresh_sai(self):
        """SAI 模式刷新 — 只刷新当前可见的标签页。

        切换标签页会触发 refresh_all (currentChanged 信号), 因此目标标签页
        在切过去时一定会被刷新, 无需在后台为不可见的标签页做计算。
        """
        tab = self._current_tab_index()

        # Tab 0: SAI 全图
        if tab == 0:
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

        # Tab 1: 局部放大 + 残差
        elif tab == 1:
            self._refresh_zoom_tab(loader=self._load_sai)

        # Tab 2: EPI
        elif tab == 2:
            epi_data = {}
            if self.epi_params.get('enabled', False):
                for method in self.selected_methods:
                    epi_data[method] = self._extract_epi_pixmap(method)
            self.comparison.update_all_epis(self.selected_methods, epi_data)

    def _do_refresh_mli(self):
        """MLI 模式刷新 — 只刷新当前可见的标签页 (MLI 模式无 EPI 标签)。"""
        tab = self._current_tab_index()

        # Tab 0: MLI 全图
        if tab == 0:
            for method in self.selected_methods:
                mli = self._load_mli(method)
                if mli is None:
                    continue
                annotated = draw_multiple_rectangles(mli, self.rects) if self.rects else mli.copy()
                self.comparison.update_method_sai(method, ndarray_to_qpixmap(annotated))

        # Tab 1: 局部放大 + 残差
        elif tab == 1:
            self._refresh_zoom_tab(loader=self._load_mli)

    def _refresh_zoom_tab(self, loader):
        """刷新局部放大标签页 (共用逻辑, loader 为 _load_sai 或 _load_mli)。"""
        crop_data = {}       # {method: [QPixmap, ...]}
        residual_data = {}   # {method: [QPixmap, ...]}

        # 加载 GT 全图 (用于残差计算)
        gt_img = None
        if self.residual_enabled and 'Ground_Truth' in self.selected_methods:
            gt_img = loader('Ground_Truth')

        # 第一遍: 裁剪图 + 残差 (仅裁剪区域, 不算全图)
        # raw_res_crops: {method: [np.ndarray, ...]}  每个矩形框的残差
        raw_res_crops = {}
        for method in self.selected_methods:
            img = loader(method)
            if img is None:
                crop_data[method] = []
                continue
            crops = []
            res_list = []
            for r in self.rects:
                crop = crop_with_border(
                    img, r['x'], r['y'], r['w'], r['h'],
                    r['color'], r['thickness'])
                crops.append(ndarray_to_qpixmap(crop))

                if self.residual_enabled and method != 'Ground_Truth' \
                        and gt_img is not None:
                    # 只裁剪区域计算残差 (比全图快很多)
                    img_crop = crop_region(img, r['x'], r['y'], r['w'], r['h'])
                    gt_crop = crop_region(gt_img, r['x'], r['y'], r['w'], r['h'])
                    res_list.append(compute_residual(img_crop, gt_crop))

            crop_data[method] = crops
            if res_list:
                raw_res_crops[method] = res_list

        # 第二遍: 每个矩形框的全局 vmax → 伪彩色 → 画框 + 生成颜色条
        colorbar_pixmap = None
        if self.residual_enabled and gt_img is not None and raw_res_crops:
            # 每个矩形框取所有方法的 max
            num_rects = len(self.rects)
            rect_vmax = []
            for i in range(num_rects):
                vm = 1
                for method in raw_res_crops:
                    if i < len(raw_res_crops[method]):
                        vm = max(vm, int(raw_res_crops[method][i].max()))
                rect_vmax.append(vm)
            global_vmax = max(rect_vmax) if rect_vmax else 1

            for method, res_list in raw_res_crops.items():
                res_maps = []
                for i, res in enumerate(res_list):
                    vm = rect_vmax[i] if i < len(rect_vmax) else global_vmax
                    res_colored = residual_to_colormap(res, vmax=vm)
                    res_crop = crop_with_border(
                        res_colored, 0, 0, res_colored.shape[1],
                        res_colored.shape[0],
                        self.rects[i]['color'], self.rects[i]['thickness'])
                    res_maps.append(ndarray_to_qpixmap(res_crop))
                residual_data[method] = res_maps

            cb_arr = generate_colorbar(global_vmax)
            colorbar_pixmap = ndarray_to_qpixmap(cb_arr)

        has_residual = bool(residual_data)
        self.comparison.update_all_zooms(
            self.selected_methods, self.rects, crop_data,
            residual_data if has_residual else None,
            colorbar_pixmap)

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

    def _load_mli(self, method):
        key = (method, self.current_scene, self.current_frame_index, self.mode)
        if key in self._mli_cache:
            return self._mli_cache[key]
        mli = self.lf_data.load_mli(
            method, self.current_scene, self.current_frame_index, self.mode)
        if mli is not None:
            mli = ensure_rgb(mli)
            self._mli_cache[key] = mli
            if len(self._mli_cache) > 20:
                oldest = next(iter(self._mli_cache))
                del self._mli_cache[oldest]
        return mli

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
            'vis_mode': self.vis_mode,
            'angular_u': self.u_max,
            'angular_v': self.v_max,
            'scene': self.current_scene,
            'frame_index': self.current_frame_index,
            'u': self.current_u,
            'v': self.current_v,
            'methods': self.selected_methods.copy(),
            'rects': [r.copy() for r in self.rects],
            'residual_enabled': self.residual_enabled,
            'epi_enabled': self.epi_params.get('enabled', False),
            'epi_orientation': self.epi_params.get('orientation', 'horizontal'),
            'epi_angular_idx': self.epi_params.get('angular_idx', 3),
            'epi_spatial_pos': self.epi_params.get('spatial_pos', 256),
            'epi_crop_start': self.epi_params.get('crop_start', 100),
            'epi_crop_end': self.epi_params.get('crop_end', 200),
            'epi_stretch': self.epi_params.get('stretch', 1),
            'export_dpi': self.settings.get_export_dpi(),
        }
