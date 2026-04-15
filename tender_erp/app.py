"""Qt application bootstrap.

Responsibilities in order:

1. Initialise the DB (create tables on first run).
2. If no users exist, prompt to create the initial admin + print the
   recovery key (spec §3.0).
3. Show the login dialog.
4. Build the main window and run the event loop.
"""

from __future__ import annotations

import secrets
import sys
from typing import Optional

from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox

from .config import APP_HOME, APP_NAME, ensure_dirs
from .db import init_db, session_scope
from .models.user import Role, User
from .services import auth
from .services.auth import CurrentSession


RECOVERY_KEY_PATH = APP_HOME / "admin_recovery_key.txt"


def _bootstrap_first_admin() -> Optional[int]:
    """If no user exists, walk the operator through creating the admin.

    Generates a one-time recovery key and writes it to the app home.
    The operator is expected to store it offline per the spec.
    """
    with session_scope() as session:
        if session.query(User).count() > 0:
            return None

    QMessageBox.information(
        None,
        "First-time setup",
        "No users exist. The next dialogs create the initial admin account.",
    )
    username, ok = QInputDialog.getText(None, "Admin username", "Username:")
    if not ok or not username.strip():
        return None
    full, ok = QInputDialog.getText(None, "Admin full name", "Full name:")
    if not ok or not full.strip():
        return None
    password, ok = QInputDialog.getText(
        None, "Admin password", "Password:", QLineEdit.EchoMode.Password
    )
    if not ok or not password:
        return None

    recovery = secrets.token_urlsafe(24)
    RECOVERY_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECOVERY_KEY_PATH.write_text(recovery)

    with session_scope() as session:
        user = auth.create_user(
            session,
            username=username.strip(),
            full_name=full.strip(),
            password=password,
            role=Role.ADMIN.value,
        )
        user_id = user.id

    QMessageBox.information(
        None,
        "Save this recovery key",
        f"Recovery key saved to {RECOVERY_KEY_PATH}\n\n"
        f"Key: {recovery}\n\n"
        "Store this offline. It is the only way to reset the admin "
        "password if it is forgotten.",
    )
    return user_id


def main(argv: list[str] | None = None) -> int:
    ensure_dirs()
    init_db()

    argv = argv or sys.argv
    qt_app = QApplication(argv)
    qt_app.setApplicationName(APP_NAME)

    _bootstrap_first_admin()

    from .ui.login_dialog import LoginDialog

    login = LoginDialog()
    if not login.exec():
        return 0
    if login.authenticated_user_id is None:
        return 0

    with session_scope() as session:
        user = session.get(User, login.authenticated_user_id)
        if user is None:
            return 1
        session.expunge(user)

    session_state = CurrentSession(user=user)

    from .ui.main_window import MainWindow

    window = MainWindow(session_state)
    window.show()
    return qt_app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
