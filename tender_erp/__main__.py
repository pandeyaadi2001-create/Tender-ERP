"""``python -m tender_erp`` entry point.

Uses an **absolute** import (``from tender_erp.app``) rather than a
relative one (``from .app``). Both work for ``python -m tender_erp``,
but PyInstaller / py2app run this file as a standalone script with
no parent package — a relative import fails there with
``ImportError: attempted relative import with no known parent package``.
Absolute imports sidestep that entirely.
"""

from tender_erp.app import main


if __name__ == "__main__":
    raise SystemExit(main())
