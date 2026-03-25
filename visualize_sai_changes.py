"""
两帧光场图像子孔径阵列变化可视化

生成四类可视化:
  1. 差异热力图: 每个视角的帧间差异, 用热力图显示运动区域
  2. 光流可视化: 用 Farneback 光流估计两帧之间的运动, 用色轮显示
  3. 各视角差异统计分析: 统计图表
  4. 子孔径阵列拼接对比

用法:
  python visualize_sai_changes.py
"""

import cv2
import numpy as np
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============================================================
# 配置
# ============================================================
DATA_ROOT = r"D:\Light_Field_Video\4_Dataset\Dataset_PNG\test"
SCENE = "Scenes_0003"
SAMPLE = "sample_000001"
FRAME_0 = "frame_0003"   # 输入帧 0
FRAME_1 = "frame_0005"   # 输入帧 1
ANG_RES = 5              # 角度分辨率 5x5
OUTPUT_DIR = r"D:\Light_Field_Video\Light_Field_Viewer\vis_output"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_sai(frame_dir, u, v):
    path = os.path.join(frame_dir, f"{u}_{v}.png")
    img = cv2.imread(path)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def compute_flow_hsv(gray0, gray1):
    flow = cv2.calcOpticalFlowFarneback(
        gray0, gray1, None,
        pyr_scale=0.5, levels=3, winsize=15,
        iterations=3, poly_n=5, poly_sigma=1.2, flags=0
    )
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    hsv = np.zeros((*gray0.shape, 3), dtype=np.uint8)
    hsv[..., 0] = ang * 180 / np.pi / 2
    hsv[..., 1] = 255
    hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB), flow, mag


def flow_color_wheel(size=80):
    y, x = np.mgrid[-size:size+1, -size:size+1].astype(np.float32)
    mag = np.sqrt(x**2 + y**2)
    ang = np.arctan2(y, x)
    hsv = np.zeros((2*size+1, 2*size+1, 3), dtype=np.uint8)
    hsv[..., 0] = ((ang + np.pi) / (2 * np.pi) * 180).astype(np.uint8)
    hsv[..., 1] = 255
    hsv[..., 2] = np.clip(mag / size * 255, 0, 255).astype(np.uint8)
    mask = mag > size
    hsv[mask] = 0
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


# ============================================================
# 加载数据
# ============================================================
frame0_dir = os.path.join(DATA_ROOT, SCENE, SAMPLE, FRAME_0)
frame1_dir = os.path.join(DATA_ROOT, SCENE, SAMPLE, FRAME_1)

print(f"Loading {SCENE}/{SAMPLE}: {FRAME_0} vs {FRAME_1}")

sais_0 = {}
sais_1 = {}
for u in range(1, ANG_RES + 1):
    for v in range(1, ANG_RES + 1):
        sais_0[(u, v)] = load_sai(frame0_dir, u, v)
        sais_1[(u, v)] = load_sai(frame1_dir, u, v)

H, W = sais_0[(1, 1)].shape[:2]
print(f"  Size: {H}x{W}, Angular: {ANG_RES}x{ANG_RES}")

# ============================================================
# 1. 差异热力图 (5x5 网格)
# ============================================================
print("\n[1/4] Difference heatmap...")

fig, axes = plt.subplots(ANG_RES, ANG_RES, figsize=(20, 20))
fig.suptitle(f"{SCENE}/{SAMPLE}: Frame Difference Heatmap\n({FRAME_0} vs {FRAME_1})",
             fontsize=16, fontweight="bold")

all_diffs = []
for u in range(1, ANG_RES + 1):
    for v in range(1, ANG_RES + 1):
        diff = np.abs(sais_0[(u, v)].astype(np.float32) - sais_1[(u, v)].astype(np.float32))
        all_diffs.append(diff.mean(axis=2))

vmax = np.percentile(np.concatenate([d.ravel() for d in all_diffs]), 99)

idx = 0
for u in range(1, ANG_RES + 1):
    for v in range(1, ANG_RES + 1):
        ax = axes[u-1, v-1]
        im = ax.imshow(all_diffs[idx], cmap="hot", vmin=0, vmax=vmax)
        title = f"({u},{v})"
        if u == 3 and v == 3:
            title += " center"
            ax.set_title(title, fontsize=10, color="blue", fontweight="bold")
        else:
            ax.set_title(title, fontsize=10)
        ax.axis("off")
        idx += 1

