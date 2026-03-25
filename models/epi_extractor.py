"""
EPI (极平面图像) 提取模块
"""

import numpy as np


def horizontal_epi(lf: np.ndarray, angular_row: int, spatial_row: int) -> np.ndarray:
    """提取水平 EPI。

    固定角度行 U=angular_row 和空间行 H=spatial_row,
    沿角度列 V 和空间列 W 展开。

    参数:
        lf: 5D 光场数组, shape=[U, V, H, W, C]
        angular_row: 角度行索引 (0-based)
        spatial_row: 空间行索引

    返回:
        EPI 图像, shape=[V, W, C]
    """
    return lf[angular_row, :, spatial_row, :, :].copy()


def vertical_epi(lf: np.ndarray, angular_col: int, spatial_col: int) -> np.ndarray:
    """提取垂直 EPI。

    固定角度列 V=angular_col 和空间列 W=spatial_col,
    沿角度行 U 和空间行 H 展开。

    参数:
        lf: 5D 光场数组, shape=[U, V, H, W, C]
        angular_col: 角度列索引 (0-based)
        spatial_col: 空间列索引

    返回:
        EPI 图像, shape=[U, H, C]
    """
    return lf[:, angular_col, :, spatial_col, :].copy()


def crop_epi(epi: np.ndarray, start_col: int, end_col: int) -> np.ndarray:
    """裁剪 EPI 的列范围。

    参数:
        epi: EPI 图像, shape=[angular, spatial, C]
        start_col: 起始列
        end_col: 结束列

    返回:
        裁剪后的 EPI
    """
    w = epi.shape[1]
    start_col = max(0, min(start_col, w - 1))
    end_col = max(start_col + 1, min(end_col, w))
    return epi[:, start_col:end_col, :].copy()


def draw_epi_region(image: np.ndarray, position: int, crop_start: int, crop_end: int,
                    orientation: str = 'horizontal',
                    line_color: tuple = (0, 0, 255),
                    thickness: int = 2) -> np.ndarray:
    """在 SAI 图像上绘制 EPI 位置标记 — 只画裁剪范围内的一条线。

    水平 EPI: 在 spatial_row 位置画一条水平短线 (从 crop_start 到 crop_end)
    垂直 EPI: 在 spatial_col 位置画一条垂直短线 (从 crop_start 到 crop_end)

    参数:
        image: RGB 图像, shape=(H, W, 3)
        position: 空间位置 (水平 EPI = 行号, 垂直 EPI = 列号)
        crop_start, crop_end: 裁剪范围
        orientation: 'horizontal' 或 'vertical'
        line_color: 线条颜色
        thickness: 线条粗细
    """
    img = image.copy()
    h, w = img.shape[:2]
    half_t = thickness // 2

    if orientation == 'horizontal':
        cs = max(0, min(crop_start, w))
        ce = max(0, min(crop_end, w))
        for t in range(-half_t, half_t + 1):
            row = position + t
            if 0 <= row < h:
                img[row, cs:ce] = line_color
    else:
        cs = max(0, min(crop_start, h))
        ce = max(0, min(crop_end, h))
        for t in range(-half_t, half_t + 1):
            col = position + t
            if 0 <= col < w:
                img[cs:ce, col] = line_color

    return img
