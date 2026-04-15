"""py2app build script for the macOS ``.app`` bundle.

This file is only used for the macOS build — the project metadata
lives in ``pyproject.toml`` and is used by ``pip install``. py2app
specifically needs a ``setup.py`` with an ``app=`` keyword to know
what to bundle, so keep this file even though it looks redundant.

Usage (on a Mac with Python 3.11 + an active venv)::

    pip install py2app
    python setup.py py2app

Produces ``dist/TenderERP.app``. The GitHub Actions macOS build
runs the same command.
"""

from __future__ import annotations

from setuptools import setup

APP = ["tender_erp/__main__.py"]

# py2app ships every package listed here wholesale. PySide6 is the
# big one — it needs the Qt frameworks, plugins, and resources. The
# other entries cover runtime imports py2app's static analysis
# sometimes misses (argon2 low-level types, cryptography hazmat
# primitives, sqlalchemy dialects).
PACKAGES = [
    "tender_erp",
    "PySide6",
    "shiboken6",
    "sqlalchemy",
    "argon2",
    "cryptography",
    "openpyxl",
    "reportlab",
    "dateutil",
]

# Modules py2app's modulegraph occasionally misses even when the
# parent package is listed. Keeping them explicit avoids "module not
# found" at first launch of the bundled app.
INCLUDES = [
    "tender_erp.services.crypto",
    "tender_erp.services.auth",
    "tender_erp.services.checklist",
    "tender_erp.services.dashboard",
    "tender_erp.ui.main_window",
]

OPTIONS = {
    "argv_emulation": False,
    "packages": PACKAGES,
    "includes": INCLUDES,
    "plist": {
        "CFBundleName": "TenderERP",
        "CFBundleDisplayName": "Tender & Compliance Manager",
        "CFBundleIdentifier": "com.tendererp.app",
        "CFBundleVersion": "0.5.0",
        "CFBundleShortVersionString": "0.5.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.business",
        # The spec's offline-first stance means no network entitlements.
        "NSAppTransportSecurity": {"NSAllowsArbitraryLoads": False},
    },
}

setup(
    name="TenderERP",
    app=APP,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
