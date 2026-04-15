"""Crypto primitives for the password vault.

Two layers live here:

1. **User-account password hashing** — Argon2id via ``argon2-cffi``.
   Uses the project's tuned parameters from ``config.SETTINGS``.
2. **Vault record encryption** — a symmetric key derived from the
   admin's master password (Argon2 raw hash) is used to encrypt vault
   field blobs with AES-256-GCM. Ciphertext format on disk:
   ``b"v1" || 12-byte nonce || ciphertext+tag``.

The ``VaultKey`` is kept in memory only. Never log it. Never pickle
it. Never write it to disk.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError
from argon2.low_level import Type as LowType
from argon2.low_level import hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import SETTINGS

# --- user-account password hashing --------------------------------------

_password_hasher = PasswordHasher(
    time_cost=SETTINGS.argon2_time_cost,
    memory_cost=SETTINGS.argon2_memory_cost,
    parallelism=SETTINGS.argon2_parallelism,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


def hash_password(password: str) -> str:
    """Return an Argon2id hash string suitable for ``User.password_hash``."""
    if not password:
        raise ValueError("password must not be empty")
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time verification. Returns ``False`` on mismatch."""
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


# --- vault encryption ----------------------------------------------------

VAULT_SALT_BYTES = 16
VAULT_KEY_LEN = 32  # AES-256
VAULT_NONCE_LEN = 12
VAULT_VERSION = b"v1"


@dataclass(frozen=True)
class VaultKey:
    """An in-memory AES-256 key derived from the master password."""

    key: bytes
    salt: bytes  # kept so we can re-derive for backups/exports

    def aesgcm(self) -> AESGCM:
        return AESGCM(self.key)


def _kdf(password: str, salt: bytes) -> bytes:
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=SETTINGS.argon2_time_cost,
        memory_cost=SETTINGS.argon2_memory_cost,
        parallelism=SETTINGS.argon2_parallelism,
        hash_len=VAULT_KEY_LEN,
        type=LowType.ID,
    )


def derive_vault_key(master_password: str, salt: Optional[bytes] = None) -> VaultKey:
    """Derive a vault key from a master password + salt.

    If ``salt`` is omitted a new random salt is generated. The salt is
    *not* secret but must be stored alongside whatever the key will
    decrypt (we put it in the app settings row).
    """
    if not master_password:
        raise ValueError("master password must not be empty")
    salt = salt or os.urandom(VAULT_SALT_BYTES)
    return VaultKey(key=_kdf(master_password, salt), salt=salt)


def encrypt_blob(key: VaultKey, plaintext: str) -> bytes:
    """Encrypt a UTF-8 string field with AES-256-GCM.

    Returns ``VAULT_VERSION || nonce || ciphertext_tag``.
    """
    if plaintext is None:
        raise ValueError("plaintext must not be None")
    nonce = os.urandom(VAULT_NONCE_LEN)
    ct = key.aesgcm().encrypt(nonce, plaintext.encode("utf-8"), None)
    return VAULT_VERSION + nonce + ct


def decrypt_blob(key: VaultKey, blob: bytes) -> str:
    if blob is None:
        raise ValueError("blob must not be None")
    if len(blob) < len(VAULT_VERSION) + VAULT_NONCE_LEN + 16:
        raise ValueError("vault blob too short")
    if blob[: len(VAULT_VERSION)] != VAULT_VERSION:
        raise ValueError("unsupported vault blob version")
    nonce = blob[len(VAULT_VERSION) : len(VAULT_VERSION) + VAULT_NONCE_LEN]
    ct = blob[len(VAULT_VERSION) + VAULT_NONCE_LEN :]
    return key.aesgcm().decrypt(nonce, ct, None).decode("utf-8")
