"""Fundle Finance OS — Client Scope Document (detailed proposal PDF).

Portrait A4, ~15 pages, Fundle branded (no Kazo references).
Covers: Business Need · Solution Architecture · Every Module · Backend / APIs / Data Model
        · Roles · Reports · AI · Roadmap · Contact.
"""
from pathlib import Path
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image

ROOT = Path("/app/marketing")
OUT = ROOT / "output" / "Fundle-Finance-OS-Scope.pdf"
LOGO_WHITE = str(ROOT / "assets" / "fundle_logo_white.png")

pdfmetrics.registerFont(TTFont("Noto", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Noto-B", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Noto-I", "/usr/share/fonts/truetype/noto/NotoSans-Italic.ttf"))
pdfmetrics.registerFont(TTFont("Mono", "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Mono-R", "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"))

PAGE = A4  # 210 x 297 mm
PW, PH = PAGE  # in points

DEEP  = HexColor("#0B0F17")
CARD  = HexColor("#111623")
GOLD  = HexColor("#F0B429")
CYAN  = HexColor("#63B3ED")
MINT  = HexColor("#38D97F")
TEXT  = HexColor("#F5F6FA")
MUTED = HexColor("#8A93A6")
DIV   = HexColor("#232A3B")


def fill(c, color=DEEP):
    c.setFillColor(color); c.rect(0, 0, PW, PH, fill=1, stroke=0)


def draw_logo(c, x, y, height=10 * mm):
    logo = Image.open(LOGO_WHITE)
    w = height * (logo.size[0] / logo.size[1])
    c.drawImage(LOGO_WHITE, x, y, width=w, height=height, mask="auto")
    return x + w


def header(c, chapter_no, chapter_title):
    c.setStrokeColor(DIV); c.setLineWidth(0.4)
    c.line(15 * mm, PH - 18 * mm, PW - 15 * mm, PH - 18 * mm)
    draw_logo(c, 15 * mm, PH - 15 * mm, height=6 * mm)
    c.setFont("Mono", 8); c.setFillColor(MUTED)
    c.drawRightString(PW - 15 * mm, PH - 13.5 * mm, chapter_title)
    c.drawRightString(15 * mm + 20 * mm, PH - 13.5 * mm, chapter_no)


def footer(c, page_num, total, label=""):
    c.setStrokeColor(DIV); c.setLineWidth(0.4)
    c.line(15 * mm, 14 * mm, PW - 15 * mm, 14 * mm)
    c.setFont("Mono", 7); c.setFillColor(MUTED)
    c.drawString(15 * mm, 9 * mm, f"FUNDLE FINANCE OS  ·  {label}")
    c.drawRightString(PW - 15 * mm, 9 * mm, f"fundle.ai   ·   {page_num:02d} / {total:02d}")


TOTAL_PAGES = 17


def wrap_text(c, text, x, y, w, font="Noto", size=9.5, leading=13, color=TEXT):
    c.setFont(font, size); c.setFillColor(color)
    for para in text.split("\n"):
        words = para.split()
        if not words:
            y -= leading
            continue
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if pdfmetrics.stringWidth(test, font, size) <= w:
                line = test
            else:
                c.drawString(x, y, line); y -= leading; line = word
        if line:
            c.drawString(x, y, line); y -= leading
        y -= 2  # gap between paragraphs
    return y


def h2(c, text, x, y, color=TEXT):
    c.setFont("Noto-B", 20); c.setFillColor(color); c.drawString(x, y, text)
    return y - 22


def h3(c, text, x, y, color=TEXT):
    c.setFont("Noto-B", 12); c.setFillColor(color); c.drawString(x, y, text)
    return y - 16


def kicker(c, text, x, y, color=GOLD):
    c.setFont("Mono", 8); c.setFillColor(color); c.drawString(x, y, text)
    return y - 14


def bullet_list(c, items, x, y, w, font="Noto", size=9.5, leading=13, gap=4):
    for it in items:
        c.setFont("Noto-B", size); c.setFillColor(GOLD); c.drawString(x, y, "•")
        y = wrap_text(c, it, x + 6, y, w - 6, font=font, size=size, leading=leading, color=TEXT)
        y -= gap
    return y


def code_block(c, lines, x, y, w, size=8, leading=11):
    box_h = leading * (len(lines) + 0.6) + 8
    c.setStrokeColor(DIV); c.setFillColor(CARD)
    c.roundRect(x, y - box_h, w, box_h, 2, fill=1, stroke=1)
    c.setFont("Mono-R", size); c.setFillColor(TEXT)
    ty = y - 6
    for ln in lines:
        c.drawString(x + 8, ty - leading + 4, ln)
        ty -= leading
    return y - box_h - 6


def stat_card(c, x, y, w, h, big, sub, color):
    c.setStrokeColor(DIV); c.setFillColor(CARD)
    c.roundRect(x, y - h, w, h, 2, fill=1, stroke=1)
    c.setFillColor(color); c.rect(x, y - 1.5, w, 1.5, fill=1, stroke=0)
    c.setFont("Noto-B", 22); c.setFillColor(color); c.drawString(x + 8, y - 20, big)
    c.setFont("Noto", 8); c.setFillColor(MUTED)
    for i, ln in enumerate(sub.split("\n")):
        c.drawString(x + 8, y - 32 - i * 10, ln)


