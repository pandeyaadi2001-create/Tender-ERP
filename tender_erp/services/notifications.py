"""Desktop notifications (spec §3.7).

``plyer`` is optional — if it's unavailable (headless CI, missing
backend) we fall back to a no-op. The caller only ever interacts with
``notify``.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from ..config import APP_NAME
from . import dashboard

try:  # pragma: no cover - plyer is an optional GUI-side dep
    from plyer import notification as _plyer_notification
except Exception:  # pragma: no cover
    _plyer_notification = None


def notify(title: str, message: str) -> bool:
    """Best-effort desktop notification. Returns ``True`` if delivered."""
    if _plyer_notification is None:
        return False
    try:
        _plyer_notification.notify(title=title, message=message, app_name=APP_NAME, timeout=10)
        return True
    except Exception:
        return False


def collect_due_alerts(
    session: Session, today: date | None = None
) -> list[tuple[str, str]]:
    """Build a list of ``(title, message)`` pairs the scheduler can emit.

    Spec §3.7 lists trigger windows: 48h/24h/6h for tenders; 30/15/7/1
    days for compliance. We build whatever fits in those buckets right
    now and let the caller decide what to actually fire.
    """
    today = today or date.today()
    alerts: list[tuple[str, str]] = []

    # Tender due-in windows.
    for days in (2, 1):
        rows = dashboard.tenders_due_between(
            session, min_days=days, max_days=days, today=today
        )
        for r in rows:
            alerts.append(
                (
                    f"Tender due in {days} day(s)",
                    f"{r.firm_name} – {r.bid_no or '-'} – {r.organisation or ''}",
                )
            )

    # Compliance renewal windows.
    for days in (30, 15, 7, 1):
        target = today + timedelta(days=days)
        docs = [
            d
            for d in dashboard.compliance_expiring_within(session, days, today)
            if d.expiry_date == target
        ]
        for d in docs:
            alerts.append(
                (
                    f"Compliance expires in {days} day(s)",
                    f"{d.firm.name if d.firm else '-'} – {d.document_name}",
                )
            )
    return alerts


def fire_due_alerts(session: Session) -> int:
    delivered = 0
    for title, message in collect_due_alerts(session):
        if notify(title, message):
            delivered += 1
    return delivered
