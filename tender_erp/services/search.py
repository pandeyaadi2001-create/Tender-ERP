"""Global search (spec §4.5).

Single entry point that hits bid no, organisation, department,
location, and certificate no across all firms. Case-insensitive
substring match — plenty for 50k rows; if the dataset grows we add
FTS5 later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..models.compliance import ComplianceDocument
from ..models.tender import Tender

ResultKind = Literal["tender", "compliance"]


@dataclass
class SearchResult:
    kind: ResultKind
    id: int
    firm_id: int
    title: str
    subtitle: str


def global_search(session: Session, query: str, limit: int = 50) -> list[SearchResult]:
    q = (query or "").strip()
    if not q:
        return []
    pat = f"%{q}%"
    tenders = session.scalars(
        select(Tender)
        .options(selectinload(Tender.firm))
        .where(
            or_(
                Tender.bid_no.ilike(pat),
                Tender.organisation.ilike(pat),
                Tender.department.ilike(pat),
                Tender.location.ilike(pat),
            )
        )
        .limit(limit)
    ).all()
    compliances = session.scalars(
        select(ComplianceDocument)
        .options(selectinload(ComplianceDocument.firm))
        .where(
            or_(
                ComplianceDocument.certificate_no.ilike(pat),
                ComplianceDocument.document_name.ilike(pat),
                ComplianceDocument.document_type.ilike(pat),
            )
        )
        .limit(limit)
    ).all()

    results: list[SearchResult] = []
    for t in tenders:
        firm_name = t.firm.name if t.firm else ""
        results.append(
            SearchResult(
                kind="tender",
                id=t.id,
                firm_id=t.firm_id,
                title=t.bid_no or t.organisation or f"Tender #{t.id}",
                subtitle=" / ".join(filter(None, [firm_name, t.organisation, t.department, t.location])),
            )
        )
    for c in compliances:
        firm_name = c.firm.name if c.firm else ""
        results.append(
            SearchResult(
                kind="compliance",
                id=c.id,
                firm_id=c.firm_id,
                title=c.document_name,
                subtitle=" / ".join(filter(None, [firm_name, c.certificate_no, c.document_type])),
            )
        )
    return results
