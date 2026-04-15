"""Checklist rule library + generated checklist instances (spec §3.6)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ChecklistRule(Base):
    """A single rule mapping a tender condition → one required doc.

    A rule fires when ``condition_field`` equals ``condition_value`` on
    the tender being processed (case-insensitive). ``condition_field``
    of ``"*"`` denotes a universal base-document rule that always fires.
    """

    __tablename__ = "checklist_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    condition_field: Mapped[str] = mapped_column(String(64), nullable=False, default="*")
    condition_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    required_document: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ChecklistInstance(Base):
    """A frozen checklist generated for a specific tender.

    ``items_json`` stores the list of ``{document, status, source}``
    entries so the checklist can be re-rendered after the underlying
    compliance data changes. ``pdf_path`` points to the file saved in
    ``CHECKLIST_DIR``.
    """

    __tablename__ = "checklist_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    tender = relationship("Tender", back_populates="checklist_instances")
