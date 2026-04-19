"""Tests for Excel bulk import (firm resolution, dates, EMD text)."""

from __future__ import annotations

from datetime import date

from tender_erp.db import session_scope
from tender_erp.models.firm import Firm
from tender_erp.services.import_service import (
    _coerce_date,
    _coerce_optional_money,
    _normalize_firm_name,
    _resolve_firm,
    process_import,
)


def test_normalize_firm_strips_prefix_and_case() -> None:
    a = _normalize_firm_name("M/s. ACME Pvt Ltd")
    b = _normalize_firm_name("mr. acme pvt ltd")
    assert a == b


def test_resolve_firm_fuzzy_typo() -> None:
    """Excel typo vs DB seed name should still match when unambiguous."""
    with session_scope() as session:
        session.add(Firm(name="Mr. Johnny Care Services (India) Pvt Ltd"))
        session.commit()

    with session_scope() as session:
        f = _resolve_firm(session, "Mr. Johnry Care Services (India) Pvt Ltd")
        assert f is not None
        assert "Johnny" in f.name


def test_coerce_date_dd_mm_yyyy() -> None:
    assert _coerce_date("28/04/2025") == date(2025, 4, 28)
    assert _coerce_date("19-05-2025") == date(2025, 5, 19)


def test_coerce_optional_money_emd_text() -> None:
    assert _coerce_optional_money("Nil") is None
    assert _coerce_optional_money("MSE Exemption") is None
    assert _coerce_optional_money("547500") == 547500.0
    assert _coerce_optional_money("54,75,000") == 5475000.0


def test_process_import_tenders_row() -> None:
    with session_scope() as session:
        session.add(Firm(name="Mr. Johnny Care Services (India) Pvt Ltd"))
        session.commit()

    mapping = {
        "firm_name": "firm_name",
        "bid_no": "bid_no",
        "organisation": "organisation",
        "department": "department",
        "state": "state",
        "location": "location",
        "publish_date": "publish_date",
        "due_date": "due_date",
        "tender_value": "tender_value",
        "emd": "emd",
        "participation_status": "participation_status",
    }
    data = [
        {
            "firm_name": "Mr. Johnry Care Services (India) Pvt Ltd",
            "bid_no": "GEM/2025/B/6177029",
            "organisation": "Medical College",
            "department": "Dept",
            "state": "UP",
            "location": "Kushinagar",
            "publish_date": "28/04/2025",
            "due_date": "19/05/2025",
            "tender_value": "54750000",
            "emd": "MSE Exemption",
            "participation_status": "PARTICIPATED",
        }
    ]

    with session_scope() as session:
        n, errs = process_import(session, "Tenders", mapping, data)
        assert n == 1
        assert errs == []

    with session_scope() as session:
        from tender_erp.models.tender import Tender

        t = session.query(Tender).one()
        assert t.tender_value == 54750000.0
        assert t.emd is None
        assert t.participation_status == "PARTICIPATED"
