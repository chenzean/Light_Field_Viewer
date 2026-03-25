"""
EPI 域帧插值概念验证

思路:
  1. 从两帧光场中提取所有 EPI
  2. 在 EPI 空间估计光流 (时间运动 = 水平平移)
  3. 用光流 warp 到 t=0.5 生成中间帧的 EPI
  4. 从插值后的 EPI 重建中间帧的 SAI
  5. 与 GT 中间帧对比

对比方案:
  A. SAI 域插帧: 直接在每个视角的 SAI 上做光流插帧
  B. EPI 域插帧: 在 EPI 上做光流插帧, 再重建 SAI

用法:
  python visualize_epi_interpolation.py
"""

import cv2
import numpy as np
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage.metrics import structural_similarity as ssim

# ============================================================
# 配置
# ============================================================
DATA_ROOT = r"D:\Light_Field_Video\4_Dataset\Dataset_PNG\test"
SCENE = "Scenes_0003"
SAMPLE = "sample_000001"
FRAME_0 = "frame_0003"   # t=0
FRAME_GT = "frame_0004"  # t=0.5 (GT)
FRAME_1 = "frame_0005"   # t=1
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


def warp_flow(img, flow):
    """用光流 warp 图像"""
    h, w = flow.shape[:2]
    flow_map = np.zeros_like(flow)
    flow_map[:, :, 0] = np.arange(w) + flow[:, :, 0]
    flow_map[:, :, 1] = np.arange(h)[:, None] + flow[:, :, 1]
    return cv2.remap(img, flow_map.astype(np.float32),
                     None, cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REFLECT)


def interpolate_sai_domain(sai0, sai1):
    """
    方案 A: SAI 域插帧
    直接在 SAI 图像上估计光流, warp 到 t=0.5
    """
    gray0 = cv2.cvtColor(sai0, cv2.COLOR_RGB2GRAY)
    gray1 = cv2.cvtColor(sai1, cv2.COLOR_RGB2GRAY)

    # 前向光流: 0 -> 1
    flow_01 = cv2.calcOpticalFlowFarneback(
        gray0, gray1, None,
        pyr_scale=0.5, levels=5, winsize=15,
        iterations=5, poly_n=7, poly_sigma=1.5, flags=0
    )
    # 后向光流: 1 -> 0
    flow_10 = cv2.calcOpticalFlowFarneback(
        gray1, gray0, None,
        pyr_scale=0.5, levels=5, winsize=15,
        iterations=5, poly_n=7, poly_sigma=1.5, flags=0
    )

    # warp 到 t=0.5
    warped_0 = warp_flow(sai0, flow_01 * 0.5)
    warped_1 = warp_flow(sai1, flow_10 * 0.5)

    # 混合
    result = ((warped_0.astype(np.float32) + warped_1.astype(np.float32)) / 2).clip(0, 255).astype(np.uint8)
    return result