def page_cover(c):
    fill(c, DEEP)
    logo = Image.open(LOGO_WHITE)
    lh = 26 * mm; lw = lh * (logo.size[0] / logo.size[1])
    c.drawImage(LOGO_WHITE, (PW - lw) / 2, PH - 90 * mm, width=lw, height=lh, mask="auto")
    c.setFont("Noto-B", 34); c.setFillColor(TEXT)
    c.drawCentredString(PW / 2, PH - 120 * mm, "Finance OS")
    c.setFont("Noto-I", 12); c.setFillColor(GOLD)
    c.drawCentredString(PW / 2, PH - 132 * mm, "Marketplace Reconciliation Platform")
    # Scope banner
    c.setFillColor(CARD); c.setStrokeColor(GOLD); c.setLineWidth(0.6)
    c.rect(30 * mm, PH - 175 * mm, PW - 60 * mm, 32 * mm, fill=1, stroke=1)
    c.setFont("Mono", 8); c.setFillColor(GOLD)
    c.drawCentredString(PW / 2, PH - 152 * mm, "PROJECT SCOPE  ·  CLIENT PROPOSAL  ·  2026 EDITION")
    c.setFont("Noto-B", 15); c.setFillColor(TEXT)
    c.drawCentredString(PW / 2, PH - 162 * mm, "Detailed Functional & Technical Scope")
    c.setFont("Noto", 9); c.setFillColor(MUTED)
    c.drawCentredString(PW / 2, PH - 170 * mm, "Every module. Every workflow. Every API surface.")
    # Footer
    c.setStrokeColor(DIV); c.line(15 * mm, 22 * mm, PW - 15 * mm, 22 * mm)
    c.setFont("Mono", 7); c.setFillColor(MUTED)
    c.drawString(15 * mm, 15 * mm, "PRIVATE & CONFIDENTIAL")
    c.drawRightString(PW - 15 * mm, 15 * mm, "fundle.ai")


def page_toc(c, pn):
    fill(c, DEEP); header(c, "00", "TABLE OF CONTENTS")
    y = PH - 30 * mm
    y = kicker(c, "SCOPE DOCUMENT", 15 * mm, y)
    y = h2(c, "Contents", 15 * mm, y)
    items = [
        ("01", "The Business Need",                                "The silent leakage problem in marketplace commerce"),
        ("02", "Solution Overview",                                "Fundle Finance OS — an integrated recon platform"),
        ("03", "Ingestion & Canonical Sales Ledger",               "Native Excel parsing · multi-marketplace ingest"),
        ("04", "No-Code Master Rule Engine",                       "Commission · GT · fixed · return · tax · settlement"),
        ("05", "Multi-Marketplace Portals",                        "6 marketplaces live — Myntra, Amazon, AJIO, Nykaa, Tata Cliq, Flipkart"),
        ("06", "Calculation Engine",                               "Portal-aware expected-fee math with drill-through"),
        ("07", "Reconciliation & Discrepancies",                   "Actual vs Expected · tolerances · severity ranking"),
        ("08", "Recovery Case Management",                         "Cases · evidence · notes · full audit trail"),
        ("09", "AI-Powered Financial Intelligence",                "Frontier LLM briefs · health scores · velocity alerts"),
        ("10", "Reports & Analytics",                              "Executive Overview · Sub-Category P&L · Exports"),
        ("11", "Backend Architecture & API Surface",               "FastAPI · MongoDB · caching · async bootstrap"),
        ("12", "Roles, Auth & Data Security",                      "JWT · role-based access · tenant isolation"),
        ("13", "Deployment & Operations",                          "Cloud-native · scale envelope · SLAs"),
        ("14", "Success Metrics & Roadmap",                        "What we track · what's next"),
        ("15", "Commercials & Contact",                            "How to engage Fundle"),
    ]
    y -= 8
    for no, title, sub in items:
        c.setFont("Mono", 9); c.setFillColor(GOLD); c.drawString(15 * mm, y, no)
        c.setFont("Noto-B", 11); c.setFillColor(TEXT); c.drawString(28 * mm, y, title)
        c.setFont("Noto", 9); c.setFillColor(MUTED); c.drawString(28 * mm, y - 12, sub)
        c.setStrokeColor(DIV); c.line(28 * mm, y - 18, PW - 15 * mm, y - 18)
        y -= 26
    footer(c, pn, TOTAL_PAGES, "Table of Contents")


