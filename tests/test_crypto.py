"""Unit tests for the crypto primitives."""

from __future__ import annotations

import pytest

from tender_erp.services import crypto


def test_password_hash_roundtrip():
    h = crypto.hash_password("hunter2")
    assert h != "hunter2"
    assert crypto.verify_password("hunter2", h) is True
    assert crypto.verify_password("wrong", h) is False


def test_password_hash_empty_rejected():
    with pytest.raises(ValueError):
        crypto.hash_password("")


def test_vault_blob_roundtrip():
    key = crypto.derive_vault_key("master-password")
    ct = crypto.encrypt_blob(key, "secret portal password")
    assert ct.startswith(crypto.VAULT_VERSION)
    assert crypto.decrypt_blob(key, ct) == "secret portal password"


def test_vault_blob_wrong_key_rejected():
    k1 = crypto.derive_vault_key("correct")
    k2 = crypto.derive_vault_key("wrong")
    ct = k1_ct = crypto.encrypt_blob(k1, "hello")
    with pytest.raises(Exception):
        crypto.decrypt_blob(k2, ct)
    assert k1_ct == ct


def test_vault_reuses_salt():
    k1 = crypto.derive_vault_key("master", b"\x00" * 16)
    k2 = crypto.derive_vault_key("master", b"\x00" * 16)
    assert k1.key == k2.key
    ct = crypto.encrypt_blob(k1, "same")
    assert crypto.decrypt_blob(k2, ct) == "same"
