"""Build 8-page Fundle Finance OS product brochure PDF.

Pages
  1. Cover                    (logo · tagline · subtitle · background pattern)
  2. The Problem              (big statistics · industry pain-points)
  3. The Solution             (Fundle Finance OS overview · 6 pillars)
  4. Ingest & Sales Ledger    (screenshot + copy)
  5. Rule Engine + Calc       (screenshot + copy)
  6. Reconciliation + Recover (two screenshots)
  7. AI Insights              (screenshot + copy · AI callout)
  8. Get Started              (WhatsApp CTAs · clickable links)
"""
from pathlib import Path

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as PlatypusImage
from PIL import Image

ROOT = Path("/app/marketing")
OUT = ROOT / "output" / "fundle_finance_os_brochure.pdf"
LOGO_WHITE = str(ROOT / "assets" / "fundle_logo_white.png")
SHOTS = ROOT / "screenshots"

# Register fonts with rupee support
pdfmetrics.registerFont(TTFont("Noto", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Noto-B", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Noto-I", "/usr/share/fonts/truetype/noto/NotoSans-Italic.ttf"))
pdfmetrics.registerFont(TTFont("Mono", "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"))

PAGE = landscape(A4)  # 297 x 210 mm
PW, PH = PAGE

DARK = HexColor("#0B0F17")
DEEP = HexColor("#070A0F")
GOLD = HexColor("#F0B429")
CYAN = HexColor("#63B3ED")
TEXT = HexColor("#F5F6FA")
MUTED = HexColor("#8892A6")
DIV = HexColor("#373E4E")
CARD = HexColor("#111623")


def fill_bg(c, color=DEEP):
    c.setFillColor(color)
    c.rect(0, 0, PW, PH, fill=1, stroke=0)


def grid_overlay(c):
    # Grids removed per user feedback — keep function as a no-op so callers still work.
    return


def draw_logo(c, x, y, height=14 * mm):
    logo = Image.open(LOGO_WHITE)
    w = height * (logo.size[0] / logo.size[1])
    c.drawImage(LOGO_WHITE, x, y, width=w, height=height, mask="auto")
    return x + w


def brand_footer(c, page_num, total=8, label=None):
    c.setStrokeColor(DIV)
    c.setLineWidth(0.4)
    c.line(15 * mm, 15 * mm, PW - 15 * mm, 15 * mm)
    draw_logo(c, 15 * mm, 6 * mm, height=8 * mm)
    c.setFont("Mono", 7)
    c.setFillColor(MUTED)
    c.drawRightString(PW - 15 * mm, 9 * mm, f"fundle.ai   ·   {page_num:02d} / {total:02d}")
    if label:
        c.drawCentredString(PW / 2, 9 * mm, label)


def chapter_label(c, text):
    c.setFont("Mono", 9)
    c.setFillColor(GOLD)
    c.drawString(15 * mm, PH - 20 * mm, text)
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.6)
    c.line(15 * mm, PH - 22 * mm, 60 * mm, PH - 22 * mm)


def draw_wrapped(c, text, x, y, max_w, font="Noto", size=11, leading=15, color=TEXT):
    c.setFont(font, size)
    c.setFillColor(color)
    words = text.split()
    line = ""
    for w in words:
        test = (line + " " + w).strip()
        if pdfmetrics.stringWidth(test, font, size) <= max_w:
            line = test
        else:
            c.drawString(x, y, line)
            y -= leading
            line = w
    if line:
        c.drawString(x, y, line)
    return y - leading


def draw_shot(c, name, x, y, w, h, radius=2):
    p = SHOTS / f"{name}.png"
    # shadow
    c.setFillColor(HexColor("#000000CC"))
    c.roundRect(x + 1.5, y - 1.5, w, h, radius, fill=1, stroke=0)
    # image
    im = Image.open(p)
    ratio = min(w / (im.size[0] * 0.264583 / mm * mm), h / (im.size[1] * 0.264583 / mm * mm))
    # simpler — just fit
    c.drawImage(str(p), x, y, width=w, height=h, mask=None, preserveAspectRatio=True, anchor="c")
    # border
    c.setStrokeColor(DIV)
    c.setLineWidth(0.4)
    c.roundRect(x, y, w, h, radius, fill=0, stroke=1)


