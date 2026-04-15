"""Dashboard queries (spec §3.7).

All functions here take an SQLAlchemy ``Session`` and return plain
dicts/dataclasses so the UI layer never has to care about ORM
internals (the Qt models just stringify what they receive).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Sequence

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..models.compliance import ComplianceDocument
from ..models.estamp import Estamp
from ..models.firm import Firm
from ..models.tender import Tender
from ..models.vault import VaultCredential


@dataclass
class DeadlineRow:
    tender_id: int
    firm_name: str
    bid_no: str | None
    organisation: str | None
    due_date: date | None
    due_in_days: int | None
    participation_status: str | None


def _to_deadline_rows(tenders: Sequence[Tender], today: date) -> list[DeadlineRow]:
    out = []
    for t in tenders:
        due_in = (t.due_date - today).days if t.due_date else None
        out.append(
            DeadlineRow(
                tender_id=t.id,
                firm_name=t.firm.name if t.firm else "-",
                bid_no=t.bid_no,
                organisation=t.organisation,
                due_date=t.due_date,
                due_in_days=due_in,
                participation_status=t.participation_status,
            )
        )
    return out


def tenders_due_between(
    session: Session, *, min_days: int, max_days: int, today: date | None = None
) -> list[DeadlineRow]:
    today = today or date.today()
    lo = today + timedelta(days=min_days)
    hi = today + timedelta(days=max_days)
    stmt = (
        select(Tender)
        .where(Tender.due_date.is_not(None))
        .where(Tender.due_date >= lo)
        .where(Tender.due_date <= hi)
        .where(Tender.is_reference == False)  # noqa: E712
        .order_by(Tender.due_date, Tender.due_time)
    )
    return _to_deadline_rows(session.scalars(stmt).all(), today)


def compliance_expiring_within(
    session: Session, days: int = 60, today: date | None = None
) -> list[ComplianceDocument]:
    today = today or date.today()
    cutoff = today + timedelta(days=days)
    stmt = (
        select(ComplianceDocument)
        .where(ComplianceDocument.expiry_date.is_not(None))
        .where(ComplianceDocument.expiry_date <= cutoff)
        .where(ComplianceDocument.status != "Not Applicable")
        .order_by(ComplianceDocument.expiry_date)
    )
    return list(session.scalars(stmt).all())


def dsc_expiring_within(
    session: Session, days: int = 90, today: date | None = None
) -> list[VaultCredential]:
    today = today or date.today()
    cutoff = today + timedelta(days=days)
    stmt = (
        select(VaultCredential)
        .where(VaultCredential.dsc_expiry.is_not(None))
        .where(VaultCredential.dsc_expiry <= cutoff)
        .order_by(VaultCredential.dsc_expiry)
    )
    return list(session.scalars(stmt).all())


def pending_status_tenders(session: Session, today: date | None = None) -> list[Tender]:
    """Tenders whose due date has passed but status fields are still PENDING."""
    today = today or date.today()
    pending = ("PENDING", "Pending", "pending")
    stmt = (
        select(Tender)
        .where(Tender.due_date.is_not(None))
        .where(Tender.due_date < today)
        .where(
            or_(
                Tender.technical_status.in_(pending),
                Tender.financial_status.in_(pending),
                Tender.our_status.in_(pending),
            )
        )
        .where(Tender.is_reference == False)  # noqa: E712
        .order_by(Tender.due_date)
    )
    return list(session.scalars(stmt).all())


def decision_required_queue(session: Session, today: date | None = None) -> list[Tender]:
    """Tenders publishing in next 7 days with no participation_status set."""
    today = today or date.today()
    cutoff = today + timedelta(days=7)
    stmt = (
        select(Tender)
        .where(Tender.publish_date.is_not(None))
        .where(Tender.publish_date >= today)
        .where(Tender.publish_date <= cutoff)
        .where(
            or_(
                Tender.participation_status.is_(None),
                Tender.participation_status == "",
            )
        )
        .where(Tender.is_reference == False)  # noqa: E712
        .order_by(Tender.publish_date)
    )
    return list(session.scalars(stmt).all())


@dataclass
class EstampSummary:
    count: int
    total_spent: float
    vs_same_month_last_fy: float


def estamp_month_to_date(
    session: Session, today: date | None = None
) -> EstampSummary:
    today = today or date.today()
    start = today.replace(day=1)
    rows = session.scalars(
        select(Estamp).where(and_(Estamp.entry_date >= start, Estamp.entry_date <= today))
    ).all()
    count = sum(r.quantity for r in rows)
    total = sum(r.total for r in rows)

    try:
        last_start = start.replace(year=start.year - 1)
        last_end = last_start.replace(
            day=28
            if start.month == 2
            else (30 if start.month in (4, 6, 9, 11) else 31)
        )
    except ValueError:
        last_start = last_end = None  # type: ignore[assignment]
    last_total = 0.0
    if last_start and last_end:
        last_rows = session.scalars(
            select(Estamp).where(
                and_(Estamp.entry_date >= last_start, Estamp.entry_date <= last_end)
            )
        ).all()
        last_total = sum(r.total for r in last_rows)
    return EstampSummary(count=count, total_spent=round(total, 2), vs_same_month_last_fy=round(last_total, 2))


@dataclass
class DashboardSnapshot:
    generated_at: datetime
    tenders_7d: list[DeadlineRow]
    tenders_8_to_30d: list[DeadlineRow]
    compliance_60d: list[ComplianceDocument]
    dsc_90d: list[VaultCredential]
    pending_status: list[Tender]
    decision_required: list[Tender]
    estamp_mtd: EstampSummary
    firm_count: int


def build_snapshot(session: Session, today: date | None = None) -> DashboardSnapshot:
    today = today or date.today()
    firm_count = session.query(Firm).filter(Firm.is_archived == False).count()  # noqa: E712
    return DashboardSnapshot(
        generated_at=datetime.utcnow(),
        tenders_7d=tenders_due_between(session, min_days=0, max_days=7, today=today),
        tenders_8_to_30d=tenders_due_between(session, min_days=8, max_days=30, today=today),
        compliance_60d=compliance_expiring_within(session, 60, today),
        dsc_90d=dsc_expiring_within(session, 90, today),
        pending_status=pending_status_tenders(session, today),
        decision_required=decision_required_queue(session, today),
        estamp_mtd=estamp_month_to_date(session, today),
        firm_count=firm_count,
    )
