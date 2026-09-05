"""
应用图标生成器 — 生成 assets/icon.ico 与 assets/icon.png

图标是程序化绘制的, 没有外部素材依赖: 改一个数字就能重新生成全部尺寸。
每个尺寸单独绘制 (而不是把大图缩小), 所以 16px 下线条仍然干净。

用法:
    python tools/make_icon.py              # 生成正式图标
    python tools/make_icon.py --preview    # 额外输出三个方案的对照图
"""

import math
import os
import sys

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen
)
from PyQt5.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")

# Windows 图标常用尺寸; 每个都单独绘制
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)

# 与界面强调色同源的蓝, 但更饱和一点, 小尺寸下才立得住
TOP = QColor("#4aa3ff")
BOTTOM = QColor("#0057d8")

SQUIRCLE_N = 5.0        # 超椭圆指数, 5 接近 Apple 的圆角方形
TILE_INSET = 0.045      # 图标边缘留白比例


def squircle(size, inset=TILE_INSET, samples=256):
    """Apple 的圆角方形是超椭圆, 不是圆角矩形 — 拐角过渡更连续。"""
    margin = size * inset
    radius = (size - margin * 2) / 2.0
    centre = size / 2.0
    path = QPainterPath()
    for index in range(samples):
        angle = 2.0 * math.pi * index / samples
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        x = centre + radius * math.copysign(abs(cos_a) ** (2.0 / SQUIRCLE_N), cos_a)
        y = centre + radius * math.copysign(abs(sin_a) ** (2.0 / SQUIRCLE_N), sin_a)
        if index == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    return path


def _tile(painter, size):
    """底板: 对角渐变 + 顶部内高光。"""
    path = squircle(size)
    gradient = QLinearGradient(QPointF(0, 0), QPointF(size * 0.55, size))
    gradient.setColorAt(0.0, TOP)
    gradient.setColorAt(1.0, BOTTOM)
    painter.fillPath(path, gradient)
    if size >= 32:
        highlight = QColor(255, 255, 255, 46)
        painter.setPen(QPen(highlight, max(1.0, size * 0.008)))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(squircle(size, TILE_INSET + 0.012))
    return path


def _cells(size, count, span, snap=False):
    """把中心的正方形区域切成 count×count 个单元。

    小尺寸下 ``snap`` 会把格子和间隙都取整: 16px 时理想间隙只有 1 像素多一点,
    四舍五入之后会归零, 于是所有格子糊成一整块白。
    """
    area = size * span
    gap_ratio = 0.13 if count == 3 else 0.12
    if snap:
        gap = max(1, round(area * gap_ratio))
        cell = max(2, int((area - gap * (count - 1)) / count))
        origin = round((size - (cell * count + gap * (count - 1))) / 2.0)
    else:
        gap = area * gap_ratio
        cell = (area - gap * (count - 1)) / count
        origin = (size - area) / 2.0
    for row in range(count):
        for col in range(count):
            yield row, col, QRectF(origin + col * (cell + gap),
                                   origin + row * (cell + gap), cell, cell)


def draw_aperture_grid(painter, size):
    """方案 A — 子孔径视角阵列, 中心视角被选中。

    尺寸自适应, 和 Apple 对图标做光学优化是一个道理:
      ≥24px  3×3, 圆角格子, 中心为白色选中视角
      20-23  3×3, 直角格子并提高对比, 否则格子会糊在一起
      <20    2×2 — 16px 下 3×3 的格子只有不到 3 像素, 会连成一块
    """
    _tile(painter, size)
    count = 3 if size >= 20 else 2
    crisp = size < 24
    radius = 0.0 if crisp else size * 0.038
    painter.setPen(Qt.NoPen)
    for row, col, rect in _cells(size, count, 0.66 if count == 3 else 0.60,
                                 snap=crisp):
        selected = count == 3 and (row, col) == (1, 1)
        # 2×2 时没有中心格, 全部用白色, 而不是把语义弄反
        alpha = 255 if (selected or count == 2) else (190 if crisp else 150)
        painter.setBrush(QColor(255, 255, 255, alpha))
        if radius:
            painter.drawRoundedRect(rect, radius, radius)
        else:
            painter.drawRect(rect.toAlignedRect())


