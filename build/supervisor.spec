# -*- mode: python ; coding: utf-8 -*-

# 指定输出目录
import os
distpath = os.path.abspath(os.path.join(SPECPATH, 'supervisor'))
workpath = os.path.abspath(os.path.join(SPECPATH, 'build'))

# 定义 supervisor 目录
supervisor_dir = os.path.abspath(os.path.join(SPECPATH, '..', 'desktop-electron', 'resources', 'supervisor'))

a = Analysis(
    [os.path.join(supervisor_dir, 'supervisor.py')],
    pathex=[supervisor_dir],
    binaries=[],
    datas=[
        # 确保 api_server.py 被包含
        (os.path.join(supervisor_dir, 'api_server.py'), '.'),
    ],
    hiddenimports=[
        'api_server',
        'psutil',  # 添加 psutil (虽然是可选的，但建议包含)
        'logging.handlers',
        'http.server',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='supervisor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
)
