"""Excel Import Wizard Dialog."""

import traceback
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QFileDialog, QTableWidget, QTableWidgetItem,
    QMessageBox, QTextEdit, QHeaderView, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt

from ..services.import_service import parse_excel, process_import
from ..db import session_scope
from .event_bus import global_bus


IMPORT_MODULES = {
    "Firms": ["name", "gstin", "pan", "udyam", "address", "contact_person", "contact_phone", "contact_email"],
    "Tenders": ["firm_name", "bid_no", "organisation", "department", "state", "location", "publish_date", "due_date", "tender_value", "emd", "participation_status"],
    "E-Stamps": ["firm_name", "entry_date", "tender_name_text", "quantity", "unit_rate"],
    "Compliance": ["firm_name", "document_name", "document_type", "certificate_no", "issue_date", "expiry_date", "status"],
    "Users": ["username", "full_name", "role", "email"]
}


class ImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Excel Bulk Import")
        self.resize(800, 600)
        
        self.file_path = ""
        self.excel_headers = []
        self.excel_data = []
        self.mapping_combos = {}

        layout = QVBoxLayout(self)

        # 1. Module & File Selection
        top_group = QGroupBox("1. Select Module & File")
        top_layout = QHBoxLayout()
        
        self.module_cb = QComboBox()
        self.module_cb.addItems(list(IMPORT_MODULES.keys()))
        self.module_cb.currentTextChanged.connect(self._rebuild_mapping)
        
        self.file_label = QLabel("No file selected")
        self.pick_btn = QPushButton("Browse Excel...")
        self.pick_btn.clicked.connect(self._pick_file)
        
        top_layout.addWidget(QLabel("Target Module:"))
        top_layout.addWidget(self.module_cb)
        top_layout.addSpacing(20)
        top_layout.addWidget(self.file_label, stretch=1)
        top_layout.addWidget(self.pick_btn)
        top_group.setLayout(top_layout)
        layout.addWidget(top_group)

        # 2. Column Mapping
        self.map_group = QGroupBox("2. Map Excel Columns to Database Fields")
        self.map_layout = QFormLayout()
        self.map_group.setLayout(self.map_layout)
        layout.addWidget(self.map_group)

        # 3. Preview & Logs
        preview_group = QGroupBox("3. Import Log")
        preview_layout = QVBoxLayout()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        preview_layout.addWidget(self.log_view)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, stretch=1)

        # Buttons
        btn_layout = QHBoxLayout()
        self.import_btn = QPushButton("Validate & Import")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._do_import)
        self.cancel_btn = QPushButton("Close")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.import_btn)
        layout.addLayout(btn_layout)

        self._rebuild_mapping()

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Excel File", "", "Excel Files (*.xlsx *.xls)")
        if not path:
            return
            
        self.file_path = path
        self.file_label.setText(path)
        
        try:
            self.excel_headers, self.excel_data = parse_excel(path)
            self.log_view.append(f"Loaded {len(self.excel_data)} rows from {path}")
            self.import_btn.setEnabled(True)
            self._rebuild_mapping()
        except Exception as e:
            self.log_view.append(f"<span style='color:red;'>Failed to load file: {str(e)}</span>")
            self.excel_headers = []
            self.excel_data = []
            self.import_btn.setEnabled(False)

    def _rebuild_mapping(self):
        # Clear old map layout
        while self.map_layout.count():
            item = self.map_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.mapping_combos.clear()
        target_fields = IMPORT_MODULES[self.module_cb.currentText()]
        
        # Build dropdowns for each DB field
        for field in target_fields:
            cb = QComboBox()
            cb.addItem("-- Ignore --", "")
            
            # Add headers and try to auto-map by similar names
            for h in self.excel_headers:
                cb.addItem(h, h)
                # Auto-select if exact match or close match
                if h.lower().replace(" ", "_") == field.lower():
                    cb.setCurrentText(h)
                    
            self.mapping_combos[field] = cb
            self.map_layout.addRow(f"DB: <b>{field}</b>", cb)

    def _do_import(self):
        if not self.excel_data:
            return
            
        module = self.module_cb.currentText()
        mapping = {field: cb.currentData() for field, cb in self.mapping_combos.items()}
        
        self.log_view.append(f"<b>Starting import for {module}...</b>")
        
        refresh_views = False
        try:
            with session_scope() as session:
                success_count, errors = process_import(session, module, mapping, self.excel_data)
                
                if errors:
                    self.log_view.append("<span style='color:red;'><b>Import Failed due to errors:</b></span>")
                    for err in errors[:20]:  # Show first 20 errors
                        self.log_view.append(f"<span style='color:red;'>{err}</span>")
                    if len(errors) > 20:
                        self.log_view.append(f"<span style='color:red;'>...and {len(errors) - 20} more errors.</span>")
                else:
                    self.log_view.append(f"<span style='color:green;'><b>Successfully imported {success_count} records!</b></span>")
                    refresh_views = True
                    
        except Exception as e:
            self.log_view.append(f"<span style='color:red;'><b>Critical Error:</b> {str(e)}</span>")
            self.log_view.append(traceback.format_exc())
            return

        # After session_scope exits so the commit from process_import is fully settled.
        if refresh_views:
            global_bus.dataChanged.emit()
