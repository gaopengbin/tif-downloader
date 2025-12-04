# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置文件
运行: pyinstaller tif_downloader.spec
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# 收集依赖数据
datas = [
    ('static', 'static'),  # 静态文件
    ('app', 'app'),  # 应用代码
]

# 尝试收集 rasterio 的 proj_data
try:
    import rasterio
    rasterio_path = os.path.dirname(rasterio.__file__)
    proj_data = os.path.join(rasterio_path, 'proj_data')
    if os.path.exists(proj_data):
        datas.append((proj_data, 'proj_data'))
except ImportError:
    pass

# 收集 rasterio 和其他库的数据文件
datas += collect_data_files('rasterio', include_py_files=False)

# 隐藏导入
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'fastapi',
    'starlette',
    'starlette.routing',
    'starlette.responses',
    'starlette.middleware',
    'starlette.middleware.cors',
    'pydantic',
    'aiohttp',
    'aiofiles',
    'rasterio',
    'rasterio.crs',
    'rasterio.transform',
    'rasterio._shim',
    'rasterio.sample',
    'rasterio.vrt',
    'rasterio.features',
    'numpy',
    'PIL',
    'PIL.Image',
    'multipart',
    'email_validator',
    'httptools',
    'websockets',
    'watchfiles',
    'python_multipart',
]

# 收集子模块
hiddenimports += collect_submodules('rasterio')
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('starlette')

a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TIF地图下载工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标: icon='icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TIF地图下载工具',
)
