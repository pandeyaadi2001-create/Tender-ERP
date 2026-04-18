"""Firm master CRUD (spec §3.1)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..db import session_scope
from ..models.firm import Firm
from ..services import audit as audit_svc
from ..services.validators import validate_firm
from .widgets import make_table
from .event_bus import global_bus


class FirmEditor(QDialog):
    def __init__(self, firm: Firm | None, parent=None) -> None:
        super().__init__(parent)
        self.firm_id = firm.id if firm else None
        self.setWindowTitle("Edit Firm" if firm else "New Firm")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name = QLineEdit(firm.name if firm else "")
        self.firm_code = QLineEdit(firm.firm_code if firm else "")
        self.firm_code.setPlaceholderText("e.g. AIPL, CCL, BEW")
        self.firm_color = QLineEdit(firm.firm_color_hex if firm else "")
        self.firm_color.setPlaceholderText("#2563EB")
        self.gstin = QLineEdit(firm.gstin if firm else "")
        self.pan = QLineEdit(firm.pan if firm else "")
        self.udyam = QLineEdit(firm.udyam if firm else "")
        self.address = QTextEdit(firm.address if firm and firm.address else "")
        self.address.setFixedHeight(80)
        self.firm_state = QLineEdit(firm.state if firm else "")
        self.contact_person = QLineEdit(firm.contact_person if firm else "")
        self.contact_phone = QLineEdit(firm.contact_phone if firm else "")
        self.contact_email = QLineEdit(firm.contact_email if firm else "")
        form.addRow("Legal name *", self.name)
        form.addRow("Firm Code *", self.firm_code)
        form.addRow("Color (hex)", self.firm_color)
        form.addRow("GSTIN", self.gstin)
        form.addRow("PAN", self.pan)
        form.addRow("Udyam/MSME", self.udyam)
        form.addRow("Address", self.address)
        form.addRow("State", self.firm_state)
        form.addRow("Contact person", self.contact_person)
        form.addRow("Phone", self.contact_phone)
        form.addRow("Email", self.contact_email)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self) -> None:
        payload = dict(
            name=self.name.text(),
            firm_code=self.firm_code.text().strip().upper() or None,
            firm_color_hex=self.firm_color.text().strip() or None,
            gstin=self.gstin.text(),
            pan=self.pan.text(),
            udyam=self.udyam.text(),
            address=self.address.toPlainText(),
            state=self.firm_state.text().strip() or None,
            contact_person=self.contact_person.text(),
            contact_phone=self.contact_phone.text(),
            contact_email=self.contact_email.text(),
        )
        errors = validate_firm(payload)
        if errors:
            QMessageBox.warning(self, "Validation", "\n".join(errors))
            return
        with session_scope() as session:
            if self.firm_id:
                firm = session.get(Firm, self.firm_id)
                if firm is None:
                    QMessageBox.warning(self, "Error", "Firm not found")
                    return
                old = {c: getattr(firm, c) for c in payload}
                for k, v in payload.items():
                    setattr(firm, k, v or None)
                audit_svc.record(
                    session,
                    user_id=None,
                    table="firms",
                    record_id=firm.id,
                    action="update",
                    old=old,
                    new=payload,
                )
            else:
                firm = Firm(**{k: v or None for k, v in payload.items()})
                session.add(firm)
                session.flush()
                audit_svc.record(
                    session,
                    user_id=None,
                    table="firms",
                    record_id=firm.id,
                    action="create",
                    new=payload,
                )
        self.accept()
        global_bus.dataChanged.emit()


class FirmsView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.new_btn = QPushButton("New firm")
        self.edit_btn = QPushButton("Edit")
        self.archive_btn = QPushButton("Archive")
        self.refresh_btn = QPushButton("Refresh")
        bar.addWidget(self.new_btn)
        bar.addWidget(self.edit_btn)
        bar.addWidget(self.archive_btn)
        bar.addStretch(1)
        bar.addWidget(self.refresh_btn)
        layout.addLayout(bar)

        self.table = make_table(["Name", "GSTIN", "PAN", "Udyam", "Contact", "Archived"])
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self._new)
        self.edit_btn.clicked.connect(self._edit)
        self.archive_btn.clicked.connect(self._archive)
        self.refresh_btn.clicked.connect(self.refresh)
        self.refresh()

    def _selected_firm_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def refresh(self) -> None:
        with session_scope() as session:
            firms = session.query(Firm).order_by(Firm.name).all()
            self.table.setRowCount(len(firms))
            for r, f in enumerate(firms):
                item = QTableWidgetItem(f.name)
                item.setData(Qt.ItemDataRole.UserRole, f.id)
                self.table.setItem(r, 0, item)
                self.table.setItem(r, 1, QTableWidgetItem(f.gstin or "-"))
                self.table.setItem(r, 2, QTableWidgetItem(f.pan or "-"))
                self.table.setItem(r, 3, QTableWidgetItem(f.udyam or "-"))
                self.table.setItem(r, 4, QTableWidgetItem(f.contact_person or "-"))
                self.table.setItem(r, 5, QTableWidgetItem("yes" if f.is_archived else "no"))

    def _new(self) -> None:
        dlg = FirmEditor(None, self)
        if dlg.exec():
            self.refresh()

    def _edit(self) -> None:
        fid = self._selected_firm_id()
        if fid is None:
            return
        with session_scope() as session:
            firm = session.get(Firm, fid)
            if firm is None:
                return
            session.expunge(firm)
        dlg = FirmEditor(firm, self)
        if dlg.exec():
            self.refresh()

    def _archive(self) -> None:
        fid = self._selected_firm_id()
        if fid is None:
            return
        with session_scope() as session:
            firm = session.get(Firm, fid)
            if firm is None:
                return
            firm.is_archived = not firm.is_archived
            audit_svc.record(
                session,
                user_id=None,
                table="firms",
                record_id=firm.id,
                action="update",
                note="archive toggled",
            )
        global_bus.dataChanged.emit()
        self.refresh()
