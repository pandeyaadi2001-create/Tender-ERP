"""Field validation and normalization."""

from __future__ import annotations

from datetime import date

from tender_erp.services import validators


def test_firm_trims_and_uppercases():
    payload = {
        "name": "  Acme Ltd  ",
        "gstin": " 27aapfu0939f1zv ",
        "pan": "aapfu0939f",
    }
    errors = validators.validate_firm(payload)
    assert errors == []
    assert payload["name"] == "Acme Ltd"
    assert payload["gstin"] == "27AAPFU0939F1ZV"
    assert payload["pan"] == "AAPFU0939F"


def test_firm_rejects_bad_gstin_and_pan():
    payload = {"name": "X", "gstin": "bogus", "pan": "BAD"}
    errors = validators.validate_firm(payload)
    assert "GSTIN format is invalid" in errors
    assert "PAN format is invalid" in errors


def test_tender_trailing_spaces_normalized():
    payload = {
        "firm_id": 1,
        "bid_no": " GEM/2025/B/6177029 ",
        "organisation": "  State Hospital  ",
        "tender_value": "125000",
    }
    errors = validators.validate_tender(payload)
    assert errors == []
    assert payload["bid_no"] == "GEM/2025/B/6177029"
    assert payload["organisation"] == "State Hospital"
    assert payload["tender_value"] == 125000.0


def test_tender_emd_exceeding_value_rejected():
    payload = {"firm_id": 1, "tender_value": 1000, "emd": 5000}
    errors = validators.validate_tender(payload)
    assert any("EMD" in e for e in errors)


def test_tender_due_before_publish_rejected():
    payload = {
        "firm_id": 1,
        "publish_date": date(2025, 5, 10),
        "due_date": date(2025, 5, 1),
    }
    errors = validators.validate_tender(payload)
    assert any("Due date" in e for e in errors)


def test_compliance_requires_document_name():
    errors = validators.validate_compliance({"firm_id": 1})
    assert "Document name is required" in errors


def test_compliance_expiry_before_issue_rejected():
    errors = validators.validate_compliance(
        {
            "firm_id": 1,
            "document_name": "GST",
            "issue_date": date(2025, 1, 1),
            "expiry_date": date(2024, 1, 1),
        }
    )
    assert any("Expiry" in e for e in errors)


def test_estamp_validates_numeric_fields():
    errors = validators.validate_estamp(
        {"firm_id": 1, "entry_date": date.today(), "quantity": "3", "unit_rate": "100.50"}
    )
    assert errors == []
