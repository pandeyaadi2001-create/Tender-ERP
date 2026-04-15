"""Compliance / certificate tracker (spec §3.3) and per-firm templates."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class ComplianceDocument(Base, TimestampMixin):
    __tablename__ = "compliance_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    firm_id: Mapped[int] = mapped_column(ForeignKey("firms.id"), nullable=False, index=True)

    certificate_no: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    document_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuing_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)

    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    renewal_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Active / To Be Renewed / Under Renewal / Expired / Not Applicable
    status: Mapped[str] = mapped_column(String(32), default="Active", nullable=False)
    responsible_person: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Path inside ATTACHMENTS_DIR to the scanned PDF. Spec §3.3 "File
    # attachment: the actual scanned PDF ... retrievable in one click."
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    firm = relationship("Firm", back_populates="compliance_documents")

    # Derived — spec §3.3: "live, recalculated on app open".
    @property
    def days_until_expiry(self) -> int | None:
        if self.expiry_date is None:
            return None
        return (self.expiry_date - date.today()).days

    @property
    def months_until_expiry(self) -> float | None:
        d = self.days_until_expiry
        if d is None:
            return None
        return round(d / 30.0, 1)

    @property
    def is_expired(self) -> bool:
        d = self.days_until_expiry
        return d is not None and d < 0


class ComplianceTemplate(Base):
    """Recurring compliance template per firm (spec §4.9).

    Seed the set of certificates a firm must always hold (e.g. Mr.
    Johnny always needs ISO 9001, EPFO, ESIC, FSSAI, GST, ...). When a
    certificate is renewed, the service layer auto-creates the next
    instance using ``default_validity_months``.
    """

    __tablename__ = "compliance_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    firm_id: Mapped[int] = mapped_column(ForeignKey("firms.id"), nullable=False, index=True)
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    default_validity_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)

    firm = relationship("Firm", back_populates="compliance_templates")