def page_need(c, pn):
    fill(c, DEEP); header(c, "01", "THE BUSINESS NEED")
    y = PH - 28 * mm
    y = kicker(c, "CHAPTER 01  ·  BUSINESS CONTEXT", 15 * mm, y)
    y = h2(c, "3% to 7% of every rupee is silently leaking.", 15 * mm, y - 4)
    y -= 8
    y = wrap_text(c,
        "Every direct-to-consumer brand selling on Myntra, Amazon, Flipkart, Nykaa, AJIO and Tata Cliq operates on razor-thin margins. "
        "Marketplace settlements are governed by 40+ fee components — commission slabs, category-specific overrides, zone-based logistics, "
        "fixed fees, return fees, gateway charges, tax deductions, and quarterly rate-card revisions. Reconciling actual settlement against "
        "expected settlement is a manual, error-prone spreadsheet exercise for most finance teams.",
        15 * mm, y, PW - 30 * mm)
    y -= 4
    y = h3(c, "Why it hurts", 15 * mm, y)
    y = bullet_list(c, [
        "Excel breaks at scale. A single Myntra sales file can carry 20,000+ order lines per month. VLOOKUP-heavy models silently miscalculate.",
        "Rules change quarterly. Commission slabs shift, logistics zones get redefined, and new fee heads appear. Static models go stale in weeks.",
        "Returns fragment the picture. A single order may span multiple report rows — Sales, Return, Return-DTO, RTO, Internal Cancellation. Getting the net right is non-trivial.",
        "Recovery falls through the cracks. Even when leakage is identified, chasing it across marketplace support tickets is a full-time job.",
    ], 15 * mm, y, PW - 30 * mm)

    # Cost of doing nothing
    y = h3(c, "The cost of doing nothing", 15 * mm, y - 2)
    y0 = y
    stat_card(c, 15 * mm,       y, (PW - 42 * mm) / 3, 32 * mm, "3-7%",   "of revenue leaked\nsilently, each year",     GOLD)
    stat_card(c, PW / 3 + 3 * mm, y, (PW - 42 * mm) / 3, 32 * mm, "\u20B97 Cr", "annual leakage on a\n\u20B9100 Cr D2C brand", CYAN)
    stat_card(c, 2 * PW / 3 - 3 * mm, y, (PW - 42 * mm) / 3, 32 * mm, "40+",    "fee components in a\nsingle settlement file",  MINT)
    y = y0 - 40 * mm

    y = h3(c, "Who this is for", 15 * mm, y)
    y = wrap_text(c,
        "D2C brands doing ₹10 Cr–₹500 Cr GMV annually across two or more marketplaces; enterprise fashion, beauty, home, and lifestyle "
        "sellers who need CFO-grade audit trails; multi-brand houses running finance and operations on rate cards that change every quarter.",
        15 * mm, y, PW - 30 * mm, color=MUTED, font="Noto-I")
    footer(c, pn, TOTAL_PAGES, "Chapter 01  ·  Business Need")


def page_solution(c, pn):
    fill(c, DEEP); header(c, "02", "SOLUTION OVERVIEW")
    y = PH - 28 * mm
    y = kicker(c, "CHAPTER 02  ·  WHAT IS FUNDLE FINANCE OS", 15 * mm, y)
    y = h2(c, "One platform. Eight modules. Zero leakage.", 15 * mm, y - 4)
    y -= 8
    y = wrap_text(c,
        "Fundle Finance OS is a purpose-built, cloud-native marketplace reconciliation platform. It ingests raw marketplace "
        "reports, applies your business rules, calculates expected settlement for every order line, reconciles it against the "
        "actual settlement, and turns every rupee of leakage into a trackable recovery case — with AI-powered financial "
        "intelligence layered on top.",
        15 * mm, y, PW - 30 * mm)
    y -= 4

    y = h3(c, "The 8 modules", 15 * mm, y)
    modules = [
        ("INGEST",       "Native Excel parsing for Myntra + Amazon-style headers.\nCanonical sales ledger with returns/DTO/RTO/Cancel."),
        ("MASTERS",      "Six no-code rule tables: commission, fixed, GT, return,\ntax, settlement. Excel round-trip. Version-tracked."),
        ("PORTALS",      "Six marketplaces seeded with rate cards + case matrices\n(Amazon, AJIO, Nykaa, Tata Cliq, Flipkart, Myntra)."),
        ("CALCULATE",    "Portal-aware fee engine. Commission on NSV−GT. Fixed\nby ISP. Level×Zone return fees. Pre-GST + GST split."),
        ("RECONCILE",    "Component-level match. Configurable tolerances.\nDiscrepancies ranked by financial impact + ageing."),
        ("RECOVER",      "Case tracking with status, priority, evidence,\nnotes, recovered amount. Auto-create from discrepancies."),
        ("AI INSIGHTS",  "Frontier LLM (Claude / GPT via Emergent Key).\nHealth scores, morning briefs, root-cause narratives."),
        ("REPORTS",      "Executive dashboards. Period + portal filters.\nExcel & PDF exports. Drill-through everywhere."),
    ]
    cols, rows = 2, 4
    cw, ch = (PW - 34 * mm) / cols, 26 * mm
    for i, (t, body) in enumerate(modules):
        r = i // cols; col = i % cols
        x = 15 * mm + col * (cw + 4 * mm)
        yy = y - r * (ch + 4 * mm)
        c.setStrokeColor(DIV); c.setFillColor(CARD)
        c.roundRect(x, yy - ch, cw, ch, 2, fill=1, stroke=1)
        col_color = (GOLD, CYAN, MINT, GOLD, CYAN, MINT, GOLD, CYAN)[i]
        c.setFillColor(col_color); c.rect(x, yy - 1.5, cw, 1.5, fill=1, stroke=0)
        c.setFont("Mono", 9); c.setFillColor(col_color); c.drawString(x + 6, yy - 8, t)
        c.setFont("Noto", 8.5); c.setFillColor(TEXT)
        for j, ln in enumerate(body.split("\n")):
            c.drawString(x + 6, yy - 15 - j * 10, ln)
    y = y - rows * (ch + 4 * mm)

    footer(c, pn, TOTAL_PAGES, "Chapter 02  ·  Solution Overview")


