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


def seed_demo_data(session: Session) -> dict:
    """Seed realistic demo data for a fresh install.

    Creates 10 firms, 30 tenders, 20 compliance docs, and e-stamps
    in every status so the dashboard renders with visual data.
    """
    from datetime import date, timedelta, datetime
    from ..models.compliance import ComplianceDocument
    from ..models.estamp import Estamp
    from ..models.tender import Tender

    if session.query(Firm).count() > 5:
        return {"firms": 0, "tenders": 0, "compliance": 0, "estamps": 0}

    today = date.today()

    # 10 Firms with codes and colors
    firms_data = [
        ("Amaze Infrastructure Pvt Ltd", "AIPL", "#2563EB"),
        ("Catering Corp Ltd", "CCL", "#16A34A"),
        ("BEW Electrical Works", "BEW", "#D97706"),
        ("Evergreen Projects Ltd", "EPL", "#7C3AED"),
        ("Delhi Enterprises Ltd", "DEL", "#DC2626"),
        ("FoodBridge Ltd", "FBL", "#0891B2"),
        ("MKS Pune Construction", "MKS", "#EA580C"),
        ("HMC Mumbai Contractors", "HMC", "#4F46E5"),
        ("ISRO Consultancy", "ISRO", "#059669"),
        ("BHEL Electrical Supply", "BHEL", "#BE123C"),
    ]
    firms = []
    for name, code, color in firms_data:
        f = Firm(name=name, firm_code=code, firm_color_hex=color)
        session.add(f)
        session.flush()
        firms.append(f)

    # 30 Tenders across statuses
    statuses = ["In Progress", "Review", "Planning", "Draft", "Pending Docs", "Submitted"]
    portals = ["GeM", "eTender", "IREPS", "Other"]
    categories = ["Healthcare Kitchen", "Cafeteria", "Housekeeping", "Manpower Supply",
                   "Equipment Supply", "Security Services", "Laundry Service", "Pest Control"]
    orgs = ["GoI Portal", "State Hospital", "CPWD Delhi", "HAU Hisar",
            "MES Pune", "Indian Railways", "DRDO Lab", "NIT Warangal",
            "AIIMS Delhi", "IIT Bombay"]

    tender_count = 0
    for i in range(30):
        firm = firms[i % len(firms)]
        is_awarded = i < 5  # First 5 are awarded
        due_offset = (i - 10) * 3  # Mix of past, near, and far due dates
        status = statuses[i % len(statuses)] if not is_awarded else "Submitted"
        t = Tender(
            firm_id=firm.id,
            bid_no=f"GEM/2025/B/{1000 + i}",
            organisation=orgs[i % len(orgs)],
            portal=portals[i % len(portals)],
            category=categories[i % len(categories)],
            nature_of_work=categories[i % len(categories)],
            publish_date=today - timedelta(days=30 + i),
            due_date=today + timedelta(days=due_offset),
            tender_value=float((i + 1) * 500000 + 100000),
            emd=float((i + 1) * 5000),
            participation_status="Participated" if i < 20 else "Not Participated",
            our_status=status,
            technical_status="Qualified" if i < 15 else "Pending",
            financial_status="Qualified" if i < 10 else "Pending",
            awarded_flag=is_awarded,
            awarded_date=today - timedelta(days=i * 10) if is_awarded else None,
            awarded_value=float((i + 1) * 400000) if is_awarded else None,
            loa_po_number=f"PO-2025-{i:03d}" if is_awarded else None,
            execution_status="In Progress" if is_awarded and i < 3 else ("Completed" if is_awarded else None),
        )
        session.add(t)
        tender_count += 1
    session.flush()

    # 20 Compliance documents with varied expiry
    comp_types = ["Tax", "Labour", "Quality", "Operational", "Registration", "Financial"]
    comp_names = [
        "Professional Tax", "GST Registration", "PF Registration",
        "ES Compliance Cert", "ISO 9001:2015", "EPFO Registration",
        "ESIC Registration", "FSSAI License", "Fire Safety NOC",
        "Pollution Control Board NOC", "Contract Labour License",
        "Trade License", "Factory License", "MSME Udyam",
        "Shop & Establishment", "Drug License", "Food Safety Cert",
        "Turnover Certificate", "Net Worth Certificate", "NSIC Cert",
    ]
    comp_count = 0
    for i, name in enumerate(comp_names):
        firm = firms[i % len(firms)]
        # Vary expiry: some expired, some critical, some safe
        if i < 3:
            expiry_offset = -5 + i  # Expired or just expired
        elif i < 8:
            expiry_offset = 5 + i * 3  # Critical (< 30 days)
        else:
            expiry_offset = 60 + i * 10  # Safe
        doc = ComplianceDocument(
            firm_id=firm.id,
            document_name=name,
            document_type=comp_types[i % len(comp_types)],
            issuing_authority=f"Authority {i + 1}",
            issue_date=today - timedelta(days=365),
            expiry_date=today + timedelta(days=expiry_offset),
            status="Active" if expiry_offset > 0 else "Expired",
        )
        session.add(doc)
        comp_count += 1
    session.flush()

    # E-stamps in every status
    estamp_count = 0
    denoms = [100, 500, 1000, 5000, 10000]
    for i, firm in enumerate(firms[:6]):
        # Purchased stamps
        for d in denoms[:3]:
            session.add(Estamp(
                firm_id=firm.id, entry_date=today - timedelta(days=i * 5),
                quantity=10 + i * 2, unit_rate=d, denomination=d,
                status="purchased", purchase_date=today - timedelta(days=i * 5),
                vendor=f"Vendor {i+1}", voucher_number=f"V-{1000+i}",
            ))
            estamp_count += 1
        # Pending stamps
        session.add(Estamp(
            firm_id=firm.id, entry_date=today, quantity=5 + i,
            unit_rate=5000, denomination=5000, status="pending",
            pending_queued_at=datetime.utcnow(),
            pending_required_by=today + timedelta(days=7 + i),
            pending_reason=f"Upcoming bid GEM/2025/B/{1000+i}",
            estimated_cost=5000 * (5 + i),
        ))
        estamp_count += 1
        # Allocated stamps
        session.add(Estamp(
            firm_id=firm.id, entry_date=today - timedelta(days=10),
            quantity=3, unit_rate=1000, denomination=1000,
            status="allocated", purchase_date=today - timedelta(days=10),
        ))
        estamp_count += 1
        # Used stamps
        session.add(Estamp(
            firm_id=firm.id, entry_date=today - timedelta(days=30),
            quantity=2, unit_rate=500, denomination=500,
            status="used", purchase_date=today - timedelta(days=30),
        ))
        estamp_count += 1

    session.flush()
    return {"firms": len(firms), "tenders": tender_count, "compliance": comp_count, "estamps": estamp_count}
