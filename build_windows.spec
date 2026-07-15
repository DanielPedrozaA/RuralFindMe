# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)
icon = root / "app" / "assets" / "app-icon.ico"

a = Analysis(
    [str(root / "app" / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "app" / "config"), "app/config"),
        (str(root / "app" / "assets"), "app/assets"),
        (str(root / "frontend" / "dist"), "frontend/dist"),
    ],
    hiddenimports=[
        "fitz",
        "rapidfuzz",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # PyMuPDF exposes optional conversion helpers for these scientific/notebook
    # stacks. RuralFindMe never calls them; excluding them keeps a portable build
    # small even when the build machine has those packages globally installed.
    excludes=[
        "pandas",
        "numpy",
        "PIL",
        "IPython",
        "matplotlib",
        "scipy",
        "jedi",
        "zmq",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RuralFindMe",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon),
    version=str(root / "build" / "version_info.txt"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RuralFindMe",
)