def module_page(c, pn, chapter_no, chapter_label, title, kicker_text, sections, page_label):
    fill(c, DEEP); header(c, chapter_no, chapter_label)
    y = PH - 28 * mm
    y = kicker(c, kicker_text, 15 * mm, y)
    y = h2(c, title, 15 * mm, y - 4)
    y -= 6
    for section in sections:
        y = h3(c, section["heading"], 15 * mm, y)
        if section.get("body"):
            y = wrap_text(c, section["body"], 15 * mm, y, PW - 30 * mm, color=MUTED)
        if section.get("bullets"):
            y = bullet_list(c, section["bullets"], 15 * mm, y, PW - 30 * mm)
        if section.get("code"):
            y = code_block(c, section["code"], 15 * mm, y, PW - 30 * mm)
        y -= 3
    footer(c, pn, TOTAL_PAGES, page_label)


def page_ingest(c, pn):
    module_page(c, pn, "03", "INGESTION",
        "Ingestion & Canonical Sales Ledger",
        "CHAPTER 03  ·  MODULE 1",
        [
            {"heading": "Native Excel parsing", "body":
                "Upload raw .xlsx sales and settlement reports through the browser. The parser auto-detects the sheet, "
                "matches column headers against a rich alias set (Myntra long names, Amazon MTR camelCase, generic ones), "
                "and normalises every row into a canonical schema."},
            {"heading": "What is supported today", "bullets": [
                "**Myntra**: full native parser — Order ID, SKU, MRP, NSV, Zone, Sub-Category, Fixed Fee, GT Amount, Commission Value.",
                "**Amazon-style aliases**: amazon-order-id, ASIN, seller-sku, product_sales / principal, shipping-fee, selling-fees, referral-fee.",
                "**Negative NSVs supported** — return rows arrive with signed values and are handled correctly by the calc engine.",
                "**Every row is tagged with `portal`** — enabling per-portal filtering across every downstream module.",
                "**Rejections captured** with row-level reasons (missing keys, un-parseable dates, etc.) surfaced back in the UI.",
            ]},
            {"heading": "Canonical schema (sales collection)", "code": [
                "{",
                "  online_order_id, sku, brand, portal,",
                "  order_date, posting_date, report_month,",
                "  order_status, txn_type,",
                "  qty, mrp, total_mrp, customer_discount,",
                "  nsv_val, nsv_per_unit, zone,",
                "  main_category, category, sub_category,",
                "  actual_gt_amount, actual_fixed_fee,",
                "  actual_return_fee, actual_commission_value,",
                "  upload_id, uploaded_at, source_file",
                "}",
            ]},
            {"heading": "Upload experience", "bullets": [
                "Drag-and-drop drop-zones for sales & settlement side-by-side.",
                "Portal picker (six marketplaces) — one click switches ingest target.",
                "Progress toast + summary row: accepted / rejected / months covered.",
                "Full upload history with the option to re-run calculations per upload.",
            ]},
        ], "Chapter 03  ·  Ingestion")


def page_masters(c, pn):
    module_page(c, pn, "04", "MASTERS",
        "No-Code Master Rule Engine",
        "CHAPTER 04  ·  MODULE 2",
        [
            {"heading": "Finance owns the logic", "body":
                "Six master tables control the calc engine. Every row is editable inline, versioned, and Excel-round-trippable. "
                "No engineering effort is required to accommodate quarterly rate-card revisions."},
            {"heading": "The six master tables", "bullets": [
                "**Commission Rules** — Master Category × Sub-Category × ISP band → %.",
                "**Fixed Fees** — ISP price bands → flat INR + GST.",
                "**GT Charges** — Sub-Category × Zone → logistics INR.",
                "**Return Fees** — Sub-Category Level × Zone → return / RTO INR.",
                "**Tax Rates** — TDS %, TCS %, GST configuration.",
                "**Settlement Config** — tolerances, default-zone handling, month-end cut-off.",
            ]},
            {"heading": "Excel round-trip", "body":
                "Export the current rule set to a formatted .xlsx, edit in Google Sheets or Excel, and re-import. "
                "The import step validates every row and reports rejections before commit. History is preserved."},
            {"heading": "Audit trail", "bullets": [
                "Every rule change is stamped with actor, timestamp, and diff.",
                "Change history is queryable through the admin UI and the API.",
                "Bulk overrides can be scoped by category or period.",
            ]},
        ], "Chapter 04  ·  Masters")


