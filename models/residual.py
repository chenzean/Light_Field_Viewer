"""
残差图计算模块 — 计算两张图像的残差, 生成伪彩色残差图 (带颜色条)
"""

import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg


def compute_residual(img: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """计算残差 (绝对差值), 转为单通道灰度图。

    参数:
        img: 待比较图像, shape=(H, W, 3), dtype=uint8
        ref: 参考图像 (Ground_Truth), shape=(H, W, 3), dtype=uint8

    返回:
        单通道残差图, shape=(H, W), dtype=uint8, 值域 [0, 255]
    """
    # 确保尺寸一致
    h = min(img.shape[0], ref.shape[0])
    w = min(img.shape[1], ref.shape[1])
    img_crop = img[:h, :w].astype(np.float32)
    ref_crop = ref[:h, :w].astype(np.float32)

    # 计算各通道绝对差值的均值
    diff = np.mean(np.abs(img_crop - ref_crop), axis=2)
    return np.clip(diff, 0, 255).astype(np.uint8)


def residual_to_colormap(residual: np.ndarray, colormap: str = 'jet',
                         vmax: int = None) -> np.ndarray:
    """将单通道残差图映射为伪彩色 RGB 图像。

    参数:
        residual: 单通道残差图, shape=(H, W), dtype=uint8
        colormap: matplotlib colormap 名称
        vmax: 归一化最大值, None 时使用 residual 自身最大值

    返回:
        RGB 图像, shape=(H, W, 3), dtype=uint8
    """
    if vmax is None:
        vmax = max(int(residual.max()), 1)
    cmap = plt.get_cmap(colormap)
    normalized = np.clip(residual.astype(np.float32) / vmax, 0, 1)
    colored = cmap(normalized)[:, :, :3]  # RGBA -> RGB
    return (colored * 255).astype(np.uint8)


_colorbar_cache = {}  # {(vmax, colormap, height, dpi): np.ndarray}


def generate_colorbar(vmax: int, colormap: str = 'jet',
                      height: int = 256, dpi: int = 100) -> np.ndarray:
    """生成独立的竖向颜色条图片 (带缓存)。

    使用 Times New Roman 字体。

    参数:
        vmax: 颜色条最大值
        colormap: matplotlib colormap 名称
        height: 颜色条图片高度 (像素)
        dpi: 输出分辨率

    返回:
        RGB 图像, shape=(H, W, 3), dtype=uint8
    """
    cache_key = (vmax, colormap, height, dpi)
    if cache_key in _colorbar_cache:
        return _colorbar_cache[cache_key]

    import matplotlib.colors as mcolors

    fig_h = max(2.5, height / dpi)
    fig = Figure(figsize=(1.2, fig_h), dpi=dpi)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_axes([0.05, 0.05, 0.3, 0.9])

    norm = mcolors.Normalize(vmin=0, vmax=vmax)
    sm = plt.cm.ScalarMappable(cmap=colormap, norm=norm)
    sm.set_array([])
    cb = fig.colorbar(sm, cax=ax)
    cb.ax.tick_params(labelsize=8)
    # Times New Roman 字体
    for label in cb.ax.get_yticklabels():
        label.set_fontfamily('Times New Roman')

    canvas.draw()
    buf = canvas.buffer_rgba()
    arr = np.asarray(buf)[:, :, :3].copy()

    _colorbar_cache[cache_key] = arr
    return arr