def page_cover(c):
    fill_bg(c, DARK)
    grid_overlay(c)
    # Big centred logo
    c.saveState()
    logo = Image.open(LOGO_WHITE)
    lh = 34 * mm
    lw = lh * (logo.size[0] / logo.size[1])
    c.drawImage(LOGO_WHITE, (PW - lw) / 2, PH / 2 + 5 * mm, width=lw, height=lh, mask="auto")
    c.restoreState()

    c.setFont("Noto-B", 42)
    c.setFillColor(TEXT)
    c.drawCentredString(PW / 2, PH / 2 - 6 * mm, "Finance OS")

    c.setFont("Noto-I", 16)
    c.setFillColor(GOLD)
    c.drawCentredString(PW / 2, PH / 2 - 18 * mm, "Marketplace Reconciliation. Reimagined.")

    c.setFont("Noto", 11)
    c.setFillColor(MUTED)
    c.drawCentredString(PW / 2, PH / 2 - 32 * mm,
        "Enterprise-grade reconciliation & AI-powered financial intelligence for D2C brands on Myntra, Amazon and Flipkart.")

    # eyebrow
    c.setFont("Mono", 8)
    c.setFillColor(GOLD)
    c.drawCentredString(PW / 2, PH - 25 * mm, "PRODUCT BROCHURE · 2026 EDITION")

    # footer
    c.setStrokeColor(DIV)
    c.setLineWidth(0.4)
    c.line(15 * mm, 20 * mm, PW - 15 * mm, 20 * mm)
    c.setFont("Mono", 8)
    c.setFillColor(MUTED)
    c.drawString(15 * mm, 12 * mm, "PRIVATE & CONFIDENTIAL   ·   FOR EVALUATION")
    c.drawRightString(PW - 15 * mm, 12 * mm, "fundle.ai")


def page_problem(c):
    fill_bg(c, DEEP)
    grid_overlay(c)
    chapter_label(c, "01  ·  THE INDUSTRY PROBLEM")

    c.setFont("Noto-B", 34)
    c.setFillColor(TEXT)
    c.drawString(15 * mm, PH - 42 * mm, "3% to 7% of your marketplace")
    c.drawString(15 * mm, PH - 52 * mm, "revenue is silently leaking.")

    body = (
        "Every year, direct-to-consumer brands selling on Myntra, Amazon and Flipkart lose "
        "between 3% and 7% of their revenue to invisible commission leakage. Miscalculated "
        "commissions. Unbilled returns. Misapplied logistics charges. Duplicate deductions. "
        "For a brand doing ₹100 crore a year, that is up to ₹7 crore of pure margin, "
        "evaporating silently, month after month, into settlement files no one has the "
        "time to audit."
    )
    draw_wrapped(c, body, 15 * mm, PH - 68 * mm, 155 * mm, font="Noto", size=11, leading=17, color=MUTED)

    # right side stat cards
    cards = [
        ("₹7 Cr",   "Est. annual leakage on a\n₹100 Cr D2C business", GOLD),
        ("40+",     "Fee components in a single\nMyntra settlement file",   CYAN),
        ("21,614",  "Order lines processed by\nFundle in a single upload",  GOLD),
        ("< 60 sec","Parse + calculate a full\nmonthly report end-to-end",  CYAN),
    ]
    sx = PW - 15 * mm - 100 * mm
    sy = PH - 40 * mm
    for big, sub, col in cards:
        cw, ch = 100 * mm, 24 * mm
        c.setStrokeColor(DIV)
        c.setFillColor(CARD)
        c.roundRect(sx, sy - ch, cw, ch, 2, fill=1, stroke=1)
        c.setFont("Noto-B", 24)
        c.setFillColor(col)
        c.drawString(sx + 6 * mm, sy - 11 * mm, big)
        c.setFont("Noto", 9)
        c.setFillColor(MUTED)
        for i, ln in enumerate(sub.split("\n")):
            c.drawString(sx + 6 * mm, sy - 16 * mm - i * 4 * mm, ln)
        sy -= (ch + 4 * mm)

    brand_footer(c, 2, label="The Problem")