def interpolate_epi_domain(lf0, lf1, ang_res):
    """
    方案 B: EPI 域插帧

    对每个 (u, y) 提取水平 EPI, 在 EPI 空间做光流插帧,
    再对每个 (v, x) 提取垂直 EPI 做光流插帧,
    最后取平均。

    水平 EPI: lf[u, :, y, :, :] -> [V, W, C]
      在这个 2D 图像上做光流, 时间运动表现为水平平移
    """
    U, V, H, W, C = lf0.shape
    lf_interp_h = np.zeros((U, V, H, W, C), dtype=np.float32)
    lf_interp_v = np.zeros((U, V, H, W, C), dtype=np.float32)

    # ---- 水平 EPI 插帧 ----
    for u in range(U):
        for y in range(H):
            epi0 = lf0[u, :, y, :, :]  # [V, W, C]
            epi1 = lf1[u, :, y, :, :]

            gray0 = cv2.cvtColor(epi0, cv2.COLOR_RGB2GRAY)
            gray1 = cv2.cvtColor(epi1, cv2.COLOR_RGB2GRAY)

            # EPI 很窄 (5xW), 用小窗口
            flow_01 = cv2.calcOpticalFlowFarneback(
                gray0, gray1, None,
                pyr_scale=0.5, levels=3, winsize=5,
                iterations=3, poly_n=5, poly_sigma=1.1, flags=0
            )
            flow_10 = cv2.calcOpticalFlowFarneback(
                gray1, gray0, None,
                pyr_scale=0.5, levels=3, winsize=5,
                iterations=3, poly_n=5, poly_sigma=1.1, flags=0
            )

            w0 = warp_flow(epi0, flow_01 * 0.5)
            w1 = warp_flow(epi1, flow_10 * 0.5)
            epi_mid = (w0.astype(np.float32) + w1.astype(np.float32)) / 2

            lf_interp_h[u, :, y, :, :] = epi_mid

        if (u + 1) % 1 == 0:
            print(f"    H-EPI: u={u+1}/{U} done")

    # ---- 垂直 EPI 插帧 ----
    for v in range(V):
        for x in range(W):
            epi0 = lf0[:, v, :, x, :]  # [U, H, C]
            epi1 = lf1[:, v, :, x, :]

            gray0 = cv2.cvtColor(epi0, cv2.COLOR_RGB2GRAY)
            gray1 = cv2.cvtColor(epi1, cv2.COLOR_RGB2GRAY)

            flow_01 = cv2.calcOpticalFlowFarneback(
                gray0, gray1, None,
                pyr_scale=0.5, levels=3, winsize=5,
                iterations=3, poly_n=5, poly_sigma=1.1, flags=0
            )
            flow_10 = cv2.calcOpticalFlowFarneback(
                gray1, gray0, None,
                pyr_scale=0.5, levels=3, winsize=5,
                iterations=3, poly_n=5, poly_sigma=1.1, flags=0
            )

            w0 = warp_flow(epi0, flow_01 * 0.5)
            w1 = warp_flow(epi1, flow_10 * 0.5)
            epi_mid = (w0.astype(np.float32) + w1.astype(np.float32)) / 2

            lf_interp_v[:, v, :, x, :] = epi_mid

        if (v + 1) % 1 == 0:
            print(f"    V-EPI: v={v+1}/{V} done")

    # 水平和垂直 EPI 结果取平均
    lf_interp = ((lf_interp_h + lf_interp_v) / 2).clip(0, 255).astype(np.uint8)
    return lf_interp


# ============================================================
# 加载数据
# ============================================================
print(f"Loading {SCENE}/{SAMPLE}")
lf0 = load_light_field(os.path.join(DATA_ROOT, SCENE, SAMPLE, FRAME_0), ANG_RES)
lf_gt = load_light_field(os.path.join(DATA_ROOT, SCENE, SAMPLE, FRAME_GT), ANG_RES)
lf1 = load_light_field(os.path.join(DATA_ROOT, SCENE, SAMPLE, FRAME_1), ANG_RES)

U, V, H, W, C = lf0.shape
print(f"  LF: [{U},{V},{H},{W},{C}]")

# ============================================================
# 方案 A: SAI 域插帧 (逐视角)
# ============================================================
print("\n[A] SAI-domain interpolation...")
lf_sai_interp = np.zeros_like(lf0)
for u in range(U):
    for v in range(V):
        lf_sai_interp[u, v] = interpolate_sai_domain(lf0[u, v], lf1[u, v])
    print(f"  u={u+1}/{U} done")

# ============================================================
# 方案 B: EPI 域插帧
# ============================================================
print("\n[B] EPI-domain interpolation...")
lf_epi_interp = interpolate_epi_domain(lf0, lf1, ANG_RES)

# ============================================================
# 方案 C: 简单平均 (baseline)
# ============================================================
print("\n[C] Simple average baseline...")
lf_avg = ((lf0.astype(np.float32) + lf1.astype(np.float32)) / 2).clip(0, 255).astype(np.uint8)

# ============================================================
# 计算指标
# ============================================================
print("\n===== Metrics =====")
methods = {
    "Average": lf_avg,
    "SAI-Flow": lf_sai_interp,
    "EPI-Flow": lf_epi_interp,
}

results = {}
for name, lf_pred in methods.items():
    psnr_list = []
    ssim_list = []
    for u in range(U):
        for v in range(V):
            p = psnr(lf_gt[u, v], lf_pred[u, v])
            s = ssim(lf_gt[u, v], lf_pred[u, v], channel_axis=2)
            psnr_list.append(p)
            ssim_list.append(s)
    avg_psnr = np.mean(psnr_list)
    avg_ssim = np.mean(ssim_list)
    results[name] = (avg_psnr, avg_ssim)
    print(f"  {name:12s}  PSNR: {avg_psnr:.2f} dB  SSIM: {avg_ssim:.4f}")

