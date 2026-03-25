"""
三帧 EPI 对比可视化

固定角度坐标 u, 固定空间行 y, 提取三帧的水平 EPI 并上下排列:
  frame_0003 (t=0)
  frame_0004 (t=0.5, GT)
  frame_0005 (t=1)

观察 EPI 斜线在时间维度上的平移变化。
"""

import cv2
import numpy as np
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.ndimage import zoom as scipy_zoom

DATA_ROOT = r"D:\Light_Field_Video\4_Dataset\Dataset_PNG\test"
SCENE = "Scenes_0003"
SAMPLE = "sample_000001"
FRAMES = ["frame_0003", "frame_0004", "frame_0005"]
FRAME_LABELS = ["t=0 (frame_0003)", "t=0.5 (frame_0004, GT)", "t=1 (frame_0005)"]
ANG_RES = 5
OUTPUT_DIR = r"D:\Light_Field_Video\vis_output"
STRETCH = 10

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
    return scipy_zoom(epi, (factor, 1, 1), order=1).clip(0, 255).astype(np.uint8)


# 加载三帧
print(f"Loading {SCENE}/{SAMPLE}, 3 frames...")
lfs = []
for fname in FRAMES:
    lf = load_light_field(os.path.join(DATA_ROOT, SCENE, SAMPLE, fname), ANG_RES)
    lfs.append(lf)
    print(f"  {fname}: {lf.shape}")

U, V, H, W, C = lfs[0].shape

# ============================================================
# 1. 水平 EPI 三帧对比 - 多个空间行
# ============================================================
print("\n[1/3] Horizontal EPI - 3 frames comparison...")

u_fix = 2  # 中心角度行 (0-based)
y_positions = [100, 200, 256, 350, 450]

fig, axes = plt.subplots(len(y_positions), 3, figsize=(24, 3.5 * len(y_positions)))

for row, y in enumerate(y_positions):
    for col, (lf, label) in enumerate(zip(lfs, FRAME_LABELS)):
        epi = lf[u_fix, :, y, :, :]  # [V, W, C]
        epi_s = stretch_epi(epi, STRETCH)

        axes[row, col].imshow(epi_s)
        axes[row, col].set_yticks([0, STRETCH * 2, STRETCH * 4])
        axes[row, col].set_yticklabels(["v=1", "v=3", "v=5"], fontsize=8)
        if col == 0:
            axes[row, col].set_ylabel(f"y={y}", fontsize=12, fontweight="bold")
        if row == 0:
            axes[row, col].set_title(label, fontsize=12, fontweight="bold")
        axes[row, col].set_xticks([])

plt.suptitle(f"Horizontal EPI: 3 Frames at u={u_fix+1}\nObserve line shift from t=0 to t=1",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "21_epi_3frames_horizontal.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 21_epi_3frames_horizontal.png")

# ============================================================
# 2. 水平 EPI 局部放大 - 看斜线平移细节
# ============================================================
print("\n[2/3] Horizontal EPI zoom - line shift detail...")

y_fix = 256
u_fix = 2
crop_ranges = [
    (100, 220, "left region"),
    (200, 320, "center-left"),
    (300, 420, "center-right"),
    (380, 500, "right region"),
]

fig, axes = plt.subplots(len(crop_ranges), 3, figsize=(20, 5 * len(crop_ranges)))

for row, (x0, x1, label) in enumerate(crop_ranges):
    for col, (lf, flabel) in enumerate(zip(lfs, FRAME_LABELS)):
        epi = lf[u_fix, :, y_fix, x0:x1, :]
        epi_s = stretch_epi(epi, STRETCH)

        axes[row, col].imshow(epi_s)
        if col == 0:
            axes[row, col].set_ylabel(f"x=[{x0},{x1}]\n{label}",
                                       fontsize=11, fontweight="bold")
        if row == 0:
            axes[row, col].set_title(flabel, fontsize=12, fontweight="bold")
        axes[row, col].set_yticks([0, STRETCH * 2, STRETCH * 4])
        axes[row, col].set_yticklabels(["v=1", "v=3", "v=5"], fontsize=8)

plt.suptitle(f"Horizontal EPI Zoom at y={y_fix}, u={u_fix+1}\n"
             f"Compare line positions across 3 frames",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "22_epi_3frames_zoom.png"), dpi=200, bbox_inches="tight")
plt.close()
print("  Saved: 22_epi_3frames_zoom.png")

# ============================================================
# 3. 垂直 EPI 三帧对比
# ============================================================
print("\n[3/3] Vertical EPI - 3 frames comparison...")

v_fix = 2  # 中心角度列
x_positions = [100, 200, 256, 350, 450]

fig, axes = plt.subplots(len(x_positions), 3, figsize=(24, 3.5 * len(x_positions)))

for row, x in enumerate(x_positions):
    for col, (lf, label) in enumerate(zip(lfs, FRAME_LABELS)):
        epi = lf[:, v_fix, :, x, :]  # [U, H, C]
        epi_s = stretch_epi(epi, STRETCH)

        axes[row, col].imshow(epi_s)
        axes[row, col].set_yticks([0, STRETCH * 2, STRETCH * 4])
        axes[row, col].set_yticklabels(["u=1", "u=3", "u=5"], fontsize=8)
        if col == 0:
            axes[row, col].set_ylabel(f"x={x}", fontsize=12, fontweight="bold")
        if row == 0:
            axes[row, col].set_title(label, fontsize=12, fontweight="bold")
        axes[row, col].set_xticks([])

plt.suptitle(f"Vertical EPI: 3 Frames at v={v_fix+1}\nObserve line shift from t=0 to t=1",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "23_epi_3frames_vertical.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 23_epi_3frames_vertical.png")

print(f"\nAll saved to: {OUTPUT_DIR}")
