"""Lightweight schema migration for SQLite.

SQLAlchemy's create_all() only creates new tables — it does NOT add
columns to existing tables.  This module runs safe ALTER TABLE ADD
COLUMN statements wrapped in try/except so existing databases pick up
new columns automatically on startup.

Called from db.init_db() after create_all().
"""

from __future__ import annotations

import logging
from sqlalchemy.engine import Engine

log = logging.getLogger(__name__)

# Each entry: (table, column_name, column_def)
_MIGRATIONS: list[tuple[str, str, str]] = [
    # ── Estamp lifecycle fields ──
    ("estamps", "denomination", "REAL"),
    ("estamps", "status", "VARCHAR(16) NOT NULL DEFAULT 'purchased'"),
    ("estamps", "pending_queued_at", "DATETIME"),
    ("estamps", "pending_required_by", "DATE"),
    ("estamps", "pending_reason", "VARCHAR(512)"),
    ("estamps", "estimated_cost", "REAL"),
    ("estamps", "actual_cost", "REAL"),
    ("estamps", "purchase_date", "DATE"),
    ("estamps", "vendor", "VARCHAR(255)"),
    ("estamps", "voucher_number", "VARCHAR(128)"),
    ("estamps", "voucher_document", "VARCHAR(1024)"),
    ("estamps", "stamp_state", "VARCHAR(64)"),
    ("estamps", "allocated_bid_id", "INTEGER REFERENCES tenders(id)"),
    # ── Tender award tracking ──
    ("tenders", "portal", "VARCHAR(64)"),
    ("tenders", "category", "VARCHAR(128)"),
    ("tenders", "document_fee", "REAL"),
    ("tenders", "processing_fee", "REAL"),
    ("tenders", "awarded_flag", "BOOLEAN NOT NULL DEFAULT 0"),
    ("tenders", "awarded_date", "DATE"),
    ("tenders", "awarded_value", "REAL"),
    ("tenders", "loa_po_number", "VARCHAR(128)"),
    ("tenders", "loa_document", "VARCHAR(1024)"),
    ("tenders", "execution_status", "VARCHAR(64)"),
    ("tenders", "service_days", "REAL"),
    # ── Firm code & color ──
    ("firms", "firm_code", "VARCHAR(16)"),
    ("firms", "firm_color_hex", "VARCHAR(7)"),
    ("firms", "state", "VARCHAR(64)"),
]


def run_migrations(engine: Engine) -> int:
    """Apply all pending column additions.  Returns count of columns added."""
    added = 0
    with engine.connect() as conn:
        for table, column, col_def in _MIGRATIONS:
            try:
                conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"
                    )
                )
                conn.commit()
                added += 1
                log.info("Migration: added %s.%s", table, column)
            except Exception:
                # Column already exists — expected on subsequent runs
                conn.rollback()
    return added
