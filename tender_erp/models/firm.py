"""Firm master table."""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Firm(Base, TimestampMixin):
    """A legal entity under the operator.

    Every row in the app's business tables has a ``firm_id`` FK pointing
    here. Firms are soft-deleted via ``is_archived`` — hard deletes are
    blocked at the service layer once a firm has any linked record
    (spec §3.1).
    """

    __tablename__ = "firms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(16), nullable=True)
    udyam: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # JSON blob: per-firm visible column profile for the tender tracker
    # (spec §3.2 "per-firm column flexibility"). Keeping it as free-form
    # text avoids a migration every time the user hides a column.
    tender_columns_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tenders = relationship("Tender", back_populates="firm", cascade="all, delete-orphan")
    compliance_documents = relationship(
        "ComplianceDocument", back_populates="firm", cascade="all, delete-orphan"
    )
    vault_credentials = relationship(
        "VaultCredential", back_populates="firm", cascade="all, delete-orphan"
    )
    estamps = relationship("Estamp", back_populates="firm", cascade="all, delete-orphan")
    compliance_templates = relationship(
        "ComplianceTemplate", back_populates="firm", cascade="all, delete-orphan"
    )
