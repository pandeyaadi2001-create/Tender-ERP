# Changelog

## [2.0.0] — 2026-04-18

### Schema Changes
- **Estamp**: Added `denomination`, `status` (pending/purchased/allocated/used/cancelled), `pending_queued_at`, `pending_required_by`, `pending_reason`, `estimated_cost`, `purchase_date`, `vendor`, `voucher_number`, `voucher_document`, `stamp_state`, `allocated_bid_id`
- **Tender**: Added `portal`, `category`, `document_fee`, `processing_fee`, `awarded_flag`, `awarded_date`, `awarded_value`, `loa_po_number`, `loa_document`, `execution_status`
- **Firm**: Added `firm_code`, `firm_color_hex`, `state`
- Added `migrate.py` for safe column-level migrations on existing SQLite databases

### Removed Components
- `UpcomingTenders8to30Table` — removed from dashboard DOM (KPI number kept)
- `OverdueActionsCard` — removed from dashboard DOM
- `DecisionQueueCard` — removed from dashboard DOM
- `MonthlySpendTrendChart` — removed from dashboard DOM
- `PendingStatusTable` — removed from dashboard DOM
- `DSCExpiryWatch` — removed from dashboard DOM
- Dark theme (`DARK_THEME_QSS`) — replaced with light design system

### New Components
- `KPICard` — reusable metric card with title, value, delta line
- `DenomChip` — colored denomination chip showing purchased/required
- `QueuePurchaseDialog` — creates pending e-stamp purchase requests
- `RecordPurchaseDialog` — converts pending→purchased or records direct purchases
- `BidsAwardedTable` — year-wise firm-wise awarded tenders summary
- `ActiveTendersDonut` — status distribution legend with counts
- `EstampStatusCard` — progress bar + denomination breakdown + alert
- `ComplianceRiskCard` — sorted compliance documents with color-coded urgency

### New Features
- **E-Stamp lifecycle**: Full pending→purchased→allocated→used workflow
- **Tender award tracking**: Awarded flag, date, value, LOA/PO, execution status
- **Firm identity**: Short code + hex color used for colored dots across all views
- **Command Center dashboard**: 8 KPI cards, urgent tenders, e-stamp status, compliance risk
- **Light design system**: White cards on #F7F8FA, Inter font, soft borders, blue accent

### Files Added
- `tender_erp/migrate.py`
- `metric_to_crud_map.md`
- `CHANGELOG.md`
- `templates/` (Excel import templates)

### Files Modified
- `tender_erp/models/estamp.py` — full rewrite with lifecycle fields
- `tender_erp/models/tender.py` — award tracking + classification fields
- `tender_erp/models/firm.py` — firm_code + color fields
- `tender_erp/app.py` — light theme QSS
- `tender_erp/services/dashboard.py` — expanded snapshot with new metrics
- `tender_erp/ui/dashboard_view.py` — complete rewrite
- `tender_erp/ui/estamps_view.py` — complete rewrite with lifecycle UI
- `tender_erp/ui/tenders_view.py` — award section + new fields
- `tender_erp/ui/firms_view.py` — firm_code + color fields
- `tender_erp/db.py` — migration hook
- `tender_erp/seed_data.py` — demo data seeder
