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

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox

from .config import APP_HOME, APP_NAME, APP_ORG, ensure_dirs
from .db import init_db, session_scope
from .models.user import Role, User
from .services import auth
from .services.auth import CurrentSession


LIGHT_THEME_QSS = """
QWidget {
    background-color: #F7F8FA;
    color: #1A1D23;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
}
QDialog { background-color: #FFFFFF; }
QMainWindow { background-color: #F7F8FA; }

QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #E6E8EC;
    border-radius: 6px;
    padding: 6px 14px;
    color: #1A1D23;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #F3F4F6;
    border: 1px solid #D1D5DB;
}
QPushButton#primaryBtn {
    background-color: #2563EB;
    color: #FFFFFF;
    border: none;
}
QPushButton#primaryBtn:hover {
    background-color: #1D4ED8;
}
QPushButton#dangerBtn {
    background-color: #DC2626;
    color: #FFFFFF;
    border: none;
}

QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background-color: #FFFFFF;
    border: 1px solid #E6E8EC;
    border-radius: 6px;
    padding: 5px 8px;
    color: #1A1D23;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid #2563EB;
}

QTableWidget {
    background-color: #FFFFFF;
    alternate-background-color: #FAFBFC;
    border: 1px solid #E6E8EC;
    border-radius: 8px;
    gridline-color: #F3F4F6;
}
QHeaderView::section {
    background-color: #FAFBFC;
    color: #9CA3AF;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    padding: 8px 6px;
    border: none;
    border-bottom: 1px solid #E6E8EC;
    border-right: 1px solid #F3F4F6;
}
QTableWidget::item {
    padding: 6px 4px;
    border-bottom: 1px solid #F3F4F6;
}
QTableWidget::item:selected {
    background-color: #DBEAFE;
    color: #1D4ED8;
}

QTabWidget::pane {
    border: 1px solid #E6E8EC;
    border-radius: 8px;
    background-color: #FFFFFF;
}
QTabBar::tab {
    background-color: #F7F8FA;
    color: #6B7280;
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #E6E8EC;
    border-bottom: none;
    margin-right: 2px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #1A1D23;
    font-weight: 600;
    border-bottom: 2px solid #2563EB;
}
QTabBar::tab:hover:!selected {
    background-color: #EEF2FF;
    color: #2563EB;
}

QScrollBar:vertical {
    width: 8px;
    background: transparent;
}
QScrollBar::handle:vertical {
    background: #D1D5DB;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QMenuBar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E6E8EC;
    padding: 2px;
}
QMenuBar::item:selected {
    background-color: #EEF2FF;
    color: #2563EB;
    border-radius: 4px;
}
QMenu {
    background-color: #FFFFFF;
    border: 1px solid #E6E8EC;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item:selected {
    background-color: #EEF2FF;
    color: #2563EB;
}

QLabel {
    background-color: transparent;
}
QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #E6E8EC;
    border-radius: 8px;
    padding-top: 20px;
    margin-top: 8px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #6B7280;
}

QCheckBox {
    background-color: transparent;
}
"""


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
    qt_app.setStyleSheet(LIGHT_THEME_QSS)

    _bootstrap_first_admin()

    from .ui.login_dialog import LoginDialog
    
    settings = QSettings(APP_ORG, APP_NAME)
    saved_user_id = settings.value("session/user_id")
    
    user = None
    if saved_user_id is not None:
        try:
            with session_scope() as session:
                user = session.get(User, int(saved_user_id))
                if user is not None and user.is_active:
                    session.expunge(user)
                else:
                    user = None
        except Exception:
            user = None

    if user is None:
        login = LoginDialog()
        if not login.exec():
            return 0
        if login.authenticated_user_id is None:
            return 0

        if login.wants_remember_me:
            settings.setValue("session/user_id", login.authenticated_user_id)
        else:
            settings.remove("session/user_id")

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
