"""First-run wizard state transitions."""

from __future__ import annotations

from datetime import date

from tender_erp.db import session_scope
from tender_erp.models.compliance import ComplianceDocument
from tender_erp.models.firm import Firm
from tender_erp.seed_data import seed_checklist_rules
from tender_erp.wizard_service import WizardStep, checklist_generator_enabled, evaluate


def test_wizard_starts_at_welcome():
    with session_scope() as session:
        state = evaluate(session)
        assert state.current_step == WizardStep.WELCOME
        assert state.is_complete is False
        assert checklist_generator_enabled(session) is False


def test_wizard_progress_through_steps():
    with session_scope() as session:
        session.add(Firm(name="Acme Ltd"))

    with session_scope() as session:
        state = evaluate(session)
        assert state.current_step == WizardStep.SEED_RULES

    with session_scope() as session:
        seed_checklist_rules(session)

    with session_scope() as session:
        state = evaluate(session)
        assert state.current_step == WizardStep.UPLOAD_COMPLIANCE

    with session_scope() as session:
        firm = session.query(Firm).first()
        session.add(
            ComplianceDocument(
                firm_id=firm.id,
                document_name="GST",
                expiry_date=date.today(),
                status="Active",
            )
        )

    with session_scope() as session:
        state = evaluate(session)
        assert state.current_step == WizardStep.DONE
        assert state.is_complete is True
        assert checklist_generator_enabled(session) is True
