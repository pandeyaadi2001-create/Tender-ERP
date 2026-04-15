"""Role-based permission helpers.

The UI hides forbidden modules; these helpers are the second line of
defense enforced at the service / query layer (spec §4.7: "enforced at
the query layer, not just the UI").
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from ..models.user import Role
from .auth import CurrentSession

F = TypeVar("F", bound=Callable)


class PermissionDenied(PermissionError):
    pass


def require_admin(session: CurrentSession) -> None:
    if not session.user.is_admin:
        raise PermissionDenied("admin role required")


def require_editor(session: CurrentSession) -> None:
    if session.user.role not in (Role.ADMIN.value, Role.EDITOR.value):
        raise PermissionDenied("editor or admin role required")


def require_viewer(session: CurrentSession) -> None:
    # Everyone with a valid session is at least a viewer.
    if session.user.role not in (r.value for r in Role):
        raise PermissionDenied("unknown role")


def admin_only(func: F) -> F:
    """Decorator for service functions that take ``session: CurrentSession``."""

    @wraps(func)
    def wrapper(session: CurrentSession, *args, **kwargs):
        require_admin(session)
        return func(session, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


def editor_or_admin(func: F) -> F:
    @wraps(func)
    def wrapper(session: CurrentSession, *args, **kwargs):
        require_editor(session)
        return func(session, *args, **kwargs)

    return wrapper  # type: ignore[return-value]
