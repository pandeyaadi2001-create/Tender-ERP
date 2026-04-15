"""Input validation and normalization (spec §4.8).

Run ``validate_tender`` / ``validate_compliance`` / ``validate_firm``
before hitting the DB. Each returns a list of error strings — empty
list means OK. They also mutate the payload in place to normalize
whitespace (the Excel had trailing spaces in Bid No.) and uppercase
IDs like GSTIN / PAN.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

GSTIN_RE = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


def _strip(d: dict[str, Any], key: str) -> None:
    v = d.get(key)
    if isinstance(v, str):
        d[key] = v.strip()


def _upper(d: dict[str, Any], key: str) -> None:
    v = d.get(key)
    if isinstance(v, str):
        d[key] = v.strip().upper()


def validate_firm(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _strip(payload, "name")
    _upper(payload, "gstin")
    _upper(payload, "pan")
    _upper(payload, "udyam")
    if not payload.get("name"):
        errors.append("Firm name is required")
    gstin = payload.get("gstin")
    if gstin and not GSTIN_RE.match(gstin):
        errors.append("GSTIN format is invalid")
    pan = payload.get("pan")
    if pan and not PAN_RE.match(pan):
        errors.append("PAN format is invalid")
    return errors


def validate_tender(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _strip(payload, "bid_no")
    _strip(payload, "organisation")
    _strip(payload, "department")

    if not payload.get("firm_id"):
        errors.append("firm_id is required")

    for field in ("tender_value", "emd", "publish_rate", "quoted_rates", "l1_rates"):
        v = payload.get(field)
        if v in (None, ""):
            continue
        try:
            payload[field] = float(v)
        except (TypeError, ValueError):
            errors.append(f"{field} must be numeric")

    pub = payload.get("publish_date")
    due = payload.get("due_date")
    if isinstance(pub, date) and isinstance(due, date) and due < pub:
        errors.append("Due date cannot be before publish date")

    tv = payload.get("tender_value")
    emd = payload.get("emd")
    if isinstance(tv, (int, float)) and isinstance(emd, (int, float)) and emd > tv:
        errors.append("EMD cannot exceed tender value")

    return errors


def validate_compliance(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _strip(payload, "certificate_no")
    _strip(payload, "document_name")
    if not payload.get("firm_id"):
        errors.append("firm_id is required")
    if not payload.get("document_name"):
        errors.append("Document name is required")
    issue = payload.get("issue_date")
    expiry = payload.get("expiry_date")
    if isinstance(issue, date) and isinstance(expiry, date) and expiry < issue:
        errors.append("Expiry date cannot be before issue date")
    return errors


def validate_estamp(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not payload.get("firm_id"):
        errors.append("firm_id is required")
    if not payload.get("entry_date"):
        errors.append("entry_date is required")
    try:
        qty = int(payload.get("quantity", 0))
        payload["quantity"] = qty
        if qty <= 0:
            errors.append("quantity must be positive")
    except (TypeError, ValueError):
        errors.append("quantity must be an integer")
    try:
        rate = float(payload.get("unit_rate", 0))
        payload["unit_rate"] = rate
        if rate < 0:
            errors.append("unit_rate cannot be negative")
    except (TypeError, ValueError):
        errors.append("unit_rate must be numeric")
    return errors
