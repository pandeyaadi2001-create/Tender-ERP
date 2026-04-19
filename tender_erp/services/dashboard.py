"""Dashboard queries (spec §3.7).

All functions here take an SQLAlchemy ``Session`` and return plain
dicts/dataclasses so the UI layer never has to care about ORM
internals (the Qt models just stringify what they receive).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..models.compliance import ComplianceDocument
from ..models.estamp import Estamp
from ..models.firm import Firm
from ..models.tender import Tender
from ..models.vault import VaultCredential


def is_participating_status(status: str | None) -> bool:
    """True for Participated / Participated in Support; false for Not Participated, Cancelled, empty."""
    if not status or not str(status).strip():
        return False
    s = str(status).strip().lower()
    if "not participated" in s:
        return False
    if s == "cancelled":
        return False
    return "participated" in s


def count_participating_tenders(session: Session) -> int:
    return sum(
        1
        for t in session.query(Tender).filter(Tender.is_reference == False).all()  # noqa: E712
        if is_participating_status(t.participation_status)
    )


@dataclass
class DeadlineRow:
    tender_id: int
    firm_name: str
    firm_code: str | None
    firm_color: str | None
    bid_no: str | None
    organisation: str | None
    category: str | None
    due_date: date | None
    due_in_days: int | None
    participation_status: str | None
    tender_value: float | None
    our_status: str | None


def _to_deadline_rows(tenders: Sequence[Tender], today: date) -> list[DeadlineRow]:
    out = []
    for t in tenders:
        due_in = (t.due_date - today).days if t.due_date else None
        out.append(
            DeadlineRow(
                tender_id=t.id,
                firm_name=t.firm.name if t.firm else "-",
                firm_code=t.firm.firm_code if t.firm else None,
                firm_color=t.firm.firm_color_hex if t.firm else None,
                bid_no=t.bid_no,
                organisation=t.organisation,
                category=t.category,
                due_date=t.due_date,
                due_in_days=due_in,
                participation_status=t.participation_status,
                tender_value=t.tender_value,
                our_status=t.our_status,
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
        select(Estamp).where(
            and_(
                Estamp.entry_date >= start,
                Estamp.entry_date <= today,
                Estamp.status.in_(("purchased", "allocated", "used")),
            )
        )
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
                and_(
                    Estamp.entry_date >= last_start,
                    Estamp.entry_date <= last_end,
                    Estamp.status.in_(("purchased", "allocated", "used")),
                )
            )
        ).all()
        last_total = sum(r.total for r in last_rows)
    return EstampSummary(count=count, total_spent=round(total, 2), vs_same_month_last_fy=round(last_total, 2))


@dataclass
class EstampStatusSummary:
    purchased_count: int = 0
    purchased_value: float = 0.0
    pending_count: int = 0
    pending_value: float = 0.0
    allocated_count: int = 0
    used_count: int = 0
    required_upcoming: int = 0
    required_upcoming_value: float = 0.0
    shortfall: int = 0
    denomination_breakdown: dict = field(default_factory=dict)


def estamp_status_summary(session: Session) -> EstampStatusSummary:
    """Build the full e-stamp status for dashboard tiles."""
    all_estamps = session.query(Estamp).all()
    summary = EstampStatusSummary()
    denom_purchased: dict[float, int] = defaultdict(int)
    denom_required: dict[float, int] = defaultdict(int)

    for e in all_estamps:
        denom = e.denomination or e.unit_rate
        if e.status == "purchased":
            summary.purchased_count += e.quantity
            summary.purchased_value += e.total
            denom_purchased[denom] += e.quantity
        elif e.status == "pending":
            summary.pending_count += e.quantity
            summary.pending_value += (e.estimated_cost or e.total)
            denom_required[denom] += e.quantity
        elif e.status == "allocated":
            summary.allocated_count += e.quantity
            denom_purchased[denom] += e.quantity
        elif e.status == "used":
            summary.used_count += e.quantity

    # Required upcoming = pending stamps not yet purchased
    summary.required_upcoming = summary.pending_count
    summary.required_upcoming_value = summary.pending_value
    summary.shortfall = max(0, summary.pending_count - summary.purchased_count)

    # Build denomination breakdown
    all_denoms = sorted(set(list(denom_purchased.keys()) + list(denom_required.keys())))
    for d in all_denoms:
        summary.denomination_breakdown[d] = {
            "purchased": denom_purchased.get(d, 0),
            "required": denom_required.get(d, 0),
        }

    return summary


@dataclass
class AwardedFirmYear:
    firm_code: str
    firm_name: str
    firm_color: str | None
    fy: str
    count: int
    total_value: float


def bids_awarded_by_firm_year(session: Session) -> list[AwardedFirmYear]:
    """Group awarded tenders by firm and financial year for the chart."""
    tenders = (
        session.query(Tender)
        .filter(Tender.awarded_flag == True)  # noqa: E712
        .filter(Tender.awarded_date.is_not(None))
        .all()
    )
    groups: dict[tuple[str, str], list[Tender]] = defaultdict(list)
    for t in tenders:
        if not t.firm:
            continue
        code = t.firm.firm_code or t.firm.name[:4].upper()
        # Derive FY from awarded_date
        y = t.awarded_date.year
        fy = f"{y}-{(y+1) % 100:02d}" if t.awarded_date.month >= 4 else f"{y-1}-{y % 100:02d}"
        groups[(code, fy)].append(t)

    result = []
    for (code, fy), ts in groups.items():
        firm = ts[0].firm
        result.append(AwardedFirmYear(
            firm_code=code,
            firm_name=firm.name,
            firm_color=firm.firm_color_hex,
            fy=fy,
            count=len(ts),
            total_value=sum(t.awarded_value or 0 for t in ts),
        ))
    return sorted(result, key=lambda x: (x.fy, x.firm_code))


def active_tenders_by_status(session: Session) -> dict[str, int]:
    """Count active tenders grouped by our_status for the donut chart."""
    tenders = (
        session.query(Tender)
        .filter(Tender.is_reference == False)  # noqa: E712
        .filter(Tender.awarded_flag == False)  # noqa: E712
        .all()
    )
    counts: dict[str, int] = defaultdict(int)
    for t in tenders:
        status = t.our_status or "Draft"
        counts[status] += 1
    return dict(counts)


def _current_fy() -> str:
    today = date.today()
    y = today.year
    if today.month >= 4:
        return f"{y}-{(y+1) % 100:02d}"
    return f"{y-1}-{y % 100:02d}"


@dataclass
class DashboardSnapshot:
    generated_at: datetime
    current_fy: str

    # KPI Row 1
    total_tenders_participated: int
    tenders_7d: list[DeadlineRow]
    tenders_7d_critical_count: int
    tenders_8_to_30d_count: int
    compliance_60d: list[ComplianceDocument]

    # KPI Row 2
    compliance_15d_count: int
    estamp_status: EstampStatusSummary
    estamp_mtd: EstampSummary

    # Charts
    bids_awarded: list[AwardedFirmYear]
    active_by_status: dict[str, int]

    # Supplemental
    dsc_90d: list[VaultCredential]
    firm_count: int


def build_snapshot(session: Session, today: date | None = None) -> DashboardSnapshot:
    today = today or date.today()
    firm_count = session.query(Firm).filter(Firm.is_archived == False).count()  # noqa: E712

    fy = _current_fy()
    tenders_participated = count_participating_tenders(session)

    tenders_7d = tenders_due_between(session, min_days=0, max_days=7, today=today)
    critical_count = sum(1 for t in tenders_7d if t.due_in_days is not None and t.due_in_days <= 3)

    tenders_8_30 = tenders_due_between(session, min_days=8, max_days=30, today=today)

    compliance_60d = compliance_expiring_within(session, 60, today)
    compliance_15d = [c for c in compliance_60d if c.days_until_expiry is not None and c.days_until_expiry <= 15]

    return DashboardSnapshot(
        generated_at=datetime.utcnow(),
        current_fy=fy,
        total_tenders_participated=tenders_participated,
        tenders_7d=tenders_7d,
        tenders_7d_critical_count=critical_count,
        tenders_8_to_30d_count=len(tenders_8_30),
        compliance_60d=compliance_60d,
        compliance_15d_count=len(compliance_15d),
        estamp_status=estamp_status_summary(session),
        estamp_mtd=estamp_month_to_date(session, today),
        bids_awarded=bids_awarded_by_firm_year(session),
        active_by_status=active_tenders_by_status(session),
        dsc_90d=dsc_expiring_within(session, 90, today),
        firm_count=firm_count,
    )
