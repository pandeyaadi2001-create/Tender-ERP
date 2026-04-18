"""Login dialog shown at app startup (spec §3.0)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QCheckBox,
)

from ..db import session_scope
from ..services import auth


class LoginDialog(QDialog):
    """Blocking dialog that returns a validated ``User`` on accept."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tender ERP — Sign in")
        self.setModal(True)
        self.setMinimumWidth(360)
        self._user_id: Optional[int] = None
        self._wants_remember_me: bool = False

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        
        self.remember_me = QCheckBox("Remember me (stay logged in)")
        form.addRow("", self.remember_me)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #c62828;")
        layout.addWidget(self.error_label)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @property
    def authenticated_user_id(self) -> Optional[int]:
        return self._user_id
        
    @property
    def wants_remember_me(self) -> bool:
        return self.remember_me.isChecked()

    def _on_accept(self) -> None:
        username = self.username.text().strip()
        password = self.password.text()
        if not username or not password:
            self.error_label.setText("Enter both username and password")
            return
        try:
            with session_scope() as session:
                user = auth.authenticate(session, username, password)
                self._user_id = user.id
        except auth.NeedsPasswordChange as exc:
            from PySide6.QtWidgets import QInputDialog
            new_pwd, ok = QInputDialog.getText(self, "Password Reset", "Set your new password:", QLineEdit.EchoMode.Password)
            if ok and new_pwd:
                with session_scope() as session:
                    from ..models.user import User
                    user = session.get(User, exc.user_id)
                    auth.set_password(session, user, new_pwd)
                self._user_id = exc.user_id
                self.accept()
            else:
                self.error_label.setText("Password reset required")
            return
        except auth.AccountLocked as exc:
            QMessageBox.warning(self, "Account locked", str(exc))
            self.error_label.setText(str(exc))
            return
        except auth.AccountDisabled as exc:
            self.error_label.setText(str(exc))
            return
        except auth.InvalidCredentials:
            self.error_label.setText("Invalid username or password")
            return
        self.accept()
