"""Dashboard query tests."""

from __future__ import annotations

from datetime import date, timedelta

from tender_erp.db import session_scope
from tender_erp.models.compliance import ComplianceDocument
from tender_erp.models.estamp import Estamp
from tender_erp.models.firm import Firm
from tender_erp.models.tender import Tender
from tender_erp.services import dashboard


def _seed_world() -> int:
    with session_scope() as session:
        firm = Firm(name="Acme Ltd")
        session.add(firm)
        session.flush()
        today = date.today()
        session.add_all(
            [
                Tender(
                    firm_id=firm.id,
                    bid_no="A",
                    due_date=today + timedelta(days=2),
                    technical_status="PENDING",
                ),
                Tender(
                    firm_id=firm.id,
                    bid_no="B",
                    due_date=today + timedelta(days=20),
                ),
                ComplianceDocument(
                    firm_id=firm.id,
                    document_name="GST",
                    expiry_date=today + timedelta(days=15),
                    status="Active",
                ),
                ComplianceDocument(
                    firm_id=firm.id,
                    document_name="ISO",
                    expiry_date=today + timedelta(days=200),
                    status="Active",
                ),
                Estamp(firm_id=firm.id, entry_date=today, quantity=3, unit_rate=100.0, status="purchased"),
            ]
        )
        return firm.id


def test_snapshot_bucketing():
    _seed_world()
    with session_scope() as session:
        snap = dashboard.build_snapshot(session)
    assert snap.firm_count == 1
    assert len(snap.tenders_7d) == 1
    assert snap.tenders_7d[0].bid_no == "A"
    assert snap.tenders_8_to_30d_count == 1
    assert any(d.document_name == "GST" for d in snap.compliance_60d)
    assert not any(d.document_name == "ISO" for d in snap.compliance_60d)
    assert snap.estamp_mtd.count == 3
    assert snap.estamp_mtd.total_spent == 300.0
    assert snap.compliance_15d_count >= 1
    assert snap.estamp_status.purchased_count == 3
