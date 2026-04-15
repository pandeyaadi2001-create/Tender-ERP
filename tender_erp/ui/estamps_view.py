"""E-stamp tracker view (spec §3.5)."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..db import session_scope
from ..models.estamp import Estamp
from ..models.firm import Firm
from ..services import audit as audit_svc
from ..services.validators import validate_estamp
from .widgets import make_date_edit, make_table


def _qdate(d: date | None) -> QDate:
    return QDate(d.year, d.month, d.day) if d else QDate.currentDate()


def _pydate(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class EstampEditor(QDialog):
    def __init__(self, row: Estamp | None, firms: list[Firm], parent=None) -> None:
        super().__init__(parent)
        self.row_id = row.id if row else None
        self.setWindowTitle("Edit E-Stamp" if row else "New E-Stamp")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.firm_cb = QComboBox()
        for f in firms:
            self.firm_cb.addItem(f.name, f.id)
        if row:
            idx = self.firm_cb.findData(row.firm_id)
            if idx >= 0:
                self.firm_cb.setCurrentIndex(idx)
        self.entry_date = make_date_edit(optional=False)
        self.entry_date.setDate(_qdate(row.entry_date if row else None))
        self.tender_name = QLineEdit(row.tender_name_text if row else "")
        self.quantity = QSpinBox()
        self.quantity.setMaximum(10000)
        self.quantity.setValue(row.quantity if row else 1)
        self.rate = QDoubleSpinBox()
        self.rate.setDecimals(2)
        self.rate.setMaximum(1e6)
        self.rate.setValue(row.unit_rate if row else 0.0)
        form.addRow("Firm *", self.firm_cb)
        form.addRow("Date *", self.entry_date)
        form.addRow("Tender name", self.tender_name)
        form.addRow("Quantity", self.quantity)
        form.addRow("Unit rate", self.rate)
        layout.addLayout(form)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self) -> None:
        payload = dict(
            firm_id=self.firm_cb.currentData(),
            entry_date=_pydate(self.entry_date.date()),
            tender_name_text=self.tender_name.text() or None,
            quantity=self.quantity.value(),
            unit_rate=self.rate.value(),
        )
        errors = validate_estamp(payload)
        if errors:
            QMessageBox.warning(self, "Validation", "\n".join(errors))
            return
        with session_scope() as session:
            if self.row_id:
                row = session.get(Estamp, self.row_id)
                if row is None:
                    return
                old = {k: getattr(row, k) for k in payload}
                for k, v in payload.items():
                    setattr(row, k, v)
                audit_svc.record(
                    session,
                    user_id=None,
                    table="estamps",
                    record_id=row.id,
                    action="update",
                    old=old,
                    new=payload,
                )
            else:
                row = Estamp(**payload)
                session.add(row)
                session.flush()
                audit_svc.record(
                    session,
                    user_id=None,
                    table="estamps",
                    record_id=row.id,
                    action="create",
                    new=payload,
                )
        self.accept()


class EstampsView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.new_btn = QPushButton("New entry")
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        self.refresh_btn = QPushButton("Refresh")
        bar.addWidget(self.new_btn)
        bar.addWidget(self.edit_btn)
        bar.addWidget(self.delete_btn)
        bar.addStretch(1)
        bar.addWidget(self.refresh_btn)
        layout.addLayout(bar)

        self.totals = QLabel()
        layout.addWidget(self.totals)

        self.table = make_table(["Date", "FY", "Firm", "Tender", "Qty", "Unit rate", "Total"])
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self._new)
        self.edit_btn.clicked.connect(self._edit)
        self.delete_btn.clicked.connect(self._delete)
        self.refresh_btn.clicked.connect(self.refresh)
        self.refresh()

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def refresh(self) -> None:
        with session_scope() as session:
            rows = session.query(Estamp).order_by(Estamp.entry_date.desc()).all()
            self.table.setRowCount(len(rows))
            total_qty = 0
            total_spent = 0.0
            for r, e in enumerate(rows):
                item = QTableWidgetItem(e.entry_date.isoformat())
                item.setData(Qt.ItemDataRole.UserRole, e.id)
                self.table.setItem(r, 0, item)
                self.table.setItem(r, 1, QTableWidgetItem(e.financial_year))
                self.table.setItem(r, 2, QTableWidgetItem(e.firm.name if e.firm else "-"))
                self.table.setItem(r, 3, QTableWidgetItem(e.tender_name_text or "-"))
                self.table.setItem(r, 4, QTableWidgetItem(str(e.quantity)))
                self.table.setItem(r, 5, QTableWidgetItem(f"{e.unit_rate:,.2f}"))
                self.table.setItem(r, 6, QTableWidgetItem(f"{e.total:,.2f}"))
                total_qty += e.quantity
                total_spent += e.total
        self.totals.setText(f"<b>Total: {total_qty} stamps — ₹{total_spent:,.2f}</b>")

    def _firms(self) -> list[Firm]:
        with session_scope() as session:
            firms = (
                session.query(Firm)
                .filter(Firm.is_archived == False)  # noqa: E712
                .order_by(Firm.name)
                .all()
            )
            for f in firms:
                session.expunge(f)
            return firms

    def _new(self) -> None:
        firms = self._firms()
        if not firms:
            QMessageBox.warning(self, "No firms", "Create a firm first.")
            return
        dlg = EstampEditor(None, firms, self)
        if dlg.exec():
            self.refresh()

    def _edit(self) -> None:
        eid = self._selected_id()
        if eid is None:
            return
        with session_scope() as session:
            row = session.get(Estamp, eid)
            if row is None:
                return
            session.expunge(row)
        dlg = EstampEditor(row, self._firms(), self)
        if dlg.exec():
            self.refresh()

    def _delete(self) -> None:
        eid = self._selected_id()
        if eid is None:
            return
        confirm = QMessageBox.question(self, "Delete", "Delete this entry?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        with session_scope() as session:
            row = session.get(Estamp, eid)
            if row is None:
                return
            session.delete(row)
            audit_svc.record(
                session,
                user_id=None,
                table="estamps",
                record_id=eid,
                action="delete",
            )
        self.refresh()