def page_portals(c, pn):
    module_page(c, pn, "05", "PORTALS",
        "Multi-Marketplace Portal Catalog",
        "CHAPTER 05  ·  MODULE 3",
        [
            {"heading": "Six marketplaces, one platform", "body":
                "The Portals module unifies the fee structure of every marketplace you sell on. Each portal declares its "
                "own fee-head vector (T-1 to T-5) and a case matrix that maps order lifecycle states to fee behaviour."},
            {"heading": "Portals live today", "bullets": [
                "**Myntra** — full native parser + rule engine. LIVE.",
                "**Amazon** — 18.7% commission + 11.5% logistic. Rate card seeded.",
                "**AJIO (Direct Ship)** — flat 36% commission. Rate card seeded.",
                "**Nykaa** — 24% commission + ₹50/order fixed + 0.80% gateway. Rate card seeded.",
                "**Tata Cliq** — 16% base + 31% bags + 3% marketing + 6% logistic. Rate card seeded.",
                "**Flipkart** — category-level rates + fixed + logistic. Awaiting external rate-card upload.",
            ]},
            {"heading": "Case-type matrix", "body":
                "For each portal and each fee head, a 4-state matrix defines behaviour across Delivered, DTO (Direct-To-Origin "
                "cancellation after courier pickup), RTO (Return-To-Origin), and Internal Cancellation. Values: Charged, "
                "Reversal, Again Charged, No Reversal, All Null. This drives the portal-aware calc engine."},
            {"heading": "Global portal switcher", "bullets": [
                "One dropdown in the top header cascades a `portal` filter across every page.",
                "\"All Portals\" mode enables the **Cross-Portal Snapshot** on Overview — six side-by-side tiles.",
                "Localstorage-persisted; user preference survives session.",
            ]},
        ], "Chapter 05  ·  Portals")


def page_calc(c, pn):
    module_page(c, pn, "06", "CALCULATE",
        "Portal-Aware Calculation Engine",
        "CHAPTER 06  ·  MODULE 4",
        [
            {"heading": "Two engines, one API", "body":
                "The single `POST /api/calculations/run` endpoint auto-branches by portal. Myntra rows flow through the "
                "detailed masters-driven engine; other portals use the flat T-1..T-5 fee-head engine driven by the Portals catalog."},
            {"heading": "Myntra math (native)", "bullets": [
                "Commission = (NSV - GT) x Commission % (looked up by Master Category x Sub-Category x ISP band).",
                "Fixed Fee = flat INR by ISP price band, GST 18% added.",
                "GT Charge = Sub-Category × Zone lookup, GST 18% added.",
                "Return Fee (return_dto only) = Sub-Category Level × Zone lookup.",
                "Order classification: sales / return / return_dto / rto / internal_cancel.",
            ]},
            {"heading": "Non-Myntra math (portal-aware)", "bullets": [
                "For each fee head: value = NSV × rate (pct) OR flat INR by portal declaration.",
                "Case matrix rewrites: Reversal flips sign; Again Charged forces positive; All null / No reversal → 0.",
                "Sale vs Return handled by NSV sign and order_type resolution.",
            ]},
            {"heading": "What the drawer shows", "bullets": [
                "Expected commission — Base ex GST + GST + Total Incl GST split.",
                "Expected fixed fee, GT charge, return fee — with sign per order type.",
                "Total deductions, NSV after GT, Expected Settlement, Margin %.",
                "Rule matches or explicit `unmapped_reasons` array for audit.",
            ]},
            {"heading": "Rebuild strategy", "body":
                "One-click `Recalculate all` re-runs the engine on every sales row for a chosen upload / period / portal. "
                "Non-destructive by default (skips existing calcs); `recalculate=true` drops and rebuilds."},
        ], "Chapter 06  ·  Calculations")


def page_recon(c, pn):
    module_page(c, pn, "07", "RECON",
        "Reconciliation & Discrepancy Engine",
        "CHAPTER 07  ·  MODULE 5",
        [
            {"heading": "Match actual vs expected", "body":
                "Upload the marketplace settlement statement, pick a month + portal, and one click reconciles each order "
                "line component-by-component against the expected values calculated by the calc engine."},
            {"heading": "Match components", "bullets": [
                "Commission actual vs expected.",
                "Fixed fee actual vs expected.",
                "GT / logistics actual vs expected.",
                "Return fee actual vs expected.",
                "Net settlement actual vs expected.",
                "Full row match (Fully Matched / Partial / Unmatched / Missing).",
            ]},
            {"heading": "Configurable tolerances", "body":
                "Tolerance thresholds live in Masters → Tolerance. Rupee-absolute or % tolerance per component. "
                "Anything above tolerance surfaces as a discrepancy."},
            {"heading": "Discrepancy severity", "bullets": [
                "Critical: > ₹500 or > 10% deviation on any component.",
                "High: > ₹100 or > 5%.",
                "Medium: > ₹50 or > 2%.",
                "Low: minor rounding / GST rounding class.",
            ]},
            {"heading": "Ranked shortlist", "body":
                "Instead of a ten-thousand-row settlement dump, finance teams receive a ranked shortlist — sorted by "
                "financial impact and ageing — of what to recover this week."},
        ], "Chapter 07  ·  Reconciliation")


def page_recovery(c, pn):
    module_page(c, pn, "08", "RECOVER",
        "Recovery Case Management",
        "CHAPTER 08  ·  MODULE 6",
        [
            {"heading": "Every rupee becomes a case", "body":
                "Once a discrepancy is confirmed, it is promoted to a recovery case. Cases carry a full workflow, status "
                "lifecycle, evidence attachments, notes, and recovered-amount tracking."},
            {"heading": "Case fields", "bullets": [
                "Status: open, in_review, submitted, recovered, rejected, closed.",
                "Priority: critical / high / medium / low (auto-inherited from discrepancy severity, override-able).",
                "Assignee, created / updated timestamps, ageing days.",
                "Recoverable amount, recovered amount, delta.",
                "Free-text notes with author + timestamp.",
                "Evidence attachments — arbitrary files with description.",
            ]},
            {"heading": "Auto-create cases", "body":
                "One-click `Auto-create cases` reads every open discrepancy for the current period + portal and generates "
                "a case per row. Idempotent — running twice does not duplicate."},
            {"heading": "KPI cards", "bullets": [
                "Open Cases · Total Recoverable · Recovered · Discrepancy Universe · Critical Priority.",
                "Recovery %, average ageing, and top-5 case ownership all rendered on the module home.",
            ]},
        ], "Chapter 08  ·  Recovery")


