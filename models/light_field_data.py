"""
光场数据加载模块 — 目录扫描、SAI 加载、5D 光场数组构建

支持三种目录结构:
  1. Method/Scene/frame_XXXX/{u}_{v}.png    (光场视频, 带帧)
  2. Method/Scene/sample_XXXXXX/{u}_{v}.png (光场视频, 带样本)
  3. Method/Scene/{u}_{v}.png               (光场图像, 无帧级目录)

默认按帧名或末尾数字 ID 对齐，frame_0001 与 sample_000001 可对应。
显式设置 frame_alignment='index' 可使用排序后的位置对应。
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
        self.frame_alignment = 'name'
        # {method: {scene: [(display_name, dir_path), ...]}}
        self.structure = {}
        self.methods = []
        self.scenes = []
        # 名称对齐使用所有方法的帧集合；光场图像为 ["(无帧)"]。
        self._frame_display = {}  # {scene: [display_name, ...]}
        # SAI 文件名映射缓存: {dir_path: {(u,v): filepath}}
        self._sai_name_map = {}
        self._mli_frames = {}  # {(method, scene): [(frame_name, filepath), ...]}

    def scan_root(self, root_dir: str) -> dict:
        """扫描根目录, 自动检测目录结构。"""
        self.root_dir = root_dir
        self.structure = {}
        self.methods = []
        self.scenes = set()
        self._frame_display = {}
        self._sai_name_map = {}
        self._mli_frames = {}

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

        # 按帧 ID 合并所有方法，缺帧保持空缺，不能让后续帧前移。
        for scene in self.scenes:
            frame_lists = [self.structure.get(m, {}).get(scene, []) for m in self.methods]
            self._frame_display[scene] = self._merge_frame_names(frame_lists)

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

    def set_frame_alignment(self, alignment: str):
        """选择按名称/末尾数字 ID 对齐，或显式使用旧的按位置模式。"""
        if alignment not in ('name', 'index'):
            raise ValueError("帧对齐方式必须是 'name' 或 'index'")
        self.frame_alignment = alignment

    @staticmethod
    def _frame_key(name: str) -> tuple:
        match = re.search(r'(\d+)$', name)
        return (0, int(match.group(1))) if match else (1, name)

    @classmethod
    def _merge_frame_names(cls, frame_lists: list) -> list:
        # 优先保留最长序列的显示名称，按数值 ID 排序并补入其他方法的帧。
        names = {}
        for frames in sorted(frame_lists, key=len, reverse=True):
            for name, _ in frames:
                names.setdefault(cls._frame_key(name), name)
        return [names[key] for key in sorted(names)]

    def _select_frame(self, frames: list, display_names: list, frame_index: int):
        if self.frame_alignment == 'index':
            return frames[frame_index][1] if 0 <= frame_index < len(frames) else None
        if not 0 <= frame_index < len(display_names):
            return None
        key = self._frame_key(display_names[frame_index])
        matches = [path for name, path in frames if self._frame_key(name) == key]
        if len(matches) > 1:
            raise ValueError(f"帧 ID 不唯一: {display_names[frame_index]}，请检查 {matches}")
        return matches[0] if matches else None

    def get_frame_display_list(self, scene: str) -> list:
        """返回场景的统一帧显示列表 (用于 UI 下拉框)。"""
        if self.frame_alignment == 'index':
            frame_lists = [self.structure.get(m, {}).get(scene, []) for m in self.methods]
            return [name for name, _ in max(frame_lists, key=len, default=[])]
        return self._frame_display.get(scene, [])

    def _resolve_dir(self, method: str, scene: str, frame_index: int) -> str:
        """根据方法、场景和统一帧索引, 解析实际的图像目录路径。

        参数:
            method: 方法名
            scene: 场景名
            frame_index: 统一帧显示列表的索引 (0-based)

        返回:
            图像目录路径, 或 None
        """
        try:
            frame_list = self.structure[method][scene]
        except KeyError:
            return None

        return self._select_frame(frame_list, self.get_frame_display_list(scene), frame_index)

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
        """获取单个方法的 MLI 帧名；跨方法 UI 应使用统一帧显示列表。"""
        return [name for name, _ in self._get_mli_frames(method, scene)]

    def get_mli_frame_display_list(self, scene: str) -> list:
        """返回所有方法共用的 MLI 视频帧列表，缺帧不会移动其他帧。"""
        frame_lists = [self._get_mli_frames(method, scene) for method in self.methods]
        if self.frame_alignment == 'index':
            return [name for name, _ in max(frame_lists, key=len, default=[])]
        return self._merge_frame_names(frame_lists)

    def _get_mli_frames(self, method: str, scene: str) -> list:
        key = (method, scene)
        if key in self._mli_frames:
            return self._mli_frames[key]
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
                        frames.append((os.path.splitext(fname)[0], os.path.join(scene_path, fname)))
        except (PermissionError, OSError):
            pass
        self._mli_frames[key] = frames
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

    def resolve_sai_path(self, method: str, scene: str, frame_index: int,
                         u: int, v: int) -> str:
        """解析统一帧对应的实际 SAI 文件，缺帧或缺视角返回 None。"""
        dir_path = self._resolve_dir(method, scene, frame_index)
        if not dir_path:
            return None
        fpath = self._build_sai_filename_map(dir_path).get((u, v))
        return fpath if fpath and os.path.isfile(fpath) else None

    def load_sai(self, method: str, scene: str, frame_index: int,
                 u: int, v: int) -> np.ndarray:
        """加载单张子孔径图像。

        参数:
            method: 方法名
            scene: 场景名
            frame_index: 统一帧显示列表的索引 (0-based)
            u, v: 角度坐标 (从 1 开始)

        返回:
            RGB numpy 数组, shape=(H, W, 3), dtype=uint8
        """
        fpath = self.resolve_sai_path(method, scene, frame_index, u, v)
        if fpath:
            with Image.open(fpath) as img:
                return np.array(img.convert('RGB'))
        return None

    def resolve_mli_path(self, method: str, scene: str,
                         frame_index: int = 0, mode: str = 'image') -> str:
        """解析实际 MLI 文件；视频使用统一帧索引，缺帧返回 None。"""
        if not self.root_dir:
            return None

        method_path = os.path.join(self.root_dir, method)

        if mode == 'image':
            # 光场图像: Method/Scene.ext
            for ext in SUPPORTED_IMAGE_EXTENSIONS:
                fpath = os.path.join(method_path, f"{scene}{ext}")
                if os.path.isfile(fpath):
                    return fpath
        else:
            path = self._select_frame(self._get_mli_frames(method, scene),
                                      self.get_mli_frame_display_list(scene), frame_index)
            return path if path and os.path.isfile(path) else None
        return None

    def load_mli(self, method: str, scene: str,
                 frame_index: int = 0, mode: str = 'image') -> np.ndarray:
        """加载统一帧对应的 MLI，返回 RGB uint8 数组或 None。"""
        fpath = self.resolve_mli_path(method, scene, frame_index, mode)
        if fpath:
            with Image.open(fpath) as img:
                return np.array(img.convert('RGB'))
        return None

    def load_light_field(self, method: str, scene: str, frame_index: int,
                         u_max: int, v_max: int) -> np.ndarray:
        """加载完整光场为 5D 数组。

        参数:
            method, scene: 定位
            frame_index: 帧位置索引 (0-based)
            u_max, v_max: 角度分辨率

        返回:
            5D numpy 数组, shape=[U, V, H, W, C], dtype=uint8；整帧缺失返回 None。
            已存在的帧若缺少视角或各视角尺寸不同，抛出 ValueError。
        """
        if not self._resolve_dir(method, scene, frame_index):
            return None
        if u_max < 1 or v_max < 1:
            raise ValueError("角度分辨率必须大于零")
        lf = None

        for u in range(1, u_max + 1):
            for v in range(1, v_max + 1):
                sai = self.load_sai(method, scene, frame_index, u, v)
                if sai is None:
                    raise ValueError(f"{method}/{scene} 帧 {frame_index} 缺少视角 ({u}, {v})")
                if lf is None:
                    lf = np.empty((u_max, v_max, *sai.shape), dtype=np.uint8)
                elif sai.shape != lf.shape[2:]:
                    raise ValueError(f"{method}/{scene} 视角 ({u}, {v}) 尺寸 {sai.shape} "
                                     f"与其他视角 {lf.shape[2:]} 不一致")
                lf[u - 1, v - 1] = sai

        return lf