def draw_lenslet(painter, size):
    """方案 B — 微透镜阵列。"""
    _tile(painter, size)
    count = 3 if size >= 24 else 2
    for row, col, rect in _cells(size, count, 0.62 if count == 3 else 0.56):
        chosen = (row, col) == (1, 1) if count == 3 else (row, col) == (1, 1)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 255 if chosen else 120))
        painter.drawEllipse(rect)


def draw_parallax(painter, size):
    """方案 C — 同一场景的多个视角, 叠放出视差。"""
    _tile(painter, size)
    side = size * 0.46
    step = size * 0.088
    radius = size * 0.055
    origin = (size - side - step * 2) / 2.0
    painter.setPen(Qt.NoPen)
    for depth, alpha in ((2, 90), (1, 150), (0, 255)):
        rect = QRectF(origin + step * (2 - depth), origin + step * (2 - depth),
                      side, side)
        painter.setBrush(QColor(255, 255, 255, alpha))
        painter.drawRoundedRect(rect, radius, radius)


CONCEPTS = {
    "A": ("视角阵列", draw_aperture_grid),
    "B": ("微透镜", draw_lenslet),
    "C": ("视差堆叠", draw_parallax),
}
CHOSEN = "A"


def render(size, draw):
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    draw(painter, size)
    painter.end()
    return image


def _to_pillow(image):
    from PIL import Image
    buffer = image.convertToFormat(QImage.Format_RGBA8888)
    width, height = buffer.width(), buffer.height()
    raw = buffer.constBits().asstring(width * height * 4)
    return Image.frombytes("RGBA", (width, height), raw)


def write_icon(draw, ico_path, png_path):
    frames = [_to_pillow(render(size, draw)) for size in SIZES]
    os.makedirs(os.path.dirname(ico_path), exist_ok=True)
    # Each size is a separately drawn bitmap, not a downscale of the largest.
    frames[-1].save(ico_path, format="ICO",
                    sizes=[(s, s) for s in SIZES],
                    append_images=frames[:-1])
    _to_pillow(render(512, draw)).save(png_path, format="PNG")
    return ico_path, png_path


def write_preview(path):
    """三个方案 × 三种尺寸的对照图, 用来在真实尺寸下比较。"""
    shown = (16, 32, 128)
    pad, gap, label = 18, 26, 22
    width = pad * 2 + sum(shown) + gap * (len(shown) - 1) + 150
    height = pad * 2 + len(CONCEPTS) * (128 + label + gap)
    sheet = QImage(width, height, QImage.Format_ARGB32)
    sheet.fill(QColor("#e6e6e9"))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.Antialiasing)
    font = painter.font()
    font.setPointSize(9)
    font.setBold(True)
    painter.setFont(font)
    y = pad
    for key, (name, draw) in CONCEPTS.items():
        painter.setPen(QColor("#1d1d1f"))
        painter.drawText(pad, y + 12, f"{key} · {name}"
                         + ("   ← 推荐" if key == CHOSEN else ""))
        x = pad
        for size in shown:
            icon = render(size, draw)
            painter.drawImage(QPointF(x, y + label + (128 - size) / 2.0), icon)
            painter.setPen(QColor("#8e8e93"))
            painter.drawText(int(x), int(y + label + 128 + 14), f"{size}px")
            x += size + gap
        y += 128 + label + gap
    painter.end()
    sheet.save(path)
    return path


def main():
    # QPainter 需要一个存活的 QApplication, 即便这里不进事件循环
    QApplication.instance() or QApplication([])
    _, draw = CONCEPTS[CHOSEN]
    ico, png = write_icon(draw, os.path.join(ASSETS, "icon.ico"),
                          os.path.join(ASSETS, "icon.png"))
    print(f"wrote {ico}")
    print(f"wrote {png}")
    if "--preview" in sys.argv:
        target = sys.argv[sys.argv.index("--preview") + 1] \
            if len(sys.argv) > sys.argv.index("--preview") + 1 else \
            os.path.join(ASSETS, "icon_concepts.png")
        print(f"wrote {write_preview(target)}")


if __name__ == "__main__":
    main()
