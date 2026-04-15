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

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
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
