# Metric → CRUD Map

Every dashboard element and its corresponding data entry path.

| Dashboard Element | Source Entity | CRUD Page | Create/Edit Form |
|---|---|---|---|
| **TOTAL TENDERS PARTICIPATED** | `Tender.participation_status == "Participated"` | Tenders tab | TenderEditor → Participation dropdown |
| **DUE IN NEXT 7 DAYS** | `Tender.due_date` within 0–7 days | Tenders tab | TenderEditor → Due date field |
| **DUE IN 8–30 DAYS** | `Tender.due_date` within 8–30 days | Tenders tab | TenderEditor → Due date field |
| **COMPLIANCE EXPIRING ≤ 60D** | `ComplianceDocument.expiry_date` within 60 days | Compliance tab | ComplianceEditor → Expiry date, Status |
| **CRITICAL COMPLIANCE (<15D)** | `ComplianceDocument.expiry_date` within 15 days | Compliance tab | ComplianceEditor → Expiry date, Renew action |
| **E-STAMPS AVAILABLE** | `Estamp.status == "purchased"` count | E-Stamps tab | Record Purchase dialog |
| **PENDING E-STAMP VALUE** | `Estamp.status == "pending"` sum of estimated_cost | E-Stamps tab | Queue Purchase dialog → denomination, qty |
| **MONTHLY SPEND (MTD)** | `Estamp` purchases in current month | E-Stamps tab | Record Purchase dialog → purchase_date |
| **Urgent Tenders (7d table)** | `Tender` where due_date ≤ 7 days | Tenders tab | TenderEditor (click row → edit) |
| **E-Stamp Status card** | `Estamp` grouped by status + denomination | E-Stamps tab | Queue Purchase / Record Purchase dialogs |
| **E-Stamp denomination chips** | `Estamp` grouped by denomination | E-Stamps tab | Queue Purchase (denomination dropdown) |
| **Compliance Risk list** | `ComplianceDocument` ordered by days_until_expiry | Compliance tab | ComplianceEditor → dates, status |
| **Active Tenders by Status (donut)** | `Tender.our_status` grouped count | Tenders tab | TenderEditor → Our status field |
| **Bids Awarded (chart + table)** | `Tender.awarded_flag == True` | Tenders tab | TenderEditor → Award Details section |
| **Nav badge: Tenders** | Open tender count | Auto-derived | — |
| **Nav badge: Compliance** | Compliance ≤60d count | Auto-derived | — |
