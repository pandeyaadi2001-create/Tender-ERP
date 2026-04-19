"""Reusable Qt widgets."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDoubleSpinBox,
    QHeaderView,
    QLineEdit,
    QTableWidget,
)


def make_date_edit(optional: bool = True) -> QDateEdit:
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setDisplayFormat("yyyy-MM-dd")
    if optional:
        edit.setSpecialValueText(" ")
        edit.setMinimumDate(QDate(1900, 1, 1))
    return edit


def make_money_spin() -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setDecimals(2)
    spin.setMaximum(1e12)
    spin.setGroupSeparatorShown(True)
    return spin


def make_table(columns: list[str], *, extended_selection: bool = False) -> QTableWidget:
    tbl = QTableWidget(0, len(columns))
    tbl.setHorizontalHeaderLabels(columns)
    tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    tbl.setSelectionMode(
        QTableWidget.SelectionMode.ExtendedSelection
        if extended_selection
        else QTableWidget.SelectionMode.SingleSelection
    )
    tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return tbl
