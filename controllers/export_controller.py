"""
导出控制器 — 保存标注图、裁剪图、EPI 到四个文件夹 + 日志
"""

import os
import numpy as np
from PIL import Image

from models.rect_annotator import (
    draw_multiple_rectangles, crop_region, crop_with_border
)
from models.epi_extractor import (
    horizontal_epi, vertical_epi, crop_epi, draw_epi_region
)
from models.residual import (
    compute_residual, residual_to_colormap, generate_colorbar
)
from utils.image_utils import ensure_rgb, scale_epi
from utils.log_utils import write_export_log
import config as cfg


class ExportController:
    """导出控制器。"""

    def __init__(self, app_controller):
        self.app = app_controller

    def export(self):
        """执行导出。"""
        params = self.app.get_export_params()
        export_dir = params['export_dir']

        if not export_dir:
            self.app.window.statusBar().showMessage("错误: 未设置导出目录")
            return

        vis_mode = params.get('vis_mode', 'sai')
        if vis_mode == 'mli':
            count = self._export_mli(params)
        else:
            count = self._export_sai(params)

        # ---- 写日志 ----
        log_path = os.path.join(export_dir, cfg.EXPORT_LOG_FILENAME)
        write_export_log(log_path, params)

        self.app.window.statusBar().showMessage(
            f"导出完成! 共保存 {count} 张图像到 {export_dir}")

    def _export_sai(self, params) -> int:
        """SAI 模式导出。"""
        export_dir = params['export_dir']
        methods = params['methods']
        rects = params['rects']
        scene = params['scene']
        frame_index = params['frame_index']
        u = params['u']
        v = params['v']
        export_dpi = params.get('export_dpi', 150)
        residual_enabled = params.get('residual_enabled', False)

        dir_original = os.path.join(export_dir, cfg.EXPORT_DIR_ORIGINAL)
        dir_annotated = os.path.join(export_dir, cfg.EXPORT_DIR_RECT_ANNOTATED)
        dir_zoom = os.path.join(export_dir, cfg.EXPORT_DIR_ZOOM_CROP)
        dir_epi_full = os.path.join(export_dir, cfg.EXPORT_DIR_EPI_FULL)
        dir_epi_crop = os.path.join(export_dir, cfg.EXPORT_DIR_EPI_CROP)
        dir_res_ann = os.path.join(export_dir, cfg.EXPORT_DIR_RESIDUAL_ANNOTATED)
        dir_res_crop = os.path.join(export_dir, cfg.EXPORT_DIR_RESIDUAL_CROP)

        count = 0

        # 预加载 GT + 计算全局 vmax (用于残差)
        gt_sai = None
        global_vmax = 0.0
        if residual_enabled and 'Ground_Truth' in methods:
            gt_sai = self.app.lf_data.load_sai(
                'Ground_Truth', scene, frame_index, u, v)
            if gt_sai is not None:
                gt_sai = ensure_rgb(gt_sai)
                global_vmax = self._compute_global_vmax_sai(
                    methods, scene, frame_index, u, v, gt_sai)

        for method in methods:
            sai = self.app.lf_data.load_sai(method, scene, frame_index, u, v)
            if sai is None:
                continue
            sai = ensure_rgb(sai)

            base = f"{method}_{scene}_f{frame_index}_{u}_{v}"

            # ---- 0. 原始 SAI ----
            save_path = os.path.join(dir_original, method, f"{base}.png")
            self._save_image(sai, save_path)
            count += 1

            # ---- 1. 带框 + EPI 标记线 ----
            annotated = draw_multiple_rectangles(sai, rects) if rects else sai.copy()
            if params['epi_enabled']:
                annotated = draw_epi_region(
                    annotated,
                    params['epi_spatial_pos'],
                    params['epi_crop_start'],
                    params['epi_crop_end'],
                    params['epi_orientation'],
                    line_color=(0, 0, 255),
                    thickness=2)
            save_path = os.path.join(dir_annotated, method, f"{base}.png")
            self._save_image(annotated, save_path)
            count += 1

            # ---- 2. 局部放大: 从原图裁剪并画框 ----
            for i, r in enumerate(rects):
                crop = crop_with_border(
                    sai, r['x'], r['y'], r['w'], r['h'],
                    r['color'], r['thickness'])
                save_path = os.path.join(dir_zoom, method,
                                         f"{base}_rect{i+1}.png")
                self._save_image(crop, save_path)
                count += 1

            # ---- 残差: 全图标注 + 局部裁剪 (GT 跳过) ----
            if residual_enabled and gt_sai is not None \
                    and method != 'Ground_Truth':
                res_full = compute_residual(sai, gt_sai)
                res_colored = residual_to_colormap(res_full, vmax=global_vmax)
                # 全图残差 + 画框
                res_annotated = draw_multiple_rectangles(res_colored, rects) \
                    if rects else res_colored.copy()
                save_path = os.path.join(dir_res_ann, method,
                                         f"{base}_residual.png")
                self._save_image(res_annotated, save_path)
                count += 1

                # 局部残差裁剪并画框
                for i, r in enumerate(rects):
                    res_crop = crop_with_border(
                        res_colored, r['x'], r['y'], r['w'], r['h'],
                        r['color'], r['thickness'])
                    save_path = os.path.join(dir_res_crop, method,
                                             f"{base}_rect{i+1}_residual.png")
                    self._save_image(res_crop, save_path)
                    count += 1

            # ---- 3 & 4. EPI ----
            if params['epi_enabled']:
                lf = self.app._get_light_field(method)
                if lf is not None:
                    orient = params['epi_orientation']
                    ang_idx = params['epi_angular_idx'] - 1
                    spatial_pos = params['epi_spatial_pos']
                    ang_idx = max(0, min(ang_idx, lf.shape[0] - 1))

                    if orient == 'horizontal':
                        spatial_pos = max(0, min(spatial_pos, lf.shape[2] - 1))
                        epi_full_arr = horizontal_epi(lf, ang_idx, spatial_pos)
                    else:
                        spatial_pos = max(0, min(spatial_pos, lf.shape[3] - 1))
                        epi_full_arr = vertical_epi(lf, ang_idx, spatial_pos)

                    epi_s = scale_epi(epi_full_arr, params['epi_stretch'])
                    save_path = os.path.join(dir_epi_full, method,
                                             f"{base}_{orient}_epi.png")
                    self._save_image(epi_s, save_path)
                    count += 1

                    epi_c = crop_epi(epi_full_arr, params['epi_crop_start'],
                                     params['epi_crop_end'])
                    epi_cs = scale_epi(epi_c, params['epi_stretch'])
                    save_path = os.path.join(dir_epi_crop, method,
                                             f"{base}_{orient}_epi_crop.png")
                    self._save_image(epi_cs, save_path)
                    count += 1

        # ---- 保存全局颜色条 ----
        if residual_enabled and gt_sai is not None and global_vmax > 0:
            cb_arr = generate_colorbar(global_vmax, dpi=export_dpi)
            save_path = os.path.join(dir_res_ann, "colorbar.png")
            self._save_image(cb_arr, save_path)
            count += 1

        return count

    def _compute_global_vmax_sai(self, methods, scene, frame_index, u, v,
                                 gt_sai) -> float:
        """计算 SAI 模式下所有非 GT 方法全图残差的全局最大值。"""
        vmax = 0.0
        for method in methods:
            if method == 'Ground_Truth':
                continue
            sai = self.app.lf_data.load_sai(method, scene, frame_index, u, v)
            if sai is None:
                continue
            sai = ensure_rgb(sai)
            res = compute_residual(sai, gt_sai)
            vmax = max(vmax, float(res.max()))
        return vmax

    def _export_mli(self, params) -> int:
        """MLI 模式导出。"""
        export_dir = params['export_dir']
        methods = params['methods']
        rects = params['rects']
        scene = params['scene']
        frame_index = params['frame_index']
        mode = params['mode']
        export_dpi = params.get('export_dpi', 150)
        residual_enabled = params.get('residual_enabled', False)

        dir_original = os.path.join(export_dir, "00_original_mli")
        dir_annotated = os.path.join(export_dir, "01_rect_annotated_mli")
        dir_zoom = os.path.join(export_dir, cfg.EXPORT_DIR_ZOOM_CROP)
        dir_res_ann = os.path.join(export_dir, cfg.EXPORT_DIR_RESIDUAL_ANNOTATED)
        dir_res_crop = os.path.join(export_dir, cfg.EXPORT_DIR_RESIDUAL_CROP)

        count = 0

        # 预加载 GT + 计算全局 vmax
        gt_mli = None
        global_vmax = 0.0
        if residual_enabled and 'Ground_Truth' in methods:
            gt_mli = self.app.lf_data.load_mli(
                'Ground_Truth', scene, frame_index, mode)
            if gt_mli is not None:
                gt_mli = ensure_rgb(gt_mli)
                global_vmax = self._compute_global_vmax_mli(
                    methods, scene, frame_index, mode, gt_mli)

        for method in methods:
            mli = self.app.lf_data.load_mli(method, scene, frame_index, mode)
            if mli is None:
                continue
            mli = ensure_rgb(mli)

            base = f"{method}_{scene}_f{frame_index}_mli"

            # ---- 0. 原始 MLI ----
            save_path = os.path.join(dir_original, method, f"{base}.png")
            self._save_image(mli, save_path)
            count += 1

            # ---- 1. 带框 ----
            annotated = draw_multiple_rectangles(mli, rects) if rects else mli.copy()
            save_path = os.path.join(dir_annotated, method, f"{base}.png")
            self._save_image(annotated, save_path)
            count += 1

            # ---- 2. 局部放大: 从原图裁剪并画框 ----
            for i, r in enumerate(rects):
                crop = crop_with_border(
                    mli, r['x'], r['y'], r['w'], r['h'],
                    r['color'], r['thickness'])
                save_path = os.path.join(dir_zoom, method,
                                         f"{base}_rect{i+1}.png")
                self._save_image(crop, save_path)
                count += 1

            # ---- 残差: 全图标注 + 局部裁剪 (GT 跳过) ----
            if residual_enabled and gt_mli is not None \
                    and method != 'Ground_Truth':
                res_full = compute_residual(mli, gt_mli)
                res_colored = residual_to_colormap(res_full, vmax=global_vmax)
                res_annotated = draw_multiple_rectangles(res_colored, rects) \
                    if rects else res_colored.copy()
                save_path = os.path.join(dir_res_ann, method,
                                         f"{base}_residual.png")
                self._save_image(res_annotated, save_path)
                count += 1

                for i, r in enumerate(rects):
                    res_crop = crop_with_border(
                        res_colored, r['x'], r['y'], r['w'], r['h'],
                        r['color'], r['thickness'])
                    save_path = os.path.join(dir_res_crop, method,
                                             f"{base}_rect{i+1}_residual.png")
                    self._save_image(res_crop, save_path)
                    count += 1

        # ---- 保存全局颜色条 ----
        if residual_enabled and gt_mli is not None and global_vmax > 0:
            cb_arr = generate_colorbar(global_vmax, dpi=export_dpi)
            save_path = os.path.join(dir_res_ann, "colorbar.png")
            self._save_image(cb_arr, save_path)
            count += 1

        return count

    def _compute_global_vmax_mli(self, methods, scene, frame_index, mode,
                                 gt_mli) -> float:
        """计算 MLI 模式下所有非 GT 方法全图残差的全局最大值。"""
        vmax = 0.0
        for method in methods:
            if method == 'Ground_Truth':
                continue
            mli = self.app.lf_data.load_mli(method, scene, frame_index, mode)
            if mli is None:
                continue
            mli = ensure_rgb(mli)
            res = compute_residual(mli, gt_mli)
            vmax = max(vmax, float(res.max()))
        return vmax

    def _save_image(self, arr: np.ndarray, path: str):
        """保存 numpy 数组为 PNG 图像。"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.fromarray(arr).save(path)
