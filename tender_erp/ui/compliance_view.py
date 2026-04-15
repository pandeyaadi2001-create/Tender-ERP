"""Compliance / certificate tracker view (spec §3.3)."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
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

from ..config import ATTACHMENTS_DIR, ensure_dirs
from ..db import session_scope
from ..models.compliance import ComplianceDocument
from ..models.firm import Firm
from ..services import audit as audit_svc
from ..services.validators import validate_compliance
from .widgets import make_date_edit, make_table

STATUS_CHOICES = ("Active", "To Be Renewed", "Under Renewal", "Expired", "Not Applicable")


def _qdate(d: date | None) -> QDate:
    return QDate(d.year, d.month, d.day) if d else QDate(1900, 1, 1)


def _pydate(q: QDate) -> date | None:
    return date(q.year(), q.month(), q.day()) if q != QDate(1900, 1, 1) else None


class ComplianceEditor(QDialog):
    def __init__(
        self, doc: ComplianceDocument | None, firms: list[Firm], parent=None
    ) -> None:
        super().__init__(parent)
        self.doc_id = doc.id if doc else None
        self.setWindowTitle("Edit Compliance" if doc else "New Compliance")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.firm_cb = QComboBox()
        for f in firms:
            self.firm_cb.addItem(f.name, f.id)
        if doc:
            idx = self.firm_cb.findData(doc.firm_id)
            if idx >= 0:
                self.firm_cb.setCurrentIndex(idx)

        self.cert_no = QLineEdit(doc.certificate_no if doc else "")
        self.doc_type = QLineEdit(doc.document_type if doc else "")
        self.doc_name = QLineEdit(doc.document_name if doc else "")
        self.authority = QLineEdit(doc.issuing_authority if doc else "")
        self.issue_date = make_date_edit()
        self.issue_date.setDate(_qdate(doc.issue_date if doc else None))
        self.expiry_date = make_date_edit()
        self.expiry_date.setDate(_qdate(doc.expiry_date if doc else None))
        self.renewal_due = make_date_edit()
        self.renewal_due.setDate(_qdate(doc.renewal_due_date if doc else None))
        self.status_cb = QComboBox()
        self.status_cb.addItems(STATUS_CHOICES)
        if doc and doc.status in STATUS_CHOICES:
            self.status_cb.setCurrentIndex(STATUS_CHOICES.index(doc.status))
        self.responsible = QLineEdit(doc.responsible_person if doc else "")
        self.notes = QTextEdit(doc.notes if doc and doc.notes else "")
        self.notes.setFixedHeight(60)

        self.file_label = QLineEdit(doc.file_path if doc and doc.file_path else "")
        self.file_label.setReadOnly(True)
        self.pick_btn = QPushButton("Attach PDF")
        self.pick_btn.clicked.connect(self._pick_file)

        file_row = QHBoxLayout()
        file_row.addWidget(self.file_label)
        file_row.addWidget(self.pick_btn)

        form.addRow("Firm *", self.firm_cb)
        form.addRow("Certificate no", self.cert_no)
        form.addRow("Document type", self.doc_type)
        form.addRow("Document name *", self.doc_name)
        form.addRow("Issuing authority", self.authority)
        form.addRow("Issue date", self.issue_date)
        form.addRow("Expiry date", self.expiry_date)
        form.addRow("Renewal due", self.renewal_due)
        form.addRow("Status", self.status_cb)
        form.addRow("Responsible", self.responsible)
        form.addRow("Notes", self.notes)
        form.addRow("PDF file", file_row)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Attach certificate", "", "PDF (*.pdf)")
        if path:
            self.file_label.setText(path)

    def _save(self) -> None:
        payload = dict(
            firm_id=self.firm_cb.currentData(),
            certificate_no=self.cert_no.text() or None,
            document_type=self.doc_type.text() or None,
            document_name=self.doc_name.text(),
            issuing_authority=self.authority.text() or None,
            issue_date=_pydate(self.issue_date.date()),
            expiry_date=_pydate(self.expiry_date.date()),
            renewal_due_date=_pydate(self.renewal_due.date()),
            status=self.status_cb.currentText(),
            responsible_person=self.responsible.text() or None,
            notes=self.notes.toPlainText() or None,
            file_path=self.file_label.text() or None,
        )
        errors = validate_compliance(payload)
        if errors:
            QMessageBox.warning(self, "Validation", "\n".join(errors))
            return
        ensure_dirs()
        with session_scope() as session:
            if self.doc_id:
                doc = session.get(ComplianceDocument, self.doc_id)
                if doc is None:
                    return
                old = {k: getattr(doc, k) for k in payload}
                for k, v in payload.items():
                    setattr(doc, k, v)
                audit_svc.record(
                    session,
                    user_id=None,
                    table="compliance_documents",
                    record_id=doc.id,
                    action="update",
                    old=old,
                    new=payload,
                )
            else:
                doc = ComplianceDocument(**payload)
                session.add(doc)
                session.flush()
                audit_svc.record(
                    session,
                    user_id=None,
                    table="compliance_documents",
                    record_id=doc.id,
                    action="create",
                    new=payload,
                )
        self.accept()


class ComplianceView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.new_btn = QPushButton("New document")
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        self.refresh_btn = QPushButton("Refresh")
        bar.addWidget(self.new_btn)
        bar.addWidget(self.edit_btn)
        bar.addWidget(self.delete_btn)
        bar.addStretch(1)
        bar.addWidget(self.refresh_btn)
        layout.addLayout(bar)

        self.table = make_table(
            ["Firm", "Name", "Type", "Cert No.", "Issue", "Expiry", "Days", "Status"]
        )
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
            docs = (
                session.query(ComplianceDocument)
                .order_by(ComplianceDocument.expiry_date.asc().nullslast())
                .all()
            )
            self.table.setRowCount(len(docs))
            for r, d in enumerate(docs):
                item = QTableWidgetItem(d.firm.name if d.firm else "-")
                item.setData(Qt.ItemDataRole.UserRole, d.id)
                self.table.setItem(r, 0, item)
                self.table.setItem(r, 1, QTableWidgetItem(d.document_name))
                self.table.setItem(r, 2, QTableWidgetItem(d.document_type or "-"))
                self.table.setItem(r, 3, QTableWidgetItem(d.certificate_no or "-"))
                self.table.setItem(r, 4, QTableWidgetItem(d.issue_date.isoformat() if d.issue_date else "-"))
                self.table.setItem(r, 5, QTableWidgetItem(d.expiry_date.isoformat() if d.expiry_date else "-"))
                self.table.setItem(
                    r,
                    6,
                    QTableWidgetItem(
                        str(d.days_until_expiry) if d.days_until_expiry is not None else "-"
                    ),
                )
                self.table.setItem(r, 7, QTableWidgetItem(d.status))

    def _with_firms(self):
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
        firms = self._with_firms()
        if not firms:
            QMessageBox.warning(self, "No firms", "Create a firm first.")
            return
        dlg = ComplianceEditor(None, firms, self)
        if dlg.exec():
            self.refresh()

    def _edit(self) -> None:
        did = self._selected_id()
        if did is None:
            return
        with session_scope() as session:
            doc = session.get(ComplianceDocument, did)
            if doc is None:
                return
            session.expunge(doc)
        firms = self._with_firms()
        dlg = ComplianceEditor(doc, firms, self)
        if dlg.exec():
            self.refresh()

    def _delete(self) -> None:
        did = self._selected_id()
        if did is None:
            return
        confirm = QMessageBox.question(self, "Delete", "Delete this document?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        with session_scope() as session:
            doc = session.get(ComplianceDocument, did)
            if doc is None:
                return
            session.delete(doc)
            audit_svc.record(
                session,
                user_id=None,
                table="compliance_documents",
                record_id=did,
                action="delete",
            )
        self.refresh()
