"""Authentication, account lockout, and session state.

The GUI holds a single ``CurrentSession`` instance for the lifetime of
the main window. ``VaultSession`` is a thin companion that tracks when
the admin last re-authenticated against the vault — used to enforce
spec §3.4's "reveal password requires re-auth if more than X minutes".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SETTINGS
from ..models.user import Role, User
from .crypto import VaultKey, derive_vault_key, hash_password, verify_password


class AuthError(Exception):
    """Base class for authentication-related errors."""


class AccountLocked(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class AccountDisabled(AuthError):
    pass


class NeedsPasswordChange(AuthError):
    """Raised when the user must change their password (e.g., first login)."""
    def __init__(self, message: str, user_id: int):
        super().__init__(message)
        self.user_id = user_id


def create_user(
    session: Session,
    *,
    username: str,
    full_name: str,
    password: str,
    role: str = Role.EDITOR.value,
    email: str | None = None,
) -> User:
    """Create a new user with an Argon2id password hash."""
    if not username or not full_name or not password:
        raise ValueError("username, full_name and password are required")
    if role not in (r.value for r in Role):
        raise ValueError(f"unknown role {role!r}")
    existing = session.scalar(select(User).where(User.username == username))
    if existing is not None:
        raise ValueError(f"username {username!r} already exists")
    user = User(
        username=username,
        full_name=full_name,
        email=email,
        password_hash=hash_password(password),
        role=role,
    )
    session.add(user)
    session.flush()
    return user


def set_password(session: Session, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    session.flush()


def authenticate(session: Session, username: str, password: str) -> User:
    """Validate credentials and update lockout bookkeeping.

    Raises ``InvalidCredentials``, ``AccountLocked`` or ``AccountDisabled``.
    """
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        # Do one dummy verify so response time isn't a username oracle.
        verify_password(password, _DUMMY_HASH)
        raise InvalidCredentials("invalid username or password")
    if not user.is_active:
        raise AccountDisabled("account is disabled")
    now = datetime.utcnow()
    if user.locked_until and user.locked_until > now:
        raise AccountLocked(f"account locked until {user.locked_until.isoformat()}")

    if verify_password(password, user.password_hash):
        is_first_login = user.last_login_at is None
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        session.flush()
        if is_first_login:
            raise NeedsPasswordChange("First login: password reset required", user.id)
        return user

    user.failed_login_count += 1
    if user.failed_login_count >= SETTINGS.max_failed_logins:
        user.locked_until = now + timedelta(minutes=SETTINGS.lockout_minutes)
        user.failed_login_count = 0
        session.flush()
        raise AccountLocked(
            f"too many failed attempts; locked for {SETTINGS.lockout_minutes} min"
        )
    session.flush()
    raise InvalidCredentials("invalid username or password")


# A hash of a throwaway password kept so ``authenticate`` can run a
# matching verify when the username doesn't exist. Prevents timing
# oracles on account enumeration.
_DUMMY_HASH = hash_password("not-a-real-password-xxxx")


# --- Session state -------------------------------------------------------


@dataclass
class CurrentSession:
    """Live session attached to the GUI / CLI.

    Tracks the authenticated user and whether the 30-minute idle limit
    has elapsed. Not persisted across process restarts — the
    ``user_sessions`` table is for audit, not for resumption.
    """

    user: User
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_activity_at: datetime = field(default_factory=datetime.utcnow)
    vault: "VaultSession" = field(default_factory=lambda: VaultSession())

    def touch(self) -> None:
        self.last_activity_at = datetime.utcnow()

    def is_expired(self) -> bool:
        deadline = self.last_activity_at + timedelta(minutes=SETTINGS.session_timeout_minutes)
        return datetime.utcnow() > deadline

    def require_role(self, *roles: str) -> None:
        if self.user.role not in roles and not self.user.is_admin:
            raise PermissionError(f"requires one of {roles}, got {self.user.role}")


@dataclass
class VaultSession:
    """Re-auth window bookkeeping for the password vault.

    The vault key is only populated after the admin enters the master
    password. ``reveal_allowed`` checks the configurable reveal window
    (default 5 min) and forces a re-prompt if it's elapsed.
    """

    _key: Optional[VaultKey] = None
    _unlocked_at: Optional[datetime] = None
    _last_reveal_at: Optional[datetime] = None

    @property
    def is_unlocked(self) -> bool:
        return self._key is not None

    @property
    def key(self) -> VaultKey:
        if self._key is None:
            raise PermissionError("vault is locked")
        return self._key

    def unlock(self, master_password: str, salt: bytes) -> None:
        self._key = derive_vault_key(master_password, salt)
        self._unlocked_at = datetime.utcnow()
        self._last_reveal_at = self._unlocked_at

    def lock(self) -> None:
        self._key = None
        self._unlocked_at = None
        self._last_reveal_at = None

    def reveal_allowed(self) -> bool:
        if not self.is_unlocked or self._last_reveal_at is None:
            return False
        window = timedelta(minutes=SETTINGS.vault_reauth_minutes)
        return datetime.utcnow() - self._last_reveal_at <= window

    def mark_revealed(self) -> None:
        self._last_reveal_at = datetime.utcnow()
