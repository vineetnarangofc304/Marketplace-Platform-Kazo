# KAZO Marketplace Finance & Reconciliation Platform — PRD

## Original Problem Statement
KAZO Marketplace Finance Operating System — ingests marketplace reports, calculates expected charges, reconciles settlements, identifies leakage, manages recoveries. First connector: Myntra. Marketplace-agnostic core.

## User Choices (2026-02)
- Auth: Simple username/password (JWT, bcrypt), role-based (admin/finance/ops/viewer)
- File storage: MongoDB (uploaded XLSX parsed and stored as normalized rows)
- Frontend: React JS (agent's choice)
- AI insights: Deferred to a later iteration

## Iteration 2 — Production Hardening (2026-02, session 2)
User: "Make it production ready...no hard code no fallback. Make it ready for monthly reports to be uploaded in the formats. Please pre-configure the rules of Myntra and add them and create report based on the June data uploaded and rules given."

### Delivered in iteration 2
- **No fallbacks in the calculation engine** — every fee component either resolves to a strict rule match OR is left `null` with a specific `unmapped_reasons[]` entry. `unmapped=True` flag surfaces at row & aggregate level.
- **Configurable defaults instead of hardcoded values**:
  - Zone default (`Local / Zonal / National`) editable in Masters → Settlement Config; toggleable to force strict mode
  - GST / TCS / TDS rates editable in Masters → Tax Rates
  - Tolerance thresholds editable in Masters → Tolerance
- **Full 173-rule Myntra commission set** loaded from `/app/backend/data_myntra_commission_rules.json` (extracted from KAZO's own Myntra master file), with a `POST /api/masters/reset-defaults` (admin-only) to re-seed
- **Monthly report engine**:
  - `report_month` (YYYY-MM) extracted from `Month` / `Posting Date` / `Order Date` on every row
  - `GET /api/reports/months` — list of available months
  - `GET /api/reports/monthly?month=YYYY-MM` — full JSON aggregate (KPIs, category/sub-cat/zone breakdowns, reconciliation summary)
  - `GET /api/reports/monthly/export?month=YYYY-MM` — 7-sheet Excel workbook (Summary, By Category, By Sub-Category, By Zone, Order Detail, Discrepancies, Unmapped Orders)
- **Flexible file format handling** — parser scans headers with an alias table, picks the best-matching sheet automatically, requires `Order Id + SKU + NSV + Sub-Category` at minimum; rejects rows with placeholder "-" SKUs
- **Month filter** on dashboards, calculations, reconciliation, discrepancies
- **Admin-only guards** on all destructive master endpoints (POST/DELETE on commission-rules, fixed-fees, gt-charges, return-fees, subcat-levels, tolerance, tax-rates, settlement-settings, reset-defaults)
- **Format validation** — bad month strings (`bad-01`, etc.) return 400 instead of empty aggregates

### Verified on real data (Apr-26 file — 14,219 orders)
- 173 authoritative commission rules seeded
- 14,219 orders calculated
- **37 unmapped (0.26%)** — all `Clothing Set` variants missing from source master file; surfaced explicitly with reasons for ops
- ₹2.61 Cr NSV → ₹31.5 L expected commission (12.03%) → ₹1.94 Cr expected settlement (74.2% margin)
- Reconciliation on synthetic 296-row settlement: 231 matched, 65 variance, ₹1,264 recoverable

## Architecture
- **Backend**: FastAPI + Motor (Mongo async), JWT bcrypt auth
  - `server.py` — auth, JWT, admin seed
  - `deps.py` — `current_user`, `require_admin`
  - `routers/masters.py` — commission rules, fixed fee, GT, return fee, sub-cat level, tolerance, tax_rates, settlement_settings
  - `routers/uploads_r.py` — flexible XLSX parsers (sales/settlement) with alias-based header matching
  - `routers/calculations.py` — strict calc engine, unmapped detection, month tagging
  - `routers/reconciliation.py` — component-level compare, month propagation
  - `routers/dashboards.py` — KPI aggregates with month filter
  - `routers/reports.py` — monthly report JSON + Excel export
- **Frontend**: React 19 + Tailwind + shadcn/ui + recharts
  - Pages: Login, Overview, Reports, Uploads, SalesLedger, Calculations, Reconciliation, Discrepancies, Masters
- **DB collections**: `users`, `uploads`, `sales`, `settlement`, `commission_rules`, `fixed_fees`, `gt_charges`, `return_fees`, `subcat_levels`, `tolerances`, `tax_rates`, `settlement_settings`, `calculations`, `discrepancies`, `recon_runs`
- **Indexes**: `report_month` on `sales`, `calculations`, `settlement`, `discrepancies`

## Test Results (iteration 2)
- Backend: **29/29 pytest passed** (15 legacy + 14 new production tests)
- Frontend: All new data-testids present and functional
- Security: auth guard + admin-only enforcement verified end-to-end

## Prioritized Backlog

### P0 (blocking for pilot)
- Rule versioning + effective_from/effective_to + maker-checker approval workflow
- Full audit log (who edited which master, when, what value changed)

### P1 (next iteration)
- AI Insights (Morning Brief / CEO Brief / SKU-level margin narrative) via Emergent Universal Key
- Recovery case management (auto-create from critical discrepancies, timeline, evidence attachments)
- Raw-file retention with checksum in object storage (currently only parsed rows)
- Scheduled report generation + email delivery via Resend
- Visual nested rule builder (IF/AND/OR) instead of slab tables
- Additional export formats — PDF, CSV, Power BI dataflow
- Bulk edit of commission rules

### P2 (future)
- Additional marketplace connectors (Ajio, Amazon, Flipkart, Nykaa) via connector SDK
- Vector-based finance copilot (MongoDB Atlas Vector Search)
- ERP integrations (SAP, Business Central, Tally)
- Multi-entity / multi-GST support

## Test Credentials
- **Admin**: `admin@kazo.com` / `admin123`
