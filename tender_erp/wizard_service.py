"""First-run onboarding wizard state (spec §3.6).

The wizard is split into discrete steps with a simple persisted
completion marker (``WizardState``). The UI layer walks through the
steps; this module holds the pure-logic helpers so tests can drive
them without Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from sqlalchemy.orm import Session

from .models.checklist import ChecklistRule
from .models.compliance import ComplianceDocument
from .models.firm import Firm


class WizardStep(IntEnum):
    WELCOME = 0
    SEED_RULES = 1
    CONFIRM_BASE = 2
    UPLOAD_COMPLIANCE = 3
    DONE = 4


@dataclass
class WizardState:
    has_firms: bool
    has_rules: bool
    has_compliance_per_firm: bool
    current_step: WizardStep

    @property
    def is_complete(self) -> bool:
        return (
            self.has_firms
            and self.has_rules
            and self.has_compliance_per_firm
        )


def evaluate(session: Session) -> WizardState:
    """Look at the DB and return where the wizard should resume."""
    has_firms = session.query(Firm).filter(Firm.is_archived == False).count() > 0  # noqa: E712
    has_rules = session.query(ChecklistRule).count() > 0
    # Per spec §3.6: "upload at least one compliance certificate per
    # active firm so the lookup has data to compare against."
    has_compliance_per_firm = True
    if has_firms:
        active = session.query(Firm).filter(Firm.is_archived == False).all()  # noqa: E712
        for firm in active:
            cnt = (
                session.query(ComplianceDocument)
                .filter(ComplianceDocument.firm_id == firm.id)
                .count()
            )
            if cnt == 0:
                has_compliance_per_firm = False
                break

    if not has_firms:
        step = WizardStep.WELCOME
    elif not has_rules:
        step = WizardStep.SEED_RULES
    elif not has_compliance_per_firm:
        step = WizardStep.UPLOAD_COMPLIANCE
    else:
        step = WizardStep.DONE

    return WizardState(
        has_firms=has_firms,
        has_rules=has_rules,
        has_compliance_per_firm=has_compliance_per_firm,
        current_step=step,
    )


def checklist_generator_enabled(session: Session) -> bool:
    return evaluate(session).is_complete
