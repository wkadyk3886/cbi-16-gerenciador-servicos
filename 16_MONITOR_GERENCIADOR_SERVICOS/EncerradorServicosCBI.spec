# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['encerrar_servicos_cbi.py'],
    pathex=['.'],
    binaries=[],
    datas=[('cbi_services_core.py', '.')],
    hiddenimports=['tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'cbi_services_core'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'pandas', 'scipy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='EncerradorServicosCBI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
)