fig.subplots_adjust(right=0.92)
cbar_ax = fig.add_axes([0.94, 0.15, 0.02, 0.7])
fig.colorbar(im, cax=cbar_ax, label="Pixel Difference (0-255)")

plt.savefig(os.path.join(OUTPUT_DIR, "01_diff_heatmap.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 01_diff_heatmap.png")

# ============================================================
# 2. 光流可视化 (5x5 网格)
# ============================================================
print("\n[2/4] Optical flow...")

fig, axes = plt.subplots(ANG_RES, ANG_RES, figsize=(20, 20))
fig.suptitle(f"{SCENE}/{SAMPLE}: Optical Flow\n({FRAME_0} -> {FRAME_1})",
             fontsize=16, fontweight="bold")

flow_mags = []
for u in range(1, ANG_RES + 1):
    for v in range(1, ANG_RES + 1):
        gray0 = cv2.cvtColor(sais_0[(u, v)], cv2.COLOR_RGB2GRAY)
        gray1 = cv2.cvtColor(sais_1[(u, v)], cv2.COLOR_RGB2GRAY)
        flow_rgb, flow, mag = compute_flow_hsv(gray0, gray1)

        ax = axes[u-1, v-1]
        ax.imshow(flow_rgb)
        title = f"({u},{v}) mag={mag.mean():.1f}"
        if u == 3 and v == 3:
            ax.set_title(title, fontsize=9, color="blue", fontweight="bold")
        else:
            ax.set_title(title, fontsize=9)
        ax.axis("off")
        flow_mags.append(mag.mean())

wheel = flow_color_wheel(80)
ax_wheel = fig.add_axes([0.92, 0.42, 0.08, 0.16])
ax_wheel.imshow(wheel)
ax_wheel.set_title("Color Wheel", fontsize=10)
ax_wheel.axis("off")

plt.savefig(os.path.join(OUTPUT_DIR, "02_optical_flow.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 02_optical_flow.png")

# ============================================================
# 3. 统计分析
# ============================================================
print("\n[3/4] Statistical analysis...")

fig = plt.figure(figsize=(24, 16))

# 3a: 每个视角的平均差异
ax1 = fig.add_subplot(2, 3, 1)
diff_map = np.zeros((ANG_RES, ANG_RES))
for u in range(1, ANG_RES + 1):
    for v in range(1, ANG_RES + 1):
        diff = np.abs(sais_0[(u, v)].astype(np.float32) - sais_1[(u, v)].astype(np.float32))
        diff_map[u-1, v-1] = diff.mean()
im1 = ax1.imshow(diff_map, cmap="YlOrRd", interpolation="nearest")
ax1.set_title("Mean Diff per View", fontsize=13, fontweight="bold")
ax1.set_xlabel("v (column)")
ax1.set_ylabel("u (row)")
ax1.set_xticks(range(ANG_RES))
ax1.set_xticklabels(range(1, ANG_RES+1))
ax1.set_yticks(range(ANG_RES))
ax1.set_yticklabels(range(1, ANG_RES+1))
for ui in range(ANG_RES):
    for vi in range(ANG_RES):
        ax1.text(vi, ui, f"{diff_map[ui, vi]:.1f}", ha="center", va="center", fontsize=9)
plt.colorbar(im1, ax=ax1, shrink=0.8)

# 3b: 每个视角的平均光流幅度
ax2 = fig.add_subplot(2, 3, 2)
flow_map = np.array(flow_mags).reshape(ANG_RES, ANG_RES)
im2 = ax2.imshow(flow_map, cmap="Blues", interpolation="nearest")
ax2.set_title("Mean Flow Magnitude per View", fontsize=13, fontweight="bold")
ax2.set_xlabel("v (column)")
ax2.set_ylabel("u (row)")
ax2.set_xticks(range(ANG_RES))
ax2.set_xticklabels(range(1, ANG_RES+1))
ax2.set_yticks(range(ANG_RES))
ax2.set_yticklabels(range(1, ANG_RES+1))
for ui in range(ANG_RES):
    for vi in range(ANG_RES):
        ax2.text(vi, ui, f"{flow_map[ui, vi]:.2f}", ha="center", va="center", fontsize=9)
plt.colorbar(im2, ax=ax2, shrink=0.8)

# 3c: 中心 vs 角落差异曲线
ax3 = fig.add_subplot(2, 3, 3)
center_diff = np.abs(sais_0[(3, 3)].astype(np.float32) - sais_1[(3, 3)].astype(np.float32)).mean(2)
corner_diff = np.abs(sais_0[(1, 1)].astype(np.float32) - sais_1[(1, 1)].astype(np.float32)).mean(2)
ax3.plot(center_diff.mean(axis=0), label="Center (3,3)", color="blue", linewidth=1.5)
ax3.plot(corner_diff.mean(axis=0), label="Corner (1,1)", color="red", linewidth=1.5)
ax3.set_title("Horizontal Diff Profile", fontsize=13, fontweight="bold")
ax3.set_xlabel("Pixel x")
ax3.set_ylabel("Mean Difference")
ax3.legend()
ax3.grid(True, alpha=0.3)

# 3d: 中心视角两帧并排
ax4 = fig.add_subplot(2, 3, 4)
concat = np.concatenate([sais_0[(3, 3)], sais_1[(3, 3)]], axis=1)
ax4.imshow(concat)
ax4.set_title(f"Center View (3,3): {FRAME_0} | {FRAME_1}", fontsize=13, fontweight="bold")
ax4.axvline(x=W, color="white", linewidth=2)
ax4.axis("off")

# 3e: 中心视角差异放大
ax5 = fig.add_subplot(2, 3, 5)
diff_center = np.abs(sais_0[(3, 3)].astype(np.float32) - sais_1[(3, 3)].astype(np.float32))
diff_vis = np.clip(diff_center * 3, 0, 255).astype(np.uint8)
ax5.imshow(diff_vis)
ax5.set_title("Center View Diff (x3 amplified)", fontsize=13, fontweight="bold")
ax5.axis("off")

# 3f: 同行不同列的差异变化
ax6 = fig.add_subplot(2, 3, 6)
row = 3
for v in range(1, ANG_RES + 1):
    diff = np.abs(sais_0[(row, v)].astype(np.float32) - sais_1[(row, v)].astype(np.float32))
    profile = diff.mean(axis=(0, 2))
    ax6.plot(profile, label=f"v={v}", alpha=0.7)
ax6.set_title(f"Row u={row}: Diff Profile by Column v", fontsize=13, fontweight="bold")
ax6.set_xlabel("Pixel x")
ax6.set_ylabel("Mean Difference")
ax6.legend()
ax6.grid(True, alpha=0.3)

fig.suptitle(f"{SCENE}/{SAMPLE}: SAI Array Change Analysis\n({FRAME_0} vs {FRAME_1})",
             fontsize=16, fontweight="bold", y=1.02)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "03_analysis.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 03_analysis.png")

# ============================================================
# 4. 子孔径阵列拼接对比
# ============================================================
print("\n[4/4] SAI array comparison...")

def make_sai_grid(sais, ang_res):
    h, w = sais[(1, 1)].shape[:2]
    grid = np.zeros((ang_res * h, ang_res * w, 3), dtype=np.uint8)
    for u in range(1, ang_res + 1):
        for v in range(1, ang_res + 1):
            grid[(u-1)*h:u*h, (v-1)*w:v*w] = sais[(u, v)]
    return grid

grid0 = make_sai_grid(sais_0, ANG_RES)
grid1 = make_sai_grid(sais_1, ANG_RES)
diff_grid = np.abs(grid0.astype(np.float32) - grid1.astype(np.float32))
diff_grid_vis = np.clip(diff_grid * 3, 0, 255).astype(np.uint8)

fig, axes = plt.subplots(1, 3, figsize=(30, 10))
axes[0].imshow(grid0)
axes[0].set_title(f"{FRAME_0} SAI Array", fontsize=14, fontweight="bold")
axes[0].axis("off")

axes[1].imshow(grid1)
axes[1].set_title(f"{FRAME_1} SAI Array", fontsize=14, fontweight="bold")
axes[1].axis("off")

axes[2].imshow(diff_grid_vis)
axes[2].set_title("Difference (x3 amplified)", fontsize=14, fontweight="bold")
axes[2].axis("off")

plt.suptitle(f"{SCENE}/{SAMPLE}: Full SAI Array Comparison", fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "04_sai_array_comparison.png"), dpi=100, bbox_inches="tight")
plt.close()
print("  Saved: 04_sai_array_comparison.png")

print(f"\nAll saved to: {OUTPUT_DIR}")
