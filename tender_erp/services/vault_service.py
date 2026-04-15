"""CRUD wrappers that transparently encrypt/decrypt vault fields.

The UI calls these instead of touching ``VaultCredential`` directly —
that way there's a single bottleneck where the encrypted fields are
handled and we can guarantee no plaintext leaks into the DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from ..models.vault import VaultCredential
from .crypto import VaultKey, decrypt_blob, encrypt_blob


@dataclass
class PlainCredential:
    """In-memory decrypted representation. Never persist this."""

    id: int | None
    firm_id: int
    portal_name: str
    portal_url: str | None
    username: str | None
    password: str | None
    security_question: str | None
    security_answer: str | None
    registered_mobile: str | None
    registered_email: str | None
    dsc_holder: str | None
    dsc_expiry: Optional[object]
    notes: str | None


def _encrypt_optional(key: VaultKey, value: str | None) -> bytes | None:
    if value is None:
        return None
    return encrypt_blob(key, value)


def _decrypt_optional(key: VaultKey, blob: bytes | None) -> str | None:
    if blob is None:
        return None
    return decrypt_blob(key, blob)


def create_credential(
    session: Session, key: VaultKey, data: PlainCredential
) -> VaultCredential:
    cred = VaultCredential(
        firm_id=data.firm_id,
        portal_name=data.portal_name,
        portal_url=data.portal_url,
        username_enc=_encrypt_optional(key, data.username),
        password_enc=_encrypt_optional(key, data.password),
        security_question=data.security_question,
        security_answer_enc=_encrypt_optional(key, data.security_answer),
        registered_mobile=data.registered_mobile,
        registered_email=data.registered_email,
        dsc_holder=data.dsc_holder,
        dsc_expiry=data.dsc_expiry,  # type: ignore[arg-type]
        notes=data.notes,
    )
    session.add(cred)
    session.flush()
    return cred


def update_credential(
    session: Session, key: VaultKey, cred: VaultCredential, data: PlainCredential
) -> VaultCredential:
    cred.portal_name = data.portal_name
    cred.portal_url = data.portal_url
    cred.username_enc = _encrypt_optional(key, data.username)
    cred.password_enc = _encrypt_optional(key, data.password)
    cred.security_question = data.security_question
    cred.security_answer_enc = _encrypt_optional(key, data.security_answer)
    cred.registered_mobile = data.registered_mobile
    cred.registered_email = data.registered_email
    cred.dsc_holder = data.dsc_holder
    cred.dsc_expiry = data.dsc_expiry  # type: ignore[assignment]
    cred.notes = data.notes
    session.flush()
    return cred


def decrypt_credential(key: VaultKey, cred: VaultCredential) -> PlainCredential:
    return PlainCredential(
        id=cred.id,
        firm_id=cred.firm_id,
        portal_name=cred.portal_name,
        portal_url=cred.portal_url,
        username=_decrypt_optional(key, cred.username_enc),
        password=_decrypt_optional(key, cred.password_enc),
        security_question=cred.security_question,
        security_answer=_decrypt_optional(key, cred.security_answer_enc),
        registered_mobile=cred.registered_mobile,
        registered_email=cred.registered_email,
        dsc_holder=cred.dsc_holder,
        dsc_expiry=cred.dsc_expiry,
        notes=cred.notes,
    )
