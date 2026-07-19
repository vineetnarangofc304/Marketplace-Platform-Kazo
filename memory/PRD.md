# KAZO Marketplace Finance & Reconciliation Platform — PRD

## Original Problem Statement
KAZO Marketplace Finance Operating System — ingests marketplace reports, calculates expected charges, reconciles settlements, identifies leakage, manages recoveries. First connector: Myntra. Marketplace-agnostic core.

## User Choices (2026-02)
- Auth: Simple username/password (JWT, bcrypt)
- File storage: MongoDB (uploaded XLSX parsed and stored as parsed docs)
- Frontend language: React JS (agent's choice)
- AI insights: Deferred to later
- Sample files provided: `Sale Data_Myntra.xlsx`, `GT CHNARGES CALCULATION.docx`

## User Personas
- Finance & reconciliation teams (primary daily users)
- Marketplace operations teams
- Finance controllers / CFO / CEO (dashboards)
- Administrators (masters, roles)

## Core Requirements (Static)
1. Upload sales data & auto-detect Myntra "Raw_Online Sale-m" schema
2. Configurable Myntra commission structure — commission % by category/sub-cat/price-slab, fixed fee slabs (AISP), GT/logistics charges by sub-cat level × price band, return fee by level × zone, TCS/TDS/GST
3. Calculate expected commission & deductions per order-item, store full breakdown
4. Upload settlement file, reconcile expected vs actual component-by-component
5. Surface discrepancies with severity (critical / high / medium / low) and recoverable amount
6. Dashboards: Total NSV, Expected Commission, Expected Settlement, Discrepancies by severity, Top recoverable
7. Master editors with real-time editing (commission rules, fixed fee, GT, return fee, sub-cat level, tolerance)
8. Enterprise Bloomberg-terminal UI aesthetic: dense grids, JetBrains Mono numbers, IBM Plex Sans UI

## Architecture
- **Backend**: FastAPI + Motor (Mongo async)
  - `server.py` — auth, app bootstrap, JWT, admin seed
  - `routers/masters.py` — commission rules, fixed fee, GT, return fee, sub-cat level, tolerance
  - `routers/uploads_r.py` — XLSX parsers for sales/settlement, upload history
  - `routers/calculations.py` — expected calc engine with explainability
  - `routers/reconciliation.py` — component-level compare + discrepancy generation
  - `routers/dashboards.py` — KPI aggregates
- **Frontend**: React 19 + Tailwind + shadcn/ui + recharts + sonner
  - Pages: Login, Overview, Uploads, SalesLedger, Calculations, Reconciliation, Discrepancies, Masters
  - Drawer components for calculation explainer & discrepancy detail
- **DB**: MongoDB collections — `users`, `uploads`, `sales`, `settlement`, `commission_rules`, `fixed_fees`, `gt_charges`, `return_fees`, `subcat_levels`, `tolerances`, `calculations`, `discrepancies`, `recon_runs`

## What's Been Implemented (2026-02)
- JWT auth (admin seeded: admin@kazo.com / admin123) with per-router `Depends(current_user)` guard
- Myntra Sales XLSX parser (14,219 rows accepted from sample file)
- Myntra Settlement XLSX parser (250 rows in synthetic test file)
- 6 masters (fully editable): commission rules (76 seeded), fixed fee (6 slabs), GT charges (240 cells), return fee (15 cells), sub-cat levels (40 mappings), tolerance
- Calculation engine — commission %, GST 18%, TCS 0.5%, TDS 0.1%, fixed fee, GT, return fee
- Reconciliation engine — component-level match with configurable tolerance & materiality
- Discrepancy detail drawer with expected/actual/variance table
- Dashboards — Overview + Commission Summary + Reconciliation Summary aggregates
- Testing: 15/15 backend tests + full frontend nav flows verified by testing subagent

## Prioritized Backlog

### P0 (blocking for enterprise pilot)
- Add role-based endpoint restrictions (admin vs viewer for master edits)
- Per-endpoint audit log for master edits & recon runs (currently only admin gate exists)

### P1 (next iteration)
- AI Insights (Morning Finance Brief, CEO Brief, anomaly commentary) using Emergent Universal Key (deferred by user)
- Recovery case management (auto-create from critical discrepancies, timeline, attachments)
- Excel/CSV export for reports (order profitability, commission analysis, settlement register)
- Rule versioning + effective_from/effective_to + maker-checker approval workflow
- Visual nested rule builder (IF/AND/OR) — currently uses simple slab tables
- Full raw-file retention with checksum + object storage (currently only parsed rows)
- Scheduled report generation and email delivery

### P2 (future)
- Additional marketplace connectors (Ajio, Amazon, Flipkart, Nykaa) via connector SDK
- Vector-based finance copilot (MongoDB Atlas Vector Search)
- ERP integrations (SAP, Business Central, Tally)
- Power BI / Tableau exports
- Multi-entity / multi-GST support

## Verified Datasets
- `/app/samples/sale_data.xlsx` — real Myntra sales file (14,219 accepted rows)
- `/app/samples/synthetic_settlement.xlsx` — generated with 20% intentional variances

## Test Credentials
Admin: `admin@kazo.com` / `admin123`
