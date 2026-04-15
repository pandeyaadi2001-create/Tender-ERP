"""Password vault view (spec §3.4).

Admin-only. The widget refuses to render its table until the vault
session is unlocked. Every reveal passes through a re-auth check
against the configurable window in ``SETTINGS.vault_reauth_minutes``.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import SETTINGS
from ..db import session_scope
from ..models.vault import VaultCredential
from ..services.auth import CurrentSession
from ..services.crypto import derive_vault_key
from ..services.vault_service import PlainCredential, decrypt_credential
from .widgets import make_table

# The vault salt lives alongside the DB in a simple file. First unlock
# creates it. Losing this file means losing the vault — document
# prominently in README.
from pathlib import Path

from ..config import APP_HOME

SALT_PATH: Path = APP_HOME / "vault.salt"


def _get_or_create_salt() -> bytes:
    from os import urandom

    if SALT_PATH.exists():
        return SALT_PATH.read_bytes()
    SALT_PATH.parent.mkdir(parents=True, exist_ok=True)
    salt = urandom(16)
    SALT_PATH.write_bytes(salt)
    return salt


class VaultView(QWidget):
    def __init__(self, current_session: CurrentSession, parent=None) -> None:
        super().__init__(parent)
        self.session_state = current_session

        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.unlock_btn = QPushButton("Unlock vault")
        self.lock_btn = QPushButton("Lock")
        self.refresh_btn = QPushButton("Refresh")
        self.copy_btn = QPushButton("Copy password")
        bar.addWidget(self.unlock_btn)
        bar.addWidget(self.lock_btn)
        bar.addWidget(self.copy_btn)
        bar.addStretch(1)
        bar.addWidget(self.refresh_btn)
        layout.addLayout(bar)

        self.status = QLabel()
        layout.addWidget(self.status)

        self.table = make_table(
            ["Firm", "Portal", "URL", "Username", "DSC holder", "DSC expiry"]
        )
        layout.addWidget(self.table)

        self.unlock_btn.clicked.connect(self._unlock)
        self.lock_btn.clicked.connect(self._lock)
        self.refresh_btn.clicked.connect(self.refresh)
        self.copy_btn.clicked.connect(self._copy_password)
        self._update_status()

    # --- vault session gate --------------------------------------------
    def _update_status(self) -> None:
        if not self.session_state.user.is_admin:
            self.status.setText("<b>Vault is admin-only.</b>")
            for btn in (self.unlock_btn, self.lock_btn, self.refresh_btn, self.copy_btn):
                btn.setEnabled(False)
            return
        vault = self.session_state.vault
        if vault.is_unlocked:
            self.status.setText("Vault is <b>unlocked</b>. Lock when leaving your desk.")
        else:
            self.status.setText("Vault is locked. Unlock to reveal entries.")

    def _unlock(self) -> None:
        if not self.session_state.user.is_admin:
            return
        password, ok = QInputDialog.getText(
            self,
            "Master password",
            "Enter master password:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not password:
            return
        salt = _get_or_create_salt()
        try:
            self.session_state.vault.unlock(password, salt)
        except Exception as exc:
            QMessageBox.warning(self, "Unlock failed", str(exc))
            return
        self._update_status()
        self.refresh()

    def _lock(self) -> None:
        self.session_state.vault.lock()
        self.table.setRowCount(0)
        self._update_status()

    # --- table rendering -----------------------------------------------
    def refresh(self) -> None:
        if not self.session_state.vault.is_unlocked:
            self.table.setRowCount(0)
            return
        with session_scope() as session:
            creds = (
                session.query(VaultCredential).order_by(VaultCredential.portal_name).all()
            )
            self.table.setRowCount(len(creds))
            key = self.session_state.vault.key
            for r, c in enumerate(creds):
                plain = decrypt_credential(key, c)
                item = QTableWidgetItem(c.firm.name if c.firm else "-")
                item.setData(Qt.ItemDataRole.UserRole, c.id)
                self.table.setItem(r, 0, item)
                self.table.setItem(r, 1, QTableWidgetItem(c.portal_name))
                self.table.setItem(r, 2, QTableWidgetItem(c.portal_url or "-"))
                self.table.setItem(r, 3, QTableWidgetItem(plain.username or "-"))
                self.table.setItem(r, 4, QTableWidgetItem(c.dsc_holder or "-"))
                self.table.setItem(
                    r, 5, QTableWidgetItem(c.dsc_expiry.isoformat() if c.dsc_expiry else "-")
                )

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _copy_password(self) -> None:
        if not self.session_state.vault.is_unlocked:
            QMessageBox.information(self, "Vault", "Unlock the vault first.")
            return
        if not self.session_state.vault.reveal_allowed():
            # Re-auth required per spec §3.4.
            password, ok = QInputDialog.getText(
                self,
                "Re-auth required",
                f"Reveal window elapsed ({SETTINGS.vault_reauth_minutes} min). Enter master password:",
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return
            try:
                self.session_state.vault.unlock(password, _get_or_create_salt())
            except Exception:
                QMessageBox.warning(self, "Re-auth failed", "Wrong master password.")
                return
        cid = self._selected_id()
        if cid is None:
            return
        with session_scope() as session:
            cred = session.get(VaultCredential, cid)
            if cred is None:
                return
            plain = decrypt_credential(self.session_state.vault.key, cred)
        pwd = plain.password or ""
        if not pwd:
            QMessageBox.information(self, "Vault", "No password stored for this entry.")
            return
        cb = QGuiApplication.clipboard()
        cb.setText(pwd)
        self.session_state.vault.mark_revealed()
        QTimer.singleShot(
            SETTINGS.clipboard_clear_seconds * 1000,
            lambda: cb.text() == pwd and cb.clear(),
        )
        QMessageBox.information(
            self,
            "Copied",
            f"Password copied. Clipboard clears in {SETTINGS.clipboard_clear_seconds}s.",
        )
