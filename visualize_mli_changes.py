"""
微透镜图像 (MLI) 格式下的两帧变化可视化

将 SAI (Sub-Aperture Image) 格式转换为 MLI (Micro-Lens Image) 格式:
  SAI: [U, V, H, W, C] -> 每个 (u,v) 是一张完整的子孔径图像
  MLI: [H*U, W*V, C]   -> 每个空间像素位置包含 UxV 的角度信息

MLI 中相邻的 5x5 像素块 (macro-pixel) 对应同一空间位置的不同视角,
能直观观察到视差结构和运动模式。

用法:
  python visualize_mli_changes.py
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
FRAME_0 = "frame_0003"
FRAME_1 = "frame_0005"
ANG_RES = 5
OUTPUT_DIR = r"D:\Light_Field_Video\Light_Field_Viewer\vis_output"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_light_field(frame_dir, ang_res):
    """加载一帧的所有 SAI, 返回 [U, V, H, W, C]"""
    first = cv2.imread(os.path.join(frame_dir, "1_1.png"))
    H, W, C = first.shape
    lf = np.zeros((ang_res, ang_res, H, W, C), dtype=np.uint8)
    for u in range(1, ang_res + 1):
        for v in range(1, ang_res + 1):
            img = cv2.imread(os.path.join(frame_dir, f"{u}_{v}.png"))
            lf[u-1, v-1] = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return lf


def sai_to_mli(lf):
    """
    SAI -> MLI 转换

    输入: lf [U, V, H, W, C]
    输出: mli [H*U, W*V, C]

    空间位置 (y, x) 的 macro-pixel 在 MLI 中的位置:
      mli[y*U + u, x*V + v, :] = lf[u, v, y, x, :]

    即: 每个空间像素被展开为 UxV 的角度块
    """
    U, V, H, W, C = lf.shape
    # einops 等价: rearrange(lf, 'U V H W C -> (H U) (W V) C')
    mli = lf.transpose(2, 0, 3, 1, 4).reshape(H * U, W * V, C)
    return mli


def compute_flow_hsv(gray0, gray1):
    """光流 -> HSV 色轮可视化"""
    flow = cv2.calcOpticalFlowFarneback(
        gray0, gray1, None,
        pyr_scale=0.5, levels=5, winsize=15,
        iterations=5, poly_n=7, poly_sigma=1.5, flags=0
    )
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    hsv = np.zeros((*gray0.shape, 3), dtype=np.uint8)
    hsv[..., 0] = ang * 180 / np.pi / 2
    hsv[..., 1] = 255
    hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB), flow, mag


# ============================================================
# 加载数据
# ============================================================
frame0_dir = os.path.join(DATA_ROOT, SCENE, SAMPLE, FRAME_0)
frame1_dir = os.path.join(DATA_ROOT, SCENE, SAMPLE, FRAME_1)

print(f"Loading {SCENE}/{SAMPLE}: {FRAME_0} vs {FRAME_1}")

lf0 = load_light_field(frame0_dir, ANG_RES)
lf1 = load_light_field(frame1_dir, ANG_RES)

U, V, H, W, C = lf0.shape
print(f"  LF shape: [{U}, {V}, {H}, {W}, {C}]")

# ============================================================
# 1. SAI -> MLI 转换
# ============================================================
print("\n[1/5] SAI -> MLI conversion...")

mli0 = sai_to_mli(lf0)
mli1 = sai_to_mli(lf1)
print(f"  MLI shape: {mli0.shape} = [{H}*{U}, {W}*{V}, {C}] = [{H*U}, {W*V}, {C}]")

# 保存完整 MLI
cv2.imwrite(os.path.join(OUTPUT_DIR, "05_mli_frame0.png"),
            cv2.cvtColor(mli0, cv2.COLOR_RGB2BGR))
cv2.imwrite(os.path.join(OUTPUT_DIR, "05_mli_frame1.png"),
            cv2.cvtColor(mli1, cv2.COLOR_RGB2BGR))
print("  Saved: 05_mli_frame0.png, 05_mli_frame1.png")

# ============================================================
# 2. MLI 差异图
# ============================================================
print("\n[2/5] MLI difference...")

diff_mli = np.abs(mli0.astype(np.float32) - mli1.astype(np.float32))
diff_mli_vis = np.clip(diff_mli * 3, 0, 255).astype(np.uint8)

cv2.imwrite(os.path.join(OUTPUT_DIR, "06_mli_diff_x3.png"),
            cv2.cvtColor(diff_mli_vis, cv2.COLOR_RGB2BGR))
print("  Saved: 06_mli_diff_x3.png")

# ============================================================
# 3. MLI 局部放大 (展示 macro-pixel 结构)
# ============================================================
print("\n[3/5] MLI macro-pixel zoom...")

# 选一个有运动的区域 (空间坐标)
cy, cx = H // 2, W // 2  # 中心空间位置
crop_size = 16  # 取 16x16 个 macro-pixel (即 80x80 像素)

y0 = (cy - crop_size // 2) * U
y1 = (cy + crop_size // 2) * U
x0 = (cx - crop_size // 2) * V
x1 = (cx + crop_size // 2) * V

crop0 = mli0[y0:y1, x0:x1]
crop1 = mli1[y0:y1, x0:x1]
crop_diff = diff_mli_vis[y0:y1, x0:x1]

fig, axes = plt.subplots(1, 3, figsize=(24, 8))

axes[0].imshow(crop0)
axes[0].set_title(f"{FRAME_0} MLI crop\n(space [{cy-crop_size//2}:{cy+crop_size//2}])",
                  fontsize=13, fontweight="bold")
axes[0].axis("off")
# 画 macro-pixel 网格线
for i in range(0, crop0.shape[0], U):
    axes[0].axhline(y=i, color="white", linewidth=0.3, alpha=0.5)
for j in range(0, crop0.shape[1], V):
    axes[0].axvline(x=j, color="white", linewidth=0.3, alpha=0.5)

axes[1].imshow(crop1)
axes[1].set_title(f"{FRAME_1} MLI crop", fontsize=13, fontweight="bold")
axes[1].axis("off")
for i in range(0, crop1.shape[0], U):
    axes[1].axhline(y=i, color="white", linewidth=0.3, alpha=0.5)
for j in range(0, crop1.shape[1], V):
    axes[1].axvline(x=j, color="white", linewidth=0.3, alpha=0.5)

axes[2].imshow(crop_diff)
axes[2].set_title("Difference (x3)", fontsize=13, fontweight="bold")
axes[2].axis("off")
for i in range(0, crop_diff.shape[0], U):
    axes[2].axhline(y=i, color="white", linewidth=0.3, alpha=0.5)
for j in range(0, crop_diff.shape[1], V):
    axes[2].axvline(x=j, color="white", linewidth=0.3, alpha=0.5)

plt.suptitle(f"MLI Macro-Pixel Zoom ({crop_size}x{crop_size} spatial pixels)",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "07_mli_zoom.png"), dpi=200, bbox_inches="tight")
plt.close()
print("  Saved: 07_mli_zoom.png")

# ============================================================
# 4. MLI 光流
# ============================================================
print("\n[4/5] MLI optical flow...")

gray0_mli = cv2.cvtColor(mli0, cv2.COLOR_RGB2GRAY)
gray1_mli = cv2.cvtColor(mli1, cv2.COLOR_RGB2GRAY)

flow_rgb, flow, mag = compute_flow_hsv(gray0_mli, gray1_mli)

cv2.imwrite(os.path.join(OUTPUT_DIR, "08_mli_flow.png"),
            cv2.cvtColor(flow_rgb, cv2.COLOR_RGB2BGR))
print("  Saved: 08_mli_flow.png")

# 光流局部放大
flow_crop = flow_rgb[y0:y1, x0:x1]
fig, axes = plt.subplots(1, 2, figsize=(16, 8))
axes[0].imshow(crop0)
axes[0].set_title(f"{FRAME_0} MLI crop", fontsize=13, fontweight="bold")
axes[0].axis("off")
axes[1].imshow(flow_crop)
axes[1].set_title("Optical Flow on MLI", fontsize=13, fontweight="bold")
axes[1].axis("off")
# 网格线
for ax in axes:
    for i in range(0, crop0.shape[0], U):
        ax.axhline(y=i, color="white", linewidth=0.3, alpha=0.5)
    for j in range(0, crop0.shape[1], V):
        ax.axvline(x=j, color="white", linewidth=0.3, alpha=0.5)

plt.suptitle("MLI Optical Flow Zoom", fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "09_mli_flow_zoom.png"), dpi=200, bbox_inches="tight")
plt.close()
print("  Saved: 09_mli_flow_zoom.png")

# ============================================================
# 5. Macro-pixel 内部结构分析 (单个 macro-pixel 放大)
# ============================================================
print("\n[5/5] Single macro-pixel analysis...")

# 选几个有代表性的空间位置
positions = [
    (H//4, W//4, "upper-left"),
    (H//2, W//2, "center"),
    (3*H//4, 3*W//4, "lower-right"),
    (H//3, W//2, "motion-area"),
]

fig, axes = plt.subplots(len(positions), 4, figsize=(16, 4*len(positions)))

for row, (sy, sx, label) in enumerate(positions):
    # 提取单个 macro-pixel (5x5)
    mp0 = lf0[:, :, sy, sx, :]  # [U, V, C] = [5, 5, 3]
    mp1 = lf1[:, :, sy, sx, :]
    mp_diff = np.abs(mp0.astype(np.float32) - mp1.astype(np.float32))
    mp_diff_vis = np.clip(mp_diff * 5, 0, 255).astype(np.uint8)

    axes[row, 0].imshow(mp0)
    axes[row, 0].set_title(f"{FRAME_0}\n({sy},{sx}) {label}", fontsize=10)
    axes[row, 0].set_xticks(range(V))
    axes[row, 0].set_yticks(range(U))

    axes[row, 1].imshow(mp1)
    axes[row, 1].set_title(f"{FRAME_1}", fontsize=10)
    axes[row, 1].set_xticks(range(V))
    axes[row, 1].set_yticks(range(U))

    axes[row, 2].imshow(mp_diff_vis)
    axes[row, 2].set_title("Diff (x5)", fontsize=10)
    axes[row, 2].set_xticks(range(V))
    axes[row, 2].set_yticks(range(U))

    # 差异柱状图
    diff_per_view = mp_diff.mean(axis=2).ravel()
    colors = plt.cm.hot(diff_per_view / max(diff_per_view.max(), 1))
    axes[row, 3].bar(range(U*V), diff_per_view, color=colors)
    axes[row, 3].set_title("Diff per view", fontsize=10)
    axes[row, 3].set_xlabel("view index (u*5+v)")
    axes[row, 3].set_ylabel("mean diff")

plt.suptitle("Single Macro-Pixel Analysis (5x5 angular samples)",
             fontsize=14, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "10_macro_pixel_analysis.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 10_macro_pixel_analysis.png")

print(f"\nAll saved to: {OUTPUT_DIR}")
