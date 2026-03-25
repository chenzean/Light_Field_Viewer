"""
时间-空间切片可视化

固定角度 (u, v) 和空间行/列, 把三帧沿时间轴排列:
  - 时间-水平切片: 固定 y, 横轴=x, 纵轴=t (3帧)
  - 时间-垂直切片: 固定 x, 横轴=y, 纵轴=t (3帧)

这样能看到运动轨迹在时间维上的变化。
斜线斜率 = 运动速度, 中间帧的位置应在两端帧之间。
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
FRAMES = ["frame_0003", "frame_0004", "frame_0005"]  # t=0, 0.5, 1
ANG_RES = 5
OUTPUT_DIR = r"D:\Light_Field_Video\vis_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

STRETCH = 30  # 时间维只有3帧, 需要大幅拉伸才能看清


def load_sai(frame_dir, u, v):
    path = os.path.join(frame_dir, f"{u}_{v}.png")
    img = cv2.imread(path)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def stretch_temporal(slc, factor):
    """拉伸时间维 (axis=0), 双线性插值"""
    return scipy_zoom(slc, (factor, 1, 1), order=1).clip(0, 255).astype(np.uint8)


# 加载三帧的所有视角
print(f"Loading {SCENE}/{SAMPLE}, 3 frames x 25 views...")
frames = {}
for fname in FRAMES:
    frame_dir = os.path.join(DATA_ROOT, SCENE, SAMPLE, fname)
    views = {}
    for u in range(1, ANG_RES + 1):
        for v in range(1, ANG_RES + 1):
            views[(u, v)] = load_sai(frame_dir, u, v)
    frames[fname] = views

H, W, C = frames[FRAMES[0]][(1, 1)].shape
print(f"  Size: {H}x{W}, Views: {ANG_RES}x{ANG_RES}")

# ============================================================
# 1. 时间-水平切片 (固定 y, 横轴=x, 纵轴=t)
# ============================================================
print("\n[1/4] Temporal-horizontal slices...")

u_fix, v_fix = 3, 3  # 中心视角
y_positions = [100, 200, 256, 350, 450]

fig, axes = plt.subplots(len(y_positions), 1, figsize=(20, 4 * len(y_positions)))

for row, y in enumerate(y_positions):
    # 三帧在 y 行的像素: 每帧取一行 [W, C], 堆叠成 [3, W, C]
    temporal_slice = np.stack([
        frames[fname][(u_fix, v_fix)][y, :, :]
        for fname in FRAMES
    ], axis=0)  # [3, W, C]

    # 拉伸时间维
    ts = stretch_temporal(temporal_slice, STRETCH)  # [90, W, C]

    axes[row].imshow(ts)
    axes[row].set_ylabel(f"y={y}", fontsize=12, fontweight="bold")
    axes[row].set_xlabel("x (spatial)", fontsize=10)
    # 标注三帧位置
    axes[row].set_yticks([0, STRETCH * 0.5, STRETCH * 1, STRETCH * 1.5, STRETCH * 2, STRETCH * 3 - 1])
    axes[row].set_yticklabels(["", "t=0", "", "t=0.5", "", "t=1"], fontsize=9)
    # 画三帧分界线
    axes[row].axhline(y=STRETCH, color="white", linewidth=0.5, linestyle="--", alpha=0.7)
    axes[row].axhline(y=STRETCH * 2, color="white", linewidth=0.5, linestyle="--", alpha=0.7)

plt.suptitle(f"Temporal-Horizontal Slice (view ({u_fix},{v_fix}))\n"
             f"x-axis=spatial x, y-axis=time (3 frames stretched x{STRETCH})\n"
             f"Slope of lines = motion velocity",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "17_temporal_horizontal.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 17_temporal_horizontal.png")

# ============================================================
# 2. 时间-垂直切片 (固定 x, 横轴=y, 纵轴=t)
# ============================================================
print("\n[2/4] Temporal-vertical slices...")

x_positions = [100, 200, 256, 350, 450]

fig, axes = plt.subplots(len(x_positions), 1, figsize=(20, 4 * len(x_positions)))

for row, x in enumerate(x_positions):
    temporal_slice = np.stack([
        frames[fname][(u_fix, v_fix)][:, x, :]
        for fname in FRAMES
    ], axis=0)  # [3, H, C]

    ts = stretch_temporal(temporal_slice, STRETCH)

    axes[row].imshow(ts)
    axes[row].set_ylabel(f"x={x}", fontsize=12, fontweight="bold")
    axes[row].set_xlabel("y (spatial)", fontsize=10)
    axes[row].set_yticks([0, STRETCH * 0.5, STRETCH * 1, STRETCH * 1.5, STRETCH * 2, STRETCH * 3 - 1])
    axes[row].set_yticklabels(["", "t=0", "", "t=0.5", "", "t=1"], fontsize=9)
    axes[row].axhline(y=STRETCH, color="white", linewidth=0.5, linestyle="--", alpha=0.7)
    axes[row].axhline(y=STRETCH * 2, color="white", linewidth=0.5, linestyle="--", alpha=0.7)

plt.suptitle(f"Temporal-Vertical Slice (view ({u_fix},{v_fix}))\n"
             f"x-axis=spatial y, y-axis=time (3 frames stretched x{STRETCH})",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "18_temporal_vertical.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 18_temporal_vertical.png")

# ============================================================
# 3. 不同视角的时间切片对比 (同一空间行, 5个角度)
# ============================================================
print("\n[3/4] Temporal slices across views...")

y_fix = 256

fig, axes = plt.subplots(ANG_RES, ANG_RES, figsize=(25, 25))

for u in range(1, ANG_RES + 1):
    for v in range(1, ANG_RES + 1):
        temporal_slice = np.stack([
            frames[fname][(u, v)][y_fix, :, :]
            for fname in FRAMES
        ], axis=0)  # [3, W, C]

        ts = stretch_temporal(temporal_slice, STRETCH)

        ax = axes[u-1, v-1]
        ax.imshow(ts)
        title = f"({u},{v})"
        if u == 3 and v == 3:
            ax.set_title(title + " center", fontsize=10, color="blue", fontweight="bold")
        else:
            ax.set_title(title, fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([0, STRETCH, STRETCH*2, STRETCH*3-1])
        ax.set_yticklabels(["t=0", "t=0.5", "t=1", ""], fontsize=7)

plt.suptitle(f"Temporal Slice at y={y_fix}, all 5x5 views\n"
             f"Each panel: x-axis=spatial x, y-axis=time\n"
             f"Notice how motion trajectory shifts across views (= disparity)",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "19_temporal_all_views.png"), dpi=120, bbox_inches="tight")
plt.close()
print("  Saved: 19_temporal_all_views.png")

# ============================================================
# 4. 时间-角度-空间 3D 切片 (固定 x 和 y, 看 t vs v)
# ============================================================
print("\n[4/4] Time-Angular slice (t vs v)...")

spatial_positions = [
    (150, 256, "background"),
    (256, 200, "person-left"),
    (256, 350, "person-right"),
    (400, 256, "foreground"),
]

u_fix = 3  # 固定 u=3, 看 v 方向

fig, axes = plt.subplots(len(spatial_positions), 1, figsize=(12, 5 * len(spatial_positions)))

for row, (y, x, label) in enumerate(spatial_positions):
    # t vs v 切片: 对每帧取 lf[u_fix-1, :, y, x, :] -> [V, C]
    # 堆叠3帧 -> [3, V, C]
    tv_slice = np.stack([
        np.stack([frames[fname][(u_fix, v)][y, x, :] for v in range(1, ANG_RES + 1)], axis=0)
        for fname in FRAMES
    ], axis=0)  # [3, 5, 3]

    # 拉伸两个维度
    ts = scipy_zoom(tv_slice, (STRETCH, STRETCH, 1), order=1).clip(0, 255).astype(np.uint8)

    axes[row].imshow(ts)
    axes[row].set_ylabel(f"({y},{x})\n{label}", fontsize=11, fontweight="bold")
    axes[row].set_xlabel("v (angular)", fontsize=10)
    axes[row].set_xticks([i * STRETCH + STRETCH//2 for i in range(ANG_RES)])
    axes[row].set_xticklabels([f"v={i+1}" for i in range(ANG_RES)], fontsize=9)
    axes[row].set_yticks([STRETCH//2, STRETCH + STRETCH//2, STRETCH*2 + STRETCH//2])
    axes[row].set_yticklabels(["t=0", "t=0.5", "t=1"], fontsize=9)
    axes[row].axhline(y=STRETCH, color="white", linewidth=0.5, linestyle="--", alpha=0.7)
    axes[row].axhline(y=STRETCH*2, color="white", linewidth=0.5, linestyle="--", alpha=0.7)

plt.suptitle(f"Time-Angular Slice (u={u_fix}, fixed spatial position)\n"
             f"x-axis=angular v, y-axis=time t\n"
             f"Shows how disparity and motion interact at each pixel",
             fontsize=14, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "20_time_angular_slice.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 20_time_angular_slice.png")

print(f"\nAll saved to: {OUTPUT_DIR}")
