"""Audit log writer. One public function: ``record``."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from ..models.audit import AuditLog


def _jsonable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    return value


def _dump(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    clean = {k: _jsonable(v) for k, v in payload.items() if not k.endswith("_enc")}
    return json.dumps(clean, default=str, sort_keys=True)


def record(
    session: Session,
    *,
    user_id: int | None,
    table: str,
    record_id: int,
    action: str,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    note: str | None = None,
) -> AuditLog:
    """Append an immutable audit row.

    ``old`` / ``new`` are JSON-serialised after stripping any key that
    ends with ``_enc`` — we never want encrypted blobs in plaintext
    logs. The caller decides what to pass in; typically this is
    ``obj.__dict__`` filtered to business fields.
    """
    entry = AuditLog(
        user_id=user_id,
        table_name=table,
        record_id=record_id,
        action=action,
        old_value_json=_dump(old),
        new_value_json=_dump(new),
        note=note,
    )
    session.add(entry)
    session.flush()
    return entry
