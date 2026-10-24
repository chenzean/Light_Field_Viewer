"""导出当前对比；每个批次独立保存图像、参数和来源清单。"""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np
from PIL import Image

from models.rect_annotator import draw_multiple_rectangles, crop_with_border
from models.epi_extractor import extract_epi, crop_epi, draw_epi_region
from models.residual import compute_residual, residual_to_colormap, generate_colorbar
from utils.image_utils import ensure_rgb, scale_epi
from utils.log_utils import write_export_log, write_export_manifest
import config as cfg


class ExportController:
    """保留可直接调用的 _export_sai/_export_mli，返回成功写出的图像数量。"""

    def __init__(self, app_controller):
        self.app = app_controller
        self.last_manifest = None

    def export(self):
        self.last_manifest = None
        params = deepcopy(self.app.get_export_params())
        status = self.app.window.statusBar()
        if not params.get('export_dir'):
            status.showMessage("错误: 未设置导出目录")
            return None
        if not params.get('methods') or not params.get('scene'):
            status.showMessage("无法导出: 请先载入场景并选择方法")
            return None

        root = Path(params['export_dir']).resolve()
        batch = root / (datetime.now().strftime('export_%Y%m%d_%H%M%S_') + uuid4().hex[:8])
        try:
            batch.mkdir(parents=True, exist_ok=False)
        except OSError as error:
            status.showMessage(f"无法创建导出目录: {error}")
            return None

        params['export_root'] = str(root)
        params['export_dir'] = str(batch)
        status.showMessage(f"正在导出: {batch}")
        if params.get('vis_mode', 'sai') == 'mli':
            count = self._export_mli(params)
        else:
            count = self._export_sai(params)

        try:
            write_export_log(batch / cfg.EXPORT_LOG_FILENAME, params, self.last_manifest)
        except OSError as error:
            self._issue(None, 'log_output', 'failed', str(error))
            self.last_manifest['status'] = 'partial' if count else 'failed'
        try:
            write_export_manifest(batch / 'manifest.json', self.last_manifest)
        except OSError as error:
            status.showMessage(f"导出未完整完成: 已写出 {count} 张图像，但记录保存失败: {error}")
            return str(batch)

        issues = self.last_manifest['issues']
        if issues:
            result = "部分导出" if count else "导出失败"
            first = issues[0]
            status.showMessage(
                f"{result}: 保存 {count} 张，{len(issues)} 项跳过或失败；"
                f"{first['method'] or '批次'}: {first['reason']}。详情: {batch / 'manifest.json'}")
        else:
            status.showMessage(f"导出完成: 保存 {count} 张图像到 {batch}")
        return str(batch)

    def _export_sai(self, params) -> int:
        return self._export_images(params, 'sai')

    def _export_mli(self, params) -> int:
        return self._export_images(params, 'mli')

    def _export_images(self, params, vis_mode):
        self.last_manifest = {
            'schema_version': 1,
            'app_version': cfg.VERSION,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'parameters': deepcopy(dict(params, vis_mode=vis_mode)),
            'frame_alignment': getattr(self.app.lf_data, 'frame_alignment', 'name'),
            'residual': {
                'enabled': params.get('residual_enabled', False),
                'formula': 'mean_c(abs(float32(image)/255 - float32(Ground_Truth)/255))',
                'reference_method': 'Ground_Truth',
                'scope': 'maximum over full images of valid selected non-reference methods',
                'colormap': 'jet', 'vmin': 0.0, 'vmax': None,
                'display_vmax': None, 'methods': [],
            },
            'methods': {method: {'source': None, 'outputs': [], 'issues': []}
                        for method in params['methods']},
            'outputs': [], 'issues': [],
        }
        images = {}
        data = self.app.lf_data
        for method in params['methods']:
            try:
                self._record_source(method, params, vis_mode)
                if vis_mode == 'sai':
                    image = data.load_sai(method, params['scene'], params['frame_index'],
                                          params['u'], params['v'])
                else:
                    image = data.load_mli(method, params['scene'], params['frame_index'],
                                          params['mode'])
                if image is None:
                    self._issue(method, 'load', 'skipped', '缺少当前场景、帧或视角的图像')
                    continue
                images[method] = ensure_rgb(image)
                self.last_manifest['methods'][method]['image_shape'] = list(images[method].shape)
            except (OSError, ValueError) as error:
                self._issue(method, 'load', 'failed', str(error))

        # 一次读取后计算统一色标，避免同一批次两次读盘期间源文件变化。
        residuals = {}
        if params.get('residual_enabled', False):
            reference = images.get('Ground_Truth')
            for method, image in images.items():
                if method == 'Ground_Truth':
                    continue
                if reference is None:
                    self._issue(method, 'residual', 'skipped', '未选择或无法读取 Ground_Truth，未生成残差')
                    continue
                try:
                    residuals[method] = compute_residual(image, reference)
                except ValueError as error:
                    self._issue(method, 'residual', 'failed', str(error))
        vmax = max((float(residual.max()) for residual in residuals.values()), default=0.0)
        if residuals:
            self.last_manifest['residual'].update(
                vmax=vmax, display_vmax=max(vmax, 1e-12), methods=list(residuals))

        for method, image in images.items():
            suffix = f"{params['u']}_{params['v']}" if vis_mode == 'sai' else 'mli'
            base = f"{method}_{params['scene']}_f{params['frame_index']}_{suffix}"
            epi = None
            if vis_mode == 'sai' and params.get('epi_enabled', False):
                try:
                    epi = self._load_epi(method, params)
                except (OSError, ValueError) as error:
                    self._issue(method, 'epi', 'failed', str(error))

            original_dir = cfg.EXPORT_DIR_ORIGINAL if vis_mode == 'sai' else '00_original_mli'
            annotated_dir = cfg.EXPORT_DIR_RECT_ANNOTATED if vis_mode == 'sai' else '01_rect_annotated_mli'
            try:
                self._write_output(image, params, original_dir, method, base + '.png', 'original')
                annotated = draw_multiple_rectangles(image, params['rects'])
                # 蓝线表示请求的采样位置，与完整光场是否可用于 EPI 独立。
                if vis_mode == 'sai' and params.get('epi_enabled', False):
                    annotated = draw_epi_region(
                        annotated, params['epi_spatial_pos'], params['epi_crop_start'],
                        params['epi_crop_end'], params['epi_orientation'], thickness=2)
                self._write_output(annotated, params, annotated_dir, method, base + '.png', 'annotated')
            except (OSError, ValueError) as error:
                self._issue(method, 'image_output', 'failed', str(error))
            self._write_roi_crops(image, params, cfg.EXPORT_DIR_ZOOM_CROP,
                                  method, base, 'crop')

            if method in residuals:
                try:
                    colored = residual_to_colormap(residuals[method], vmax=vmax)
                    annotated = draw_multiple_rectangles(colored, params['rects'])
                    self._write_output(annotated, params, cfg.EXPORT_DIR_RESIDUAL_ANNOTATED,
                                       method, f'{base}_residual.png', 'residual')
                    self._write_roi_crops(colored, params, cfg.EXPORT_DIR_RESIDUAL_CROP,
                                          method, base, 'residual_crop')
                except (OSError, ValueError) as error:
                    self._issue(method, 'residual_output', 'failed', str(error))

            if epi is not None:
                try:
                    stretch = params.get('epi_stretch', 1)
                    orient = params['epi_orientation']
                    self._write_output(scale_epi(epi, stretch), params, cfg.EXPORT_DIR_EPI_FULL,
                                       method, f'{base}_{orient}_epi.png', 'epi_full')
                    cropped = crop_epi(epi, params['epi_crop_start'], params['epi_crop_end'])
                    self._write_output(scale_epi(cropped, stretch), params, cfg.EXPORT_DIR_EPI_CROP,
                                       method, f'{base}_{orient}_epi_crop.png', 'epi_crop')
                except (OSError, ValueError) as error:
                    self._issue(method, 'epi_output', 'failed', str(error))

        if residuals:
            try:
                # vmax=0 也保存色标；manifest 同时记录真实值与显示用 epsilon。
                colorbar = generate_colorbar(vmax, dpi=params.get('export_dpi', 150))
                self._write_output(colorbar, params, cfg.EXPORT_DIR_RESIDUAL_ANNOTATED,
                                   None, 'colorbar.png', 'colorbar')
            except (OSError, ValueError) as error:
                self._issue(None, 'colorbar_output', 'failed', str(error))

        for entry in self.last_manifest['methods'].values():
            if entry['outputs']:
                entry['status'] = 'partial' if entry['issues'] else 'complete'
            else:
                entry['status'] = ('failed' if any(i['status'] == 'failed' for i in entry['issues'])
                                   else 'skipped')
        count = len(self.last_manifest['outputs'])
        self.last_manifest['image_count'] = count
        self.last_manifest['status'] = ('failed' if not count else
                                       'partial' if self.last_manifest['issues'] else 'complete')
        return count

    def _record_source(self, method, params, vis_mode):
        resolver = getattr(self.app.lf_data, 'resolve_' + vis_mode + '_path', None)
        if resolver is None:
            return
        args = (method, params['scene'], params['frame_index'])
        path = (resolver(*args, params['u'], params['v']) if vis_mode == 'sai'
                else resolver(*args, params['mode']))
        if path is not None:
            source = Path(path).resolve()
            self.last_manifest['methods'][method]['source'] = {
                'path': str(source), 'file_name': source.name,
                'frame_name': source.parent.name if vis_mode == 'sai' else source.stem,
            }

    def _load_epi(self, method, params):
        data = self.app.lf_data
        resolver = getattr(data, 'resolve_sai_path', None)
        if resolver is not None:
            self.last_manifest['methods'][method]['epi_sources'] = [
                {'u': u, 'v': v, 'path': resolver(method, params['scene'], params['frame_index'], u, v)}
                for u in range(1, params['angular_u'] + 1)
                for v in range(1, params['angular_v'] + 1)
            ]
        lf = data.load_light_field(method, params['scene'], params['frame_index'],
                                   params['angular_u'], params['angular_v'])
        if lf is None:
            raise ValueError('缺少当前帧的完整光场，未生成 EPI')
        return extract_epi(lf, params['epi_orientation'], params['epi_angular_idx'],
                           params['epi_spatial_pos'])

    def _issue(self, method, stage, status, reason):
        issue = dict(method=method, stage=stage, status=status, reason=reason)
        self.last_manifest['issues'].append(issue)
        if method is not None:
            self.last_manifest['methods'][method]['issues'].append(issue)

    def _write_roi_crops(self, image, params, category, method, base, kind):
        """逐个写出 ROI；一个无交集选区不能阻止其余选区导出。"""
        height, width = image.shape[:2]
        suffix = '_residual' if kind == 'residual_crop' else ''
        for index, rect in enumerate(params['rects'], 1):
            x, y, w, h = (rect[key] for key in ('x', 'y', 'w', 'h'))
            bounds = f'ROI {index} (x={x}, y={y}, w={w}, h={h})'
            # 与 crop_with_border 的扩展/裁剪范围一致，也避免负切片索引反向取图。
            pad = max(0, rect['thickness'] - 1)
            if (min(width, x + w + pad) <= max(0, x - pad)
                    or min(height, y + h + pad) <= max(0, y - pad)):
                self._issue(method, kind, 'skipped',
                            f'{bounds} 裁剪范围与 {width}×{height} 图像无交集，未导出')
                continue
            try:
                crop = crop_with_border(image, **rect)
                self._write_output(crop, params, category, method,
                                   f'{base}_rect{index}{suffix}.png', kind)
            except (OSError, ValueError) as error:
                self._issue(method, kind, 'failed', f'{bounds}: {error}')

    def _write_output(self, image, params, category, method, filename, kind):
        relative = Path(category) / method / filename if method is not None else Path(category) / filename
        path = Path(params['export_dir']) / relative
        self._save_image(image, path)
        output = {'path': str(path.resolve()), 'relative_path': relative.as_posix(),
                  'method': method, 'kind': kind}
        self.last_manifest['outputs'].append(output)
        if method is not None:
            self.last_manifest['methods'][method]['outputs'].append(output)

    def _save_image(self, arr: np.ndarray, path):
        if arr.ndim != 3 or arr.shape[2] != 3 or not arr.shape[0] or not arr.shape[1]:
            raise ValueError(f'无法保存空图像或非 RGB 图像: shape={arr.shape}')
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(arr).save(path)
