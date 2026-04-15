"""Application paths, constants and tunable settings.

All filesystem locations the app uses at runtime are resolved here. On
Windows the data directory is ``%APPDATA%\\TenderManager``; on other
platforms we fall back to ``~/.tender_erp`` so the app still runs in CI
and during development on Linux/macOS. Override the base directory with
the ``TENDER_ERP_HOME`` environment variable — tests rely on this to point
at a temporary folder.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_home() -> Path:
    env = os.environ.get("TENDER_ERP_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "TenderManager"
    return Path.home() / ".tender_erp"


APP_HOME: Path = _default_home()
DB_PATH: Path = APP_HOME / "tender_erp.sqlite3"
ATTACHMENTS_DIR: Path = APP_HOME / "attachments"
CHECKLIST_DIR: Path = APP_HOME / "checklists"
BACKUP_DIR: Path = APP_HOME / "backups"
LOG_DIR: Path = APP_HOME / "logs"


def ensure_dirs() -> None:
    """Create all runtime directories if they don't exist yet."""
    for d in (APP_HOME, ATTACHMENTS_DIR, CHECKLIST_DIR, BACKUP_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Settings:
    """Security-related tuning knobs.

    These match the spec's non-negotiables: Argon2id for password hashing,
    AES-256-GCM for vault records, 5 failed logins → 15 min lockout, 30
    min idle session timeout, and a 5 min vault re-auth window.
    """

    session_timeout_minutes: int = 30
    vault_reauth_minutes: int = 5
    clipboard_clear_seconds: int = 20
    max_failed_logins: int = 5
    lockout_minutes: int = 15

    # Argon2id parameters — reasonable for a desktop app (~250ms on modern CPUs).
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 64 * 1024  # KiB
    argon2_parallelism: int = 2


SETTINGS = Settings()

# Application metadata used in the UI title bar and exported documents.
APP_NAME = "Tender & Compliance Manager"
APP_ORG = "TenderERP"
