"""User administration (spec §3.0). Admin-only."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..db import session_scope
from ..models.user import Role, User
from ..services import auth
from .event_bus import global_bus
from .widgets import make_table


class UserEditor(QDialog):
    def __init__(self, user: User | None, parent=None) -> None:
        super().__init__(parent)
        self.user_id = user.id if user else None
        self.setWindowTitle("Edit user" if user else "New user")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username = QLineEdit(user.username if user else "")
        if user:
            self.username.setReadOnly(True)
        self.full_name = QLineEdit(user.full_name if user else "")
        self.email = QLineEdit(user.email if user and user.email else "")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText(
            "Leave blank to keep current password" if user else "Choose a strong password"
        )
        self.role_cb = QComboBox()
        for r in Role:
            self.role_cb.addItem(r.value, r.value)
        if user:
            idx = self.role_cb.findData(user.role)
            if idx >= 0:
                self.role_cb.setCurrentIndex(idx)
        self.active = QCheckBox("Active")
        self.active.setChecked(user.is_active if user else True)

        form.addRow("Username *", self.username)
        form.addRow("Full name *", self.full_name)
        form.addRow("Email", self.email)
        form.addRow("Password", self.password)
        form.addRow("Role", self.role_cb)
        form.addRow("", self.active)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self) -> None:
        uname = self.username.text().strip()
        full = self.full_name.text().strip()
        pwd = self.password.text()
        if not uname or not full:
            QMessageBox.warning(self, "Validation", "Username and full name are required.")
            return
        if self.user_id is None and not pwd:
            QMessageBox.warning(self, "Validation", "Set an initial password.")
            return
        with session_scope() as session:
            if self.user_id is None:
                try:
                    u = auth.create_user(
                        session,
                        username=uname,
                        full_name=full,
                        password=pwd,
                        role=self.role_cb.currentData(),
                        email=self.email.text().strip() or None,
                    )
                except ValueError as exc:
                    QMessageBox.warning(self, "Error", str(exc))
                    return
                u.is_active = self.active.isChecked()
            else:
                user = session.get(User, self.user_id)
                if user is None:
                    return
                user.full_name = full
                user.email = self.email.text().strip() or None
                user.role = self.role_cb.currentData()
                user.is_active = self.active.isChecked()
                if pwd:
                    auth.set_password(session, user, pwd)
        self.accept()


class UsersView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.new_btn = QPushButton("New user")
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        self.delete_many_btn = QPushButton("Delete selected")
        self.refresh_btn = QPushButton("Refresh")
        bar.addWidget(self.new_btn)
        bar.addWidget(self.edit_btn)
        bar.addWidget(self.delete_btn)
        bar.addWidget(self.delete_many_btn)
        bar.addStretch(1)
        bar.addWidget(self.refresh_btn)
        layout.addLayout(bar)

        self.table = make_table(
            ["", "Username", "Full name", "Role", "Active", "Last login"],
            extended_selection=True,
        )
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self._new)
        self.edit_btn.clicked.connect(self._edit)
        self.delete_btn.clicked.connect(self._delete)
        self.delete_many_btn.clicked.connect(self._delete_many)
        self.refresh_btn.clicked.connect(self.refresh)
        self.refresh()

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _checked_ids(self) -> list[int]:
        out: list[int] = []
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and it.checkState() == Qt.CheckState.Checked:
                rid = it.data(Qt.ItemDataRole.UserRole)
                if rid is not None:
                    out.append(int(rid))
        return out

    def refresh(self) -> None:
        with session_scope() as session:
            users = session.query(User).order_by(User.username).all()
            self.table.setRowCount(len(users))
            for r, u in enumerate(users):
                sel = QTableWidgetItem("")
                sel.setFlags(
                    sel.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEnabled
                )
                sel.setCheckState(Qt.CheckState.Unchecked)
                sel.setData(Qt.ItemDataRole.UserRole, u.id)
                self.table.setItem(r, 0, sel)
                self.table.setItem(r, 1, QTableWidgetItem(u.username))
                self.table.setItem(r, 2, QTableWidgetItem(u.full_name))
                self.table.setItem(r, 3, QTableWidgetItem(u.role))
                self.table.setItem(r, 4, QTableWidgetItem("yes" if u.is_active else "no"))
                self.table.setItem(
                    r,
                    5,
                    QTableWidgetItem(
                        u.last_login_at.isoformat(timespec="minutes")
                        if u.last_login_at
                        else "-"
                    ),
                )

    def _new(self) -> None:
        dlg = UserEditor(None, self)
        if dlg.exec():
            self.refresh()

    def _edit(self) -> None:
        uid = self._selected_id()
        if uid is None:
            return
        with session_scope() as session:
            user = session.get(User, uid)
            if user is None:
                return
            session.expunge(user)
        dlg = UserEditor(user, self)
        if dlg.exec():
            self.refresh()

    def _delete(self) -> None:
        uid = self._selected_id()
        if uid is None:
            return
        if (
            QMessageBox.question(self, "Delete user", "Delete this user account?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        with session_scope() as session:
            user = session.get(User, uid)
            if user is None:
                return
            session.delete(user)
        global_bus.dataChanged.emit()
        self.refresh()

    def _delete_many(self) -> None:
        ids = self._checked_ids()
        if not ids:
            QMessageBox.information(self, "Delete", "Tick one or more rows in the first column.")
            return
        if (
            QMessageBox.question(
                self,
                "Delete users",
                f"Delete {len(ids)} selected user account(s)?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        with session_scope() as session:
            for uid in ids:
                user = session.get(User, uid)
                if user is not None:
                    session.delete(user)
        global_bus.dataChanged.emit()
        self.refresh()
