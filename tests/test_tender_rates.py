"""Tests for kitchen/laundry publish rate formulas."""

from tender_erp.services.dashboard import is_participating_status
from tender_erp.services.tender_rates import computed_publish_rate_fields, service_kind


def test_service_kind():
    assert service_kind("Healthcare Kitchen", None) == "kitchen"
    assert service_kind(None, "Laundry Service") == "laundry"


def test_kitchen_rate():
    r = computed_publish_rate_fields(
        tender_value=900000.0,
        quantity=100.0,
        nature_of_work="Healthcare Kitchen",
        category=None,
        contract_period_months=None,
        service_days=30.0,
        period_in_days_fallback=None,
    )
    assert r is not None
    assert abs(r - 900000.0 / 30.0 / 100.0) < 0.01


def test_laundry_rate():
    r = computed_publish_rate_fields(
        tender_value=600000.0,
        quantity=500.0,
        nature_of_work="Laundry Service",
        category=None,
        contract_period_months=12.0,
        service_days=None,
        period_in_days_fallback=None,
    )
    assert r is not None
    assert abs(r - 600000.0 / 12.0 / 500.0) < 0.01


def test_participation_flags():
    assert is_participating_status("Participated")
    assert is_participating_status("PARTICIPATED IN SUPPORT")
    assert not is_participating_status("Not Participated")
