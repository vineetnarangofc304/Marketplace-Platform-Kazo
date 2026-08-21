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

## Iteration 9 — Production login "long wait then fails" (2026-07-21)
User: login on production https://kazob2b.fundlezone.com hangs then errors with "Something went wrong. Please try again."

### Root causes
1. **CORS spec violation** — server had `allow_origins=["*"]` **and** `allow_credentials=True`. Per CORS spec, `Access-Control-Allow-Origin: *` is invalid when credentials are used, so browsers reject the response. Frontend sends `withCredentials:true`, so cross-origin requests silently failed.
2. **bcrypt blocks the event loop** — `bcrypt.checkpw` / `bcrypt.hashpw` are CPU-bound (~250 ms). Being called directly inside `async def login` stalls every concurrent request behind it.
3. **Admin seed in background** — since we moved bootstrap to a background task in iteration 4, the very first login attempt after a cold pod restart could race the seed and 401.

### Delivered
- **CORS**: middleware now uses `allow_origin_regex=".*"` when `CORS_ORIGINS="*"`. Response reflects the caller's origin + `access-control-allow-credentials: true` — spec compliant.
- **Async bcrypt**: new `hash_pwd_async` / `verify_pwd_async` wrap the bcrypt calls in `asyncio.to_thread` so the event loop stays free. Login now handles concurrent requests without stacking.
- **Inline admin seed**: `@app.on_event("startup")` seeds/rehashes admin **inline** (fast — one Atlas round-trip + at most one bcrypt hash), then kicks off the rest of bootstrap (40+ indexes + masters) in the background. Login is available from the very first request after a pod restart.

### Test Results (iteration 9)
- `testing_agent_v3_fork` iteration_9 PASS. 10/10 backend regressions. Cold-start login within 230 ms of supervisor restart returns 200. Frontend login redirects in ~0.3 s. No CORS blocks. Zero bugs.

## Iteration 8 — Return-DTO fix + drawer base+GST split (2026-07-21)
User: (1) "commission & fixed fee should always be before GST for all calc"; (2) "return fee logic is based on the tables attached.. its coming same as fixed fee, while it has to come based on tables attached".

### Delivered
- **Backend `compute_expected` — Return-DTO branch**: now uses `return_fee_master` from the Return Fee_TABLE (level, zone) instead of `fixed_fee_incl_gst`. Fixed Fee, Commission, GT, TCS, TDS are all set to zero for return_dto rows. Test order `DFC4F34A-58F6-40EA-9AA1-2C13EB9F2140` (nsv=-646, zone=Zonal, Level 1) now correctly returns ₹112 (was ₹71.98) and expected_settlement=-758.
- **Drawer UI** (`SalesLedger` order detail + `Calculations` explainer): each Expected-Calculation row shows base and GST separately — `Commission (ex GST)`, `GST on Commission (18%)`, `Fixed Fee (ex GST)`, `GST on Fixed Fee (18%)`, `GT Charge (incl GST)`, `Return Fee (Level/Zone)`, `TCS`, `TDS`, `Total Deductions`, `Expected Settlement`.
- **Return Velocity widget**: metric renamed from `fixed_fee_leakage` → `leakage` (now sums `return_fee` on return_dto rows). April Return-fee leakage: **₹6,58,488** total; worst: Dresses ₹1.72L (58.6%), Tops ₹1.57L (52.6%), Shirts ₹75K.

### Test Results (iteration 8)
- `testing_agent_v3_fork` iteration_8 PASS (6/6 backend + drawer UI). Zero bugs, zero action items. Sample validated end-to-end.

## Iteration 7 — Return Velocity widget on CEO Overview (2026-07-21)

User approved the iteration 6 suggestion. Added:
- **New endpoint** `GET /api/dashboard/return-velocity?period_type&period_value&top` returns `{overall: {sales_orders, return_dto_orders, return_orders, rto_orders, internal_cancel_orders, velocity_pct, total_fixed_fee_leakage}, by_sub_category: [{sub_category, orders, return_dto_orders, velocity_pct, fixed_fee_leakage, sales_nsv, ...}]}`. Sorted by fixed-fee leakage desc.
- **New backend filter** `GET /api/calculations?order_type=return_dto|sales|return|rto|internal_cancel` — enables drill-through.
- **Overview panel** `data-testid='return-velocity-panel'` — headline "X% of sales orders flipped to Return-DTO", plus table with row-level drill (each row → `/calculations?sub_category=&order_type=return_dto&period=...`). Colored velocity heatmap (blue/orange/red bands).
- **April 2026 data**: 44.4% overall velocity, ₹2.85L fixed-fee leakage. Worst offenders: Dresses (58.6%, ₹88,599), Trousers (55.5%, ₹16,563), Shirts (53.6%, ₹36,838).

Test agent iteration_7 PASS — no bugs, no action items.

## Iteration 6 — Return rows dropped by parser (2026-07-21)
Reported: "the original April sales file also had return orders. those seem to have not got processed."

