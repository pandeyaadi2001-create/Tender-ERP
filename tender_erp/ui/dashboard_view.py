"""Dashboard landing view (spec §3.7)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..db import session_scope
from ..services import dashboard


def _card(title: str) -> tuple[QWidget, QTableWidget]:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(8, 8, 8, 8)
    header = QLabel(f"<b>{title}</b>")
    header.setTextFormat(Qt.TextFormat.RichText)
    layout.addWidget(header)
    table = QTableWidget(0, 0)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    layout.addWidget(table)
    return widget, table


class DashboardView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.grid = QGridLayout(self)

        self.tenders_7_widget, self.tenders_7_tbl = _card("Tenders due — next 7 days")
        self.tenders_30_widget, self.tenders_30_tbl = _card("Tenders due — 8 to 30 days")
        self.compliance_widget, self.compliance_tbl = _card(
            "Compliance expiring — next 60 days"
        )
        self.dsc_widget, self.dsc_tbl = _card("DSC expiry watch — 90 days")
        self.pending_widget, self.pending_tbl = _card("Pending status past due")
        self.decision_widget, self.decision_tbl = _card("Decision required")
        self.summary_label = QLabel()

        self.grid.addWidget(self.summary_label, 0, 0, 1, 2)
        self.grid.addWidget(self.tenders_7_widget, 1, 0)
        self.grid.addWidget(self.tenders_30_widget, 1, 1)
        self.grid.addWidget(self.compliance_widget, 2, 0)
        self.grid.addWidget(self.dsc_widget, 2, 1)
        self.grid.addWidget(self.pending_widget, 3, 0)
        self.grid.addWidget(self.decision_widget, 3, 1)

        self.refresh()

    def refresh(self) -> None:
        with session_scope() as session:
            snap = dashboard.build_snapshot(session)
        self._fill_deadlines(self.tenders_7_tbl, snap.tenders_7d)
        self._fill_deadlines(self.tenders_30_tbl, snap.tenders_8_to_30d)
        self._fill_compliance(self.compliance_tbl, snap.compliance_60d)
        self._fill_dsc(self.dsc_tbl, snap.dsc_90d)
        self._fill_pending(self.pending_tbl, snap.pending_status)
        self._fill_decision(self.decision_tbl, snap.decision_required)
        self.summary_label.setText(
            f"<h2>Dashboard</h2>"
            f"Firms: <b>{snap.firm_count}</b> &nbsp; "
            f"E-stamps MTD: <b>{snap.estamp_mtd.count}</b> "
            f"(₹{snap.estamp_mtd.total_spent:,.2f}) &nbsp; "
            f"Same month last FY: ₹{snap.estamp_mtd.vs_same_month_last_fy:,.2f}"
        )

    def _fill_deadlines(self, tbl: QTableWidget, rows) -> None:
        headers = ["Due", "Days", "Firm", "Bid No.", "Organisation", "Status"]
        tbl.clear()
        tbl.setColumnCount(len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setRowCount(len(rows))
        for r, row in enumerate(rows):
            tbl.setItem(r, 0, QTableWidgetItem(row.due_date.isoformat() if row.due_date else "-"))
            tbl.setItem(r, 1, QTableWidgetItem(str(row.due_in_days) if row.due_in_days is not None else "-"))
            tbl.setItem(r, 2, QTableWidgetItem(row.firm_name))
            tbl.setItem(r, 3, QTableWidgetItem(row.bid_no or "-"))
            tbl.setItem(r, 4, QTableWidgetItem(row.organisation or "-"))
            tbl.setItem(r, 5, QTableWidgetItem(row.participation_status or "-"))

    def _fill_compliance(self, tbl: QTableWidget, docs) -> None:
        headers = ["Expiry", "Days", "Firm", "Document", "Status"]
        tbl.clear()
        tbl.setColumnCount(len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setRowCount(len(docs))
        for r, d in enumerate(docs):
            tbl.setItem(r, 0, QTableWidgetItem(d.expiry_date.isoformat() if d.expiry_date else "-"))
            tbl.setItem(r, 1, QTableWidgetItem(str(d.days_until_expiry) if d.days_until_expiry is not None else "-"))
            tbl.setItem(r, 2, QTableWidgetItem(d.firm.name if d.firm else "-"))
            tbl.setItem(r, 3, QTableWidgetItem(d.document_name))
            tbl.setItem(r, 4, QTableWidgetItem(d.status))

    def _fill_dsc(self, tbl: QTableWidget, rows) -> None:
        headers = ["Expiry", "Firm", "Portal", "DSC Holder"]
        tbl.clear()
        tbl.setColumnCount(len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setRowCount(len(rows))
        for r, v in enumerate(rows):
            tbl.setItem(r, 0, QTableWidgetItem(v.dsc_expiry.isoformat() if v.dsc_expiry else "-"))
            tbl.setItem(r, 1, QTableWidgetItem(v.firm.name if v.firm else "-"))
            tbl.setItem(r, 2, QTableWidgetItem(v.portal_name))
            tbl.setItem(r, 3, QTableWidgetItem(v.dsc_holder or "-"))

    def _fill_pending(self, tbl: QTableWidget, rows) -> None:
        headers = ["Due", "Firm", "Bid No.", "Tech", "Fin", "Our"]
        tbl.clear()
        tbl.setColumnCount(len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setRowCount(len(rows))
        for r, t in enumerate(rows):
            tbl.setItem(r, 0, QTableWidgetItem(t.due_date.isoformat() if t.due_date else "-"))
            tbl.setItem(r, 1, QTableWidgetItem(t.firm.name if t.firm else "-"))
            tbl.setItem(r, 2, QTableWidgetItem(t.bid_no or "-"))
            tbl.setItem(r, 3, QTableWidgetItem(t.technical_status or "-"))
            tbl.setItem(r, 4, QTableWidgetItem(t.financial_status or "-"))
            tbl.setItem(r, 5, QTableWidgetItem(t.our_status or "-"))

    def _fill_decision(self, tbl: QTableWidget, rows) -> None:
        headers = ["Publish", "Firm", "Bid No.", "Organisation"]
        tbl.clear()
        tbl.setColumnCount(len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setRowCount(len(rows))
        for r, t in enumerate(rows):
            tbl.setItem(r, 0, QTableWidgetItem(t.publish_date.isoformat() if t.publish_date else "-"))
            tbl.setItem(r, 1, QTableWidgetItem(t.firm.name if t.firm else "-"))
            tbl.setItem(r, 2, QTableWidgetItem(t.bid_no or "-"))
            tbl.setItem(r, 3, QTableWidgetItem(t.organisation or "-"))
