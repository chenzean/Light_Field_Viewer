"""
日志工具模块 — 导出参数日志
"""

import os
from datetime import datetime


def write_export_log(filepath: str, params: dict):
    """将导出参数写入日志文件。

    参数:
        filepath: 日志文件路径
        params: 参数字典, 包含所有导出相关的设置
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("光场图像查看器 — 导出参数日志\n")
        f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")

        # 数据设置
        f.write("【数据设置】\n")
        f.write(f"  数据根目录:   {params.get('data_root', 'N/A')}\n")
        f.write(f"  导出目录:     {params.get('export_dir', 'N/A')}\n")
        f.write(f"  可视化模式:   {params.get('vis_mode', 'sai')}\n")
        f.write(f"  角度分辨率:   {params.get('angular_u', '?')} x {params.get('angular_v', '?')}\n")
        f.write(f"  场景:         {params.get('scene', 'N/A')}\n")
        f.write(f"  帧索引:       {params.get('frame_index', 'N/A')}\n")
        f.write(f"  角度坐标:     u={params.get('u', '?')}, v={params.get('v', '?')}\n")
        f.write(f"  选中方法:     {', '.join(params.get('methods', []))}\n")
        f.write(f"  残差图:       {params.get('residual_enabled', False)}\n\n")

        # 矩形框参数
        rects = params.get('rects', [])
        f.write(f"【矩形框参数】 (共 {len(rects)} 个)\n")
        for i, r in enumerate(rects):
            f.write(f"  框 {i + 1}: x={r['x']}, y={r['y']}, "
                    f"w={r['w']}, h={r['h']}, "
                    f"颜色=({r['color'][0]},{r['color'][1]},{r['color'][2]}), "
                    f"粗细={r['thickness']}\n")
        f.write("\n")

        # EPI 参数
        f.write("【EPI 参数】\n")
        f.write(f"  显示 EPI:     {params.get('epi_enabled', False)}\n")
        f.write(f"  方向:         {params.get('epi_orientation', 'N/A')}\n")
        f.write(f"  角度索引:     {params.get('epi_angular_idx', 'N/A')}\n")
        f.write(f"  空间位置:     {params.get('epi_spatial_pos', 'N/A')}\n")
        f.write(f"  裁剪范围:     {params.get('epi_crop_start', 'N/A')} ~ {params.get('epi_crop_end', 'N/A')}\n")
        f.write(f"  高度拉伸:     {params.get('epi_stretch', 'N/A')}x\n")
        f.write("\n" + "=" * 60 + "\n")
