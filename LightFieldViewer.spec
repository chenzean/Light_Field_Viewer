# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 — 单文件、无控制台窗口。

用 build.bat 调用, 产物是 dist/LightFieldViewer.exe, 目标机器不需要 Python 环境。
"""

import sys
from pathlib import Path


env_dir = Path(sys.prefix)
conda_bin = env_dir / 'Library' / 'bin'
# PyInstaller 会顺着 PATH 收集同名 DLL, 可能抓到 MATLAB/Polyspace 等目录下的版本,
# 导致 exe 启动时 pyexpat 加载失败。这里强制使用当前 conda 环境里的那几个。
forced_dll_names = {
    'libexpat.dll',
    'libcrypto-3-x64.dll',
    'libssl-3-x64.dll',
}
forced_binaries = [
    (str(conda_bin / name), '.')
    for name in forced_dll_names
    if (conda_bin / name).exists()
]

# 应用图标要随 exe 一起带上, 否则 utils/resources.py 在 sys._MEIPASS 下取不到。
datas = [('assets', 'assets')]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=forced_binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
a.binaries = [
    binary for binary in a.binaries
    if binary[0].lower() not in forced_dll_names
]
a.binaries += [
    (name, str(conda_bin / name), 'BINARY')
    for name in forced_dll_names
    if (conda_bin / name).exists()
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LightFieldViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)
