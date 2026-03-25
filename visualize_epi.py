"""
EPI (Epipolar Plane Image) 可视化

提取并可视化两帧光场图像的水平/垂直 EPI, 观察:
  - EPI 斜线斜率 = 视差大小
  - 两帧 EPI 差异 = 时间运动在 EPI 空间的表现
  - 不同空间位置的 EPI 结构差异

水平 EPI: 固定 u, 固定 y -> lf[u, :, y, :, :] -> [V, W, C]
  横轴=空间 x, 纵轴=角度 v, 斜线斜率反映水平视差

垂直 EPI: 固定 v, 固定 x -> lf[:, v, :, x, :] -> [U, H, C]
  横轴=空间 y, 纵轴=角度 u, 斜线斜率反映垂直视差

用法:
  python visualize_epi.py
"""

import cv2
import numpy as np
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.ndimage import zoom as scipy_zoom

# ============================================================
# 配置
# ============================================================
DATA_ROOT = r"D:\Light_Field_Video\4_Dataset\Dataset_PNG\test"
SCENE = "Scenes_0003"
SAMPLE = "sample_000001"
FRAME_0 = "frame_0003"
FRAME_1 = "frame_0005"
ANG_RES = 5
OUTPUT_DIR = r"D:\Light_Field_Video\vis_output"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_light_field(frame_dir, ang_res):
    first = cv2.imread(os.path.join(frame_dir, "1_1.png"))
    H, W, C = first.shape
    lf = np.zeros((ang_res, ang_res, H, W, C), dtype=np.uint8)
    for u in range(1, ang_res + 1):
        for v in range(1, ang_res + 1):
            img = cv2.imread(os.path.join(frame_dir, f"{u}_{v}.png"))
            lf[u-1, v-1] = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return lf


def stretch_epi(epi, factor=10):
    """用双线性插值拉伸 EPI 的角度维度"""
    # epi: [ang, spatial, 3]
    return scipy_zoom(epi, (factor, 1, 1), order=1).clip(0, 255).astype(np.uint8)


# ============================================================
# 加载数据
# ============================================================
frame0_dir = os.path.join(DATA_ROOT, SCENE, SAMPLE, FRAME_0)
frame1_dir = os.path.join(DATA_ROOT, SCENE, SAMPLE, FRAME_1)

print(f"Loading {SCENE}/{SAMPLE}")
lf0 = load_light_field(frame0_dir, ANG_RES)
lf1 = load_light_field(frame1_dir, ANG_RES)
U, V, H, W, C = lf0.shape
print(f"  LF: [{U},{V},{H},{W},{C}]")

STRETCH = 10  # 角度维度拉伸倍数

# ============================================================
# 1. 水平 EPI - 多个空间行, 固定 u=中心
# ============================================================
print("\n[1/4] Horizontal EPIs at different spatial rows...")

u_idx = 2  # 中心角度行 (0-based)
y_positions = [100, 200, 256, 350, 450]  # 不同空间行

fig, axes = plt.subplots(len(y_positions), 3, figsize=(24, 3 * len(y_positions)))

for row, y in enumerate(y_positions):
    # 水平 EPI: lf[u, :, y, :, :] -> [V, W, C]
    epi0 = lf0[u_idx, :, y, :, :]  # [5, 512, 3]
    epi1 = lf1[u_idx, :, y, :, :]

    # 拉伸
    epi0_s = stretch_epi(epi0, STRETCH)  # [50, 512, 3]
    epi1_s = stretch_epi(epi1, STRETCH)
    diff_s = np.abs(epi0_s.astype(np.float32) - epi1_s.astype(np.float32))
    diff_vis = np.clip(diff_s * 3, 0, 255).astype(np.uint8)

    axes[row, 0].imshow(epi0_s)
    axes[row, 0].set_ylabel(f"y={y}", fontsize=12, fontweight="bold")
    if row == 0:
        axes[row, 0].set_title(f"{FRAME_0}", fontsize=13, fontweight="bold")
    axes[row, 0].set_xticks([])
    axes[row, 0].set_yticks([0, 25, 49])
    axes[row, 0].set_yticklabels(["v=1", "v=3", "v=5"], fontsize=8)

    axes[row, 1].imshow(epi1_s)
    if row == 0:
        axes[row, 1].set_title(f"{FRAME_1}", fontsize=13, fontweight="bold")
    axes[row, 1].set_xticks([])
    axes[row, 1].set_yticks([])

    axes[row, 2].imshow(diff_vis)
    if row == 0:
        axes[row, 2].set_title("Diff (x3)", fontsize=13, fontweight="bold")
    axes[row, 2].set_xticks([])
    axes[row, 2].set_yticks([])

plt.suptitle(f"Horizontal EPI (u={u_idx+1}, vary v)\nSlope = horizontal disparity",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "11_epi_horizontal_rows.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 11_epi_horizontal_rows.png")

# ============================================================
# 2. 垂直 EPI - 多个空间列, 固定 v=中心
# ============================================================
print("\n[2/4] Vertical EPIs at different spatial columns...")

v_idx = 2  # 中心角度列
x_positions = [100, 200, 256, 350, 450]

fig, axes = plt.subplots(len(x_positions), 3, figsize=(24, 3 * len(x_positions)))

