"""Encrypted password vault (spec §3.4).

Every sensitive field (``username``, ``password``, ``security_answer``)
is stored as an AES-256-GCM ciphertext blob. The encryption key is
derived at runtime from the admin's master password via Argon2id — it
is never written to disk. See ``tender_erp.services.crypto`` for the
actual primitives and ``services.auth.VaultSession`` for the re-auth
window enforcement.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class VaultCredential(Base, TimestampMixin):
    __tablename__ = "vault_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    firm_id: Mapped[int] = mapped_column(ForeignKey("firms.id"), nullable=False, index=True)

    portal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    portal_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Ciphertext blobs. AES-GCM output layout (from crypto.py):
    # [12 bytes nonce][ciphertext+tag]. Plain ``None`` means "not set".
    username_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    password_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    security_question: Mapped[str | None] = mapped_column(String(255), nullable=True)
    security_answer_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    registered_mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    registered_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    dsc_holder: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dsc_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)

    last_changed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    firm = relationship("Firm", back_populates="vault_credentials")
