"""Tender tracker and attachment tables (spec §3.2).

The column list mirrors ``02_Mr__Johnny_Tender_Tracker.xlsx`` and the
extended fields spec requires for commercial, workflow, and audit
tracking. Most of the "auto-derived" columns from the spec are *not*
stored here — they are computed on the fly (``period_in_days``,
``tender_value_cr``, ``billing_per_month``, ``variance``) to avoid
stale data exactly like the Excel had.
"""

from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Tender(Base, TimestampMixin):
    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    firm_id: Mapped[int] = mapped_column(ForeignKey("firms.id"), nullable=False, index=True)

    # Identification
    publish_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    due_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    bid_no: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    organisation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Commercial
    contract_period_months: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    publish_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    tender_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    pbg_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    pbg_period_months: Mapped[float | None] = mapped_column(Float, nullable=True)
    mse_preference: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    emd: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quoted_rates: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Workflow
    participation_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    participation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    in_whom_support: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nature_of_work: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    scope_of_work: Mapped[str | None] = mapped_column(Text, nullable=True)
    on_basis_of: Mapped[str | None] = mapped_column(String(128), nullable=True)
    technical_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    technical_disq_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    financial_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    financial_disq_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    our_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    l1_rates: Mapped[float | None] = mapped_column(Float, nullable=True)
    month_of_award: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Audit attribution beyond the mixin (spec §3.2 "Audit").
    technical_prepared_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    financial_prepared_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    checked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Reference-only flag — spec §3.2 "Reference Tenders sub-module".
    is_reference: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    firm = relationship("Firm", back_populates="tenders")
    attachments = relationship(
        "TenderAttachment", back_populates="tender", cascade="all, delete-orphan"
    )
    estamps = relationship("Estamp", back_populates="tender")
    checklist_instances = relationship(
        "ChecklistInstance", back_populates="tender", cascade="all, delete-orphan"
    )

    # Derived values (computed, never written). Kept here so the UI and
    # service layer call the same logic.
    @property
    def period_in_days(self) -> float | None:
        if self.contract_period_months is None:
            return None
        return round(self.contract_period_months * 30, 2)

    @property
    def tender_value_cr(self) -> float | None:
        if self.tender_value is None:
            return None
        return round(self.tender_value / 1e7, 4)

    @property
    def billing_per_month(self) -> float | None:
        if self.tender_value is None or not self.contract_period_months:
            return None
        return round(self.tender_value / self.contract_period_months, 2)

    @property
    def value_per_day(self) -> float | None:
        days = self.period_in_days
        if self.tender_value is None or not days:
            return None
        return round(self.tender_value / days, 2)

    @property
    def variance(self) -> str | None:
        """At par / Above / Below against the publish rate."""
        if self.quoted_rates is None or self.publish_rate is None:
            return None
        if abs(self.quoted_rates - self.publish_rate) < 1e-6:
            return "At par"
        return "Above" if self.quoted_rates > self.publish_rate else "Below"

    @property
    def tender_month(self) -> str | None:
        d = self.publish_date or self.due_date
        if d is None:
            return None
        return d.strftime("%Y-%m")


class TenderAttachment(Base):
    __tablename__ = "tender_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)  # "technical", "financial", "emd", "boq", "other"
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    tender = relationship("Tender", back_populates="attachments")
