"""
图像工具模块 — ndarray 与 QPixmap 之间的转换, RGBA→RGB, EPI 拉伸
"""

import numpy as np
from PyQt5.QtGui import QImage, QPixmap


def ndarray_to_qpixmap(arr: np.ndarray) -> QPixmap:
    """将 RGB numpy 数组转换为 QPixmap。

    参数:
        arr: shape=(H, W, 3), dtype=uint8, RGB 格式

    返回:
        QPixmap 对象
    """
    arr = ensure_rgb(arr)
    h, w, c = arr.shape
    bytes_per_line = c * w
    # numpy 数组必须是连续内存
    arr = np.ascontiguousarray(arr)
    qimg = QImage(arr.data, w, h, bytes_per_line, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def ensure_rgb(arr: np.ndarray) -> np.ndarray:
    """确保图像为 RGB 格式 (去掉 alpha 通道)。"""
    if arr is None:
        return None
    if arr.ndim == 2:
        # 灰度 → RGB
        arr = np.stack([arr, arr, arr], axis=-1)
    elif arr.ndim == 3 and arr.shape[2] == 4:
        # RGBA → RGB
        arr = arr[:, :, :3]
    return arr.astype(np.uint8) if arr.dtype != np.uint8 else arr


def scale_epi(epi: np.ndarray, stretch_factor: int = 5) -> np.ndarray:
    """在高度方向拉伸 EPI, 方便观察线性结构。

    使用最近邻插值 (保持 EPI 的锐利线性结构, 不模糊)。

    参数:
        epi: shape=(H, W, C), H 通常很小 (如 5)
        stretch_factor: 高度拉伸倍数

    返回:
        拉伸后的 EPI, shape=(H*stretch_factor, W, C)
    """
    if stretch_factor <= 1:
        return epi
    from PIL import Image
    h, w = epi.shape[:2]
    new_h = h * stretch_factor
    img = Image.fromarray(epi)
    # NEAREST 保持锐利的线性结构, 不会模糊
    img_resized = img.resize((w, new_h), Image.NEAREST)
    return np.array(img_resized)
