"""E-Stamp consumption ledger (spec §3.5)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


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

    firm = relationship("Firm", back_populates="estamps")
    tender = relationship("Tender", back_populates="estamps")

    @property
    def total(self) -> float:
        return round(self.quantity * self.unit_rate, 2)

    @property
    def financial_year(self) -> str:
        """Indian FY (April–March) — spec §3.5 FY auto-bucketing."""
        y = self.entry_date.year
        if self.entry_date.month >= 4:
            return f"{y}-{(y + 1) % 100:02d}"
        return f"{y - 1}-{y % 100:02d}"
