"""Backup / restore / export helpers (spec §4.6)."""

from __future__ import annotations

import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ATTACHMENTS_DIR, BACKUP_DIR, DB_PATH, ensure_dirs


def manual_backup(label: str | None = None) -> Path:
    """Zip the live DB + attachments into ``BACKUP_DIR``.

    Returns the path to the zipfile. The vault ciphertext lives inside
    the DB so this archive is only as safe as the directory it's
    written to — document this to the operator.
    """
    ensure_dirs()
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    tag = f"_{label}" if label else ""
    out = BACKUP_DIR / f"backup{tag}_{ts}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        if DB_PATH.exists():
            zf.write(DB_PATH, arcname="tender_erp.sqlite3")
        if ATTACHMENTS_DIR.exists():
            for f in ATTACHMENTS_DIR.rglob("*"):
                if f.is_file():
                    zf.write(f, arcname=f"attachments/{f.relative_to(ATTACHMENTS_DIR)}")
    return out


def restore_backup(zip_path: Path, target_home: Path) -> None:
    """Extract a backup zip into a target home directory.

    Caller is responsible for shutting the app down first — we just
    unpack the archive. Refuses to restore over an existing DB file to
    avoid silent data loss.
    """
    target_db = target_home / "tender_erp.sqlite3"
    if target_db.exists():
        raise FileExistsError(f"refusing to overwrite existing DB at {target_db}")
    target_home.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target_home)


def export_table_to_xlsx(
    session: Session,
    *,
    model,
    columns: Iterable[str],
    out_path: Path,
) -> Path:
    """Export selected columns from a table to .xlsx (no vault blobs).

    The caller chooses the columns so we never accidentally dump a
    vault ciphertext into a spreadsheet.
    """
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = model.__tablename__
    columns = list(columns)
    ws.append(columns)
    for row in session.scalars(select(model)).all():
        ws.append([getattr(row, c, None) for c in columns])
    wb.save(out_path)
    return out_path