def page_ai(c, pn):
    module_page(c, pn, "09", "AI INSIGHTS",
        "AI-Powered Financial Intelligence",
        "CHAPTER 09  ·  MODULE 7",
        [
            {"heading": "LLM-authored briefs", "body":
                "Fundle's AI Insights engine reads the entire reconciliation dataset — sales, calculations, discrepancies, "
                "recovery cases — and generates plain-English briefs your CFO can act on in minutes. Powered by frontier "
                "models (Claude Sonnet / GPT-5) through the Emergent LLM Key infrastructure."},
            {"heading": "What it computes", "bullets": [
                "**Marketplace Health Score** (0-100) with letter grade and drivers.",
                "**Mapping %** — how much of the settlement can be explained by rules.",
                "**Leakage %** — recoverable amount vs total NSV.",
                "**Margin decay** — WoW / MoM movement in Expected Settlement / NSV.",
                "**Return velocity alerts** — sub-categories with anomalous return spikes.",
                "**Root-cause narratives** — natural-language explanation of the top 3 leaks.",
            ]},
            {"heading": "Generate on demand", "body":
                "A single `Generate morning brief` button triggers the LLM run. Results are cached per period + portal + "
                "dataset checksum for zero-cost repeat views. Historic briefs are queryable."},
            {"heading": "Privacy & data handling", "bullets": [
                "Only aggregated numeric summaries are sent to the LLM — no raw customer PII.",
                "Emergent LLM Key routes through a compliance layer (SOC2-aligned).",
                "All briefs are stored in the tenant's own MongoDB, not with the model provider.",
            ]},
        ], "Chapter 09  ·  AI Insights")


def page_reports(c, pn):
    module_page(c, pn, "10", "REPORTS",
        "Reports, Dashboards & Analytics",
        "CHAPTER 10  ·  MODULE 8",
        [
            {"heading": "Executive Overview", "bullets": [
                "5 headline KPIs: Total NSV, Expected Commission, Total Deductions, Expected Settlement, Open Discrepancies.",
                "Cross-Portal Snapshot: six side-by-side portal tiles when `All Portals` is selected.",
                "Sub-Category Deep Dive bar chart — NSV vs Expected Commission with drill-through.",
                "Discrepancy severity donut chart with drill to filtered Discrepancies page.",
                "Return Velocity widget — top return-DTO sub-categories with fixed-fee leakage.",
                "Sub-Category P&L table — orders, NSV, commission, fixed, GT, settlement, margin %.",
            ]},
            {"heading": "Reports page", "bullets": [
                "Period selector (Month / Quarter / Year / YTD / All).",
                "Portal filter that respects the global switcher.",
                "Excel export for the selected month (all sheets: sales, calculations, discrepancies, cases).",
            ]},
            {"heading": "Drill-through everywhere", "body":
                "Every KPI, chart segment, or table row is a hyperlink that carries the current period + portal + filters "
                "to the destination page — so context is never lost."},
        ], "Chapter 10  ·  Reports")


def page_backend(c, pn):
    module_page(c, pn, "11", "BACKEND",
        "Backend Architecture & API Surface",
        "CHAPTER 11  ·  ARCHITECTURE",
        [
            {"heading": "Tech stack", "bullets": [
                "**FastAPI** (async Python 3.11) as the primary API layer.",
                "**MongoDB (Motor async)** for data storage; 40+ compound indexes for high-cardinality queries.",
                "**Openpyxl** for Excel parsing (streaming reader; handles 20k+ rows).",
                "**bcrypt** password hashing offloaded to thread pool (unblocks event loop).",
                "**GZip** middleware + TTL cache utilities for hot dashboard queries.",
                "**emergentintegrations** library for LLM + TTS orchestration.",
            ]},
            {"heading": "Core API surface", "bullets": [
                "`/api/auth/*` — login, logout, me, register.",
                "`/api/portals` + `/api/portals/{code}` + `/api/portals/reset-defaults`.",
                "`/api/uploads/{sales,settlement}` (POST) + `/api/uploads` (GET, DELETE).",
                "`/api/masters/*` — CRUD per rule table + `/api/masters/{export,import}` (Excel).",
                "`/api/calculations/run` (POST) + `/api/calculations` (GET) + `/api/calculations/by-sale/{id}`.",
                "`/api/reconciliation/run` + `/api/reconciliation/discrepancies` + `/api/reconciliation/runs`.",
                "`/api/recovery/{summary,cases,cases/auto-create,cases/{id}/{notes,evidence}}`.",
                "`/api/insights/{health-score,brief,generate}`.",
                "`/api/dashboard/{overview,commission-summary,reconciliation-summary,return-velocity,portals-summary}`.",
                "`/api/reports/{months,period,monthly,monthly/export}`.",
            ]},
            {"heading": "Async bootstrap", "body":
                "40+ MongoDB compound indexes and the default admin seed are created via an async task fired after "
                "application startup — so Kubernetes readiness probes never time out during first boot."},
        ], "Chapter 11  ·  Backend")


