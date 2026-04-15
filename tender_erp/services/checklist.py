"""Checklist generator (spec §3.6).

Given a tender, combine:

1. All active "universal" rules (``condition_field == '*'``).
2. All active conditional rules whose ``condition_field`` on the
   tender matches ``condition_value`` (case-insensitive).

For every required document, look up the firm's compliance tracker:

* Available + valid through the tender's due/contract end  → GREEN
* Available but expires before contract end                 → AMBER
* Missing or expired                                        → RED

Return a list of item dicts the UI can render and the PDF generator
can consume.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import CHECKLIST_DIR, ensure_dirs
from ..models.checklist import ChecklistInstance, ChecklistRule
from ..models.compliance import ComplianceDocument
from ..models.tender import Tender

STATUS_GREEN = "green"
STATUS_AMBER = "amber"
STATUS_RED = "red"


@dataclass
class ChecklistItem:
    document: str
    status: str  # green | amber | red
    source_rule: str
    compliance_id: int | None
    expiry_date: str | None
    note: str


def _contract_end(tender: Tender) -> date | None:
    if tender.due_date is None or not tender.contract_period_months:
        return tender.due_date
    return tender.due_date + timedelta(days=int(tender.contract_period_months * 30))


def _match(rule: ChecklistRule, tender: Tender) -> bool:
    if not rule.is_active:
        return False
    if rule.condition_field == "*":
        return True
    field = getattr(tender, rule.condition_field, None)
    if field is None:
        return False
    if rule.condition_value is None:
        return True
    return str(field).strip().lower() == rule.condition_value.strip().lower()


def _pick_doc(
    docs: Sequence[ComplianceDocument], required: str
) -> ComplianceDocument | None:
    """Best-effort match by document_name / document_type / certificate_no.

    Case-insensitive substring match. Prefers the non-expired document
    with the latest expiry date among multiple candidates.
    """
    key = required.strip().lower()
    cands = []
    for d in docs:
        haystack = " ".join(
            filter(
                None,
                [d.document_name, d.document_type or "", d.certificate_no or ""],
            )
        ).lower()
        if key in haystack:
            cands.append(d)
    if not cands:
        return None
    cands.sort(key=lambda d: d.expiry_date or date.min, reverse=True)
    return cands[0]


def build_items(session: Session, tender: Tender) -> list[ChecklistItem]:
    rules = list(session.scalars(select(ChecklistRule).where(ChecklistRule.is_active == True)))  # noqa: E712
    firm_docs = list(
        session.scalars(
            select(ComplianceDocument).where(ComplianceDocument.firm_id == tender.firm_id)
        )
    )

    seen: dict[str, ChecklistItem] = {}
    contract_end = _contract_end(tender)
    tender_due = tender.due_date or date.today()

    for rule in rules:
        if not _match(rule, tender):
            continue
        doc_name = rule.required_document.strip()
        if doc_name.lower() in seen:
            continue
        doc = _pick_doc(firm_docs, doc_name)
        if doc is None:
            item = ChecklistItem(
                document=doc_name,
                status=STATUS_RED,
                source_rule=rule.name,
                compliance_id=None,
                expiry_date=None,
                note="Not on file — must be procured before submission.",
            )
        elif doc.expiry_date is None:
            item = ChecklistItem(
                document=doc_name,
                status=STATUS_AMBER,
                source_rule=rule.name,
                compliance_id=doc.id,
                expiry_date=None,
                note="On file but expiry date unknown — verify manually.",
            )
        elif doc.expiry_date < tender_due:
            item = ChecklistItem(
                document=doc_name,
                status=STATUS_RED,
                source_rule=rule.name,
                compliance_id=doc.id,
                expiry_date=doc.expiry_date.isoformat(),
                note=f"Expired on {doc.expiry_date.isoformat()} — renew before submission.",
            )
        elif contract_end and doc.expiry_date < contract_end:
            item = ChecklistItem(
                document=doc_name,
                status=STATUS_AMBER,
                source_rule=rule.name,
                compliance_id=doc.id,
                expiry_date=doc.expiry_date.isoformat(),
                note=f"Valid for submission but expires {doc.expiry_date.isoformat()} before contract end.",
            )
        else:
            item = ChecklistItem(
                document=doc_name,
                status=STATUS_GREEN,
                source_rule=rule.name,
                compliance_id=doc.id,
                expiry_date=doc.expiry_date.isoformat() if doc.expiry_date else None,
                note="Valid through tender submission.",
            )
        seen[doc_name.lower()] = item

    # Sort: red first, then amber, then green.
    order = {STATUS_RED: 0, STATUS_AMBER: 1, STATUS_GREEN: 2}
    return sorted(seen.values(), key=lambda i: (order.get(i.status, 9), i.document))


def save_instance(
    session: Session,
    tender: Tender,
    items: list[ChecklistItem],
    pdf_path: Path | None = None,
) -> ChecklistInstance:
    inst = ChecklistInstance(
        tender_id=tender.id,
        generated_at=datetime.utcnow(),
        items_json=json.dumps([asdict(i) for i in items]),
        pdf_path=str(pdf_path) if pdf_path else None,
    )
    session.add(inst)
    session.flush()
    return inst


def render_pdf(
    tender: Tender, items: list[ChecklistItem], firm_name: str
) -> Path:
    """Write a checklist PDF using ReportLab.

    Lives next to the DB under ``CHECKLIST_DIR``. Filename embeds the
    tender id + timestamp so re-runs don't overwrite.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    ensure_dirs()
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    out = CHECKLIST_DIR / f"checklist_tender{tender.id}_{timestamp}.pdf"

    doc = SimpleDocTemplate(str(out), pagesize=A4, title="Submission Checklist")
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(f"<b>Submission Checklist</b>", styles["Title"]))
    story.append(Paragraph(f"Firm: {firm_name}", styles["Normal"]))
    story.append(Paragraph(f"Bid No: {tender.bid_no or '-'}", styles["Normal"]))
    story.append(Paragraph(f"Organisation: {tender.organisation or '-'}", styles["Normal"]))
    story.append(
        Paragraph(
            f"Due: {tender.due_date.isoformat() if tender.due_date else '-'}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 12))

    data = [["#", "Document", "Status", "Expiry", "Note"]]
    for idx, item in enumerate(items, start=1):
        data.append(
            [
                str(idx),
                item.document,
                item.status.upper(),
                item.expiry_date or "-",
                item.note,
            ]
        )
    table = Table(data, repeatRows=1, colWidths=[20, 160, 50, 70, 220])
    style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
    )
    for idx, item in enumerate(items, start=1):
        color = {
            STATUS_GREEN: colors.HexColor("#c8e6c9"),
            STATUS_AMBER: colors.HexColor("#ffe0b2"),
            STATUS_RED: colors.HexColor("#ffcdd2"),
        }.get(item.status, colors.white)
        style.add("BACKGROUND", (2, idx), (2, idx), color)
    table.setStyle(style)
    story.append(table)

    doc.build(story)
    return out


def generate_checklist(
    session: Session,
    tender: Tender,
    *,
    write_pdf: bool = True,
) -> tuple[list[ChecklistItem], ChecklistInstance]:
    items = build_items(session, tender)
    pdf_path: Path | None = None
    if write_pdf:
        try:
            pdf_path = render_pdf(tender, items, tender.firm.name if tender.firm else "-")
        except Exception:
            pdf_path = None
    instance = save_instance(session, tender, items, pdf_path)
    return items, instance


def is_rule_library_seeded(session: Session) -> bool:
    """First-run wizard gate (spec §3.6)."""
    return session.query(ChecklistRule).count() > 0
