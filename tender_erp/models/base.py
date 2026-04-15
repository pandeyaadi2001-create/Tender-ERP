"""Declarative base and common mixins."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base. All ORM models inherit from this."""


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` columns that the audit log
    helper keeps in sync. Every business table in this app carries these
    so we can reconstruct "who touched what and when" from the row
    itself, in addition to the dedicated ``audit_log`` table."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modified_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