### Root cause
The raw file has 21,614 rows: 14,219 with `txn_type='Sales'` and **7,395 with `txn_type='Return'`**. Every return row has a **negative NSV / QTY** (Myntra's convention for reversals). The sales parser rejected all rows with `nsv_val < 0`, silently dropping the 7,395 return rows. Additionally, the previous classifier tagged both Sales+DTO and Return+DTO as `dto` — after importing returns, this would have double-counted refunds.

### Delivered in iteration 6
- **Parser** (`uploads_r._parse_sales_xlsx`): removed the negative-NSV rejection so Return rows import cleanly.
- **Classifier** (`_classify_order`): now emits **5 order types**:
  - `sales` — everything with `txn_type='Sales'` and no RTO/InternalCancellation status (includes Sales+DTO — the original sale record for a DTO order)
  - `return_dto` — `txn_type='Return' AND order_status='DTO'` — applies only Fixed Fee (incl GST) as Return Fee
  - `return` — any other `txn_type='Return'` (e.g. Return+Delivered, Return+Status NF) — sign-flipped with return fee from (level, zone) matrix
  - `rto` — any `order_status='RTO'` (Sales+RTO or Return+RTO) — all fees nullified
  - `internal_cancel` — any `order_status='Internal Cancellation'` — all fees nullified
- **compute_expected**: the `sales` branch now uses `abs(nsv_val)` (defensive); `return_dto` branch mirrors the old `dto` branch (fixed fee only). Net-effect for a DTO order across both Sales and Return rows = seller loses one fixed fee — matches the user's spec exactly.
- **Data reload**: uploaded raw file → 21,614 accepted / 0 rejected; recalculated all → distribution matches expected exact counts.

### Test Results (iteration 6)
- 21,614 sales rows imported (was 14,219; +7,395 returns now processed)
- Order-type distribution: sales=12,246 · return_dto=5,443 · rto=3,705 · internal_cancel=128 · return=92 (sums to 21,614 ✓)
- Aggregate April expected settlement: **₹4,631,550** (previously ₹16,575,054 which was inflated because returns weren't offsetting)
  - Sales: +₹14,690,173
  - Return DTO: −₹9,797,947
  - Return: −₹260,676
  - RTO / Internal Cancel: 0
- `testing_agent_v3_fork` iteration_6 PASS — no bugs, no action items.

## Iteration 5 — Bug-fix punchlist from CEO (2026-07-21)
Reported items:
1. NSV − GT amount = NSV-after-GT; all downstream calculations to use this base
2. Return transactions to be deducted (signed negative)
3. Search by Order ID not working
4. Commission Masters — download / upload option for configuration
5. Return Fee zonal charges to be considered
6. Sub-category → GTA charges level master
7. Return DTO — only fixed charges applied as return fee
8. RTO / Internal Cancellation — all fees nullified

### Delivered in iteration 5
- **Calculation engine rewrite (`compute_expected` + new `_classify_order`)**:
  - `order_type` ∈ {sales, return, dto, rto, internal_cancel} — classified by `order_status` (exact 'RTO' / 'Internal Cancellation' / 'DTO') and `txn_type` (contains 'return')
  - `nsv_after_gt = nsv_val − gt_charge` for sales; sign-flipped for returns/DTO
  - Commission base, TCS, TDS all computed on `nsv_after_gt` (previously used raw NSV)
  - **DTO**: only Fixed Fee (incl GST) applies, counted as Return Fee; everything else 0; expected_settlement = −|NSV| − FixedFeeInclGST
  - **RTO / Internal Cancellation**: every fee = 0; expected_settlement = 0; no unmapped flag
  - **Return**: all component signs reversed, plus return_fee (positive) from the (level, zone) matrix
  - New `nsv_after_gt` field in `breakdown` and top-level for reporting
- **Search fixes**:
  - Regex-escape `search` param on `/api/sales` and `/api/calculations` so UUIDs / meta-chars don't 500
  - Debounced search (400 ms) on both `SalesLedger.jsx` and `Calculations.jsx` — fires on every keystroke, not just Enter
- **Commission Masters download/upload**:
  - New `GET /api/masters/export` → single multi-sheet Excel with 8 sheets: Commission Rules, Fixed Fee, GT Charges, Return Fee, Sub-Cat Levels, Tolerance, Tax Rates, Settlement Config
  - New `POST /api/masters/import?mode=replace|merge` — round-trips the exported file; wipes/upserts collections; auto-invalidates cache
  - Masters page: `Download config` / `Upload (replace)` / `Upload (merge)` buttons with confirmation prompt

### Test Results (iteration 5)
- `testing_agent_v3_fork` iteration_5 → PASS. Verified DTO math (−6561.98 for the ₹6490 handbag test row), sales math (NSV-after-GT commission base), RTO/internal-cancel nullification, order-type classification on 14,219 rows, search-by-fragment on both Sales and Calculations, Masters download → import roundtrip (replace + merge). No bugs.

## Iteration 4 — Rebrand + Production Performance (2026-02, session 3)
User: "Pls add this logo.. powered by fundle on all pages... remove emergent mentions everywhere... all reports taking time to load... please help adding indexes on the DB and also compound indexing on all relevant fields... pls optimise reports dashboards and DB indexes fully for this to run smoothly on Production."

### Delivered in iteration 4
- **Rebrand to Fundle**:
  - Browser title → "KAZO Marketplace Finance · Powered by Fundle"
  - `Powered by [fundle logo]` badge on login page (data-testid `powered-by-fundle-login`) and in the sidebar footer of every authenticated page (data-testid `powered-by-fundle-sidebar`), linking to https://fundle.ai
  - Removed all `Emergent` references from rendered DOM: `index.html` title/description, PostHog block, `emergent-main.js` script, "Emergent Universal Key" text on `/insights`, and the dead `constants/testIds/` folder
- **Performance — DB indexes**:
  - Compound indexes on `sales` (report_month + sub_category / zone / order_status / txn_type)
  - Compound indexes on `calculations` (report_month + breakdown.sub_category / master_category / zone / unmapped / expected_settlement)
  - Compound indexes on `discrepancies` (report_month + severity, report_month + recoverable, recon_run_id + severity)
  - Compound indexes on `recovery_cases` (report_month + status / priority, recoverable_amount desc)
  - Compound indexes on `settlement` (report_month + online_order_id + sku)
  - Extra indexes on `insights_briefs` and `commission_rules`
- **Performance — parallelization**:
  - Dashboards (`overview`, `commission-summary`, `reconciliation-summary`) now run their sub-aggregations in parallel via `asyncio.gather`
  - Reports `_period_aggregate` runs 9 sub-queries in parallel (KPI, sales KPI, 4 group-bys, count, severity, recoverable)
- **Performance — caching**:
  - New `cache_utils.py`: in-memory TTL cache with tag-based invalidation
  - 30s TTL on all hot dashboard + reports endpoints, 60s on period lists
  - Auto-invalidation on writes: uploads (sales/settlement), delete-upload, run-calculations, run-reconciliation
- **Performance — transport**: GZipMiddleware enabled (minimum_size=1024)
- **Observed timings on preview**: cold 150–240ms, warm cached 106–140ms across dashboards + reports + insights + recovery

### Test Results (iteration 4)
- Testing agent verified: title/badges/anti-emergent DOM check across 11 routes, 7 endpoints cache-hot <1.5s with 2nd call ≤ 1st, GZip present, all required compound Mongo indexes exist, drill-downs regression pass. No bugs, no action items.

## Iteration 3 — Recovery Management + AI Insights (2026-02, session 3)
User: "go ahead and complete pending tasks" — deliver Phase 6 & Phase 7 from the backlog.

### Delivered in iteration 3
- **Phase 6 — Recovery Management** (new `routers/recovery.py`, new page `/recovery`)
  - Case tracking with statuses `open → in_review → submitted → recovered | rejected | closed`
  - Auto-create cases from open discrepancies (period-filtered, ₹>0 recoverable)
  - Manual case creation from any discrepancy via a new "Open Recovery Case" button in the Discrepancies drawer
  - Communication log (channel: note/email/call/chat/myntra_ticket, direction: inbound/outbound/internal)
  - Evidence file upload (≤15MB), download, delete — stored in Mongo (`recovery_evidence`, base64)
  - Summary endpoint: totals + by_status + by_priority + coverage % of discrepancy universe
  - Endpoints: `POST /api/recovery/cases`, `POST /api/recovery/cases/auto-create`, `GET/PATCH/DELETE /api/recovery/cases/{id}`, `GET/POST /api/recovery/cases/{id}/notes`, `GET/POST /api/recovery/cases/{id}/evidence`, `GET /api/recovery/evidence/{id}/download`, `GET /api/recovery/summary`
  - New collections: `recovery_cases`, `recovery_notes`, `recovery_evidence` with indexes
- **Phase 7 — AI Insights** (new `routers/insights.py`, new page `/insights`)
  - Deterministic Health Score (0–100, Grade A–F) from four weighted components: Mapping (25%), Leakage (35%), Margin (25%), Recovery (15%)
  - Morning Finance Brief — Claude Sonnet 4.6 via Emergent Universal Key (`EMERGENT_LLM_KEY`), rule-based fallback when LLM unavailable
  - Radial gauge, per-component progress bars, tone selector (executive/operational/concise), audit log of past briefs
  - Endpoints: `GET /api/insights/health-score`, `POST /api/insights/morning-brief`, `GET /api/insights/briefs`
  - Numbers never fabricated — LLM receives only real aggregates from Mongo and is instructed to quote them verbatim
- **Fix** — `period_utils.month_query()` now tolerates missing `period_value` (returns `{}` instead of raising) so dashboards do not 500 on initial load

### Test Results (iteration 3)
- 10/10 new pytest tests pass covering Recovery + Insights (create, duplicate 409, PATCH transitions, notes, evidence upload/download/delete, LLM brief with source='llm', period switching)
- Frontend Recovery + Insights render correctly on 2026-04; Overview health-check regression passes
- Insights Morning Brief validated end-to-end with live Claude Sonnet 4.6 output

## Prioritized Backlog (updated)

### P0 (blocking for pilot)
- Rule versioning + effective_from/effective_to + maker-checker approval workflow
- Full audit log (who edited which master, when, what value changed)

### P1 (next iteration)
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
- SSO / stricter tenant boundaries

## Iteration 11 — Multi-Marketplace Portals (2026-07)
User uploaded `All Portal_Commercial -AI.xlsx` with rate cards for **Amazon, AJIO (Direct Ship), Nykaa, Tata Cliq, Flipkart**. Instruction: "the marketplaces and their rules should be in the masters.. all reports should have marketplace filters.. upload should allow selection of which marketplace and ingest data.. pls build".

### Delivered
- **Backend**
  - `data_portals_seed.py` — parsed rate cards for all 5 portals + Myntra (fee heads T1..T5, case matrix Delivered/DTO/RTO/InternalCancel × each fee head)
  - `routers/portals.py` — GET /api/portals, GET /api/portals/{code}, POST /api/portals/{code} (admin), POST /api/portals/reset-defaults (admin)
  - Bootstrap seeds portals collection on first run + back-fills `portal='myntra'` on 21,614 existing sales, uploads, calculations
  - `POST /api/uploads/sales` and `POST /api/uploads/settlement` now accept `?portal=` query param
  - `GET /api/uploads` and `GET /api/sales` accept `?portal=` filter (value 'all' or missing = no filter)
- **Frontend**
  - `context/PortalContext.jsx` — global portal state, reloads on auth-user change (login/logout)
  - `components/PortalSwitcher.jsx` — dropdown in header (All Portals + 6 portals)
  - `pages/Masters.jsx` — new **Portals** tab (first, default). Left list of 6 portals with LIVE / SOON badges + row counts. Right pane shows rate card (T1..T5 with Sale/Return/Unit) + case-type matrix (color-coded: Charged=green, Again Charged=orange, Reversal=blue, All null=grey). Editable label per fee head. Status dropdown. Reset-to-defaults button
  - `pages/Uploads.jsx` — Ingest-portal button bar (Myntra default; others show SOON badge). Non-Myntra portals show a warning banner "parser is on our roadmap". Upload History now has a Portal column
- **Data-testids** — portal-switcher, portal-switcher-select, portal-option-{code}, portals-master, portal-item-{code}, portal-status-{code}, ingest-portal-{code}, btn-reset-portals

### Bugs found & fixed by testing agent (iter_10)
- Route ordering: `/portals/reset-defaults` was shadowed by `/portals/{code}` → moved literal above catch-all (fixed)
- `PortalContext` didn't reload after login → now watches AuthContext `user` state (fixed)
- Tests: 13/15 pytest pass initially; both fixed and re-verified via curl (reset-defaults returns `{"reseeded": 6}`)

### Known limitations (roadmap)
- Non-Myntra upload parsers not yet implemented — Amazon / AJIO / Nykaa / Tata Cliq / Flipkart files can be uploaded and are tagged with the correct `portal`, but parsing may be partial until each portal's native parser is built. Warning banner is shown in the UI
- Non-Myntra calculation engine not yet implemented — the calc router still uses Myntra-specific formulas
- Category-level Flipkart commission rate card requires an external upload (per Excel notes)

## Iteration 12 — Portal Filter Everywhere + Cross-Portal Overview + Portal-Aware Calc (2026-07)
User: "Amazon Parser + Calc — build the native Amazon report parser... Portal Filter Everywhere — thread portalParam from PortalContext into every remaining API call... Cross-Portal Overview — a 'Combined view' dashboard when portal='all' showing consolidated leakage / margin across every active marketplace side-by-side. DO"

### Delivered
- **Backend**
  - `GET /api/dashboard/portals-summary` — per-portal aggregation (sales_count, nsv, expected_settlement, expected_commission, disc_count, leakage) + totals
  - `?portal=` query param added to: `/dashboard/overview`, `/dashboard/commission-summary`, `/dashboard/reconciliation-summary`, `/dashboard/return-velocity`, `/calculations`, `/reconciliation/discrepancies`, `/recovery/cases`, `/recovery/summary`, `/reports/period`
  - `POST /calculations/run` accepts `{portal}` in body — branches by portal: Myntra uses full masters-driven `compute_expected(sale, masters)`; non-Myntra uses new `_compute_expected_portal(sale, portal_doc)` which reads T1..T5 fee_heads and case_matrix (Delivered/DTO/RTO/InternalCancel × head)
  - `_ORDER_TYPE_TO_CASE` mapping: sales/return → Delivered, return_dto → DTO, rto → RTO, internal_cancel → InternalCancel
  - Behaviour translation: `All null`/`No reversal` → 0, `Reversal` → −abs, `Again Charged` → +abs
  - `SALES_HEADER_ALIASES` extended to recognise Amazon MTR headers: `amazon-order-id`, `ASIN`, `seller-sku`, `product_sales`, `principal`, `quantity-purchased`, `shipping-fee`, `selling-fees`, `referral-fee`, etc.
  - Required upload columns relaxed from `{online_order_id, sku, nsv_val, sub_category}` → `{online_order_id, sku, nsv_val}` (sub_category now optional so non-Myntra portals parse)
- **Frontend**
  - `Overview.jsx` — new **Cross-Portal Snapshot** widget (shown only when portal=all). 6 clickable portal tiles with NSV, orders, disc_count, expected settlement + LIVE/SOON badges. Clicking a tile sets portalCode via setPortalCode
  - Threaded `portalParam` into `Overview`, `SalesLedger`, `Calculations`, `Discrepancies`, `Recovery`, `Reports` — all list APIs re-fetch when the top-header switcher changes
  - Fixed pre-existing broken tail in `Recovery.jsx` (stray `</div>` + duplicate closing braces)
- **Test suite** — `/app/backend/tests/test_iter12_portals.py` (15 tests, all passing)

### Bugs found & fixed by testing agent
- Dead code cleanup: `_apply_portal()` had an unreachable `return {}` — removed
- Zero critical/major issues found by testing agent
- Frontend E2E verified: portal-switcher persists, tile-click updates localStorage, Calculations correctly shows 0 rows for portal=amazon

### Known limitations (roadmap)
- **True native Amazon parser** — the header-alias approach handles common Amazon MTR columns, but a real Amazon file may have quirks (multi-header, sub-order IDs, tax splits). Need a real sample file to build a truly native parser
- **Non-Myntra masters editing UI** — currently the portal rate cards from Masters → Portals tab are readable but the frontend inline editing only saves label changes (fee_heads full editor is roadmap)
- **Amazon settlement reconciliation** — settlement parser also needs Amazon-specific header aliases (currently only sales-side aliases were expanded)

## Test Credentials
- **Admin (Kazo tenant)**: `admin@kazo.com` / `admin123`
- **Admin (Fundle marketing/demo)**: `admin@fundle.ai` / `admin123`

## Iteration 10 — Fundle Marketing Assets (2026-07)
User: "now need a nicely done video that explains the problem, the solution and everything that we have delve roped here.. and a PDF document too that defines the solution and its features to start sharing with customers. All content should be actual. Fundle logo & branding — Kazo is a customer, so present as product of Fundle.ai. Emphasise AI insights. Voice-over via OpenAI TTS. All LLMs via Emergent LLM Key."

### Delivered
- **Full UI rebranding** for user-visible strings: sidebar title, header caption, login card, footer copyright, page title — all now say "Fundle Finance OS" (internal localStorage keys `kazo_token`/`kazo_user` unchanged to avoid breaking sessions).
- **Marketing pipeline** at `/app/marketing/` with fully-scripted narration (`narration.json`), TTS generator (`generate_tts.py`), Playwright screenshotter (`capture_screenshots.py`), PIL slide builder (`build_slides.py`), ffmpeg video assembler (`build_video.py`), and ReportLab PDF builder (`build_pdf.py`).
- **Product Video** — 3-min 16-sec MP4, 1920×1080, ~5.2 MB. 10 chapters: Hook → Why broken → Solution → Ingest → Masters → Calculations → Reconciliation → Recovery → AI Insights → CTA. OpenAI TTS `onyx` voice (tts-1-hd) via Emergent LLM Key. Real preview screenshots. Available at `/app/frontend/public/fundle_finance_os.mp4` and `${REACT_APP_BACKEND_URL}/fundle_finance_os.mp4`.
- **Product Brochure PDF** — 8 pages landscape A4, 532 KB. Fundle branded cover, industry problem stats, six-pillar overview, three product deep-dive spreads (Ingest, Rule Engine + Calc, Reconcile + Recover + AI), and CTA page with **clickable WhatsApp cards** (Abhinav Khanna +91 99105 30372, Anmol Berry +91 98995 33604) and clickable `fundle.ai` link. Available at `/app/frontend/public/fundle_finance_os_brochure.pdf` and `${REACT_APP_BACKEND_URL}/fundle_finance_os_brochure.pdf`.
- **Fundle admin account** created (`admin@fundle.ai` / `admin123`) so marketing screenshots show a clean sidebar without Kazo email.

### Assets Location
- `/app/marketing/output/fundle_finance_os.mp4` (source, master copy)
- `/app/marketing/output/fundle_finance_os_brochure.pdf` (source, master copy)
- `/app/marketing/scripts/` — all generation scripts, re-runnable
- `/app/marketing/audio/` — 10 OpenAI TTS mp3 segments
- `/app/marketing/slides/` — 10 rendered 1920×1080 slides
- `/app/marketing/screenshots/` — real Playwright captures of Preview


## Iteration 13 — Multi-Portal Live Activation + Rebuild UI (2026-02, session 3)
User: "Changes" (following upload of `All Portal_Commercial -AI.xlsx`) → interpreted as: activate non-Myntra portals, add Amazon parser, add a Rebuild-All button, and finish the parked Return-DTO patch.

### Delivered
- **All 6 portals now `live`** (Myntra, Amazon, AJIO, Nykaa, Tata Cliq, Flipkart). `data_portals_seed.py` bumped from `coming_soon` → `live` for the 5 new marketplaces. `bootstrap_portals()` now upserts status on every startup so existing MongoDB docs sync without a manual reset.
- **Amazon MTR / Settlement parser**:
  - Extended `SALES_HEADER_ALIASES` in `backend/routers/uploads_r.py` with Amazon-specific columns (`Amazon Order ID`, `ASIN`, `MSKU`, `Ship To State`, `Item Total Amount`, `FBA Fee`, `Referral Fee`, `Marketplace Fee`, etc.).
  - New `_normalize_row_for_portal(rec, portal)` helper maps portal-native vocabularies (Amazon `Shipped`/`Refund`/`Cancelled`, AJIO/Nykaa/Tata Cliq/Flipkart `Order`/`Return`/`Cancel`) onto the canonical `{Sales, Return} × {Delivered, DTO, RTO, Internal Cancellation}` taxonomy used by `_classify_order`.
  - Called from `upload_sales()` immediately before persistence so downstream calculation engine sees canonical rows.
  - Myntra remains untouched (no-op).
- **"Rebuild All Calculations" UI trigger** (`Uploads.jsx`):
  - New header button `data-testid="btn-rebuild-all-calculations"` that calls `POST /api/calculations/run` with `{recalculate: true, portal: <scope>}` and confirms via `window.confirm` before wiping calculations.
  - Label auto-updates to show scope: "Rebuild Calculations · All Portals" or "Rebuild Calculations · Amazon" etc.
  - Toast surfaces `{processed, fully_mapped_count, unmapped_count}` rounded with `en-IN` formatting.
  - Per-upload Run Calc button relaxed from `myntra`-only → any portal (multi-portal calc engine now covers all 6).
  - Portal-compat check switched from `ingestPortal === 'myntra'` → `portalObj.status === 'live'` so amber warning banner only shows for future `coming_soon` portals.
- **Return-DTO fixed-fee patch — verified**: Confirmed via 3 tests in `test_return_dto_fix.py` (all 5,443 return_dto rows have `fixed_fee_incl_gst = 0`, `return_fee` matches Level×Zone master, sum ≈ ₹6.58L). No new code needed — was already correctly implemented in Iteration 8. Added explicit regression tests + documentation.
- **Login page** — prefilled email + demo credentials updated to `admin@fundle.ai`.

### Tests
- `/app/backend/tests/test_iter13_multi_portal.py` — 8 tests: all-portals-live, Amazon sales/return/RTO normalizer, Amazon calc math (18.7% + 11.5%), Amazon RTO zeroing, rebuild endpoint with portal scope, full Myntra rebuild (21,614 rows).
- All 14 tests (6 pre-existing return_dto + 8 new) pass in 10s.

### Files touched
- `backend/routers/uploads_r.py` — Amazon header aliases + `_normalize_row_for_portal` + hook in `upload_sales`.
- `backend/routers/portals.py` — idempotent status-sync in `bootstrap_portals`.
- `backend/data_portals_seed.py` — 5 portals status: `coming_soon` → `live`.
- `frontend/src/pages/Uploads.jsx` — Rebuild button + `isCompatible` from portal status + Run Calc for all portals.
- `frontend/src/pages/Login.jsx` — default email `admin@fundle.ai`.
- `backend/tests/test_iter13_multi_portal.py` — new.
- All test files: `admin@kazo.com` → `admin@fundle.ai`.

### Roadmap (unchanged)
- P1: Automated Return-Velocity monthly email (Resend integration).
- P2: SSO / tenant boundaries, white-label logo upload, `/api/health/ready` endpoint.
- Backlog: True native Amazon settlement (MTR) tax-split parsing when a real file is provided.


## Iteration 23 — Production-vs-Preview Verification (2026-02, session 23)
User: "Point 2.1 and 2.2 - Not resolved" (5th recurrence — reported after redeploy to production).

### Investigation & outcome — no code change needed
- **bug_testing_agent (iter 23) verified on Preview:**
  - `/api/calculations?order_type=return_dto` → 5/5 sampled rows: commission < 0, fixed_fee = 0, gt_charge < 0, return_fee > 0 ✅ (Point 2.1)
  - `/api/calculations?order_type=rto` → 5/5 sampled rows: all four fee heads < 0 ✅ (Point 2.2)
  - UI (Calculations table, Calculations drawer, Sales Ledger drawer) shows correct signs.
- **Root cause of user report:** Production still serves stale stored calculation rows even after redeploying the code. Fresh code + old computed rows in `db.calculations` = same displayed values. Fix on production side = click **"Run Calculations"** button (calls `POST /api/calculations/run` with `recalculate: true`) to reprocess all rows.
- **No preview code changes** were made in this session. Test artefacts written:
  - `/app/tests/bug_verify_dto_rto_signs_iter23_backend.py`
  - `/app/tests/bug_verify_dto_rto_signs_iter23_ui.py`
  - `/app/test_reports/iteration_23.json`

## Iteration 24 — Point 6 fix: RTO Total Deductions (2026-02, session 24)
User: "point 2.1 and 6" — Google Doc updated with a new Point 6: "RTO - Sum of Total deductions should be Sum of Commission, Fixed Fee, GT Charge, Return Fee".

### Fix delivered
- `/app/backend/routers/calculations.py` — RTO branch: `total_deductions` now = `commission_base + fixed_fee + gt_charge_final + return_fee_final` (was hard-coded 0.0). Expected settlement stays 0 (net-zero refund semantics).
- Recalculated all 21,614 Myntra rows on Preview so stored calc rows reflect the new logic.
- Point 2.1 (DTO) signs verified as still correct: commission < 0, fixed_fee = 0, GT < 0, return_fee > 0.

### Verified (bug_testing_agent iteration_24.json — 100% backend + frontend)
- RTO API: 5 samples confirm `total_deductions == comm + ff + gt + rf` (e.g. -205.11 + -61 + -207 + -112 = -585.11).
- RTO signs & settlement=0 preserved.
- DTO Point 2.1 signs unchanged.
- Sales Ledger Excel export Total Deductions column matches the sum for RTO rows.
- Calculations UI table + drawer reflect the fix.

### Production note
User must redeploy Production for the code change to propagate, then click "Run Calculations" on the Calculations page to reprocess stored rows.


## Iteration 25 — Value-driven sign colouring (2026-02, session 25)
User feedback: "RTO corrected but DTO - No change after re calculation also".

### Root cause
Backend DTO values were already correct (commission < 0, fixed = 0, GT < 0, return_fee > 0 per Point 2.1), but the UI hard-coded all fee cells to `fin-neg` (red) regardless of sign. Result: a DTO reversal (Commission = -₹279) rendered visually identical to a fresh charge (Return Fee = +₹112). User couldn't visually tell them apart and reported "no change".

### Fix
- `/app/frontend/src/lib/format.js` — new helpers `signClass(v)` (positive → red charge, negative → green credit, zero → neutral) and `settlementClass(v)` (positive → green, negative → red).
- `/app/frontend/src/pages/Calculations.jsx` — table row + drawer use `signClass` / `settlementClass` instead of hard-coded `fin-neg` / `fin-pos`.
- `/app/frontend/src/pages/SalesLedger.jsx` — same.

### Verified (bug_testing_agent iteration_25.json — 100% frontend)
Sample DTO row `C1256672-9678-4D76-...`:
- Commission ₹-11.76 → `fin-pos` green ✅ (reversal / credit)
- Fixed Fee ₹0.00 → neutral (no colour) ✅
- GT ₹-59.00 → `fin-pos` green ✅
- Return Fee ₹112.00 → `fin-neg` red ✅ (fresh charge)
- Total Deductions ₹41.24 → `fin-neg` red ✅
- Expected Settlement ₹-188.24 → `fin-neg` red ✅ (seller loses)

RTO, sales-type, and Sales Ledger drawer regressions all passed.


## Iteration 26 — RTO Return Fee = ZERO (2026-02, session 26)
User revised Point 6 (RTO) spec (19 Aug 2026):
- Commission NEGATIVE ✅ (already Done)
- Fixed Fee NEGATIVE ✅ (already Done)
- GT Charge NEGATIVE ✅ (already Done)
- **Return Fee (Level/Zone): ZERO** (previously was negative; now must be exactly 0)

### Fix
- `/app/backend/routers/calculations.py` — RTO branch: `return_fee_final = 0.0` (was `-abs(return_fee_master)`). Total Deductions now = Commission + Fixed Fee + GT + 0. Settlement stays 0.
- Recalculated all 21,614 Myntra rows on Preview.

### Verified (bug_testing_agent iteration_26.json — 100% backend + frontend)
- RTO sample: commission=-205.11, fixed_fee=-61, gt=-207, return_fee=0.0, total_deductions=-473.11, settlement=0.0.
- DTO Point 2.1 regression: 0 violations across 2000 sampled rows (comm<0, ff=0, gt<0, rf>0).
- Calculations UI RTO drawer: Return Fee ₹0.00 neutral ✅
- Sales Ledger DTO drawer: Commission green negative, Fixed Fee ₹0 neutral, GT green negative, Return Fee red positive ✅


## Iteration 27–28 — Sales+DTO leg + rounding fix (2026-02, session 27-28)
User showed production screenshots (19 Aug 2026):
- RTO: Return Fee still ₹-112 (production DB stale)
- DTO: Sales-leg row (order_status=DTO, txn_type=Sales) showing POSITIVE charges — user expects DTO signs even on the Sales leg per Point 2.1.

### Root cause
Classifier previously mapped Sales+DTO → `sales` (positive charges) and only Return+DTO → `return_dto` (correct reversal signs). User expected any status=DTO row to show DTO signs regardless of txn_type.

### Fix
- `/app/backend/routers/calculations.py`
  - New `order_type = "sale_dto"` for status=DTO + txn_type=Sales (5,210 preview rows).
  - `sale_dto` compute branch: commission NEG, fixed_fee ZERO, GT NEG, return_fee POS. `expected_settlement = 0` on this leg so aggregate does NOT double-count the real DTO loss (which stays on the paired Return+DTO row).
  - Rounding-drift fix: fee heads are rounded to 2 dp FIRST, then `total_deductions` is computed from the rounded values. Removes the ₹0.01 drift found on 574/5,210 sale_dto rows in iteration_27.
- Preview recalculated all 21,614 Myntra rows.

### Verified (bug_testing_agent iteration_28 — 100% backend + frontend)
- sale_dto: 5,210/5,210 rows correct signs, settlement=0, total_deductions=sum-of-4-heads with 0.00 drift.
- return_dto: 5,443/5,443 regression clean.
- rto: 3,705/3,705 regression clean (return_fee=0, settlement=0).
- sales/return: 7,036/7,036 + 92/92 regressions clean.
- UI drawers show sale_dto with Commission green negative, Fixed Fee ₹0 neutral, GT green negative, Return Fee red positive.

### Production note
User must redeploy production, then click "Run Calculations" on the Calculations page to reprocess stored rows.


## Iteration 29 — Revert Sales-leg reversal (2026-02, session 29)
User clarification: "RTO and DTO this logic is for *Return* flag only .. for *sales* it should be as previous".

### Change
Reverted iteration_27 `sale_dto` experiment. Reversal logic (Point 2.1 / Point 6) now applies **only when txn_type=Return**:
- Sales+DTO → `sales` (positive charges as before)
- Return+DTO → `return_dto` (Point 2.1 signs)
- Sales+RTO → `sales` (positive charges as before)
- Return+RTO → `rto` (Point 6 signs, return_fee=0)
- Internal Cancellation → `internal_cancel` (both legs zero, unchanged)

### Verified (bug_testing_agent iteration_29 — 100% backend + frontend)
Counts: sales=14,219 · return=92 · return_dto=5,443 · rto=1,787 · internal_cancel=73 · sale_dto=**0** (removed).
- Sales+DTO rows show POSITIVE Commission/Fixed/GT (normal sale) ✅
- Sales+RTO rows show POSITIVE Commission/Fixed/GT ✅
- Return+DTO signs correct per Point 2.1 ✅
- Return+RTO signs correct per Point 6 with return_fee=0 ✅
- UI Sales Ledger drawers match expected colours on both leg types.


## Iterations 30–31 — Marketing Studio + Rebrand (2026-02, session 30-31)
User asked for a password-protected `/marketing` page to house all LinkedIn infographics + a Create button to generate new ones from keywords, and a rebrand of "Finance OS" → "Marketplace AutoPilot".

### Delivered
- **Rebrand** — sidebar tagline ('Marketplace AutoPilot · Recon'), document `<title>`, meta description all switched. 0 remaining 'Finance OS' matches in the app shell.
- **Fundle logo** — dark-variant PNG derived from the light logo (only the light-grey letters darkened, coloured icons untouched). Composited pixel-perfect via idempotent PIL overlay (`refresh_overlays.py`). No more clipping / stacking / overlap.
- **5 seed infographics regenerated** with the "Marketplace AutoPilot" title on every image (01 platform overview, 02 modules, 03 workflow, 04 multi-marketplace, 05 ROI). Real Fundle logo top-left off-white pill; marketplace names rendered brand-recognisably.
- **/marketing route** — self-contained page with:
  - Password-gated login (marketing-only JWT scope, seeded user `marketing@fundle.ai` / `market123`).
  - Gallery grid (3-col responsive) — each card shows image, title, LinkedIn text preview, hashtag chips, Copy/PNG/Delete actions.
  - **Create dialog** — title, keywords (comma-separated), style (`Infographic` | `Screen Collage`), tone. POST /api/marketing/posts uses Gemini Nano Banana (`gemini-3.1-flash-image-preview`) + Gemini 3.6 Flash for LinkedIn copy generation.
  - Bulletproof clipboard: navigator.clipboard.writeText → document.execCommand fallback → error toast (never the CRA red overlay).

### Backend
- `/app/backend/routers/marketing.py` — new router: `POST /login`, `GET /posts`, `POST /posts`, `GET /posts/{id}/image`, `DELETE /posts/{id}`. Own JWT scope `role='marketing'`.
- `server.py` startup — seeds `marketing_users` + `marketing_posts` (imports the 5 pre-generated infographics into the gallery on first boot; idempotent).

### Verified (testing_agent iteration 30 + 31 — 100% pass)
- 17/17 backend pytest cases (`/app/backend/tests/test_marketing_studio.py`).
- Frontend: login, wrong-password error, gallery renders 5 cards, images load, copy/download/delete, Create infographic + screen-collage end-to-end, logout.
- Regression: `admin@fundle.ai` still logs into the main app; Overview KPIs render; no 'Finance OS' anywhere.
- Clipboard: 16 assertions cover permission-granted, permission-denied, and both-paths-failing; no CRA overlay, no unhandled rejections.

### Credentials
- Main app admin: `admin@fundle.ai` / `admin123`
- Marketing Studio: `marketing@fundle.ai` / `market123`