# ============================================================
# 可视化对比
# ============================================================
print("\nGenerating comparison images...")

# 选中心视角 (3,3)
u_c, v_c = 2, 2
gt = lf_gt[u_c, v_c]
pred_avg = lf_avg[u_c, v_c]
pred_sai = lf_sai_interp[u_c, v_c]
pred_epi = lf_epi_interp[u_c, v_c]

fig, axes = plt.subplots(2, 4, figsize=(24, 12))

# 第一行: 结果图
titles = [f"GT ({FRAME_GT})", "Average", "SAI-Flow", "EPI-Flow"]
imgs = [gt, pred_avg, pred_sai, pred_epi]
for i, (title, img) in enumerate(zip(titles, imgs)):
    axes[0, i].imshow(img)
    if i > 0:
        p, s = results[list(methods.keys())[i-1]]
        axes[0, i].set_title(f"{title}\nPSNR={p:.2f} SSIM={s:.4f}", fontsize=12, fontweight="bold")
    else:
        axes[0, i].set_title(title, fontsize=12, fontweight="bold")
    axes[0, i].axis("off")

# 第二行: 差异图 (x5)
axes[1, 0].imshow(gt)
axes[1, 0].set_title("GT", fontsize=12)
axes[1, 0].axis("off")

for i, (name, pred) in enumerate([(n, imgs[j+1]) for j, n in enumerate(titles[1:])]):
    diff = np.abs(gt.astype(np.float32) - pred.astype(np.float32))
    diff_vis = np.clip(diff * 5, 0, 255).astype(np.uint8)
    axes[1, i+1].imshow(diff_vis)
    axes[1, i+1].set_title(f"{name} Error (x5)", fontsize=12)
    axes[1, i+1].axis("off")

plt.suptitle(f"Frame Interpolation Comparison: SAI vs EPI Domain\n{SCENE}/{SAMPLE} center view ({u_c+1},{v_c+1})",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "15_interpolation_comparison.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 15_interpolation_comparison.png")

# ============================================================
# EPI 插帧前后的 EPI 对比
# ============================================================
print("\nGenerating EPI comparison...")
from scipy.ndimage import zoom as scipy_zoom

def stretch_epi(epi, factor=10):
    return scipy_zoom(epi, (factor, 1, 1), order=1).clip(0, 255).astype(np.uint8)

y_fix = 256
u_fix = 2
STRETCH = 10

epi_0 = lf0[u_fix, :, y_fix, :, :]
epi_gt = lf_gt[u_fix, :, y_fix, :, :]
epi_1 = lf1[u_fix, :, y_fix, :, :]
epi_sai = lf_sai_interp[u_fix, :, y_fix, :, :]
epi_epi = lf_epi_interp[u_fix, :, y_fix, :, :]

fig, axes = plt.subplots(5, 1, figsize=(20, 12))

labels = [f"{FRAME_0} (input)", f"GT ({FRAME_GT})", f"{FRAME_1} (input)",
          "SAI-Flow interp", "EPI-Flow interp"]
epis = [epi_0, epi_gt, epi_1, epi_sai, epi_epi]

for i, (label, epi) in enumerate(zip(labels, epis)):
    epi_s = stretch_epi(epi, STRETCH)
    axes[i].imshow(epi_s)
    axes[i].set_ylabel(label, fontsize=11, fontweight="bold")
    axes[i].set_xticks([])
    axes[i].set_yticks([0, 25, 49])
    axes[i].set_yticklabels(["v=1", "v=3", "v=5"], fontsize=8)

plt.suptitle(f"EPI Comparison at y={y_fix}, u={u_fix+1}\nInput frames vs GT vs Interpolated",
             fontsize=16, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "16_epi_interpolation_compare.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  Saved: 16_epi_interpolation_compare.png")

# ============================================================
# 指标汇总表
# ============================================================
print("\n" + "=" * 60)
print(f"{'Method':12s}  {'PSNR (dB)':>10s}  {'SSIM':>8s}")
print("-" * 60)
for name, (p, s) in results.items():
    print(f"{name:12s}  {p:10.2f}  {s:8.4f}")
print("=" * 60)
print(f"\nAll saved to: {OUTPUT_DIR}")
