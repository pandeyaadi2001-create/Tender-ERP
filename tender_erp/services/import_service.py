"""Excel Import Service."""

from typing import Any
from datetime import datetime, date
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from ..models.firm import Firm
from ..models.tender import Tender
from ..models.estamp import Estamp
from ..models.compliance import ComplianceDocument
from ..models.user import Role
from .auth import create_user


def parse_excel(file_path: str) -> tuple[list[str], list[dict[str, Any]]]:
    """Parse an excel file into headers and data dictionaries."""
    wb = load_workbook(filename=file_path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], []
    
    headers = [str(cell) for cell in rows[0] if cell is not None]
    data = []
    for row in rows[1:]:
        row_dict = {}
        is_empty = True
        for i, val in enumerate(row):
            if i < len(headers):
                if isinstance(val, datetime):
                    val = val.date()
                row_dict[headers[i]] = val
                if val is not None and str(val).strip():
                    is_empty = False
        if not is_empty:
            data.append(row_dict)
            
    return headers, data


def process_import(
    session: Session, module: str, mapping: dict[str, str], data: list[dict[str, Any]]
) -> tuple[int, list[str]]:
    """Convert mapped data into ORM models and save them.
    
    If any row fails validation or DB integrity constraints, 
    the entire transaction is rolled back and errors are returned.
    """
    success_count = 0
    errors = []
    
    for idx, row in enumerate(data):
        try:
            mapped_row = {db_f: row.get(ex_h) for db_f, ex_h in mapping.items() if ex_h}
            
            # Helper to fetch Firm ID from name
            firm_name = mapped_row.pop("firm_name", None)
            firm_id = None
            if firm_name:
                firm = session.query(Firm).filter(Firm.name == firm_name).first()
                if firm:
                    firm_id = firm.id
                else:
                    errors.append(f"Row {idx+1}: Firm '{firm_name}' not found in DB.")
                    continue

            if module == "Firms":
                if not mapped_row.get("name"):
                    errors.append(f"Row {idx+1}: Legal name is required")
                    continue
                session.add(Firm(**mapped_row))
                
            elif module == "Tenders":
                if not firm_id:
                    errors.append(f"Row {idx+1}: 'firm_name' is required for Tenders")
                    continue
                mapped_row["firm_id"] = firm_id
                
                # Coerce numeric fields safely
                for num_col in ['tender_value', 'emd', 'publish_rate', 'quoted_rates', 'contract_period_months']:
                    if mapped_row.get(num_col):
                        try:
                            mapped_row[num_col] = float(mapped_row[num_col])
                        except ValueError:
                            mapped_row.pop(num_col, None)
                
                session.add(Tender(**mapped_row))
                
            elif module == "Users":
                username = mapped_row.get("username")
                full_name = mapped_row.get("full_name")
                role = mapped_row.get("role", Role.EDITOR.value)
                if not username or not full_name:
                    errors.append(f"Row {idx+1}: Username and Full Name required")
                    continue
                
                # Create with a dummy password. The auth interceptor will force reset
                # because `last_login_at` will remain None.
                create_user(
                    session, 
                    username=username, 
                    full_name=full_name, 
                    password="TempPassword123!", 
                    role=role
                )
                
            elif module == "E-Stamps":
                if not firm_id:
                    errors.append(f"Row {idx+1}: 'firm_name' is required for E-Stamps")
                    continue
                mapped_row["firm_id"] = firm_id
                if not mapped_row.get("entry_date"):
                    mapped_row["entry_date"] = date.today()
                    
                if mapped_row.get("quantity"):
                    mapped_row["quantity"] = int(mapped_row["quantity"])
                if mapped_row.get("unit_rate"):
                    mapped_row["unit_rate"] = float(mapped_row["unit_rate"])
                    
                session.add(Estamp(**mapped_row))
                
            elif module == "Compliance":
                if not firm_id:
                    errors.append(f"Row {idx+1}: 'firm_name' is required for Compliance")
                    continue
                mapped_row["firm_id"] = firm_id
                if not mapped_row.get("document_name"):
                    errors.append(f"Row {idx+1}: Document name required")
                    continue
                    
                session.add(ComplianceDocument(**mapped_row))
                
            success_count += 1
            
        except Exception as e:
            errors.append(f"Row {idx+1}: {str(e)}")
            
    if not errors:
        session.commit()
    else:
        session.rollback()
        success_count = 0
        
    return success_count, errors
