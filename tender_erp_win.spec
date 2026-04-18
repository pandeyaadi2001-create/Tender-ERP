# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Windows builds ONLY.

Usage on Windows:
    pip install pyinstaller
    pyinstaller --noconfirm tender_erp_win.spec

Output: dist\\TenderERP\\TenderERP.exe

The macOS build should use tender_erp.spec instead (includes BUNDLE).
"""

from PyInstaller.utils.hooks import collect_submodules
import sys

block_cipher = None

hidden = (
    collect_submodules("tender_erp")
    + collect_submodules("sqlalchemy.dialects.sqlite")
    + [
        "argon2.low_level",
        "cryptography.hazmat.primitives.ciphers.aead",
        "reportlab.graphics.barcode",
        "openpyxl.cell._writer",
    ]
)

a = Analysis(
    ["tender_erp/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("templates", "templates"),       # Excel import templates
    ],
    hiddenimports=hidden,
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
    name="TenderERP",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,              # Windowed mode — no console on launch
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico" if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TenderERP",
)
