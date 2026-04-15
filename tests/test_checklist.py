"""Checklist generator tests."""

from __future__ import annotations

from datetime import date, timedelta

from tender_erp.db import session_scope
from tender_erp.models.compliance import ComplianceDocument
from tender_erp.models.firm import Firm
from tender_erp.models.tender import Tender
from tender_erp.seed_data import seed_checklist_rules
from tender_erp.services import checklist


def _make_firm_and_tender():
    with session_scope() as session:
        firm = Firm(name="Acme Ltd")
        session.add(firm)
        session.flush()
        tender = Tender(
            firm_id=firm.id,
            bid_no="GEM/2025/B/1",
            organisation="State Hospital",
            nature_of_work="Healthcare Kitchen",
            due_date=date.today() + timedelta(days=14),
            contract_period_months=12,
        )
        session.add(tender)
        session.flush()
        return firm.id, tender.id


def test_rule_library_seeds():
    with session_scope() as session:
        added = seed_checklist_rules(session)
        assert added > 10  # universal + conditional
        second = seed_checklist_rules(session)
        assert second == 0  # idempotent


def test_generator_produces_base_and_conditional_items():
    firm_id, tender_id = _make_firm_and_tender()
    with session_scope() as session:
        seed_checklist_rules(session)

    with session_scope() as session:
        tender = session.get(Tender, tender_id)
        items = checklist.build_items(session, tender)

    documents = {i.document for i in items}
    assert "PAN Card" in documents
    assert "FSSAI License" in documents  # from Healthcare Kitchen rule


def test_generator_marks_missing_as_red_and_valid_as_green():
    firm_id, tender_id = _make_firm_and_tender()
    with session_scope() as session:
        seed_checklist_rules(session)
        # Drop in one valid compliance doc that should satisfy "PAN Card".
        session.add(
            ComplianceDocument(
                firm_id=firm_id,
                document_name="PAN Card",
                document_type="Statutory",
                issue_date=date.today() - timedelta(days=30),
                expiry_date=date.today() + timedelta(days=365 * 5),
                status="Active",
            )
        )

    with session_scope() as session:
        tender = session.get(Tender, tender_id)
        items = checklist.build_items(session, tender)

    by_name = {i.document: i for i in items}
    assert by_name["PAN Card"].status == checklist.STATUS_GREEN
    assert by_name["FSSAI License"].status == checklist.STATUS_RED


def test_generator_marks_expiring_before_contract_end_as_amber():
    firm_id, tender_id = _make_firm_and_tender()
    with session_scope() as session:
        seed_checklist_rules(session)
        # GST valid for submission, but expires before the 12-month contract ends.
        session.add(
            ComplianceDocument(
                firm_id=firm_id,
                document_name="GST Registration Certificate",
                issue_date=date.today() - timedelta(days=30),
                expiry_date=date.today() + timedelta(days=60),
                status="Active",
            )
        )

    with session_scope() as session:
        tender = session.get(Tender, tender_id)
        items = checklist.build_items(session, tender)

    gst = next(i for i in items if "GST" in i.document)
    assert gst.status == checklist.STATUS_AMBER


def test_generator_save_instance_without_pdf():
    firm_id, tender_id = _make_firm_and_tender()
    with session_scope() as session:
        seed_checklist_rules(session)

    with session_scope() as session:
        tender = session.get(Tender, tender_id)
        items, inst = checklist.generate_checklist(session, tender, write_pdf=False)
        assert inst.id is not None
        assert inst.items_json
        assert len(items) > 0
