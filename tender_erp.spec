# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for the Windows build.

Used by both:

* The CI workflow (``.github/workflows/build.yml``), which runs
  ``pyinstaller tender_erp.spec`` on ``windows-latest``.
* Developers who want to build locally on their Windows box::

      pip install pyinstaller
      pyinstaller tender_erp.spec

The output goes to ``dist\\TenderERP\\TenderERP.exe``.

Keeping this file committed (instead of passing flags on the CLI)
means every build uses exactly the same hiddenimports / data files.
"""

from PyInstaller.utils.hooks import collect_submodules

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
    datas=[],
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
    console=False,  # windowed mode — no console window on launch
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
