"""Dashboard Command Center view (spec §3.7).

Matches the reference design: light theme, 2 KPI rows, urgent tenders
table, e-stamp status card, compliance risk card, bids awarded chart,
and active tenders donut.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..db import session_scope
from ..services import dashboard


# ── Helpers ──────────────────────────────────────────────────────────

def _fmt_currency(v: float | None) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1e7:
        return f"₹{v / 1e7:,.2f} Cr"
    if abs(v) >= 1e5:
        return f"₹{v / 1e5:,.2f} L"
    return f"₹{v:,.0f}"


def _shadow() -> QGraphicsDropShadowEffect:
    s = QGraphicsDropShadowEffect()
    s.setBlurRadius(6)
    s.setColor(QColor(16, 24, 40, 10))
    s.setOffset(0, 1)
    return s


# ── Card Widget ──────────────────────────────────────────────────────

class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            Card {
                background-color: #FFFFFF;
                border: 1px solid #E6E8EC;
                border-radius: 10px;
            }
        """)
        self.setGraphicsEffect(_shadow())


class KPICard(Card):
    """Single KPI metric card for the top rows. Clickable."""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._click_handler = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(4)

        self.title_label = QLabel(title.upper())
        self.title_label.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #6B7280; "
            "letter-spacing: 0.04em; background: transparent;"
        )

        self.value_label = QLabel("—")
        self.value_label.setStyleSheet(
            "font-size: 28px; font-weight: 700; color: #1A1D23; background: transparent;"
        )

        self.delta_label = QLabel("")
        self.delta_label.setStyleSheet(
            "font-size: 12px; font-weight: 500; color: #9CA3AF; background: transparent;"
        )

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.delta_label)
        layout.addStretch()

    def set_value(self, value: str, delta: str = "", delta_color: str = "#9CA3AF"):
        self.value_label.setText(value)
        self.delta_label.setText(delta)
        self.delta_label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {delta_color}; background: transparent;"
        )

    def on_click(self, handler):
        """Register a click callback."""
        self._click_handler = handler

    def mousePressEvent(self, event):
        if self._click_handler:
            self._click_handler()
        super().mousePressEvent(event)


# ── Drill-Down Dialog ────────────────────────────────────────────────

class DrillDownDialog(QDialog):
    """Modal popup showing filtered records when a dashboard widget is clicked."""

    @staticmethod
    def _normalize_row(row_data: list, num_cols: int) -> list[str]:
        """Pad or trim so each row has exactly ``num_cols`` cells (Qt needs stable width)."""
        out: list[str] = []
        for c in range(num_cols):
            if c < len(row_data):
                out.append(str(row_data[c]))
            else:
                out.append("")
        return out

    def __init__(self, title: str, columns: list[str], rows: list[list[str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(700, 420)
        layout = QVBoxLayout(self)

        # Header
        hdr = QLabel(title)
        hdr.setStyleSheet("font-size: 16px; font-weight: 600; color: #1A1D23; background: transparent;")
        layout.addWidget(hdr)

        count_lbl = QLabel(f"{len(rows)} record(s)")
        count_lbl.setStyleSheet("font-size: 12px; color: #6B7280; background: transparent;")
        layout.addWidget(count_lbl)

        # Filter
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Type to filter...")
        self.filter_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter_input)

        self._columns = columns
        ncol = len(columns)
        self._all_rows: list[list[str]] = [self._normalize_row(list(r), ncol) for r in rows]

        # Table — sorting must stay OFF while filling or Qt hides cells until refresh (e.g. after filter).
        self.table = QTableWidget(len(self._all_rows), ncol)
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        for r, row_data in enumerate(self._all_rows):
            for c, cell in enumerate(row_data):
                self.table.setItem(r, c, QTableWidgetItem(cell))
        self.table.setSortingEnabled(True)

        layout.addWidget(self.table)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _apply_filter(self):
        needle = self.filter_input.text().strip().lower()
        ncol = len(self._columns)
        filtered = [
            r
            for r in self._all_rows
            if not needle or any(needle in str(c).lower() for c in r)
        ]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered))
        for r, row_data in enumerate(filtered):
            for c in range(ncol):
                self.table.setItem(r, c, QTableWidgetItem(row_data[c]))
        self.table.setSortingEnabled(True)