def page_why_broken(c):
    fill_bg(c, DEEP)
    grid_overlay(c)
    chapter_label(c, "02  ·  WHY RECONCILIATION IS BROKEN")

    c.setFont("Noto-B", 42)
    c.setFillColor(TEXT)
    c.drawString(15 * mm, PH - 48 * mm, "The settlement statement")
    c.drawString(15 * mm, PH - 61 * mm, "is not a bill —")
    c.setFillColor(GOLD)
    c.drawString(15 * mm, PH - 74 * mm, "it's a 40-column data dump.")

    pain = [
        ("Excel breaks at scale",
         "Tens of thousands of order lines, dozens of fee components, VLOOKUP hell. Errors compound. Cross-checks fail silently."),
        ("Rules change quarterly",
         "Commission slabs shift. Zone-based logistics fees are refreshed. Rate cards get versioned. Static Excel models go stale in weeks."),
        ("Returns fragment the picture",
         "A single order can span multiple report rows — Sales, Return, Return+DTO, RTO, Internal Cancellation. Getting the net right is non-trivial."),
        ("Finance teams give up",
         "Without a purpose-built system, leakage becomes the cost of doing business. Recoveries stop happening. Margin quietly erodes."),
    ]
    x = 15 * mm
    y = PH - 92 * mm
    for title, body in pain:
        c.setFont("Noto-B", 12)
        c.setFillColor(TEXT)
        c.drawString(x, y, title)
        y = draw_wrapped(c, body, x, y - 6 * mm, 260 * mm, font="Noto", size=10, leading=14, color=MUTED)
        y -= 4 * mm

    brand_footer(c, 3, label="Why It's Broken")


def page_solution(c):
    fill_bg(c, DEEP)
    grid_overlay(c)
    chapter_label(c, "03  ·  THE FUNDLE FINANCE OS")

    c.setFont("Noto-B", 34)
    c.setFillColor(TEXT)
    c.drawString(15 * mm, PH - 42 * mm, "One platform. Six modules.")
    c.drawString(15 * mm, PH - 54 * mm, "Zero leakage.")

    intro = (
        "Fundle Finance OS is a purpose-built marketplace reconciliation platform for "
        "finance and operations teams. Ingest raw marketplace reports, calculate expected "
        "settlement with configurable business rules, reconcile against actuals, and recover "
        "every rupee of leakage — with AI-powered financial intelligence on top."
    )
    draw_wrapped(c, intro, 15 * mm, PH - 68 * mm, 267 * mm, font="Noto", size=11, leading=17, color=MUTED)

    pillars = [
        ("INGEST",       "Parse Myntra sales &\nsettlement reports\nin < 60 seconds",  GOLD),
        ("MASTERS",      "No-code rule engine\nfor commissions, GT,\nreturn & fixed fees", CYAN),
        ("CALCULATE",    "Component-level fee\nexpectations, drill-\nthrough, audit-ready", GOLD),
        ("RECONCILE",    "Match actual vs\nexpected. Rank by\nimpact & ageing",         CYAN),
        ("RECOVER",      "Track each rupee of\nleakage to closure —\nwith audit trail", GOLD),
        ("AI INSIGHTS",  "LLM-authored briefs\non health, velocity\nand margin decay",  CYAN),
    ]
    cw, ch = 40 * mm, 42 * mm
    gap = 4 * mm
    sx0 = (PW - 6 * cw - 5 * gap) / 2
    sy = PH - 130 * mm
    for i, (t, body, col) in enumerate(pillars):
        x = sx0 + i * (cw + gap)
        c.setStrokeColor(DIV)
        c.setFillColor(CARD)
        c.roundRect(x, sy, cw, ch, 2, fill=1, stroke=1)
        # top accent
        c.setFillColor(col)
        c.rect(x, sy + ch - 1.2 * mm, cw, 1.2 * mm, fill=1, stroke=0)
        c.setFont("Mono", 9)
        c.setFillColor(col)
        c.drawString(x + 5 * mm, sy + ch - 8 * mm, t)
        c.setFont("Noto", 9)
        c.setFillColor(TEXT)
        for j, ln in enumerate(body.split("\n")):
            c.drawString(x + 5 * mm, sy + ch - 14 * mm - j * 4 * mm, ln)

    brand_footer(c, 4, label="The Solution")


