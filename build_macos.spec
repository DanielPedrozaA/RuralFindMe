# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import re

root = Path(SPECPATH)
icon = root / "app" / "assets" / "app-icon.icns"
version_source = (root / "app" / "__init__.py").read_text(encoding="utf-8")
version_match = re.search(r'__version__\s*=\s*"([^"]+)"', version_source)
if not version_match:
    raise RuntimeError("No se pudo leer la versión desde app/__init__.py")
app_version = version_match.group(1)
a = Analysis(
    [str(root / "app" / "main.py")],
    pathex=[str(root)],
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
    excludes=["pandas", "numpy", "PIL", "IPython", "matplotlib", "scipy", "jedi", "zmq"],
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    name="RuralFindMe",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    exclude_binaries=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="RuralFindMe",
)
app = BUNDLE(
    coll,
    name="RuralFindMe.app",
    icon=str(icon),
    bundle_identifier="co.ruralfindme.app",
    version=app_version,
    info_plist={"NSHighResolutionCapable": "True"},
)
