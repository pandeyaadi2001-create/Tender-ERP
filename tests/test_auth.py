"""Auth + lockout tests."""

from __future__ import annotations

import pytest

from tender_erp.db import session_scope
from tender_erp.models.user import Role
from tender_erp.services import auth


def _make_user(password: str = "hunter2") -> int:
    with session_scope() as session:
        user = auth.create_user(
            session,
            username="admin",
            full_name="Test Admin",
            password=password,
            role=Role.ADMIN.value,
        )
        return user.id


def test_create_and_authenticate():
    _make_user()
    with session_scope() as session:
        user = auth.authenticate(session, "admin", "hunter2")
        assert user.username == "admin"
        assert user.is_admin is True
        assert user.failed_login_count == 0


def test_wrong_password_counts_failure():
    _make_user()
    with session_scope() as session:
        with pytest.raises(auth.InvalidCredentials):
            auth.authenticate(session, "admin", "wrong")
    with session_scope() as session:
        user = auth.authenticate(session, "admin", "hunter2")
        assert user.failed_login_count == 0


def test_lockout_after_5_failures():
    _make_user()
    for _ in range(5):
        with session_scope() as session:
            with pytest.raises((auth.InvalidCredentials, auth.AccountLocked)):
                auth.authenticate(session, "admin", "wrong")
    with session_scope() as session:
        with pytest.raises(auth.AccountLocked):
            auth.authenticate(session, "admin", "hunter2")


def test_unknown_user_is_invalid_not_missing():
    with session_scope() as session:
        with pytest.raises(auth.InvalidCredentials):
            auth.authenticate(session, "nope", "whatever")


def test_duplicate_username_rejected():
    _make_user()
    with session_scope() as session:
        with pytest.raises(ValueError):
            auth.create_user(
                session,
                username="admin",
                full_name="Dup",
                password="x",
            )


def test_vault_session_reveal_window():
    vs = auth.VaultSession()
    assert vs.is_unlocked is False
    assert vs.reveal_allowed() is False
    vs.unlock("master", salt=b"\x00" * 16)
    assert vs.is_unlocked is True
    assert vs.reveal_allowed() is True
    vs.lock()
    assert vs.is_unlocked is False