def page_module(c, page_num, chapter, title, subtitle, shot, bullets, callout=None):
    fill_bg(c, DEEP)
    grid_overlay(c)
    chapter_label(c, chapter)

    c.setFont("Noto-B", 24)
    c.setFillColor(TEXT)
    c.drawString(15 * mm, PH - 40 * mm, title)
    c.setFont("Noto-I", 12)
    c.setFillColor(GOLD)
    c.drawString(15 * mm, PH - 48 * mm, subtitle)

    # left column bullets, right column screenshot
    text_x = 15 * mm
    text_w = 110 * mm
    y = PH - 60 * mm
    for head, body in bullets:
        c.setFont("Noto-B", 11)
        c.setFillColor(TEXT)
        c.drawString(text_x, y, head)
        y = draw_wrapped(c, body, text_x, y - 5 * mm, text_w, font="Noto", size=9.5, leading=13, color=MUTED)
        y -= 3 * mm

    # callout box
    if callout:
        c.setStrokeColor(GOLD)
        c.setFillColor(HexColor("#F0B4290F"))
        cy = 25 * mm
        ch = 22 * mm
        c.roundRect(text_x, cy, text_w, ch, 2, fill=1, stroke=1)
        c.setFont("Mono", 8)
        c.setFillColor(GOLD)
        c.drawString(text_x + 4 * mm, cy + ch - 5 * mm, "KEY CAPABILITY")
        c.setFont("Noto", 9)
        c.setFillColor(TEXT)
        draw_wrapped(c, callout, text_x + 4 * mm, cy + ch - 10 * mm, text_w - 8 * mm,
                     font="Noto", size=9, leading=12, color=TEXT)

    # screenshot on right — compute frame to match image aspect ratio
    shot_path = SHOTS / f"{shot}.png"
    im = Image.open(shot_path)
    img_ar = im.size[0] / im.size[1]  # 16:9 = 1.78 for our shots

    frame_x = 135 * mm
    frame_w = PW - frame_x - 15 * mm
    frame_h = frame_w / img_ar
    # keep within page height
    max_h = PH - 45 * mm
    if frame_h > max_h:
        frame_h = max_h
        frame_w = frame_h * img_ar
    frame_y = (PH - 25 * mm - frame_h) / 2 + 6 * mm
    # subtle shadow
    c.setFillColor(HexColor("#000000"))
    c.roundRect(frame_x + 1, frame_y - 1, frame_w, frame_h, 1.5, fill=1, stroke=0)
    c.drawImage(str(shot_path),
                frame_x, frame_y, width=frame_w, height=frame_h,
                preserveAspectRatio=False, mask=None)
    c.setStrokeColor(DIV)
    c.setLineWidth(0.4)
    c.roundRect(frame_x, frame_y, frame_w, frame_h, 1.5, fill=0, stroke=1)

    brand_footer(c, page_num, label=title)


def page_cta(c):
    fill_bg(c, DARK)
    grid_overlay(c)
    chapter_label(c, "07  ·  GET STARTED")

    c.setFont("Noto-B", 42)
    c.setFillColor(TEXT)
    c.drawCentredString(PW / 2, PH - 65 * mm, "Stop leaking.")
    c.setFillColor(GOLD)
    c.drawCentredString(PW / 2, PH - 80 * mm, "Start reconciling.")

    c.setFont("Noto", 13)
    c.setFillColor(MUTED)
    c.drawCentredString(PW / 2, PH - 96 * mm, "Book a 30-minute walkthrough. See your own numbers reconciled — live.")

    # WhatsApp CTA cards, clickable
    cards = [
        ("Abhinav Khanna", "+91 99105 30372", "https://wa.me/919910530372"),
        ("Anmol Berry",    "+91 98995 33604", "https://wa.me/919899533604"),
    ]
    cw = 105 * mm
    ch = 40 * mm
    gap = 10 * mm
    sx0 = (PW - 2 * cw - gap) / 2
    sy = 55 * mm
    for i, (name, phone, url) in enumerate(cards):
        x = sx0 + i * (cw + gap)
        c.setStrokeColor(GOLD)
        c.setFillColor(CARD)
        c.roundRect(x, sy, cw, ch, 2, fill=1, stroke=1)
        # WA circle
        cx = x + 12 * mm
        cy = sy + ch / 2
        c.setFillColor(HexColor("#25D366"))
        c.circle(cx, cy, 7 * mm, fill=1, stroke=0)
        c.setFont("Noto-B", 12)
        c.setFillColor(white)
        c.drawCentredString(cx, cy - 1.4 * mm, "WA")

        c.setFont("Mono", 8)
        c.setFillColor(MUTED)
        c.drawString(x + 24 * mm, sy + ch - 9 * mm, "WHATSAPP")
        c.setFont("Noto-B", 15)
        c.setFillColor(TEXT)
        c.drawString(x + 24 * mm, sy + ch - 17 * mm, name)
        c.setFont("Mono", 12)
        c.setFillColor(GOLD)
        c.drawString(x + 24 * mm, sy + ch - 26 * mm, phone)
        c.setFont("Noto", 8)
        c.setFillColor(MUTED)
        c.drawString(x + 24 * mm, sy + ch - 33 * mm, "Tap card → open WhatsApp chat")

        # clickable full-card link
        c.linkURL(url, (x, sy, x + cw, sy + ch), relative=0, thickness=0)

    # Website line
    c.setFont("Noto-B", 20)
    c.setFillColor(TEXT)
    c.drawCentredString(PW / 2, 35 * mm, "fundle.ai")
    c.linkURL("https://fundle.ai", (PW / 2 - 25 * mm, 32 * mm, PW / 2 + 25 * mm, 40 * mm), relative=0, thickness=0)

    brand_footer(c, 8, label="Get in touch")


