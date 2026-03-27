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
        # SAI 文件名映射缓存: {dir_path: {(u,v): filepath}}
        self._sai_name_map = {}

    def scan_root(self, root_dir: str) -> dict:
        """扫描根目录, 自动检测目录结构。"""
        self.root_dir = root_dir
        self.structure = {}
        self.methods = []
        self.scenes = set()
        self._frame_display = {}
        self._sai_name_map = {}

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
            elif self._has_mli_files(method_path):
                # 纯 MLI 数据集: 无 SAI 子目录, 但有图像文件
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

    def _has_mli_files(self, method_path: str) -> bool:
        """检查方法目录是否包含 MLI 图像文件 (图像模式或视频模式)。"""
        sai_pattern = re.compile(r'^\d+_\d+\.\w+$')
        try:
            for fname in os.listdir(method_path):
                fpath = os.path.join(method_path, fname)
                # 图像模式: Method/Scene.ext
                if os.path.isfile(fpath):
                    _, ext = os.path.splitext(fname)
                    if ext.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                        return True
                # 视频模式: Method/Scene/frame.ext
                elif os.path.isdir(fpath):
                    for sub_fname in os.listdir(fpath):
                        if sai_pattern.match(sub_fname):
                            continue
                        _, ext = os.path.splitext(sub_fname)
                        if ext.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                            if os.path.isfile(os.path.join(fpath, sub_fname)):
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

    def get_mli_scenes(self, mode: str = 'image') -> list:
        """扫描根目录, 检测 MLI 场景。

        光场图像模式: 场景 = Method 目录下的图像文件名 (不含扩展名)
        光场视频模式: 场景 = Method 目录下包含图像文件的子目录名
        """
        if not self.root_dir:
            return []
        mli_scenes = set()
        try:
            all_methods = [d for d in sorted(os.listdir(self.root_dir))
                           if os.path.isdir(os.path.join(self.root_dir, d))
                           and not d.startswith('.')]
        except (PermissionError, OSError):
            return []
        for method_name in all_methods:
            method_path = os.path.join(self.root_dir, method_name)
            if not os.path.isdir(method_path):
                continue

            if mode == 'image':
                # Method/Scene.ext
                for fname in os.listdir(method_path):
                    name, ext = os.path.splitext(fname)
                    if ext.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                        fpath = os.path.join(method_path, fname)
                        if os.path.isfile(fpath):
                            mli_scenes.add(name)
            else:
                # Method/Scene/ 下有图像文件
                for dname in os.listdir(method_path):
                    dpath = os.path.join(method_path, dname)
                    if not os.path.isdir(dpath):
                        continue
                    # 检查目录中是否有图像文件 (排除 SAI 格式)
                    sai_pattern = re.compile(r'^\d+_\d+\.\w+$')
                    for fname in os.listdir(dpath):
                        if sai_pattern.match(fname):
                            continue
                        _, ext = os.path.splitext(fname)
                        if ext.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                            if os.path.isfile(os.path.join(dpath, fname)):
                                mli_scenes.add(dname)
                                break

        return sorted(mli_scenes)

    def get_mli_frame_list(self, method: str, scene: str) -> list:
        """获取 MLI 视频模式下的帧文件名列表 (用于 UI 显示)。"""
        if not self.root_dir:
            return []
        scene_path = os.path.join(self.root_dir, method, scene)
        if not os.path.isdir(scene_path):
            return []
        sai_pattern = re.compile(r'^\d+_\d+\.\w+$')
        frames = []
        try:
            for fname in sorted(os.listdir(scene_path)):
                if sai_pattern.match(fname):
                    continue
                _, ext = os.path.splitext(fname)
                if ext.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                    if os.path.isfile(os.path.join(scene_path, fname)):
                        frames.append(os.path.splitext(fname)[0])
        except (PermissionError, OSError):
            pass
        return frames

    def _find_any_image_dir(self) -> str:
        """找到任意一个有效的图像目录。"""
        for m in self.methods:
            for s in self.scenes:
                d = self._resolve_dir(m, s, 0)
                if d:
                    return d
        return None

    def _build_sai_filename_map(self, dir_path: str) -> dict:
        """扫描目录, 建立 {(u,v): filepath} 映射, 支持零填充文件名。"""
        if dir_path in self._sai_name_map:
            return self._sai_name_map[dir_path]

        name_map = {}
        pattern = re.compile(r'^(\d+)_(\d+)\.(\w+)$')
        try:
            for fname in os.listdir(dir_path):
                m = pattern.match(fname)
                if m:
                    ext = '.' + m.group(3)
                    if ext.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                        u_val, v_val = int(m.group(1)), int(m.group(2))
                        name_map[(u_val, v_val)] = os.path.join(dir_path, fname)
        except (PermissionError, OSError):
            pass

        self._sai_name_map[dir_path] = name_map
        return name_map

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

        name_map = self._build_sai_filename_map(dir_path)
        fpath = name_map.get((u, v))
        if fpath and os.path.exists(fpath):
            img = Image.open(fpath).convert('RGB')
            return np.array(img)
        return None

    def load_mli(self, method: str, scene: str,
                 frame_index: int = 0, mode: str = 'image') -> np.ndarray:
        """加载微透镜图像 (Micro-Lens Image)。

        光场图像模式: {root}/{method}/{scene}.{ext}
        光场视频模式: {root}/{method}/{scene}/{帧文件名}.{ext}
                     帧文件按排序后位置索引匹配

        参数:
            method: 方法名
            scene: 场景名
            frame_index: 帧位置索引 (0-based, 仅视频模式)
            mode: 'image' 或 'video'

        返回:
            RGB numpy 数组, shape=(H, W, 3), dtype=uint8, 或 None
        """
        if not self.root_dir:
            return None

        method_path = os.path.join(self.root_dir, method)

        if mode == 'image':
            # 光场图像: Method/Scene.ext
            for ext in SUPPORTED_IMAGE_EXTENSIONS:
                fpath = os.path.join(method_path, f"{scene}{ext}")
                if os.path.exists(fpath):
                    img = Image.open(fpath).convert('RGB')
                    return np.array(img)
        else:
            # 光场视频: Method/Scene/帧文件.ext
            scene_path = os.path.join(method_path, scene)
            if not os.path.isdir(scene_path):
                return None
            # 扫描场景目录下的图像文件 (排除 SAI 格式的 {u}_{v})
            sai_pattern = re.compile(r'^\d+_\d+\.\w+$')
            frame_files = []
            try:
                for fname in sorted(os.listdir(scene_path)):
                    if sai_pattern.match(fname):
                        continue
                    _, ext = os.path.splitext(fname)
                    if ext.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                        fpath = os.path.join(scene_path, fname)
                        if os.path.isfile(fpath):
                            frame_files.append(fpath)
            except (PermissionError, OSError):
                return None

            if 0 <= frame_index < len(frame_files):
                img = Image.open(frame_files[frame_index]).convert('RGB')
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
