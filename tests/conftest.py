"""Shared pytest fixtures.

Every test gets a fresh SQLite DB under a temp dir so we never pollute
the developer's real app home.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def tender_erp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TENDER_ERP_HOME", str(tmp_path))

    # Re-evaluate the config module so the paths pick up the env var.
    import importlib

    from tender_erp import config as cfg

    importlib.reload(cfg)
    # Re-bind the db module to the new config.
    from tender_erp import db as db_mod

    importlib.reload(db_mod)
    db_mod.init_db()
    yield tmp_path
