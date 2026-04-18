"""E-Stamp consumption ledger with full lifecycle (spec §3.5).

Status lifecycle: pending → purchased → allocated → used
                  pending → cancelled
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


# Valid denominations for Indian e-stamps
DENOMINATIONS = (100, 500, 1000, 5000, 10000)

ESTAMP_STATUSES = ("purchased", "pending", "allocated", "used", "cancelled")

# User-facing status labels
STATUS_LABELS = {
    "purchased": "Purchased",
    "pending": "Pending Arrangement",
    "allocated": "Allocated",
    "used": "Used",
    "cancelled": "Cancelled",
}


class Estamp(Base, TimestampMixin):
    __tablename__ = "estamps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    firm_id: Mapped[int] = mapped_column(ForeignKey("firms.id"), nullable=False, index=True)
    tender_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenders.id"), nullable=True, index=True
    )
    # Free-text name used when the stamp was bought for a tender that
    # never made it into the tracker (e.g. reference bids). Keeping
    # both the FK and the text means the roll-ups still balance.
    tender_name_text: Mapped[str | None] = mapped_column(String(255), nullable=True)

    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # --- New lifecycle fields ---
    denomination: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="purchased", index=True
    )

    # Pending workflow
    pending_queued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pending_required_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    pending_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Actual cost paid (distinct from face value / denomination)
    # e.g. ₹100 stamp may cost ₹180 to purchase
    actual_cost: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Purchase details
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    voucher_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    voucher_document: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    stamp_state: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Allocation
    allocated_bid_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenders.id"), nullable=True, index=True
    )

    firm = relationship("Firm", back_populates="estamps")
    tender = relationship("Tender", back_populates="estamps", foreign_keys=[tender_id])
    allocated_tender = relationship("Tender", foreign_keys=[allocated_bid_id])

    @property
    def face_value_total(self) -> float:
        """Total face value (denomination × qty)."""
        return round(self.quantity * (self.denomination or self.unit_rate), 2)

    @property
    def actual_cost_total(self) -> float:
        """Total actual cost paid. Falls back to face value if not set."""
        if self.actual_cost is not None:
            return round(self.actual_cost * self.quantity, 2)
        return self.face_value_total

    @property
    def total(self) -> float:
        """Alias — returns actual cost if available, else face value."""
        return self.actual_cost_total

    @property
    def financial_year(self) -> str:
        """Indian FY (April–March) — spec §3.5 FY auto-bucketing."""
        y = self.entry_date.year
        if self.entry_date.month >= 4:
            return f"{y}-{(y + 1) % 100:02d}"
        return f"{y - 1}-{y % 100:02d}"
