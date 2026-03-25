"""
导出控制器 — 保存标注图、裁剪图、EPI 到四个文件夹 + 日志
"""

import os
import numpy as np
from PIL import Image

from models.rect_annotator import draw_multiple_rectangles, crop_region
from models.epi_extractor import (
    horizontal_epi, vertical_epi, crop_epi, draw_epi_region
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

        methods = params['methods']
        rects = params['rects']
        scene = params['scene']
        frame_index = params['frame_index']
        u = params['u']
        v = params['v']

        # 创建五个子目录
        dir_original = os.path.join(export_dir, cfg.EXPORT_DIR_ORIGINAL)
        dir_annotated = os.path.join(export_dir, cfg.EXPORT_DIR_RECT_ANNOTATED)
        dir_zoom = os.path.join(export_dir, cfg.EXPORT_DIR_ZOOM_CROP)
        dir_epi_full = os.path.join(export_dir, cfg.EXPORT_DIR_EPI_FULL)
        dir_epi_crop = os.path.join(export_dir, cfg.EXPORT_DIR_EPI_CROP)

        count = 0

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

            # ---- 2. 局部放大 (带对应颜色边框) ----
            for i, r in enumerate(rects):
                crop = crop_region(sai, r['x'], r['y'], r['w'], r['h'])
                # 给裁剪图加上对应颜色的边框
                crop = self._add_border(crop, r['color'], width=3)
                save_path = os.path.join(dir_zoom, method, f"{base}_rect{i+1}.png")
                self._save_image(crop, save_path)
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

                    # 完整 EPI
                    epi_s = scale_epi(epi_full_arr, params['epi_stretch'])
                    save_path = os.path.join(dir_epi_full, method, f"{base}_{orient}_epi.png")
                    self._save_image(epi_s, save_path)
                    count += 1

                    # 裁剪 EPI
                    epi_c = crop_epi(epi_full_arr, params['epi_crop_start'], params['epi_crop_end'])
                    epi_cs = scale_epi(epi_c, params['epi_stretch'])
                    save_path = os.path.join(dir_epi_crop, method, f"{base}_{orient}_epi_crop.png")
                    self._save_image(epi_cs, save_path)
                    count += 1

        # ---- 写日志 ----
        log_path = os.path.join(export_dir, cfg.EXPORT_LOG_FILENAME)
        write_export_log(log_path, params)

        self.app.window.statusBar().showMessage(
            f"导出完成! 共保存 {count} 张图像到 {export_dir}")

    def _save_image(self, arr: np.ndarray, path: str):
        """保存 numpy 数组为 PNG 图像。"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.fromarray(arr).save(path)

    def _add_border(self, img: np.ndarray, color: tuple, width: int = 3) -> np.ndarray:
        """给图像四周加上指定颜色的边框。"""
        img = img.copy()
        h, w = img.shape[:2]
        # 上下
        img[:width, :] = color
        img[h - width:, :] = color
        # 左右
        img[:, :width] = color
        img[:, w - width:] = color
        return img