for row, x in enumerate(x_positions):
    # 垂直 EPI: lf[:, v, :, x, :] -> [U, H, C]
    epi0 = lf0[:, v_idx, :, x, :]  # [5, 512, 3]
    epi1 = lf1[:, v_idx, :, x, :]

    epi0_s = stretch_epi(epi0, STRETCH)
    epi1_s = stretch_epi(epi1, STRETCH)
    diff_s = np.abs(epi0_s.astype(np.float32) - epi1_s.astype(np.float32))
    diff_vis = np.clip(diff_s * 3, 0, 255).astype(np.uint8)

    axes[row, 0].imshow(epi0_s)
    axes[row, 0].set_ylabel(f"x={x}", fontsize=12, fontweight="bold")
    if row == 0:
        axes[row, 0].set_title(f"{FRAME_0}", fontsize=13, fontweight="bold")
    axes[row, 0].set_xticks([])
    axes[row, 0].set_yticks([0, 25, 49])
    axes[row, 0].set_yticklabels(["u=1", "u=3", "u=5"], fontsize=8)

    axes[row, 1].imshow(epi1_s)
    if row == 0:
        axes[row, 1].set_title(f"{FRAME_1}", fontsize=13, fontweight="bold")
    axes[row, 1].set_xticks([])
    axes[row, 1].set_yticks([])

    axes[row, 2].imshow(diff_vis)
    if row == 0:
        axes[row, 2].set_title("Diff (x3)", fontsize=13, fontweight="bold")
    axes[row, 2].set_xticks([])
    axes[row, 2].set_yticks([])

plt.suptitle(f"Vertical EPI (v={v_idx+1}, vary u)\nSlope = vertical disparity",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "12_epi_vertical_cols.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 12_epi_vertical_cols.png")

# ============================================================
# 3. 同一位置, 不同角度索引的 EPI 对比
# ============================================================
print("\n[3/4] EPIs at same position, different angular indices...")

y_fix = 256  # 固定空间行

fig, axes = plt.subplots(ANG_RES, 2, figsize=(20, 2.5 * ANG_RES))

for u in range(ANG_RES):
    epi0 = lf0[u, :, y_fix, :, :]  # [V, W, C]
    epi1 = lf1[u, :, y_fix, :, :]

    epi0_s = stretch_epi(epi0, STRETCH)
    epi1_s = stretch_epi(epi1, STRETCH)

    axes[u, 0].imshow(epi0_s)
    axes[u, 0].set_ylabel(f"u={u+1}", fontsize=12, fontweight="bold")
    if u == 0:
        axes[u, 0].set_title(f"{FRAME_0} (y={y_fix})", fontsize=13, fontweight="bold")
    axes[u, 0].set_xticks([])
    axes[u, 0].set_yticks([0, 25, 49])
    axes[u, 0].set_yticklabels(["v=1", "v=3", "v=5"], fontsize=8)

    axes[u, 1].imshow(epi1_s)
    if u == 0:
        axes[u, 1].set_title(f"{FRAME_1} (y={y_fix})", fontsize=13, fontweight="bold")
    axes[u, 1].set_xticks([])
    axes[u, 1].set_yticks([])

plt.suptitle(f"Horizontal EPI at y={y_fix}, all u rows\nEPI slope changes with angular row u",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "13_epi_all_u.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 13_epi_all_u.png")

# ============================================================
# 4. EPI 局部放大 (展示斜线结构)
# ============================================================
print("\n[4/4] EPI local zoom with disparity annotation...")

y_fix = 256
u_fix = 2
crop_ranges = [
    (100, 200, "background"),
    (200, 300, "object-edge"),
    (350, 450, "motion-area"),
]

fig, axes = plt.subplots(len(crop_ranges), 3, figsize=(20, 4 * len(crop_ranges)))

for row, (x0, x1, label) in enumerate(crop_ranges):
    epi0 = lf0[u_fix, :, y_fix, x0:x1, :]  # [5, 100, 3]
    epi1 = lf1[u_fix, :, y_fix, x0:x1, :]

    epi0_s = stretch_epi(epi0, STRETCH)  # [50, 100, 3]
    epi1_s = stretch_epi(epi1, STRETCH)
    diff_s = np.abs(epi0_s.astype(np.float32) - epi1_s.astype(np.float32))
    diff_vis = np.clip(diff_s * 3, 0, 255).astype(np.uint8)

    axes[row, 0].imshow(epi0_s)
    axes[row, 0].set_ylabel(f"x=[{x0},{x1}]\n{label}", fontsize=11, fontweight="bold")
    if row == 0:
        axes[row, 0].set_title(f"{FRAME_0}", fontsize=13, fontweight="bold")
    axes[row, 0].set_yticks([0, 25, 49])
    axes[row, 0].set_yticklabels(["v=1", "v=3", "v=5"], fontsize=8)

    axes[row, 1].imshow(epi1_s)
    if row == 0:
        axes[row, 1].set_title(f"{FRAME_1}", fontsize=13, fontweight="bold")
    axes[row, 1].set_yticks([])

    axes[row, 2].imshow(diff_vis)
    if row == 0:
        axes[row, 2].set_title("Diff (x3)", fontsize=13, fontweight="bold")
    axes[row, 2].set_yticks([])

plt.suptitle(f"EPI Local Zoom (u={u_fix+1}, y={y_fix})\nDisparity = slope of lines in EPI",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "14_epi_zoom.png"), dpi=200, bbox_inches="tight")
plt.close()
print("  Saved: 14_epi_zoom.png")

print(f"\nAll saved to: {OUTPUT_DIR}")
