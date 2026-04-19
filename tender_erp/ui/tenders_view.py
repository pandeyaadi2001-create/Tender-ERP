"""Tender tracker view (spec §3.2)."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
from ..models.tender import Tender
from ..services import audit as audit_svc
from ..services.tender_rates import computed_publish_rate_fields, effective_publish_rate
from ..services.validators import validate_tender
from .widgets import make_date_edit, make_money_spin, make_table
from .event_bus import global_bus

PARTICIPATION_CHOICES = (
    "",
    "Participated",
    "Participated in Support",
    "Not Participated",
    "Cancelled",
)


def _qdate(d: date | None) -> QDate:
    if d is None:
        return QDate(1900, 1, 1)
    return QDate(d.year, d.month, d.day)


def _pydate(q: QDate) -> date | None:
    if q == QDate(1900, 1, 1):
        return None
    return date(q.year(), q.month(), q.day())


class TenderEditor(QDialog):
    def __init__(self, tender: Tender | None, firms: list[Firm], parent=None) -> None:
        super().__init__(parent)
        self.tender_id = tender.id if tender else None
        self.setWindowTitle("Edit Tender" if tender else "New Tender")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.firm_cb = QComboBox()
        for f in firms:
            self.firm_cb.addItem(f.name, f.id)
        if tender:
            idx = self.firm_cb.findData(tender.firm_id)
            if idx >= 0:
                self.firm_cb.setCurrentIndex(idx)

        self.bid_no = QLineEdit(tender.bid_no if tender else "")
        self.organisation = QLineEdit(tender.organisation if tender else "")
        self.department = QLineEdit(tender.department if tender else "")
        self.state = QLineEdit(tender.state if tender else "")
        self.location = QLineEdit(tender.location if tender else "")

        self.publish_date = make_date_edit()
        self.publish_date.setDate(_qdate(tender.publish_date if tender else None))
        self.due_date = make_date_edit()
        self.due_date.setDate(_qdate(tender.due_date if tender else None))

        self.tender_value = make_money_spin()
        if tender and tender.tender_value is not None:
            self.tender_value.setValue(tender.tender_value)
        self.emd = make_money_spin()
        if tender and tender.emd is not None:
            self.emd.setValue(tender.emd)
        self.publish_rate = make_money_spin()
        if tender and tender.publish_rate is not None:
            self.publish_rate.setValue(tender.publish_rate)
        self.quoted_rates = make_money_spin()
        if tender and tender.quoted_rates is not None:
            self.quoted_rates.setValue(tender.quoted_rates)

        self.contract_months = QDoubleSpinBox()
        self.contract_months.setDecimals(1)
        self.contract_months.setMaximum(360)
        if tender and tender.contract_period_months is not None:
            self.contract_months.setValue(tender.contract_period_months)

        self.quantity = QDoubleSpinBox()
        self.quantity.setDecimals(4)
        self.quantity.setMaximum(1e12)
        self.quantity.setMinimum(0)
        if tender and tender.quantity is not None:
            self.quantity.setValue(tender.quantity)
        else:
            self.quantity.setValue(0)

        self.service_days = QDoubleSpinBox()
        self.service_days.setDecimals(1)
        self.service_days.setMaximum(1e6)
        self.service_days.setMinimum(0)
        if tender and getattr(tender, "service_days", None) is not None:
            self.service_days.setValue(tender.service_days)
        else:
            self.service_days.setValue(0)

        self.participation_cb = QComboBox()
        self.participation_cb.addItems(PARTICIPATION_CHOICES)
        if tender and tender.participation_status:
            idx = self.participation_cb.findText(tender.participation_status)
            if idx >= 0:
                self.participation_cb.setCurrentIndex(idx)

        self.nature = QLineEdit(tender.nature_of_work if tender else "")
        self.scope = QTextEdit(tender.scope_of_work if tender and tender.scope_of_work else "")
        self.scope.setFixedHeight(60)

        self.technical_status = QLineEdit(tender.technical_status if tender else "")
        self.financial_status = QLineEdit(tender.financial_status if tender else "")
        self.our_status = QLineEdit(tender.our_status if tender else "")

        self.is_reference = QCheckBox("Reference only (benchmark, not bid by us)")
        if tender:
            self.is_reference.setChecked(tender.is_reference)

        # Portal & classification
        self.portal_cb = QComboBox()
        self.portal_cb.addItems(["", "GeM", "eTender", "IREPS", "Other"])
        if tender and tender.portal:
            idx = self.portal_cb.findText(tender.portal)
            if idx >= 0:
                self.portal_cb.setCurrentIndex(idx)
        self.category_field = QLineEdit(tender.category if tender else "")
        self.document_fee = make_money_spin()
        if tender and tender.document_fee is not None:
            self.document_fee.setValue(tender.document_fee)
        self.processing_fee = make_money_spin()
        if tender and tender.processing_fee is not None:
            self.processing_fee.setValue(tender.processing_fee)

        # Award section
        self.awarded_check = QCheckBox("Tender Awarded")
        if tender:
            self.awarded_check.setChecked(tender.awarded_flag)
        self.awarded_date = make_date_edit()
        self.awarded_date.setDate(_qdate(tender.awarded_date if tender else None))
        self.awarded_value = make_money_spin()
        if tender and tender.awarded_value is not None:
            self.awarded_value.setValue(tender.awarded_value)
        self.loa_po = QLineEdit(tender.loa_po_number if tender else "")
        self.exec_status_cb = QComboBox()
        self.exec_status_cb.addItems(["", "Not Started", "In Progress", "Completed"])
        if tender and tender.execution_status:
            idx = self.exec_status_cb.findText(tender.execution_status)
            if idx >= 0:
                self.exec_status_cb.setCurrentIndex(idx)

        form.addRow("Firm *", self.firm_cb)
        form.addRow("Bid No.", self.bid_no)
        form.addRow("Organisation", self.organisation)
        form.addRow("Portal", self.portal_cb)
        form.addRow("Category", self.category_field)
        form.addRow("Department", self.department)
        form.addRow("State", self.state)
        form.addRow("Location", self.location)
        form.addRow("Publish date", self.publish_date)
        form.addRow("Due date", self.due_date)
        form.addRow("Tender value", self.tender_value)
        form.addRow("EMD", self.emd)
        form.addRow("Document fee", self.document_fee)
        form.addRow("Processing fee", self.processing_fee)
        form.addRow("Publish rate", self.publish_rate)
        form.addRow("Quoted rates", self.quoted_rates)
        form.addRow("Contract period (months)", self.contract_months)
        form.addRow("Quantity (diet/day or kg/mo)", self.quantity)
        form.addRow("Service days (kitchen, optional)", self.service_days)
        form.addRow("Participation", self.participation_cb)
        form.addRow("Nature of work", self.nature)
        form.addRow("Scope of work", self.scope)
        form.addRow("Technical status", self.technical_status)
        form.addRow("Financial status", self.financial_status)
        form.addRow("Our status", self.our_status)
        form.addRow("", self.is_reference)

        # Award section
        award_sep = QLabel("── Award Details ──")
        award_sep.setStyleSheet("font-weight: 600; color: #6B7280; padding-top: 8px; background: transparent;")
        form.addRow("", award_sep)
        form.addRow("", self.awarded_check)
        self.award_date_row_label = QLabel("Award date")
        form.addRow(self.award_date_row_label, self.awarded_date)
        self.award_value_row_label = QLabel("Awarded value")
        form.addRow(self.award_value_row_label, self.awarded_value)
        self.loa_row_label = QLabel("LOA / PO Number")
        form.addRow(self.loa_row_label, self.loa_po)
        self.exec_row_label = QLabel("Execution status")
        form.addRow(self.exec_row_label, self.exec_status_cb)

        self.awarded_check.toggled.connect(self._toggle_award)
        self._toggle_award(self.awarded_check.isChecked())

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _toggle_award(self, checked: bool):
        for w in [self.awarded_date, self.awarded_value, self.loa_po, self.exec_status_cb,
                   self.award_date_row_label, self.award_value_row_label,
                   self.loa_row_label, self.exec_row_label]:
            w.setVisible(checked)

    def _save(self) -> None:
        qv = self.quantity.value()
        qty = None if qv <= 0 else qv
        sdv = self.service_days.value()
        service_days = None if sdv <= 0 else sdv
        cpm = self.contract_months.value() or None
        period_fallback = (cpm * 30.0) if cpm else None
        payload = dict(
            firm_id=self.firm_cb.currentData(),
            bid_no=self.bid_no.text(),
            organisation=self.organisation.text(),
            portal=self.portal_cb.currentText() or None,
            category=self.category_field.text() or None,
            department=self.department.text(),
            state=self.state.text(),
            location=self.location.text(),
            publish_date=_pydate(self.publish_date.date()),
            due_date=_pydate(self.due_date.date()),
            tender_value=self.tender_value.value() or None,
            emd=self.emd.value() or None,
            document_fee=self.document_fee.value() or None,
            processing_fee=self.processing_fee.value() or None,
            publish_rate=self.publish_rate.value() or None,
            quoted_rates=self.quoted_rates.value() or None,
            contract_period_months=cpm,
            quantity=qty,
            service_days=service_days,
            participation_status=self.participation_cb.currentText() or None,
            nature_of_work=self.nature.text() or None,
            scope_of_work=self.scope.toPlainText() or None,
            technical_status=self.technical_status.text() or None,
            financial_status=self.financial_status.text() or None,
            our_status=self.our_status.text() or None,
            is_reference=self.is_reference.isChecked(),
            awarded_flag=self.awarded_check.isChecked(),
            awarded_date=_pydate(self.awarded_date.date()) if self.awarded_check.isChecked() else None,
            awarded_value=self.awarded_value.value() or None if self.awarded_check.isChecked() else None,
            loa_po_number=self.loa_po.text() or None,
            execution_status=self.exec_status_cb.currentText() or None,
        )
        auto_pr = computed_publish_rate_fields(
            tender_value=payload.get("tender_value"),
            quantity=payload.get("quantity"),
            nature_of_work=payload.get("nature_of_work"),
            category=payload.get("category"),
            contract_period_months=payload.get("contract_period_months"),
            service_days=payload.get("service_days"),
            period_in_days_fallback=period_fallback,
        )
        if auto_pr is not None:
            payload["publish_rate"] = auto_pr
        errors = validate_tender(payload)
        if errors:
            QMessageBox.warning(self, "Validation", "\n".join(errors))
            return
        with session_scope() as session:
            if self.tender_id:
                tender = session.get(Tender, self.tender_id)
                if tender is None:
                    return
                old = {k: getattr(tender, k) for k in payload}
                for k, v in payload.items():
                    setattr(tender, k, v)
                audit_svc.record(
                    session,
                    user_id=None,
                    table="tenders",
                    record_id=tender.id,
                    action="update",
                    old=old,
                    new=payload,
                )
            else:
                tender = Tender(**payload)
                session.add(tender)
                session.flush()
                audit_svc.record(
                    session,
                    user_id=None,
                    table="tenders",
                    record_id=tender.id,
                    action="create",
                    new=payload,
                )
        self.accept()
        global_bus.dataChanged.emit()


class TendersView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.new_btn = QPushButton("New tender")
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        self.delete_many_btn = QPushButton("Delete selected")
        self.import_btn = QPushButton("Import Excel")
        self.generate_btn = QPushButton("Generate submission checklist")
        self.refresh_btn = QPushButton("Refresh")
        
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter by bid no / org")
        
        self.status_filter = QComboBox()
        self.status_filter.addItem("All Statuses", "")
        self.status_filter.addItems(PARTICIPATION_CHOICES[1:]) # Skip empty string in choices
        
        bar.addWidget(self.new_btn)
        bar.addWidget(self.edit_btn)
        bar.addWidget(self.delete_btn)
        bar.addWidget(self.delete_many_btn)
        bar.addWidget(self.import_btn)
        bar.addWidget(self.generate_btn)
        bar.addWidget(self.filter)
        bar.addWidget(self.status_filter)
        bar.addStretch(1)
        bar.addWidget(self.refresh_btn)
        layout.addLayout(bar)

        self.table = make_table(
            [
                "",
                "Due",
                "Firm",
                "Bid No.",
                "Organisation",
                "Dept",
                "Nature",
                "Mo.",
                "Qty",
                "Value",
                "Pub. rate",
                "Participation",
                "Our status",
            ],
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
        self.import_btn.clicked.connect(self._open_import)
        self.generate_btn.clicked.connect(self._generate_checklist)
        self.refresh_btn.clicked.connect(self.refresh)
        self.filter.textChanged.connect(self.refresh)
        self.status_filter.currentTextChanged.connect(self.refresh)
        self.refresh()

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _checked_ids(self) -> list[int]:
        ids: list[int] = []
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it is None:
                continue
            if it.checkState() == Qt.CheckState.Checked:
                rid = it.data(Qt.ItemDataRole.UserRole)
                if rid is not None:
                    ids.append(int(rid))
        return ids

    def _set_row_color(self, row: int, color: str) -> None:
        from PySide6.QtGui import QColor, QBrush
        brush = QBrush(QColor(color))
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setForeground(brush)

    def _participation_filter_value(self) -> str:
        """Participation dropdown: index 0 is 'all' (UserRole data is '' which is falsy — do not use ``or currentText()``)."""
        if self.status_filter.currentIndex() == 0:
            return ""
        return (self.status_filter.currentText() or "").strip()

    def refresh(self) -> None:
        needle = (self.filter.text() or "").strip().lower()
        status_filter = self._participation_filter_value()

        with session_scope() as session:
            q = session.query(Tender).order_by(Tender.due_date.asc().nullslast())
            tenders = q.all()
            rows = []
            for t in tenders:
                hay = " ".join(
                    filter(None, [t.bid_no, t.organisation, t.department, t.location])
                ).lower()
                if needle and needle not in hay:
                    continue
                if status_filter:
                    t_status = (t.participation_status or "").strip().lower()
                    if t_status != status_filter.lower():
                        continue
                rows.append(t)
            
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(rows))
            for r, t in enumerate(rows):
                due = t.due_date.isoformat() if t.due_date else "-"
                firm = t.firm.name if t.firm else "-"
                sel = QTableWidgetItem("")
                sel.setFlags(
                    sel.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEnabled
                )
                sel.setCheckState(Qt.CheckState.Unchecked)
                sel.setData(Qt.ItemDataRole.UserRole, t.id)
                self.table.setItem(r, 0, sel)
                self.table.setItem(r, 1, QTableWidgetItem(due))
                self.table.setItem(r, 2, QTableWidgetItem(firm))
                self.table.setItem(r, 3, QTableWidgetItem(t.bid_no or "-"))
                self.table.setItem(r, 4, QTableWidgetItem(t.organisation or "-"))
                self.table.setItem(r, 5, QTableWidgetItem(t.department or "-"))
                self.table.setItem(r, 6, QTableWidgetItem(t.nature_of_work or "-"))
                cpm = t.contract_period_months
                self.table.setItem(
                    r, 7, QTableWidgetItem(f"{cpm:g}" if cpm is not None else "-")
                )
                qty = t.quantity
                self.table.setItem(
                    r, 8, QTableWidgetItem(f"{qty:g}" if qty is not None else "-")
                )
                self.table.setItem(
                    r,
                    9,
                    QTableWidgetItem(
                        f"{t.tender_value:,.0f}" if t.tender_value is not None else "-"
                    ),
                )
                er = effective_publish_rate(t)
                self.table.setItem(
                    r,
                    10,
                    QTableWidgetItem(f"{er:,.4f}" if er is not None else "-"),
                )
                self.table.setItem(r, 11, QTableWidgetItem(t.participation_status or "-"))
                self.table.setItem(r, 12, QTableWidgetItem(t.our_status or "-"))

                # Color Coding
                from datetime import date

                if t.due_date:
                    days_left = (t.due_date - date.today()).days
                    if days_left <= 3:
                        self._set_row_color(r, "#ef4444")  # Red
                    elif days_left <= 7:
                        self._set_row_color(r, "#eab308")  # Yellow
                    else:
                        self._set_row_color(r, "#22c55e")  # Green
            self.table.setSortingEnabled(True)

    def _open_editor(self, tender: Tender | None) -> None:
        with session_scope() as session:
            firms = (
                session.query(Firm)
                .filter(Firm.is_archived == False)  # noqa: E712
                .order_by(Firm.name)
                .all()
            )
            for f in firms:
                session.expunge(f)
        if not firms:
            QMessageBox.warning(self, "No firms", "Create a firm first.")
            return
        dlg = TenderEditor(tender, firms, self)
        if dlg.exec():
            self.refresh()

    def _new(self) -> None:
        self._open_editor(None)

    def _edit(self) -> None:
        tid = self._selected_id()
        if tid is None:
            return
        with session_scope() as session:
            tender = session.get(Tender, tid)
            if tender is None:
                return
            session.expunge(tender)
        self._open_editor(tender)

    def _delete(self) -> None:
        tid = self._selected_id()
        if tid is None:
            return
        confirm = QMessageBox.question(self, "Delete", "Delete the selected tender?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        with session_scope() as session:
            tender = session.get(Tender, tid)
            if tender is None:
                return
            session.delete(tender)
            audit_svc.record(
                session,
                user_id=None,
                table="tenders",
                record_id=tid,
                action="delete",
            )
        global_bus.dataChanged.emit()
        self.refresh()

    def _delete_many(self) -> None:
        ids = self._checked_ids()
        if not ids:
            QMessageBox.information(self, "Delete", "Tick one or more rows in the first column.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete",
            f"Delete {len(ids)} selected tender(s)?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        with session_scope() as session:
            for tid in ids:
                tender = session.get(Tender, tid)
                if tender is None:
                    continue
                session.delete(tender)
                audit_svc.record(
                    session,
                    user_id=None,
                    table="tenders",
                    record_id=tid,
                    action="delete",
                )
        global_bus.dataChanged.emit()
        self.refresh()

    def _generate_checklist(self) -> None:
        from ..services import checklist as checklist_svc
        from ..wizard_service import checklist_generator_enabled

        tid = self._selected_id()
        if tid is None:
            return
        with session_scope() as session:
            if not checklist_generator_enabled(session):
                QMessageBox.information(
                    self,
                    "Setup required",
                    "Setup required — see Settings → Checklist Rules.",
                )
                return
            tender = session.get(Tender, tid)
            if tender is None:
                return
            items, instance = checklist_svc.generate_checklist(session, tender)
        pdf = instance.pdf_path or "(PDF skipped)"
        QMessageBox.information(
            self,
            "Checklist generated",
            f"{len(items)} items. PDF: {pdf}",
        )

    def _open_import(self):
        from .import_dialog import ImportDialog
        dlg = ImportDialog(self)
        if dlg.exec():
            self.refresh()
