"""Checklist rule library editor (spec §3.6)."""

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
from ..models.checklist import ChecklistRule
from .event_bus import global_bus
from .widgets import make_table

INSTRUCTIONS = (
    "<b>How checklist rules work.</b> Every rule maps a condition "
    "(e.g., Nature of Work = 'Healthcare Kitchen') to one required "
    "document. The app applies all matching rules plus the universal "
    "base list (condition field <tt>*</tt>) when generating a "
    "checklist. To add a new tender type, click <b>New rule</b>, set "
    "the condition field to <tt>nature_of_work</tt> and the value to "
    "your tender type, and list the required document. Test by "
    "generating a checklist on a sample tender."
)


class RuleEditor(QDialog):
    def __init__(self, rule: ChecklistRule | None, parent=None) -> None:
        super().__init__(parent)
        self.rule_id = rule.id if rule else None
        self.setWindowTitle("Edit rule" if rule else "New rule")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(rule.name if rule else "")
        self.field_cb = QComboBox()
        self.field_cb.addItems(
            [
                "*",
                "nature_of_work",
                "department",
                "state",
                "issuing_authority",
                "payment_mode",
            ]
        )
        if rule:
            idx = self.field_cb.findText(rule.condition_field)
            if idx >= 0:
                self.field_cb.setCurrentIndex(idx)
        self.value = QLineEdit(rule.condition_value if rule and rule.condition_value else "")
        self.doc = QLineEdit(rule.required_document if rule else "")
        self.notes = QTextEdit(rule.notes if rule and rule.notes else "")
        self.notes.setFixedHeight(60)
        self.active = QCheckBox("Active")
        self.active.setChecked(rule.is_active if rule else True)
        form.addRow("Rule name", self.name)
        form.addRow("Condition field", self.field_cb)
        form.addRow("Condition value", self.value)
        form.addRow("Required document", self.doc)
        form.addRow("Notes", self.notes)
        form.addRow("", self.active)
        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self) -> None:
        if not self.name.text().strip() or not self.doc.text().strip():
            QMessageBox.warning(self, "Validation", "Name and required document are mandatory.")
            return
        with session_scope() as session:
            if self.rule_id:
                rule = session.get(ChecklistRule, self.rule_id)
                if rule is None:
                    return
            else:
                rule = ChecklistRule(name="", required_document="")
                session.add(rule)
            rule.name = self.name.text().strip()
            rule.condition_field = self.field_cb.currentText()
            rule.condition_value = self.value.text().strip() or None
            rule.required_document = self.doc.text().strip()
            rule.notes = self.notes.toPlainText() or None
            rule.is_active = self.active.isChecked()
        self.accept()


class ChecklistRulesView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        help_box = QLabel(INSTRUCTIONS)
        help_box.setWordWrap(True)
        help_box.setStyleSheet(
            "background: #eef5ff; border: 1px solid #99b; padding: 8px;"
        )
        layout.addWidget(help_box)

        bar = QHBoxLayout()
        self.new_btn = QPushButton("New rule")
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        self.delete_many_btn = QPushButton("Delete selected")
        self.seed_btn = QPushButton("Seed starter library")
        self.refresh_btn = QPushButton("Refresh")
        bar.addWidget(self.new_btn)
        bar.addWidget(self.edit_btn)
        bar.addWidget(self.delete_btn)
        bar.addWidget(self.delete_many_btn)
        bar.addWidget(self.seed_btn)
        bar.addStretch(1)
        bar.addWidget(self.refresh_btn)
        layout.addLayout(bar)

        self.table = make_table(
            ["", "Name", "Field", "Value", "Required document", "Active"],
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
        self.seed_btn.clicked.connect(self._seed)
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
            rules = (
                session.query(ChecklistRule)
                .order_by(ChecklistRule.condition_field, ChecklistRule.name)
                .all()
            )
            self.table.setRowCount(len(rules))
            for r, rule in enumerate(rules):
                sel = QTableWidgetItem("")
                sel.setFlags(
                    sel.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEnabled
                )
                sel.setCheckState(Qt.CheckState.Unchecked)
                sel.setData(Qt.ItemDataRole.UserRole, rule.id)
                self.table.setItem(r, 0, sel)
                self.table.setItem(r, 1, QTableWidgetItem(rule.name))
                self.table.setItem(r, 2, QTableWidgetItem(rule.condition_field))
                self.table.setItem(r, 3, QTableWidgetItem(rule.condition_value or "-"))
                self.table.setItem(r, 4, QTableWidgetItem(rule.required_document))
                self.table.setItem(r, 5, QTableWidgetItem("yes" if rule.is_active else "no"))

    def _new(self) -> None:
        dlg = RuleEditor(None, self)
        if dlg.exec():
            self.refresh()

    def _edit(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        with session_scope() as session:
            rule = session.get(ChecklistRule, rid)
            if rule is None:
                return
            session.expunge(rule)
        dlg = RuleEditor(rule, self)
        if dlg.exec():
            self.refresh()

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        with session_scope() as session:
            rule = session.get(ChecklistRule, rid)
            if rule is None:
                return
            session.delete(rule)
        global_bus.dataChanged.emit()
        self.refresh()

    def _delete_many(self) -> None:
        ids = self._checked_ids()
        if not ids:
            QMessageBox.information(self, "Delete", "Tick one or more rows in the first column.")
            return
        if (
            QMessageBox.question(self, "Delete", f"Delete {len(ids)} rule(s)?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        with session_scope() as session:
            for rid in ids:
                rule = session.get(ChecklistRule, rid)
                if rule is not None:
                    session.delete(rule)
        global_bus.dataChanged.emit()
        self.refresh()

    def _seed(self) -> None:
        from ..seed_data import seed_checklist_rules

        with session_scope() as session:
            added = seed_checklist_rules(session)
        if added:
            QMessageBox.information(self, "Seeded", f"Added {added} starter rules.")
        else:
            QMessageBox.information(self, "Seeded", "Library already populated.")
        self.refresh()
