"""Publish rate helpers for Healthcare Kitchen vs Laundry tenders.

Kitchen:  tender_value / days / quantity (diet portions per day)
  — days = ``service_days`` if set, else ``contract_period_months * 30``.

Laundry: tender_value / contract_period_months / quantity (kg per month)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.tender import Tender


def service_kind(nature_of_work: str | None, category: str | None) -> str | None:
    text = " ".join(filter(None, [nature_of_work or "", category or ""])).lower()
    if "laundry" in text:
        return "laundry"
    if "kitchen" in text or "dietary" in text or "healthcare kitchen" in text:
        return "kitchen"
    return None


def computed_publish_rate_fields(
    *,
    tender_value: float | None,
    quantity: float | None,
    nature_of_work: str | None,
    category: str | None,
    contract_period_months: float | None,
    service_days: float | None,
    period_in_days_fallback: float | None = None,
) -> float | None:
    """Pure function for editor save / tests."""
    kind = service_kind(nature_of_work, category)
    if kind is None:
        return None
    if tender_value is None or quantity is None or quantity <= 0:
        return None

    if kind == "kitchen":
        days = service_days if service_days is not None and service_days > 0 else None
        if days is None or days <= 0:
            days = period_in_days_fallback
        if days is None or days <= 0:
            if contract_period_months and contract_period_months > 0:
                days = float(contract_period_months) * 30.0
            else:
                return None
        return round(float(tender_value) / float(days) / float(quantity), 6)

    if kind == "laundry":
        if contract_period_months is None or contract_period_months <= 0:
            return None
        return round(float(tender_value) / float(contract_period_months) / float(quantity), 6)

    return None


def computed_publish_rate(tender: Tender) -> float | None:
    """Return rate from formula when kind + inputs are valid; else None."""
    pd = tender.period_in_days
    sd = getattr(tender, "service_days", None)
    return computed_publish_rate_fields(
        tender_value=tender.tender_value,
        quantity=tender.quantity,
        nature_of_work=tender.nature_of_work,
        category=tender.category,
        contract_period_months=tender.contract_period_months,
        service_days=sd,
        period_in_days_fallback=pd,
    )


def effective_publish_rate(tender: Tender) -> float | None:
    """Prefer formula when applicable; fall back to stored publish_rate."""
    c = computed_publish_rate(tender)
    if c is not None:
        return c
    return tender.publish_rate
