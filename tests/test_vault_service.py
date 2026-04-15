"""End-to-end vault CRUD: encryption, decryption, no plaintext on disk."""

from __future__ import annotations

from tender_erp.db import session_scope
from tender_erp.models.firm import Firm
from tender_erp.models.vault import VaultCredential
from tender_erp.services.crypto import derive_vault_key
from tender_erp.services.vault_service import (
    PlainCredential,
    create_credential,
    decrypt_credential,
    update_credential,
)


def test_vault_roundtrip_and_no_plaintext():
    key = derive_vault_key("master-password")
    with session_scope() as session:
        firm = Firm(name="Acme Ltd")
        session.add(firm)
        session.flush()

        plain = PlainCredential(
            id=None,
            firm_id=firm.id,
            portal_name="GeM",
            portal_url="https://gem.gov.in",
            username="acme-buyer",
            password="S3cret!",
            security_question="mother's maiden name",
            security_answer="smith",
            registered_mobile="+919876543210",
            registered_email="acme@example.com",
            dsc_holder="Director",
            dsc_expiry=None,
            notes="test entry",
        )
        cred = create_credential(session, key, plain)
        cred_id = cred.id

        # Ciphertext blobs must be bytes and must not equal the plaintext.
        assert isinstance(cred.username_enc, bytes)
        assert isinstance(cred.password_enc, bytes)
        assert b"S3cret!" not in cred.password_enc
        assert b"acme-buyer" not in cred.username_enc

    with session_scope() as session:
        cred = session.get(VaultCredential, cred_id)
        decrypted = decrypt_credential(key, cred)
        assert decrypted.username == "acme-buyer"
        assert decrypted.password == "S3cret!"

        update_credential(
            session,
            key,
            cred,
            PlainCredential(
                id=cred.id,
                firm_id=cred.firm_id,
                portal_name="GeM",
                portal_url=cred.portal_url,
                username="acme-buyer",
                password="NewPassword123",
                security_question=None,
                security_answer=None,
                registered_mobile=None,
                registered_email=None,
                dsc_holder=None,
                dsc_expiry=None,
                notes=None,
            ),
        )

    with session_scope() as session:
        cred = session.get(VaultCredential, cred_id)
        assert decrypt_credential(key, cred).password == "NewPassword123"