def main():
    c = canvas.Canvas(str(OUT), pagesize=PAGE)
    c.setTitle("Fundle Finance OS · Product Brochure")
    c.setAuthor("Fundle")
    c.setSubject("Marketplace Reconciliation Platform")

    page_cover(c);          c.showPage()
    page_problem(c);        c.showPage()
    page_why_broken(c);     c.showPage()
    page_solution(c);       c.showPage()

    page_module(c, 5,
        chapter="04  ·  INGEST & SALES LEDGER",
        title="Ingest & Canonicalise",
        subtitle="From raw Excel to a query-ready sales ledger.",
        shot="uploads",
        bullets=[
            ("Native Myntra parser",
             "Ingests raw sales and settlement Excel reports. Handles positive & negative NSV, returns, DTOs, RTOs, and internal cancellations natively."),
            ("Canonical sales ledger",
             "Normalises SKUs, categories, zones, sub-category levels. Every order line is now query-ready, filterable and drill-through."),
            ("Period-aware",
             "Month, quarter, YTD and annual views out of the box. No date-formula nightmares."),
        ],
        callout="21,614 order lines processed end-to-end in under 60 seconds — no VBA, no manual clean-up.",
    ); c.showPage()

    page_module(c, 6,
        chapter="05  ·  MASTERS  +  CALCULATIONS",
        title="Rule Engine + Fee Calculator",
        subtitle="Finance owns the logic. No engineers required.",
        shot="calculations",
        bullets=[
            ("No-code masters",
             "Commission slabs, GT logistics charges, fixed fees by ISP band, and zone-level return fees — all configurable through a spreadsheet-style editor."),
            ("Excel round-trip",
             "Import from your existing rule cards. Export for finance audit or legal review. Every version tracked."),
            ("Strict expected-fee math",
             "Commission on NSV - GT. Pre-GST + GST split. Level x Zone return fees. Order-type aware (Sales, Return, Return-DTO, RTO, Cancel)."),
        ],
        callout="No fallbacks. No dummy defaults. If a rule is missing, the row is flagged 'unmapped' with a precise reason — so ops can fix the master and rerun.",
    ); c.showPage()

    page_module(c, 7,
        chapter="06  ·  RECONCILE + RECOVER + AI",
        title="Discrepancies, Recovery & AI Insights",
        subtitle="Turn leakage into a workflow, not a wish.",
        shot="insights",
        bullets=[
            ("Reconciliation with tolerance",
             "Component-level match of actual vs expected. Configurable tolerances. Discrepancies ranked by financial impact, ageing and severity."),
            ("Recovery case management",
             "Each rupee of leakage becomes a tracked case — status, priority, evidence attachments, notes, recovered amount, and full audit trail."),
            ("AI Financial Intelligence",
             "Fundle's LLM-powered engine reads your entire reconciliation dataset and generates plain-English briefs: health scores, return velocity alerts, category-level margin decay, and root-cause narratives."),
        ],
        callout="Frontier LLMs · plain-English CFO-ready narratives · category & zone drilldowns · monthly health scores.",
    ); c.showPage()

    page_cta(c);            c.showPage()

    c.save()
    size_kb = OUT.stat().st_size / 1024
    print(f"\n✅ PDF ready: {OUT}")
    print(f"   Size: {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
