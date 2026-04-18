"""E-stamp tracker view with full lifecycle (spec §3.5 / §6).

Supports: Queue Purchase → Record Purchase → Edit → Delete
Status: Purchased / Pending Arrangement
Tracks actual cost paid (not face value).
"""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QSpinBox, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget, QTabBar,
)

from ..db import session_scope
from ..models.estamp import DENOMINATIONS, ESTAMP_STATUSES, STATUS_LABELS, Estamp
from ..models.firm import Firm
from ..models.tender import Tender
from ..services import audit as audit_svc
from .widgets import make_date_edit, make_money_spin, make_table
from .event_bus import global_bus


def _qdate(d: date | None) -> QDate:
    return QDate(d.year, d.month, d.day) if d else QDate.currentDate()

def _pydate(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


# ── E-Stamp Editor Dialog (Edit existing) ────────────────────────────

class EstampEditor(QDialog):
    """Edit an existing e-stamp entry."""
    def __init__(self, estamp_id: int, firms: list[Firm], parent=None):
        super().__init__(parent)
        self.estamp_id = estamp_id
        self.setWindowTitle("Edit E-Stamp")
        self.setMinimumWidth(480)

        # Load data
        with session_scope() as session:
            e = session.get(Estamp, estamp_id)
            if not e:
                QMessageBox.warning(self, "Error", "E-Stamp not found")
                return
            self._data = {
                "firm_id": e.firm_id,
                "denomination": e.denomination or e.unit_rate,
                "quantity": e.quantity,
                "status": e.status,
                "actual_cost": e.actual_cost,
                "entry_date": e.entry_date,
                "purchase_date": e.purchase_date,
                "vendor": e.vendor,
                "voucher_number": e.voucher_number,
                "pending_reason": e.pending_reason,
                "pending_required_by": e.pending_required_by,
            }

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.firm_cb = QComboBox()
        for f in firms:
            self.firm_cb.addItem(f.name, f.id)
        idx = self.firm_cb.findData(self._data["firm_id"])
        if idx >= 0:
            self.firm_cb.setCurrentIndex(idx)

        self.denomination_cb = QComboBox()
        for d in DENOMINATIONS:
            self.denomination_cb.addItem(f"₹{d:,}", d)
        denom_idx = self.denomination_cb.findData(int(self._data["denomination"]))
        if denom_idx >= 0:
            self.denomination_cb.setCurrentIndex(denom_idx)

        self.quantity = QSpinBox()
        self.quantity.setMinimum(1)
        self.quantity.setMaximum(10000)
        self.quantity.setValue(self._data["quantity"])

        self.status_cb = QComboBox()
        for key, label in STATUS_LABELS.items():
            self.status_cb.addItem(label, key)
        status_idx = self.status_cb.findData(self._data["status"])
        if status_idx >= 0:
            self.status_cb.setCurrentIndex(status_idx)

        self.actual_cost = make_money_spin()
        if self._data["actual_cost"] is not None:
            self.actual_cost.setValue(self._data["actual_cost"])

        self.entry_date = make_date_edit(optional=False)
        self.entry_date.setDate(_qdate(self._data["entry_date"]))

        self.purchase_date = make_date_edit(optional=True)
        if self._data["purchase_date"]:
            self.purchase_date.setDate(_qdate(self._data["purchase_date"]))

        self.vendor = QLineEdit(self._data["vendor"] or "")
        self.voucher = QLineEdit(self._data["voucher_number"] or "")
        self.reason = QLineEdit(self._data["pending_reason"] or "")

        self.required_by = make_date_edit(optional=True)
        if self._data["pending_required_by"]:
            self.required_by.setDate(_qdate(self._data["pending_required_by"]))

        form.addRow("Firm *", self.firm_cb)
        form.addRow("Denomination *", self.denomination_cb)
        form.addRow("Quantity *", self.quantity)
        form.addRow("Status *", self.status_cb)
        form.addRow("Actual Cost Per Stamp", self.actual_cost)
        form.addRow("Entry Date", self.entry_date)
        form.addRow("Purchase Date", self.purchase_date)
        form.addRow("Vendor", self.vendor)
        form.addRow("Voucher #", self.voucher)
        form.addRow("Reason / Linked Bid", self.reason)
        form.addRow("Required By", self.required_by)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        with session_scope() as session:
            e = session.get(Estamp, self.estamp_id)
            if not e:
                return
            old = {"status": e.status, "actual_cost": e.actual_cost, "quantity": e.quantity}
            e.firm_id = self.firm_cb.currentData()
            e.denomination = self.denomination_cb.currentData()
            e.unit_rate = e.denomination
            e.quantity = self.quantity.value()
            e.status = self.status_cb.currentData()
            cost_val = self.actual_cost.value()
            e.actual_cost = cost_val if cost_val > 0 else None
            e.entry_date = _pydate(self.entry_date.date())
            pdate = self.purchase_date.date()
            e.purchase_date = _pydate(pdate) if pdate != QDate(1900, 1, 1) else None
            e.vendor = self.vendor.text().strip() or None
            e.voucher_number = self.voucher.text().strip() or None
            e.pending_reason = self.reason.text().strip() or None
            rby = self.required_by.date()
            e.pending_required_by = _pydate(rby) if rby != QDate(1900, 1, 1) else None
            new = {"status": e.status, "actual_cost": e.actual_cost, "quantity": e.quantity}
            audit_svc.record(session, user_id=None, table="estamps",
                             record_id=e.id, action="update", old=old, new=new)
        self.accept()
        global_bus.dataChanged.emit()


# ── Queue Purchase Dialog ────────────────────────────────────────────

class QueuePurchaseDialog(QDialog):
    """Create pending e-stamp purchase requests."""
    def __init__(self, firms: list[Firm], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Queue E-Stamp Purchase")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.firm_cb = QComboBox()
        for f in firms:
            self.firm_cb.addItem(f.name, f.id)

        self.denomination_cb = QComboBox()
        for d in DENOMINATIONS:
            self.denomination_cb.addItem(f"₹{d:,}", d)
        self.denomination_cb.currentIndexChanged.connect(self._update_cost)

        self.quantity = QSpinBox()
        self.quantity.setMinimum(1)
        self.quantity.setMaximum(10000)
        self.quantity.setValue(1)
        self.quantity.valueChanged.connect(self._update_cost)

        self.required_by = make_date_edit(optional=False)
        self.required_by.setDate(QDate.currentDate().addDays(7))

        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Reason or linked bid...")

        self.estimated_cost = make_money_spin()

        form.addRow("Firm *", self.firm_cb)
        form.addRow("Denomination *", self.denomination_cb)
        form.addRow("Quantity *", self.quantity)
        form.addRow("Required By *", self.required_by)
        form.addRow("Reason / Linked Bid", self.reason)
        form.addRow("Estimated Total Cost", self.estimated_cost)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self._update_cost()

    def _update_cost(self):
        denom = self.denomination_cb.currentData() or 100
        qty = self.quantity.value()
        self.estimated_cost.setValue(denom * qty)

    def _save(self):
        firm_id = self.firm_cb.currentData()
        denom = self.denomination_cb.currentData()
        qty = self.quantity.value()
        required_by = _pydate(self.required_by.date())
        est_cost = self.estimated_cost.value()
        reason = self.reason.text().strip() or None

        if not firm_id:
            QMessageBox.warning(self, "Validation", "Please select a firm.")
            return

        with session_scope() as session:
            for _ in range(qty):
                row = Estamp(
                    firm_id=firm_id,
                    entry_date=date.today(),
                    quantity=1,
                    unit_rate=denom,
                    denomination=denom,
                    status="pending",
                    pending_queued_at=datetime.utcnow(),
                    pending_required_by=required_by,
                    pending_reason=reason,
                    estimated_cost=denom,
                )
                session.add(row)
            session.flush()
            audit_svc.record(session, user_id=None, table="estamps", record_id=0,
                             action="queue_purchase", new={"qty": qty, "denomination": denom})
        self.accept()
        global_bus.dataChanged.emit()


# ── Record Purchase Dialog ───────────────────────────────────────────

class RecordPurchaseDialog(QDialog):
    """Convert pending→purchased or record a direct purchase."""
    def __init__(self, firms: list[Firm], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Record E-Stamp Purchase")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)

        # Mode selector
        mode_row = QHBoxLayout()
        self.mode_pending = QPushButton("From Pending Queue")
        self.mode_pending.setCheckable(True)
        self.mode_pending.setChecked(True)
        self.mode_direct = QPushButton("Direct Purchase")
        self.mode_direct.setCheckable(True)
        self.mode_pending.clicked.connect(lambda: self._set_mode("pending"))
        self.mode_direct.clicked.connect(lambda: self._set_mode("direct"))
        mode_row.addWidget(self.mode_pending)
        mode_row.addWidget(self.mode_direct)
        layout.addLayout(mode_row)

        # Pending list
        self.pending_list = QListWidget()
        self.pending_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.pending_list)

        form = QFormLayout()
        self.firm_cb = QComboBox()
        for f in firms:
            self.firm_cb.addItem(f.name, f.id)

        self.denomination_cb = QComboBox()
        for d in DENOMINATIONS:
            self.denomination_cb.addItem(f"₹{d:,}", d)

        self.quantity = QSpinBox()
        self.quantity.setMinimum(1)
        self.quantity.setMaximum(10000)
        self.quantity.setValue(1)

        self.purchase_date = make_date_edit(optional=False)
        self.purchase_date.setDate(QDate.currentDate())
        self.vendor = QLineEdit()
        self.voucher = QLineEdit()

        # Actual cost PER STAMP (critical: separate from face value)
        self.actual_cost = make_money_spin()
        cost_hint = QLabel("Cost per stamp, NOT face value (e.g. ₹180 for a ₹100 stamp)")
        cost_hint.setStyleSheet("font-size: 11px; color: #6B7280; background: transparent;")

        form.addRow("Firm *", self.firm_cb)
        form.addRow("Denomination", self.denomination_cb)
        form.addRow("Quantity", self.quantity)
        form.addRow("Purchase Date *", self.purchase_date)
        form.addRow("Vendor", self.vendor)
        form.addRow("Voucher #", self.voucher)
        form.addRow("Actual Cost / Stamp *", self.actual_cost)
        form.addRow("", cost_hint)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._load_pending()
        self._set_mode("pending")

    def _set_mode(self, mode):
        is_pending = mode == "pending"
        self.mode_pending.setChecked(is_pending)
        self.mode_direct.setChecked(not is_pending)
        self.pending_list.setVisible(is_pending)
        self.firm_cb.setEnabled(not is_pending)
        self.denomination_cb.setEnabled(not is_pending)
        self.quantity.setEnabled(not is_pending)

    def _load_pending(self):
        self.pending_list.clear()
        with session_scope() as session:
            pending = session.query(Estamp).filter(Estamp.status == "pending").order_by(Estamp.pending_required_by).all()
            for e in pending:
                text = f"₹{e.denomination or e.unit_rate:,.0f} — {e.firm.name if e.firm else '?'} — req by {e.pending_required_by or '?'}"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, e.id)
                self.pending_list.addItem(item)

    def _save(self):
        pdate = _pydate(self.purchase_date.date())
        vendor_text = self.vendor.text().strip() or None
        voucher_text = self.voucher.text().strip() or None
        cost_per_stamp = self.actual_cost.value()

        if self.mode_pending.isChecked():
            selected = self.pending_list.selectedItems()
            if not selected:
                QMessageBox.warning(self, "Select", "Select at least one pending e-stamp.")
                return
            ids = [item.data(Qt.ItemDataRole.UserRole) for item in selected]
            with session_scope() as session:
                for eid in ids:
                    e = session.get(Estamp, eid)
                    if e and e.status == "pending":
                        e.status = "purchased"
                        e.purchase_date = pdate
                        e.vendor = vendor_text
                        e.voucher_number = voucher_text
                        if cost_per_stamp > 0:
                            e.actual_cost = cost_per_stamp
                audit_svc.record(session, user_id=None, table="estamps", record_id=0,
                                 action="mark_purchased", new={"ids": ids, "actual_cost": cost_per_stamp})
        else:
            firm_id = self.firm_cb.currentData()
            denom = self.denomination_cb.currentData()
            qty = self.quantity.value()
            if not firm_id:
                QMessageBox.warning(self, "Validation", "Select a firm.")
                return
            with session_scope() as session:
                for _ in range(qty):
                    row = Estamp(
                        firm_id=firm_id, entry_date=pdate, quantity=1,
                        unit_rate=denom, denomination=denom, status="purchased",
                        purchase_date=pdate, vendor=vendor_text,
                        voucher_number=voucher_text,
                        actual_cost=cost_per_stamp if cost_per_stamp > 0 else None,
                    )
                    session.add(row)
                session.flush()

        self.accept()
        global_bus.dataChanged.emit()


# ── Main E-Stamps View ───────────────────────────────────────────────

class EstampsView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Header row
        header = QHBoxLayout()
        header.addWidget(QLabel("<b style='font-size:16px'>E-Stamps</b>"))
        header.addStretch()

        self.import_btn = QPushButton("Import Excel")
        self.queue_btn = QPushButton("+ Queue Purchase")
        self.queue_btn.setObjectName("primaryBtn")
        self.record_btn = QPushButton("+ Record Purchase")
        self.record_btn.setObjectName("primaryBtn")
        self.refresh_btn = QPushButton("Refresh")

        header.addWidget(self.import_btn)
        header.addWidget(self.queue_btn)
        header.addWidget(self.record_btn)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)

        # Summary tiles
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.tile_purchased = self._make_tile("Purchased", "0")
        self.tile_pending = self._make_tile("Pending", "0")
        self.tile_allocated = self._make_tile("Allocated", "0")
        self.tile_used = self._make_tile("Used", "0")
        tiles.addWidget(self.tile_purchased)
        tiles.addWidget(self.tile_pending)
        tiles.addWidget(self.tile_allocated)
        tiles.addWidget(self.tile_used)
        layout.addLayout(tiles)

        # Status filter tabs
        self.status_tabs = QTabBar()
        for tab in ["All", "Purchased", "Pending", "Allocated", "Used", "Cancelled"]:
            self.status_tabs.addTab(tab)
        self.status_tabs.currentChanged.connect(self.refresh)
        layout.addWidget(self.status_tabs)

        # Table — actual cost is primary, face value shown for reference
        self.table = make_table([
            "Denomination", "Qty", "Status", "Firm",
            "Actual Cost/Stamp", "Total Cost", "Face Value",
            "Purchase Date", "Vendor", "Voucher #",
        ])
        self.table.doubleClicked.connect(self._edit)
        layout.addWidget(self.table)

        # Action buttons under table
        action_bar = QHBoxLayout()
        self.edit_btn = QPushButton("✎ Edit")
        self.edit_btn.setStyleSheet("font-weight: 600;")
        self.delete_btn = QPushButton("✕ Delete")
        self.delete_btn.setObjectName("dangerBtn")
        action_bar.addWidget(self.edit_btn)
        action_bar.addWidget(self.delete_btn)
        action_bar.addStretch()
        layout.addLayout(action_bar)

        # Connections
        self.queue_btn.clicked.connect(self._queue_purchase)
        self.record_btn.clicked.connect(self._record_purchase)
        self.refresh_btn.clicked.connect(self.refresh)
        self.import_btn.clicked.connect(self._open_import)
        self.edit_btn.clicked.connect(self._edit)
        self.delete_btn.clicked.connect(self._delete)

        self.refresh()

    def _make_tile(self, title: str, value: str) -> QWidget:
        tile = QWidget()
        tile.setStyleSheet(
            "background-color: #FFFFFF; border: 1px solid #E6E8EC; border-radius: 8px; padding: 12px;"
        )
        vlayout = QVBoxLayout(tile)
        vlayout.setContentsMargins(12, 8, 12, 8)
        t = QLabel(title)
        t.setStyleSheet("font-size: 11px; color: #6B7280; font-weight: 600; background: transparent;")
        v = QLabel(value)
        v.setObjectName(f"tile_{title.lower()}_value")
        v.setStyleSheet("font-size: 22px; font-weight: 700; color: #1A1D23; background: transparent;")
        vlayout.addWidget(t)
        vlayout.addWidget(v)
        return tile

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def refresh(self) -> None:
        tab_idx = self.status_tabs.currentIndex()
        status_filter = self.status_tabs.tabText(tab_idx) if tab_idx >= 0 else "All"

        with session_scope() as session:
            q = session.query(Estamp).order_by(Estamp.entry_date.desc())
            if status_filter != "All":
                q = q.filter(Estamp.status == status_filter.lower())
            rows = q.all()

            # Update tiles
            all_stamps = session.query(Estamp).all()
            counts = {"purchased": 0, "pending": 0, "allocated": 0, "used": 0}
            total_actual_cost = 0.0
            pending_val = 0.0
            for e in all_stamps:
                if e.status in counts:
                    counts[e.status] += e.quantity
                if e.status == "pending":
                    pending_val += (e.estimated_cost or e.face_value_total)
                if e.status in ("purchased", "allocated", "used"):
                    total_actual_cost += e.actual_cost_total

            self._update_tile(self.tile_purchased, f"{counts['purchased']}")
            self._update_tile(self.tile_pending, f"{counts['pending']} (₹{pending_val:,.0f})")
            self._update_tile(self.tile_allocated, str(counts["allocated"]))
            self._update_tile(self.tile_used, str(counts["used"]))

            # Fill table
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(rows))
            for r, e in enumerate(rows):
                denom_item = QTableWidgetItem(f"₹{e.denomination or e.unit_rate:,.0f}")
                denom_item.setData(Qt.ItemDataRole.UserRole, e.id)
                self.table.setItem(r, 0, denom_item)
                self.table.setItem(r, 1, QTableWidgetItem(str(e.quantity)))

                status_label = STATUS_LABELS.get(e.status, e.status.title())
                status_item = QTableWidgetItem(status_label)
                colors = {
                    "pending": "#D97706", "purchased": "#16A34A",
                    "allocated": "#2563EB", "used": "#6B7280", "cancelled": "#DC2626"
                }
                status_item.setForeground(QBrush(QColor(colors.get(e.status, "#1A1D23"))))
                self.table.setItem(r, 2, status_item)

                self.table.setItem(r, 3, QTableWidgetItem(e.firm.name if e.firm else "-"))

                # Actual cost per stamp
                if e.actual_cost is not None:
                    self.table.setItem(r, 4, QTableWidgetItem(f"₹{e.actual_cost:,.2f}"))
                else:
                    self.table.setItem(r, 4, QTableWidgetItem("-"))

                # Total actual cost
                self.table.setItem(r, 5, QTableWidgetItem(f"₹{e.actual_cost_total:,.2f}"))

                # Face value (de-prioritized, shown for reference)
                self.table.setItem(r, 6, QTableWidgetItem(f"₹{e.face_value_total:,.2f}"))

                self.table.setItem(r, 7, QTableWidgetItem(
                    e.purchase_date.isoformat() if e.purchase_date else "-"))
                self.table.setItem(r, 8, QTableWidgetItem(e.vendor or "-"))
                self.table.setItem(r, 9, QTableWidgetItem(e.voucher_number or "-"))

            self.table.setSortingEnabled(True)

    def _update_tile(self, tile: QWidget, value: str):
        for child in tile.findChildren(QLabel):
            if child.objectName().startswith("tile_") and child.objectName().endswith("_value"):
                child.setText(value)
                break

    def _firms(self) -> list[Firm]:
        with session_scope() as session:
            firms = session.query(Firm).filter(Firm.is_archived == False).order_by(Firm.name).all()
            for f in firms:
                session.expunge(f)
            return firms

    def _edit(self):
        eid = self._selected_id()
        if eid is None:
            QMessageBox.information(self, "Select", "Select an e-stamp row to edit.")
            return
        firms = self._firms()
        dlg = EstampEditor(eid, firms, self)
        if dlg.exec():
            self.refresh()

    def _delete(self):
        eid = self._selected_id()
        if eid is None:
            QMessageBox.information(self, "Select", "Select an e-stamp row to delete.")
            return
        confirm = QMessageBox.question(
            self, "Confirm Delete",
            "Are you sure you want to delete this e-stamp entry?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        with session_scope() as session:
            e = session.get(Estamp, eid)
            if e:
                audit_svc.record(session, user_id=None, table="estamps",
                                 record_id=e.id, action="delete",
                                 old={"denomination": e.denomination, "status": e.status, "qty": e.quantity})
                session.delete(e)
        self.refresh()
        global_bus.dataChanged.emit()

    def _queue_purchase(self):
        firms = self._firms()
        if not firms:
            QMessageBox.warning(self, "No firms", "Create a firm first.")
            return
        dlg = QueuePurchaseDialog(firms, self)
        if dlg.exec():
            self.refresh()

    def _record_purchase(self):
        firms = self._firms()
        if not firms:
            QMessageBox.warning(self, "No firms", "Create a firm first.")
            return
        dlg = RecordPurchaseDialog(firms, self)
        if dlg.exec():
            self.refresh()

    def _open_import(self):
        from .import_dialog import ImportDialog
        dlg = ImportDialog(self)
        dlg.exec()
