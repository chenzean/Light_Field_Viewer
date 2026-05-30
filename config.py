"""
光场图像查看器 V1 — 全局配置与默认参数
"""

VERSION = "1.0.3"

# ---- 默认角度分辨率 ----
DEFAULT_ANGULAR_U = 5
DEFAULT_ANGULAR_V = 5

# ---- 矩形框默认参数 ----
DEFAULT_RECT_X = 100
DEFAULT_RECT_Y = 100
DEFAULT_RECT_W = 128
DEFAULT_RECT_H = 128
DEFAULT_RECT_THICKNESS = 3

# ---- 矩形框自动颜色循环 (RGB) ----
RECT_COLOR_CYCLE = [
    (255, 0, 0),      # 红
    (0, 255, 0),      # 绿
    (0, 0, 255),      # 蓝
    (255, 255, 0),    # 黄
    (0, 255, 255),    # 青
    (255, 0, 255),    # 品红
    (255, 128, 0),    # 橙
    (128, 0, 255),    # 紫
]

# ---- EPI 默认参数 ----
DEFAULT_EPI_ANGULAR_IDX = 3      # 角度行/列索引 (从 1 开始)
DEFAULT_EPI_SPATIAL_POS = 256    # 空间位置
DEFAULT_EPI_CROP_START = 200     # 裁剪起始列
DEFAULT_EPI_CROP_END = 260       # 裁剪结束列 (默认 60 像素宽, 局部观察)
DEFAULT_EPI_STRETCH = 1          # EPI 高度拉伸倍数 (1=不拉伸, 保持原始角度分辨率)

# ---- 支持的图像格式 ----
SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}

# ---- 5D 光场数组 LRU 缓存大小 ----
LF_CACHE_SIZE = 4

# ---- 导出子目录名 ----
EXPORT_DIR_ORIGINAL = "00_original_sai"       # 原始无标注的 SAI
EXPORT_DIR_RECT_ANNOTATED = "01_rect_annotated"  # 带红框 + EPI 标记的 SAI
EXPORT_DIR_ZOOM_CROP = "02_zoom_crop"            # 局部放大裁剪
EXPORT_DIR_EPI_FULL = "03_epi_full"              # 完整 EPI
EXPORT_DIR_EPI_CROP = "04_epi_crop"              # 裁剪后的局部 EPI
EXPORT_DIR_RESIDUAL_ANNOTATED = "05_residual_annotated"  # 全图残差 + 矩形框
EXPORT_DIR_RESIDUAL_CROP = "06_residual_crop"            # 局部残差 (带颜色条 + 边框)
EXPORT_LOG_FILENAME = "export_log.txt"