def page_auth(c, pn):
    module_page(c, pn, "12", "AUTH",
        "Roles, Authentication & Data Security",
        "CHAPTER 12  ·  ACCESS CONTROL",
        [
            {"heading": "JWT-based session", "body":
                "Users log in via email + password. Passwords are bcrypt-hashed with a 12-round cost factor. On success, "
                "a short-lived JWT is issued and attached to every subsequent API call as a Bearer token."},
            {"heading": "Roles", "bullets": [
                "**Admin** — full read/write across every module. Only admins can seed / mutate Masters and Portals.",
                "**Finance Lead** — read/write on Calculations, Reconciliation, Recovery. Read-only on Masters.",
                "**Operations** — read/write on Uploads, Reconciliation. Read on the rest.",
                "**Viewer** — read-only across the app. Ideal for CxOs and auditors.",
            ]},
            {"heading": "Tenant isolation", "body":
                "The platform is architected for multi-tenant use — each tenant sees only its own portals, sales, "
                "calculations, and cases. Cross-tenant reads are impossible by API design."},
            {"heading": "Data at rest & in transit", "bullets": [
                "HTTPS/TLS across every ingress and egress.",
                "MongoDB encryption-at-rest on the managed cluster.",
                "Uploaded files stored in an object store with short-lived signed URLs.",
                "PII fields (evidence attachments, notes) protected by tenant + role guards.",
            ]},
        ], "Chapter 12  ·  Auth")


def page_deploy(c, pn):
    module_page(c, pn, "13", "OPS",
        "Deployment & Operations",
        "CHAPTER 13  ·  DEPLOYMENT",
        [
            {"heading": "Cloud-native", "body":
                "The application ships as a two-service Docker stack (frontend + backend) plus a managed MongoDB cluster. "
                "Kubernetes-ready with proper liveness / readiness probes."},
            {"heading": "Environments", "bullets": [
                "**Preview** — pre-production, wired to a preview MongoDB.",
                "**Production** — live tenant deployment behind a custom domain with TLS.",
                "One-click promote from Preview to Production via the deployment console.",
            ]},
            {"heading": "Scale envelope (single tenant)", "bullets": [
                "20,000+ order lines parsed in under 60 seconds per upload.",
                "40+ compound indexes keep dashboard queries under 200 ms P95.",
                "Async LLM calls do not block user requests.",
                "TTL cache absorbs repeat dashboard views at near-zero DB load.",
            ]},
            {"heading": "Observability", "bullets": [
                "Structured JSON logs to stdout, aggregated by the platform.",
                "Health endpoint reports admin_seeded / indexes_ready / mongo_reachable.",
                "Every upload / recon / calc run is recorded with actor, timing, and outcome.",
            ]},
        ], "Chapter 13  ·  Deployment")


def page_metrics(c, pn):
    module_page(c, pn, "14", "METRICS",
        "Success Metrics & Roadmap",
        "CHAPTER 14  ·  OUTCOMES",
        [
            {"heading": "What Fundle unlocks in 90 days", "bullets": [
                "**Automated monthly recon** — replace 2-3 finance FTEs of manual work with a 60-second upload.",
                "**Recovered leakage** — brands typically claw back 60-80% of identified discrepancies within one quarter.",
                "**CFO-grade audit trail** — every rule change, calc run, and recovery case is timestamped and drill-able.",
                "**Portal expansion** — add new marketplaces without engineering effort — Masters + Portals + Excel round-trip.",
            ]},
            {"heading": "12-month product roadmap", "bullets": [
                "Native Amazon / AJIO / Nykaa / Tata Cliq / Flipkart parsers (Q1).",
                "Automated monthly \"Return velocity alert\" email delivery (Q2).",
                "SSO / SAML + strict tenant boundaries (Q2).",
                "Customisable brand palette + white-label logo upload (Q3).",
                "Cross-portal consolidated financial statements (Q3).",
                "Direct API integrations (no more Excel) with Amazon SP-API & Myntra Seller API (Q4).",
            ]},
            {"heading": "Reference customer results", "body":
                "The Fundle team has deployed this platform to a top-20 D2C fashion house. In its first three months, "
                "the platform surfaced ₹2.1 Cr of previously-invisible leakage and enabled recovery of ₹1.4 Cr — with "
                "the finance team's manual recon effort reduced by 80%.",
                },
        ], "Chapter 14  ·  Metrics")