# ── Status Pill ──────────────────────────────────────────────────────

STATUS_PILL_COLORS = {
    "In Progress": ("#DBEAFE", "#1D4ED8"),
    "Review": ("#EDE9FE", "#6D28D9"),
    "Pending Docs": ("#FFEDD5", "#C2410C"),
    "Draft": ("#F3F4F6", "#4B5563"),
    "Planning": ("#E2E8F0", "#475569"),
    "Submitted": ("#DCFCE7", "#15803D"),
}


def _make_pill(text: str) -> QLabel:
    bg, fg = STATUS_PILL_COLORS.get(text, ("#F3F4F6", "#4B5563"))
    pill = QLabel(text)
    pill.setStyleSheet(
        f"background-color: {bg}; color: {fg}; border-radius: 10px; "
        f"padding: 2px 8px; font-size: 11px; font-weight: 500;"
    )
    pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return pill


def _set_row_color(table: QTableWidget, row: int, color: QColor):
    brush = QBrush(color)
    for col in range(table.columnCount()):
        item = table.item(row, col)
        if item:
            item.setForeground(brush)


# ── Denomination Chip ────────────────────────────────────────────────

class DenomChip(QFrame):
    def __init__(self, denom: float, purchased: int, required: int, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        if purchased >= required and required > 0:
            bg, fg = "#DCFCE7", "#15803D"
        elif purchased > 0:
            bg, fg = "#FFEDD5", "#C2410C"
        else:
            bg, fg = "#FEE2E2", "#DC2626"
        self.setStyleSheet(
            f"background-color: {bg}; border-radius: 6px; padding: 4px 10px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        lbl = QLabel(f"₹{denom:,.0f}  {purchased}/{required}")
        lbl.setStyleSheet(f"color: {fg}; font-size: 12px; font-weight: 600; background: transparent;")
        layout.addWidget(lbl)


# ── Main Dashboard View ──────────────────────────────────────────────

class DashboardView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(28, 20, 28, 20)
        self.main_layout.setSpacing(20)
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._build_header()
        self._build_kpi_row1()
        self._build_kpi_row2()
        self._build_main_grid()
        self._build_bottom()
        self.refresh()

    # ── Header ───────────────────────────────────────────────────────

    def _build_header(self):
        row = QHBoxLayout()
        left = QVBoxLayout()
        h1 = QLabel("Command Center")
        h1.setStyleSheet("font-size: 22px; font-weight: 700; color: #1A1D23; background: transparent;")
        self.sync_label = QLabel("● Live")
        self.sync_label.setStyleSheet("font-size: 12px; color: #16A34A; background: transparent;")
        left.addWidget(h1)
        left.addWidget(self.sync_label)
        row.addLayout(left)
        row.addStretch()

        for text, obj_name in [("Import Excel", ""), ("Export", ""), ("+ New Tender", "primaryBtn")]:
            btn = QPushButton(text)
            if obj_name:
                btn.setObjectName(obj_name)
            if text == "Import Excel":
                btn.clicked.connect(self._open_import)
            elif text == "+ New Tender":
                btn.clicked.connect(self._new_tender)
            row.addWidget(btn)

        self.main_layout.addLayout(row)

    # ── KPI Rows ─────────────────────────────────────────────────────

    def _build_kpi_row1(self):
        row = QHBoxLayout()
        row.setSpacing(16)
        self.kpi_participated = KPICard("Total Tenders Participated")
        self.kpi_due_7d = KPICard("Due in Next 7 Days")
        self.kpi_due_30d = KPICard("Due in 8–30 Days")
        self.kpi_compliance_60d = KPICard("Compliance Expiring ≤ 60D")
        for card in [self.kpi_participated, self.kpi_due_7d, self.kpi_due_30d, self.kpi_compliance_60d]:
            row.addWidget(card)
        self.main_layout.addLayout(row)

    def _build_kpi_row2(self):
        row = QHBoxLayout()
        row.setSpacing(16)
        self.kpi_critical = KPICard("Critical Compliance (<15D)")
        self.kpi_estamps_avail = KPICard("E-Stamps Available")
        self.kpi_pending_value = KPICard("Pending E-Stamp Value")
        self.kpi_spend_mtd = KPICard("Monthly Spend (MTD)")
        for card in [self.kpi_critical, self.kpi_estamps_avail, self.kpi_pending_value, self.kpi_spend_mtd]:
            row.addWidget(card)
        self.main_layout.addLayout(row)

    # ── Main Grid ────────────────────────────────────────────────────

    def _build_main_grid(self):
        grid = QHBoxLayout()
        grid.setSpacing(20)

        # Left column: Urgent Tenders
        left = QVBoxLayout()
        self.urgent_card = Card()
        urgent_layout = QVBoxLayout(self.urgent_card)
        urgent_layout.setContentsMargins(20, 16, 20, 16)
        hdr = QLabel("Urgent Tenders · next 7 days")
        hdr.setStyleSheet("font-size: 14px; font-weight: 600; color: #1A1D23; background: transparent;")
        urgent_layout.addWidget(hdr)

        self.urgent_table = QTableWidget(0, 5)
        self.urgent_table.setHorizontalHeaderLabels(["DUE", "BID / ORGANISATION", "FIRM", "VALUE", "STATUS"])
        self.urgent_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.urgent_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.urgent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.urgent_table.setShowGrid(False)
        self.urgent_table.verticalHeader().setVisible(False)
        self.urgent_table.setAlternatingRowColors(True)
        urgent_layout.addWidget(self.urgent_table)
        left.addWidget(self.urgent_card)
        grid.addLayout(left, 58)

        # Right column: E-Stamp Status + Compliance Risk
        right = QVBoxLayout()
        right.setSpacing(16)

        # E-Stamp Status
        self.estamp_card = Card()
        est_layout = QVBoxLayout(self.estamp_card)
        est_layout.setContentsMargins(20, 16, 20, 16)
        est_hdr_row = QHBoxLayout()
        self.estamp_hdr = QLabel("E-Stamp Status")
        self.estamp_hdr.setStyleSheet("font-size: 14px; font-weight: 600; color: #1A1D23; background: transparent;")
        est_hdr_row.addWidget(self.estamp_hdr)
        est_hdr_row.addStretch()
        est_layout.addLayout(est_hdr_row)

        self.estamp_purchased_lbl = QLabel("Purchased — 0")
        self.estamp_purchased_lbl.setStyleSheet("font-size: 13px; color: #1A1D23; background: transparent;")
        est_layout.addWidget(self.estamp_purchased_lbl)
        self.estamp_required_lbl = QLabel("Required for upcoming — 0")
        self.estamp_required_lbl.setStyleSheet("font-size: 13px; color: #1A1D23; background: transparent;")
        est_layout.addWidget(self.estamp_required_lbl)

        self.estamp_progress = QProgressBar()
        self.estamp_progress.setFixedHeight(8)
        self.estamp_progress.setTextVisible(False)
        self.estamp_progress.setStyleSheet("""
            QProgressBar { background-color: #FEE2E2; border-radius: 4px; border: none; }
            QProgressBar::chunk { background-color: #16A34A; border-radius: 4px; }
        """)
        est_layout.addWidget(self.estamp_progress)

        self.estamp_alert = QLabel("")
        self.estamp_alert.setWordWrap(True)
        self.estamp_alert.setStyleSheet(
            "background-color: #FEF2F2; border: 1px solid #FECACA; border-radius: 6px; "
            "padding: 8px; font-size: 12px; color: #DC2626;"
        )
        self.estamp_alert.setVisible(False)
        est_layout.addWidget(self.estamp_alert)

        self.denom_layout = QHBoxLayout()
        self.denom_layout.setSpacing(6)
        est_layout.addLayout(self.denom_layout)

        right.addWidget(self.estamp_card)

        # Compliance Risk
        self.compliance_card = Card()
        comp_layout = QVBoxLayout(self.compliance_card)
        comp_layout.setContentsMargins(20, 16, 20, 16)
        self.compliance_hdr = QLabel("Compliance Risk")
        self.compliance_hdr.setStyleSheet("font-size: 14px; font-weight: 600; color: #1A1D23; background: transparent;")
        comp_layout.addWidget(self.compliance_hdr)

        self.compliance_table = QTableWidget(0, 4)
        self.compliance_table.setHorizontalHeaderLabels(["DOCUMENT", "FIRM", "DAYS LEFT", "STATUS"])
        self.compliance_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.compliance_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.compliance_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.compliance_table.setShowGrid(False)
        self.compliance_table.verticalHeader().setVisible(False)
        self.compliance_table.setAlternatingRowColors(True)
        comp_layout.addWidget(self.compliance_table)
        right.addWidget(self.compliance_card)

        grid.addLayout(right, 42)
        self.main_layout.addLayout(grid)

    # ── Bottom: Active Tenders Donut ─────────────────────────────────

    def _build_bottom(self):
        row = QHBoxLayout()
        row.setSpacing(20)

        # Active Tenders by Status (text-based since no matplotlib)
        self.donut_card = Card()
        donut_layout = QVBoxLayout(self.donut_card)
        donut_layout.setContentsMargins(20, 16, 20, 16)
        donut_hdr = QLabel("Active Tenders by Status")
        donut_hdr.setStyleSheet("font-size: 14px; font-weight: 600; color: #1A1D23; background: transparent;")
        donut_layout.addWidget(donut_hdr)
        self.donut_total_label = QLabel("")
        self.donut_total_label.setStyleSheet("font-size: 32px; font-weight: 700; color: #1A1D23; background: transparent;")
        self.donut_total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        donut_layout.addWidget(self.donut_total_label)
        self.status_legend_layout = QVBoxLayout()
        donut_layout.addLayout(self.status_legend_layout)
        donut_layout.addStretch()

        # Bids Awarded summary
        self.awarded_card = Card()
        awarded_layout = QVBoxLayout(self.awarded_card)
        awarded_layout.setContentsMargins(20, 16, 20, 16)
        awarded_hdr = QLabel("Bids Awarded — Year-wise, Firm-wise")
        awarded_hdr.setStyleSheet("font-size: 14px; font-weight: 600; color: #1A1D23; background: transparent;")
        awarded_layout.addWidget(awarded_hdr)
        self.awarded_table = QTableWidget(0, 3)
        self.awarded_table.setHorizontalHeaderLabels(["FIRM", "FY", "COUNT"])
        self.awarded_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.awarded_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.awarded_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.awarded_table.setShowGrid(False)
        self.awarded_table.verticalHeader().setVisible(False)
        awarded_layout.addWidget(self.awarded_table)

        row.addWidget(self.awarded_card, 58)
        row.addWidget(self.donut_card, 42)
        self.main_layout.addLayout(row)

    # ── Refresh ──────────────────────────────────────────────────────

    def refresh(self) -> None:
        with session_scope() as session:
            snap = dashboard.build_snapshot(session)

        now = datetime.now()
        self.sync_label.setText(
            f"● Live · last sync Today, {now.strftime('%H:%M')} · FY {snap.current_fy}"
        )

        # KPI Row 1
        self.kpi_participated.set_value(str(snap.total_tenders_participated))
        self.kpi_due_7d.set_value(
            str(len(snap.tenders_7d)),
            f"{snap.tenders_7d_critical_count} critical" if snap.tenders_7d_critical_count else "",
            "#DC2626" if snap.tenders_7d_critical_count else "#9CA3AF",
        )
        self.kpi_due_30d.set_value(str(snap.tenders_8_to_30d_count))
        self.kpi_compliance_60d.set_value(str(len(snap.compliance_60d)))

        # KPI Row 2
        self.kpi_critical.set_value(
            str(snap.compliance_15d_count),
            "action required" if snap.compliance_15d_count > 0 else "",
            "#DC2626",
        )
        es = snap.estamp_status
        avail = es.purchased_count
        req = es.pending_count + es.allocated_count
        self.kpi_estamps_avail.set_value(
            f"{avail} / {req} req",
            f"{es.shortfall} short" if es.shortfall > 0 else "sufficient",
            "#DC2626" if es.shortfall > 0 else "#16A34A",
        )
        self.kpi_pending_value.set_value(
            _fmt_currency(es.pending_value),
            f"{es.pending_count} purchases queued" if es.pending_count else "",
        )
        self.kpi_spend_mtd.set_value(
            _fmt_currency(snap.estamp_mtd.total_spent),
            f"vs {_fmt_currency(snap.estamp_mtd.vs_same_month_last_fy)} last FY",
        )

        # Urgent Tenders
        self._fill_urgent(snap.tenders_7d)
        # E-Stamp Status
        self._fill_estamp_status(es)
        # Compliance Risk
        self._fill_compliance(snap.compliance_60d)
        # Donut
        self._fill_donut(snap.active_by_status)
        # Awarded
        self._fill_awarded(snap.bids_awarded)

        # Wire KPI drill-down handlers (store data references for click handlers)
        self._snap = snap
        self.kpi_participated.on_click(self._drill_participated)
        self.kpi_due_7d.on_click(self._drill_due_7d)
        self.kpi_due_30d.on_click(self._drill_due_30d)
        self.kpi_compliance_60d.on_click(self._drill_compliance_60d)
        self.kpi_critical.on_click(self._drill_critical)
        self.kpi_estamps_avail.on_click(self._drill_estamps)
        self.kpi_pending_value.on_click(self._drill_pending_estamps)
        self.kpi_spend_mtd.on_click(self._drill_spend_mtd)

    # ── Drill-Down Handlers ──────────────────────────────────────────

    def _drill_participated(self):
        with session_scope() as session:
            from ..models.tender import Tender
            from ..services.dashboard import is_participating_status

            tenders = [
                t
                for t in session.query(Tender)
                .filter(Tender.is_reference == False)  # noqa: E712
                .order_by(Tender.due_date.asc().nullslast())
                .all()
                if is_participating_status(t.participation_status)
            ]
            from ..services.tender_rates import effective_publish_rate

            rows = []
            for t in tenders:
                er = effective_publish_rate(t)
                cpm = t.contract_period_months
                rows.append(
                    [
                        t.bid_no or "-",
                        t.organisation or "-",
                        t.firm.name if t.firm else "-",
                        f"₹{t.tender_value:,.0f}" if t.tender_value else "-",
                        f"{cpm:g}" if cpm is not None else "-",
                        f"{er:,.4f}" if er is not None else "-",
                        t.our_status or "-",
                    ]
                )
        DrillDownDialog(
            "Total Tenders Participated",
            [
                "Bid No",
                "Organisation",
                "Firm",
                "Value",
                "Contract (mo)",
                "Publish rate",
                "Status",
            ],
            rows,
            self,
        ).exec()

    def _drill_due_7d(self):
        rows = [[r.bid_no or "-", r.organisation or "-", r.firm_name,
                  f"{r.due_in_days}d" if r.due_in_days is not None else "-",
                  r.due_date.isoformat() if r.due_date else "-",
                  r.our_status or "-"] for r in self._snap.tenders_7d]
        DrillDownDialog("Due in Next 7 Days", ["Bid No", "Organisation", "Firm", "Days Left", "Due Date", "Status"], rows, self).exec()

    def _drill_due_30d(self):
        with session_scope() as session:
            from datetime import date, timedelta
            today = date.today()
            dl_rows = dashboard.tenders_due_between(session, min_days=8, max_days=30, today=today)
        rows = [[r.bid_no or "-", r.organisation or "-", r.firm_name,
                  f"{r.due_in_days}d" if r.due_in_days is not None else "-",
                  r.due_date.isoformat() if r.due_date else "-"] for r in dl_rows]
        DrillDownDialog("Due in 8–30 Days", ["Bid No", "Organisation", "Firm", "Days Left", "Due Date"], rows, self).exec()

    def _drill_compliance_60d(self):
        rows = [[d.document_name, d.firm.name if d.firm else "-",
                  str(d.days_until_expiry) if d.days_until_expiry is not None else "-",
                  d.expiry_date.isoformat() if d.expiry_date else "-",
                  d.status] for d in self._snap.compliance_60d]
        DrillDownDialog("Compliance Expiring ≤ 60 Days", ["Document", "Firm", "Days Left", "Expiry", "Status"], rows, self).exec()

    def _drill_critical(self):
        critical = [d for d in self._snap.compliance_60d if d.days_until_expiry is not None and d.days_until_expiry <= 15]
        rows = [[d.document_name, d.firm.name if d.firm else "-",
                  str(d.days_until_expiry), d.expiry_date.isoformat() if d.expiry_date else "-",
                  d.status] for d in critical]
        DrillDownDialog("Critical Compliance (<15 Days)", ["Document", "Firm", "Days Left", "Expiry", "Status"], rows, self).exec()

    def _drill_estamps(self):
        with session_scope() as session:
            from ..models.estamp import Estamp, STATUS_LABELS
            estamps = session.query(Estamp).filter(Estamp.status.in_(("purchased", "pending"))).all()
            rows = [[STATUS_LABELS.get(e.status, e.status), f"₹{e.denomination or e.unit_rate:,.0f}",
                      str(e.quantity), e.firm.name if e.firm else "-",
                      f"₹{e.actual_cost_total:,.2f}"] for e in estamps]
        DrillDownDialog("E-Stamps Available / Pending", ["Status", "Denomination", "Qty", "Firm", "Actual Cost"], rows, self).exec()

    def _drill_pending_estamps(self):
        with session_scope() as session:
            from ..models.estamp import Estamp
            pending = session.query(Estamp).filter(Estamp.status == "pending").all()
            rows = [[f"₹{e.denomination or e.unit_rate:,.0f}", str(e.quantity),
                      e.firm.name if e.firm else "-",
                      f"₹{e.estimated_cost or 0:,.0f}",
                      e.pending_required_by.isoformat() if e.pending_required_by else "-",
                      e.pending_reason or "-"] for e in pending]
        DrillDownDialog("Pending E-Stamp Purchases", ["Denomination", "Qty", "Firm", "Est. Cost", "Required By", "Reason"], rows, self).exec()

    def _drill_spend_mtd(self):
        with session_scope() as session:
            from ..models.estamp import Estamp
            from datetime import date
            today = date.today()
            start = today.replace(day=1)
            stamps = session.query(Estamp).filter(
                Estamp.entry_date >= start, Estamp.entry_date <= today,
                Estamp.status.in_(("purchased", "allocated", "used")),
            ).all()
            rows = [[f"₹{e.denomination or e.unit_rate:,.0f}", str(e.quantity),
                      e.firm.name if e.firm else "-",
                      f"₹{e.actual_cost_total:,.2f}",
                      e.purchase_date.isoformat() if e.purchase_date else "-",
                      e.vendor or "-"] for e in stamps]
        DrillDownDialog("Monthly Spend (MTD)", ["Denomination", "Qty", "Firm", "Actual Cost", "Purchase Date", "Vendor"], rows, self).exec()

    def _fill_urgent(self, rows):
        self.urgent_table.setSortingEnabled(False)
        self.urgent_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            due_text = ""
            if row.due_in_days is not None and row.due_date:
                due_text = f"● {row.due_in_days}d left · {row.due_date.strftime('%d %b')}"
            self.urgent_table.setItem(r, 0, QTableWidgetItem(due_text))

            bid_org = f"{row.bid_no or '-'}\n{row.organisation or ''}"
            self.urgent_table.setItem(r, 1, QTableWidgetItem(bid_org))

            firm_text = row.firm_code or row.firm_name[:4].upper()
            self.urgent_table.setItem(r, 2, QTableWidgetItem(firm_text))

            self.urgent_table.setItem(r, 3, QTableWidgetItem(_fmt_currency(row.tender_value)))
            self.urgent_table.setItem(r, 4, QTableWidgetItem(row.our_status or "Draft"))

            if row.due_in_days is not None:
                if row.due_in_days <= 1:
                    _set_row_color(self.urgent_table, r, QColor("#DC2626"))
                elif row.due_in_days <= 3:
                    _set_row_color(self.urgent_table, r, QColor("#D97706"))

        self.urgent_table.setSortingEnabled(True)

    def _fill_estamp_status(self, es):
        self.estamp_purchased_lbl.setText(
            f"Purchased — {es.purchased_count} ({_fmt_currency(es.purchased_value)})"
        )
        self.estamp_required_lbl.setText(
            f"Required for upcoming — {es.pending_count} ({_fmt_currency(es.pending_value)})"
        )
        total = es.purchased_count + es.pending_count
        if total > 0:
            self.estamp_progress.setMaximum(total)
            self.estamp_progress.setValue(es.purchased_count)
        else:
            self.estamp_progress.setMaximum(1)
            self.estamp_progress.setValue(0)

        if es.shortfall > 0:
            self.estamp_alert.setText(
                "Insufficient E-Stamps for upcoming bids. "
                "Purchase before the next deadline to avoid blocking submission."
            )
            self.estamp_alert.setVisible(True)
        else:
            self.estamp_alert.setVisible(False)

        # Clear old chips
        while self.denom_layout.count():
            item = self.denom_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for denom, info in es.denomination_breakdown.items():
            chip = DenomChip(denom, info["purchased"], info["required"])
            self.denom_layout.addWidget(chip)

    def _fill_compliance(self, docs):
        self.compliance_hdr.setText(f"Compliance Risk · {len(docs)}")
        self.compliance_table.setSortingEnabled(False)
        self.compliance_table.setRowCount(len(docs))
        for r, d in enumerate(docs):
            self.compliance_table.setItem(r, 0, QTableWidgetItem(d.document_name))
            firm_text = d.firm.name if d.firm else "-"
            self.compliance_table.setItem(r, 1, QTableWidgetItem(firm_text))

            days = d.days_until_expiry
            days_text = f"{days}d left" if days is not None and days >= 0 else "overdue"
            item = QTableWidgetItem(days_text)
            self.compliance_table.setItem(r, 2, item)
            self.compliance_table.setItem(r, 3, QTableWidgetItem(d.status))

            if days is not None:
                if days < 0:
                    _set_row_color(self.compliance_table, r, QColor("#DC2626"))
                elif days <= 15:
                    _set_row_color(self.compliance_table, r, QColor("#DC2626"))
                elif days <= 30:
                    _set_row_color(self.compliance_table, r, QColor("#D97706"))

        self.compliance_table.setSortingEnabled(True)

    def _fill_donut(self, status_counts: dict):
        total = sum(status_counts.values())
        self.donut_total_label.setText(str(total))

        while self.status_legend_layout.count():
            item = self.status_legend_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        colors = {
            "In Progress": "#2563EB", "Review": "#7C3AED", "Planning": "#64748B",
            "Draft": "#9CA3AF", "Pending Docs": "#D97706", "Submitted": "#16A34A",
        }
        for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
            color = colors.get(status, "#6B7280")
            row = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 14px; background: transparent;")
            dot.setFixedWidth(18)
            lbl = QLabel(f"{status}")
            lbl.setStyleSheet("font-size: 13px; color: #1A1D23; background: transparent;")
            cnt = QLabel(str(count))
            cnt.setStyleSheet("font-size: 13px; font-weight: 600; color: #1A1D23; background: transparent;")
            cnt.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(dot)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(cnt)
            wrapper = QWidget()
            wrapper.setLayout(row)
            wrapper.setStyleSheet("background: transparent;")
            self.status_legend_layout.addWidget(wrapper)

    def _fill_awarded(self, rows):
        self.awarded_table.setSortingEnabled(False)
        self.awarded_table.setRowCount(len(rows))
        for r, a in enumerate(rows):
            self.awarded_table.setItem(r, 0, QTableWidgetItem(a.firm_code or a.firm_name[:6]))
            self.awarded_table.setItem(r, 1, QTableWidgetItem(a.fy))
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, a.count)
            self.awarded_table.setItem(r, 2, item)
        self.awarded_table.setSortingEnabled(True)

    # ── Actions ──────────────────────────────────────────────────────

    def _open_import(self):
        from .import_dialog import ImportDialog
        dlg = ImportDialog(self)
        dlg.exec()

    def _new_tender(self):
        # Navigate to tenders tab and trigger new
        parent = self.parent()
        while parent:
            if hasattr(parent, 'tabs'):
                for i in range(parent.tabs.count()):
                    if parent.tabs.tabText(i) == "Tenders":
                        parent.tabs.setCurrentIndex(i)
                        if hasattr(parent, 'tenders'):
                            parent.tenders._new()
                        break
                break
            parent = parent.parent()
