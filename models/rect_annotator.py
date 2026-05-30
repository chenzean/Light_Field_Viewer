"""
矩形框绘制与裁剪模块
"""

import numpy as np


def draw_rectangle(image: np.ndarray, x: int, y: int, w: int, h: int,
                   color: tuple = (255, 0, 0), thickness: int = 3,
                   inplace: bool = False) -> np.ndarray:
    """在图像上绘制矩形框。

    参数:
        image: RGB 图像, shape=(H, W, 3)
        x, y: 矩形左上角坐标
        w, h: 矩形宽高
        color: RGB 颜色元组
        thickness: 线条粗细
        inplace: True 时直接在传入数组上绘制 (避免拷贝), 否则绘制在副本上

    返回:
        绘制了矩形框的图像 (inplace=True 时为传入数组本身, 否则为副本)
    """
    img = image if inplace else image.copy()
    img_h, img_w = img.shape[:2]

    # 计算四条边的范围 (向外扩展 thickness)
    x1, y1 = x, y
    x2, y2 = x + w, y + h

    for t in range(thickness):
        # 上边
        row = y1 - t
        if 0 <= row < img_h:
            c1 = max(0, x1 - t)
            c2 = min(img_w, x2 + t)
            img[row, c1:c2] = color

        # 下边
        row = y2 + t
        if 0 <= row < img_h:
            c1 = max(0, x1 - t)
            c2 = min(img_w, x2 + t)
            img[row, c1:c2] = color

        # 左边
        col = x1 - t
        if 0 <= col < img_w:
            r1 = max(0, y1 - t)
            r2 = min(img_h, y2 + t)
            img[r1:r2, col] = color

        # 右边
        col = x2 + t
        if 0 <= col < img_w:
            r1 = max(0, y1 - t)
            r2 = min(img_h, y2 + t)
            img[r1:r2, col] = color

    return img


def draw_multiple_rectangles(image: np.ndarray, rects: list) -> np.ndarray:
    """在图像上绘制多个矩形框。

    参数:
        image: RGB 图像
        rects: 矩形列表, 每个元素为 dict:
               {'x': int, 'y': int, 'w': int, 'h': int,
                'color': (R, G, B), 'thickness': int}

    返回:
        绘制了所有矩形框的图像副本
    """
    # 只拷贝一次, 之后所有框就地绘制 (避免每个框各拷贝一次全图)
    img = image.copy()
    for r in rects:
        draw_rectangle(img, r['x'], r['y'], r['w'], r['h'],
                       r['color'], r['thickness'], inplace=True)
    return img


def crop_region(image: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    """裁剪图像的矩形区域。

    参数:
        image: RGB 图像
        x, y: 左上角坐标
        w, h: 裁剪宽高

    返回:
        裁剪后的图像, shape=(h, w, 3)
    """
    img_h, img_w = image.shape[:2]
    # 边界裁剪
    x1 = max(0, min(x, img_w - 1))
    y1 = max(0, min(y, img_h - 1))
    x2 = max(0, min(x + w, img_w))
    y2 = max(0, min(y + h, img_h))
    return image[y1:y2, x1:x2].copy()


def crop_with_border(image: np.ndarray, x: int, y: int, w: int, h: int,
                     color: tuple = (255, 0, 0), thickness: int = 3) -> np.ndarray:
    """从原始图像裁剪局部区域并在边缘画框。

    参考 MATLAB 的 expandROI + drawBoxPixel + cropROI 流程:
      1. 向外扩展 pad = thickness - 1 像素
      2. 裁剪扩展区域
      3. 在裁剪结果的边缘向内画 thickness 像素宽的框

    框的最内侧恰好对齐原始 ROI 边界, 框内内容即为原始 ROI 图像。

    参数:
        image: 原始 RGB 图像 (未画框)
        x, y: 内容区域左上角坐标
        w, h: 内容区域宽高
        color: 框颜色 (R, G, B)
        thickness: 框粗细

    返回:
        裁剪后的图像, 尺寸 = (h + 2*pad, w + 2*pad, 3), 边缘为彩色框
    """
    img_h, img_w = image.shape[:2]
    pad = max(0, thickness - 1)

    # 扩展区域 (clamp to image bounds)
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(img_w, x + w + pad)
    y2 = min(img_h, y + h + pad)

    patch = image[y1:y2, x1:x2].copy()
    ph, pw = patch.shape[:2]

    # 向量化画框 (比逐行循环快 3-5 倍)
    t = min(thickness, ph // 2, pw // 2)  # 防止框比 patch 还大
    if t > 0:
        patch[:t, :] = color           # 上
        patch[ph - t:, :] = color      # 下
        patch[:, :t] = color           # 左
        patch[:, pw - t:] = color      # 右

    return patch
