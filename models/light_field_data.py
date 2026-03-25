"""
光场数据加载模块 — 目录扫描、SAI 加载、5D 光场数组构建

支持三种目录结构:
  1. Method/Scene/frame_XXXX/{u}_{v}.png    (光场视频, 带帧)
  2. Method/Scene/sample_XXXXXX/{u}_{v}.png (光场视频, 带样本)
  3. Method/Scene/{u}_{v}.png               (光场图像, 无帧级目录)

不同方法可以有不同的子目录命名 (frame_ vs sample_),
按排序后的位置索引对应 (第 1 个对第 1 个, 第 2 个对第 2 个...)。
"""

import os
import re
import numpy as np
from PIL import Image

from config import SUPPORTED_IMAGE_EXTENSIONS


class LightFieldData:
    """光场数据管理器。"""

    def __init__(self):
        self.root_dir = None
        # {method: {scene: [(display_name, dir_path), ...]}}
        # 按位置索引对应, 不依赖子目录名
        self.structure = {}
        self.methods = []
        self.scenes = []
        # 统一的帧显示列表 (按位置索引): ["帧1", "帧2", ...]
        # 或光场图像时为 ["(无帧)"]
        self._frame_display = {}  # {scene: [display_name, ...]}

    def scan_root(self, root_dir: str) -> dict:
        """扫描根目录, 自动检测目录结构。"""
        self.root_dir = root_dir
        self.structure = {}
        self.methods = []
        self.scenes = set()
        self._frame_display = {}

        if not os.path.isdir(root_dir):
            return {}

        for method_name in sorted(os.listdir(root_dir)):
            method_path = os.path.join(root_dir, method_name)
            if not os.path.isdir(method_path):
                continue
            if method_name.startswith('.'):
                continue

            method_dict = {}

            for scene_name in sorted(os.listdir(method_path)):
                scene_path = os.path.join(method_path, scene_name)
                if not os.path.isdir(scene_path):
                    continue

                # 情况 2: 场景文件夹下直接是视角图像 (光场图像有场景, 无帧)
                #   Method/Scene/{u}_{v}.png
                if self._has_sai_images(scene_path):
                    method_dict[scene_name] = [("(无帧)", scene_path)]
                    self.scenes.add(scene_name)
                    continue

                # 情况 3: 场景文件夹下有帧/样本子目录 (光场视频)
                #   Method/Scene/frame_XXXX/{u}_{v}.png
                sub_dirs = sorted([
                    d for d in os.listdir(scene_path)
                    if os.path.isdir(os.path.join(scene_path, d))
                ])

                frame_list = []
                for sub_name in sub_dirs:
                    sub_path = os.path.join(scene_path, sub_name)
                    if self._has_sai_images(sub_path):
                        frame_list.append((sub_name, sub_path))

                if frame_list:
                    method_dict[scene_name] = frame_list
                    self.scenes.add(scene_name)

            if method_dict:
                self.structure[method_name] = method_dict
                self.methods.append(method_name)

        self.scenes = sorted(self.scenes)

        # 构建统一帧显示列表 (取最大帧数的方法作为参考)
        for scene in self.scenes:
            max_count = 0
            ref_method = None
            for m in self.methods:
                if scene in self.structure.get(m, {}):
                    count = len(self.structure[m][scene])
                    if count > max_count:
                        max_count = count
                        ref_method = m
            if ref_method and scene in self.structure.get(ref_method, {}):
                names = [item[0] for item in self.structure[ref_method][scene]]
                self._frame_display[scene] = names
            else:
                self._frame_display[scene] = []

        return self.structure

    def _has_sai_images(self, dir_path: str) -> bool:
        """检查目录中是否包含 {u}_{v}.ext 格式的图像文件。"""
        pattern = re.compile(r'^\d+_\d+\.\w+$')
        try:
            for fname in os.listdir(dir_path):
                if pattern.match(fname):
                    _, ext = os.path.splitext(fname)
                    if ext.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                        return True
        except (PermissionError, OSError):
            pass
        return False

    def get_methods(self) -> list:
        return self.methods

    def get_scenes(self) -> list:
        return self.scenes

    def get_frame_display_list(self, scene: str) -> list:
        """返回场景的统一帧显示列表 (用于 UI 下拉框)。"""
        return self._frame_display.get(scene, [])

    def get_frame_count(self, scene: str) -> int:
        """返回场景的帧数。"""
        return len(self._frame_display.get(scene, []))

    def _resolve_dir(self, method: str, scene: str, frame_index: int) -> str:
        """根据方法、场景和帧位置索引, 解析实际的图像目录路径。

        按位置索引匹配 — 不同方法的子目录名可以不同。

        参数:
            method: 方法名
            scene: 场景名
            frame_index: 帧的位置索引 (0-based)

        返回:
            图像目录路径, 或 None
        """
        try:
            frame_list = self.structure[method][scene]
        except KeyError:
            return None

        if 0 <= frame_index < len(frame_list):
            return frame_list[frame_index][1]  # (display_name, dir_path)
        return None

    def detect_angular_resolution(self) -> tuple:
        """从文件名推断角度分辨率。"""
        dir_path = self._find_any_image_dir()
        if not dir_path:
            return (5, 5)

        u_max, v_max = 0, 0
        pattern = re.compile(r'^(\d+)_(\d+)\.\w+$')
        for fname in os.listdir(dir_path):
            m = pattern.match(fname)
            if m:
                u, v = int(m.group(1)), int(m.group(2))
                u_max = max(u_max, u)
                v_max = max(v_max, v)
        return (u_max, v_max) if u_max > 0 else (5, 5)

    def _find_any_image_dir(self) -> str:
        """找到任意一个有效的图像目录。"""
        for m in self.methods:
            for s in self.scenes:
                d = self._resolve_dir(m, s, 0)
                if d:
                    return d
        return None

    def load_sai(self, method: str, scene: str, frame_index: int,
                 u: int, v: int) -> np.ndarray:
        """加载单张子孔径图像。

        参数:
            method: 方法名
            scene: 场景名
            frame_index: 帧位置索引 (0-based)
            u, v: 角度坐标 (从 1 开始)

        返回:
            RGB numpy 数组, shape=(H, W, 3), dtype=uint8
        """
        dir_path = self._resolve_dir(method, scene, frame_index)
        if not dir_path:
            return None

        for ext in SUPPORTED_IMAGE_EXTENSIONS:
            fpath = os.path.join(dir_path, f"{u}_{v}{ext}")
            if os.path.exists(fpath):
                img = Image.open(fpath).convert('RGB')
                return np.array(img)
        return None

    def load_light_field(self, method: str, scene: str, frame_index: int,
                         u_max: int, v_max: int) -> np.ndarray:
        """加载完整光场为 5D 数组。

        参数:
            method, scene: 定位
            frame_index: 帧位置索引 (0-based)
            u_max, v_max: 角度分辨率

        返回:
            5D numpy 数组, shape=[U, V, H, W, C], dtype=uint8
        """
        sample = self.load_sai(method, scene, frame_index, 1, 1)
        if sample is None:
            return None

        h, w, c = sample.shape
        lf = np.zeros((u_max, v_max, h, w, c), dtype=np.uint8)

        for u in range(1, u_max + 1):
            for v in range(1, v_max + 1):
                sai = self.load_sai(method, scene, frame_index, u, v)
                if sai is not None:
                    lf[u - 1, v - 1] = sai

        return lf