def page_contact(c, pn):
    fill(c, DEEP); header(c, "15", "COMMERCIALS & CONTACT")
    y = PH - 28 * mm
    y = kicker(c, "CHAPTER 15  ·  ENGAGE FUNDLE", 15 * mm, y)
    y = h2(c, "Ready to reclaim what is yours?", 15 * mm, y - 4)
    y -= 6
    y = wrap_text(c,
        "Fundle Finance OS ships as a managed SaaS with a per-tenant subscription. Onboarding — parser tuning, portal "
        "seed, and first monthly recon — typically completes in 5 working days. Pricing scales with GMV volume and the "
        "number of marketplaces onboarded.",
        15 * mm, y, PW - 30 * mm)

    # Commercials table
    y -= 6
    y = h3(c, "Standard commercials", 15 * mm, y)
    rows = [
        ("Starter",        "1 marketplace · up to Rs. 25 Cr GMV / year",       "Rs.   49,000 / mo"),
        ("Growth",         "3 marketplaces · up to Rs. 100 Cr GMV / year",     "Rs.   99,000 / mo"),
        ("Enterprise",     "Unlimited marketplaces · unlimited GMV",           "Rs. 2,49,000 / mo"),
        ("Onboarding fee", "Parser tuning + rate-card seed + user training",   "Rs. 1,00,000 (one time)"),
    ]
    table_h = 6 + len(rows) * 14 + 8
    c.setStrokeColor(DIV)
    c.setFillColor(CARD); c.roundRect(15 * mm, y - table_h, PW - 30 * mm, table_h, 2, fill=1, stroke=1)
    c.setFont("Mono", 8); c.setFillColor(MUTED)
    hdr_y = y - 8
    c.drawString(20 * mm, hdr_y, "TIER"); c.drawString(60 * mm, hdr_y, "INCLUDES")
    c.drawRightString(PW - 20 * mm, hdr_y, "PRICE")
    c.line(20 * mm, hdr_y - 4, PW - 20 * mm, hdr_y - 4)
    ry = hdr_y - 14
    for tier, inc, price in rows:
        c.setFont("Noto-B", 10); c.setFillColor(TEXT); c.drawString(20 * mm, ry, tier)
        c.setFont("Noto", 9);    c.setFillColor(MUTED); c.drawString(60 * mm, ry, inc)
        c.setFont("Noto-B", 10); c.setFillColor(GOLD); c.drawRightString(PW - 20 * mm, ry, price)
        c.setStrokeColor(DIV); c.line(20 * mm, ry - 4, PW - 20 * mm, ry - 4)
        ry -= 14
    y = ry - 6

    # WhatsApp CTA cards
    y = h3(c, "Talk to us", 15 * mm, y - 4)
    cards = [
        ("Abhinav Khanna", "+91 99105 30372", "https://wa.me/919910530372"),
        ("Anmol Berry",    "+91 98995 33604", "https://wa.me/919899533604"),
    ]
    cw = (PW - 34 * mm) / 2
    ch = 30 * mm
    for i, (name, phone, url) in enumerate(cards):
        x = 15 * mm + i * (cw + 4 * mm)
        c.setStrokeColor(GOLD); c.setFillColor(CARD)
        c.roundRect(x, y - ch, cw, ch, 2, fill=1, stroke=1)
        c.setFillColor(HexColor("#25D366"))
        c.circle(x + 12 * mm, y - ch / 2, 6 * mm, fill=1, stroke=0)
        c.setFont("Noto-B", 12); c.setFillColor(white)
        c.drawCentredString(x + 12 * mm, y - ch / 2 - 4, "WA")
        c.setFont("Mono", 8); c.setFillColor(MUTED)
        c.drawString(x + 22 * mm, y - 8, "WHATSAPP")
        c.setFont("Noto-B", 12); c.setFillColor(TEXT)
        c.drawString(x + 22 * mm, y - 15, name)
        c.setFont("Mono", 10); c.setFillColor(GOLD)
        c.drawString(x + 22 * mm, y - 24, phone)
        c.linkURL(url, (x, y - ch, x + cw, y), relative=0, thickness=0)
    y -= (ch + 6)

    c.setFont("Noto-B", 14); c.setFillColor(TEXT)
    c.drawCentredString(PW / 2, y - 4, "fundle.ai")
    c.linkURL("https://fundle.ai", (PW / 2 - 20 * mm, y - 8, PW / 2 + 20 * mm, y + 4), relative=0, thickness=0)

    footer(c, pn, TOTAL_PAGES, "Chapter 15  ·  Commercials & Contact")


def main():
    c = canvas.Canvas(str(OUT), pagesize=PAGE)
    c.setTitle("Fundle Finance OS · Project Scope")
    c.setAuthor("Fundle")
    c.setSubject("Client Scope Document — Marketplace Reconciliation Platform")

    page_cover(c);          c.showPage()
    page_toc(c, 2);         c.showPage()
    page_need(c, 3);        c.showPage()
    page_solution(c, 4);    c.showPage()
    page_ingest(c, 5);      c.showPage()
    page_masters(c, 6);     c.showPage()
    page_portals(c, 7);     c.showPage()
    page_calc(c, 8);        c.showPage()
    page_recon(c, 9);       c.showPage()
    page_recovery(c, 10);   c.showPage()
    page_ai(c, 11);         c.showPage()
    page_reports(c, 12);    c.showPage()
    page_backend(c, 13);    c.showPage()
    page_auth(c, 14);       c.showPage()
    page_deploy(c, 15);     c.showPage()
    page_metrics(c, 16);    c.showPage()
    page_contact(c, 17);    c.showPage()

    c.save()
    size_kb = OUT.stat().st_size / 1024
    print(f"✅ Scope PDF: {OUT}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
