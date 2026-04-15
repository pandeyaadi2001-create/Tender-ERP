"""Starter rule library + universal base documents (spec §3.6).

The first-run wizard seeds the DB with these so the checklist
generator is immediately useful. Admins are expected to edit the
list through ``Settings → Checklist Rules``. Each tuple is
``(rule_name, condition_field, condition_value, required_document)``.
"""

from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from .models.checklist import ChecklistRule
from .models.compliance import ComplianceTemplate
from .models.firm import Firm

# --- universal base documents -------------------------------------------

UNIVERSAL_DOCUMENTS: tuple[str, ...] = (
    "PAN Card",
    "GST Registration Certificate",
    "Udyam / MSME Certificate",
    "Income Tax Return – last 3 years",
    "Bank Statement – last 6 months",
    "Cancelled Cheque",
    "Authorisation Letter",
    "MSE Preference Certificate",
    "EMD Proof / BG",
    "Tender Fee Proof",
    "Affidavit – No Blacklisting",
    "Affidavit – Compliance Declaration",
)

# --- conditional rules ---------------------------------------------------

CONDITIONAL_RULES: tuple[tuple[str, str, str, str], ...] = (
    # Healthcare Kitchen
    ("Healthcare Kitchen – FSSAI", "nature_of_work", "Healthcare Kitchen", "FSSAI License"),
    (
        "Healthcare Kitchen – Pollution Control",
        "nature_of_work",
        "Healthcare Kitchen",
        "Pollution Control Board NOC",
    ),
    (
        "Healthcare Kitchen – Fire NOC",
        "nature_of_work",
        "Healthcare Kitchen",
        "Fire Safety NOC",
    ),
    # Cafeteria
    ("Cafeteria – FSSAI", "nature_of_work", "Cafeteria", "FSSAI License"),
    ("Cafeteria – Trade License", "nature_of_work", "Cafeteria", "Municipal Trade License"),
    # Laundry
    (
        "Laundry – Pollution Control",
        "nature_of_work",
        "Laundry Service",
        "Pollution Control Board NOC",
    ),
    (
        "Laundry – Water Discharge Consent",
        "nature_of_work",
        "Laundry Service",
        "Water Discharge Consent",
    ),
    # Equipment Supply
    (
        "Equipment Supply – OEM Authorisation",
        "nature_of_work",
        "Equipment Supply",
        "OEM Authorisation Letter",
    ),
    (
        "Equipment Supply – MAF",
        "nature_of_work",
        "Equipment Supply",
        "Manufacturer Authorisation Form (MAF)",
    ),
    (
        "Equipment Supply – Datasheet",
        "nature_of_work",
        "Equipment Supply",
        "Product Datasheet / Brochure",
    ),
    # Housekeeping
    (
        "Housekeeping – EPFO Registration",
        "nature_of_work",
        "Housekeeping",
        "EPFO Registration",
    ),
    ("Housekeeping – ESIC Registration", "nature_of_work", "Housekeeping", "ESIC Registration"),
    (
        "Housekeeping – Labour License",
        "nature_of_work",
        "Housekeeping",
        "Contract Labour License",
    ),
    # Manpower Supply
    (
        "Manpower Supply – EPFO Registration",
        "nature_of_work",
        "Manpower Supply",
        "EPFO Registration",
    ),
    (
        "Manpower Supply – ESIC Registration",
        "nature_of_work",
        "Manpower Supply",
        "ESIC Registration",
    ),
    (
        "Manpower Supply – Labour License",
        "nature_of_work",
        "Manpower Supply",
        "Contract Labour License",
    ),
    # Pest Control
    ("Pest Control – CIB License", "nature_of_work", "Pest Control", "CIB Licence"),
    (
        "Pest Control – Trained Operator",
        "nature_of_work",
        "Pest Control",
        "Trained Operator Certificate",
    ),
    # Security Services
    (
        "Security Services – PSARA License",
        "nature_of_work",
        "Security Services",
        "PSARA Licence",
    ),
    (
        "Security Services – Police Verification",
        "nature_of_work",
        "Security Services",
        "Police Verification Reports",
    ),
)


# --- compliance templates per "known" firm ------------------------------

DEFAULT_COMPLIANCE_TEMPLATE: tuple[tuple[str, str, int], ...] = (
    ("PAN Card", "Statutory", 120),
    ("GST Registration Certificate", "Statutory", 60),
    ("Udyam / MSME Certificate", "Statutory", 60),
    ("ISO 9001 Certificate", "Quality", 36),
    ("ISO 14001 Certificate", "Quality", 36),
    ("EPFO Registration", "Labour", 60),
    ("ESIC Registration", "Labour", 60),
    ("FSSAI License", "Food", 12),
)


def seed_checklist_rules(session: Session, *, include_base: bool = True) -> int:
    """Insert starter rules if none exist. Returns number inserted."""
    if session.query(ChecklistRule).count() > 0:
        return 0
    count = 0
    if include_base:
        for doc in UNIVERSAL_DOCUMENTS:
            session.add(
                ChecklistRule(
                    name=f"Base – {doc}",
                    condition_field="*",
                    condition_value=None,
                    required_document=doc,
                )
            )
            count += 1
    for name, field, value, doc in CONDITIONAL_RULES:
        session.add(
            ChecklistRule(
                name=name,
                condition_field=field,
                condition_value=value,
                required_document=doc,
            )
        )
        count += 1
    session.flush()
    return count


def seed_compliance_templates(session: Session, firm: Firm) -> int:
    """Attach the default compliance template to a firm."""
    existing = {t.document_name for t in firm.compliance_templates}
    added = 0
    for name, kind, validity in DEFAULT_COMPLIANCE_TEMPLATE:
        if name in existing:
            continue
        session.add(
            ComplianceTemplate(
                firm_id=firm.id,
                document_name=name,
                document_type=kind,
                default_validity_months=validity,
            )
        )
        added += 1
    session.flush()
    return added


def seed_known_firms(session: Session) -> list[Firm]:
    """Create the firms listed in spec §2 if they don't exist yet."""
    names: Iterable[str] = (
        "Mr. Johnny Care Services (India) Pvt Ltd",
        "Green Foods",
        "AV Engineers",
        "I-Nova Healthcare",
    )
    created = []
    for name in names:
        if session.query(Firm).filter_by(name=name).first():
            continue
        firm = Firm(name=name)
        session.add(firm)
        created.append(firm)
    session.flush()
    return created
