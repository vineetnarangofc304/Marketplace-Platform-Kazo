"""Build the 1920x1080 slides for each narration segment.
- Story slides: rendered from scratch with PIL (typography + brand accents)
- Product slides: overlay a title bar + Fundle watermark on real screenshots
"""
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path("/app/marketing")
SHOTS = ROOT / "screenshots"
OUT = ROOT / "slides"
OUT.mkdir(parents=True, exist_ok=True)
LOGO = Image.open(ROOT / "assets" / "fundle_logo_white.png").convert("RGBA")

W, H = 1920, 1080
BG_DARK = (11, 15, 23)          # #0B0F17 near-black navy
BG_DEEP = (7, 10, 15)
ACCENT = (240, 180, 41)         # warm gold - premium finance vibe
ACCENT_2 = (99, 179, 237)       # cool cyan
TEXT_MAIN = (245, 246, 250)
TEXT_MUTED = (150, 158, 175)
DIVIDER = (55, 62, 78)

# Fonts — Debian ships DejaVu; use as fallback
FONT_PATHS = {
    "bold": "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "reg":  "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "mono": "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "italic": "/usr/share/fonts/truetype/noto/NotoSans-Italic.ttf",
}


def F(kind, size):
    return ImageFont.truetype(FONT_PATHS[kind], size)


def wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def paste_logo(img, x, y, height=48):
    scale = height / LOGO.size[1]
    new_w = int(LOGO.size[0] * scale)
    lg = LOGO.resize((new_w, height), Image.LANCZOS)
    img.alpha_composite(lg, (x, y))


def base_dark():
    img = Image.new("RGBA", (W, H), BG_DEEP + (255,))
    d = ImageDraw.Draw(img)
    # radial-ish gradient using overlaid ellipses — no grid overlay
    grad = Image.new("RGBA", (W, H), BG_DEEP + (255,))
    gd = ImageDraw.Draw(grad)
    for r, a in [(1600, 22), (1200, 30), (700, 42), (350, 55)]:
        gd.ellipse((W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r), fill=(30, 44, 78, a))
    grad = grad.filter(ImageFilter.GaussianBlur(90))
    img = Image.alpha_composite(img, grad)
    # subtle diagonal noise/scan lines (very low alpha)
    lines = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    for gy in range(0, H, 3):
        ld.line([(0, gy), (W, gy)], fill=(255, 255, 255, 3), width=1)
    lines = lines.filter(ImageFilter.GaussianBlur(0.5))
    img = Image.alpha_composite(img, lines)
    return img


def brand_footer(img, overline="Fundle Finance OS"):
    d = ImageDraw.Draw(img)
    d.line([(80, H - 100), (W - 80, H - 100)], fill=DIVIDER, width=1)
    paste_logo(img, 80, H - 78, height=40)
    d.text((W - 80, H - 62), "fundle.ai", font=F("mono", 22), fill=TEXT_MUTED, anchor="rm")


def slide_intro_problem(text):
    img = base_dark()
    d = ImageDraw.Draw(img)
    # eyebrow
    d.text((160, 220), "THE SILENT LEAKAGE PROBLEM", font=F("mono", 24), fill=ACCENT)
    d.line([(160, 264), (500, 264)], fill=ACCENT, width=2)
    # Big headline — crisper
    d.text((160, 320), "3% to 7%", font=F("bold", 168), fill=TEXT_MAIN)
    d.text((160, 490), "of your marketplace", font=F("reg", 54), fill=TEXT_MUTED)
    d.text((160, 555), "revenue is leaking.", font=F("bold", 62), fill=TEXT_MAIN)
    d.text((160, 660), "Miscalculated commissions.  Unbilled returns.", font=F("reg", 26), fill=TEXT_MUTED)
    d.text((160, 700), "Misapplied logistics.  Every month. Every marketplace.", font=F("italic", 26), fill=TEXT_MUTED)

    # Right column - 2 dominant stats
    sx = 1230
    # ₹7 Cr
    d.rectangle([(sx, 340), (sx + 560, 500)], outline=ACCENT, width=1)
    d.text((sx + 30, 355), "₹ 7 Cr", font=F("bold", 84), fill=ACCENT)
    d.text((sx + 30, 458), "Est. annual leakage on a", font=F("reg", 20), fill=TEXT_MUTED)
    d.text((sx + 30, 480), "₹100 Cr D2C business", font=F("reg", 20), fill=TEXT_MUTED)
    # < 60 sec
    d.rectangle([(sx, 530), (sx + 560, 690)], outline=ACCENT_2, width=1)
    d.text((sx + 30, 545), "< 60 sec", font=F("bold", 84), fill=ACCENT_2)
    d.text((sx + 30, 648), "Fundle parses your full", font=F("reg", 20), fill=TEXT_MUTED)
    d.text((sx + 30, 670), "monthly report end-to-end", font=F("reg", 20), fill=TEXT_MUTED)

    brand_footer(img)
    return img


def slide_why_hard():
    img = base_dark()
    d = ImageDraw.Draw(img)
    d.text((160, 220), "WHY RECONCILIATION IS BROKEN", font=F("mono", 24), fill=ACCENT_2)
    d.line([(160, 262), (600, 262)], fill=ACCENT_2, width=2)
    d.text((160, 310), "The settlement", font=F("bold", 100), fill=TEXT_MAIN)
    d.text((160, 420), "statement is not", font=F("bold", 100), fill=TEXT_MAIN)
    d.text((160, 530), "a bill.", font=F("bold", 100), fill=ACCENT)
    d.text((160, 660), "It's a 40-column data dump — with dozens of fee components,", font=F("reg", 32), fill=TEXT_MUTED)
    d.text((160, 704), "changing commission slabs, zone-based logistics, and quarterly rate cards.", font=F("reg", 32), fill=TEXT_MUTED)
    d.text((160, 760), "Excel breaks. Finance teams give up. Leakage becomes the cost of doing business.", font=F("italic", 28), fill=TEXT_MUTED)
    brand_footer(img)
    return img


def slide_solution():
    img = base_dark()
    d = ImageDraw.Draw(img)
    # centre logo big
    scale = 180 / LOGO.size[1]
    new_w = int(LOGO.size[0] * scale)
    lg = LOGO.resize((new_w, 180), Image.LANCZOS)
    img.alpha_composite(lg, ((W - new_w) // 2, 300))
    d.text((W // 2, 520), "Finance OS", font=F("bold", 92), fill=TEXT_MAIN, anchor="mm")
    d.text((W // 2, 610), "Marketplace Reconciliation. Reimagined.", font=F("italic", 38), fill=ACCENT, anchor="mm")
    # 4 pillars
    labels = ["INGEST", "CALCULATE", "RECONCILE", "RECOVER"]
    px = 240
    py = 780
    step = (W - 480) // (len(labels) - 1)
    for i, lb in enumerate(labels):
        x = px + i * step
        d.ellipse((x - 12, py - 12, x + 12, py + 12), fill=ACCENT)
        d.text((x, py + 44), lb, font=F("mono", 22), fill=TEXT_MAIN, anchor="mm")
        if i < len(labels) - 1:
            d.line([(x + 20, py), (x + step - 20, py)], fill=DIVIDER, width=2)
    brand_footer(img)
    return img


def slide_cta():
    img = base_dark()
    d = ImageDraw.Draw(img)
    d.text((W // 2, 220), "RECLAIM WHAT IS YOURS", font=F("mono", 28), fill=ACCENT, anchor="mm")
    d.text((W // 2, 320), "Stop leaking.", font=F("bold", 108), fill=TEXT_MAIN, anchor="mm")
    d.text((W // 2, 440), "Start reconciling.", font=F("bold", 108), fill=ACCENT, anchor="mm")

    d.text((W // 2, 600), "fundle.ai", font=F("bold", 72), fill=TEXT_MAIN, anchor="mm")

    # Two WhatsApp contact cards
    cards = [
        ("Abhinav Khanna", "+91 99105 30372", "https://wa.me/919910530372"),
        ("Anmol Berry",    "+91 98995 33604", "https://wa.me/919899533604"),
    ]
    cw = 520
    ch = 180
    gap = 60
    total_w = cw * 2 + gap
    sx = (W - total_w) // 2
    sy = 720
    for i, (name, phone, _url) in enumerate(cards):
        x = sx + i * (cw + gap)
        d.rectangle([(x, sy), (x + cw, sy + ch)], outline=ACCENT, width=2)
        # WhatsApp icon (simple circle + phone-glyph via unicode fallback text)
        d.ellipse((x + 30, sy + 40, x + 110, sy + 120), fill=(37, 211, 102))
        d.text((x + 70, sy + 80), "WA", font=F("bold", 32), fill=(255, 255, 255), anchor="mm")
        d.text((x + 140, sy + 46), "WhatsApp", font=F("mono", 20), fill=TEXT_MUTED)
        d.text((x + 140, sy + 78), name, font=F("bold", 30), fill=TEXT_MAIN)
        d.text((x + 140, sy + 118), phone, font=F("mono", 26), fill=ACCENT)
    brand_footer(img)
    return img


def slide_product(screenshot_name, chapter, title, subtitle, callout=None):
    """Compose a screenshot into a branded card with title bar."""
    img = Image.new("RGBA", (W, H), BG_DEEP + (255,))
    d = ImageDraw.Draw(img)
    # Top chapter bar
    d.rectangle([(0, 0), (W, 96)], fill=(17, 22, 33, 255))
    d.text((80, 32), chapter, font=F("mono", 22), fill=ACCENT)
    d.text((80, 60), title, font=F("bold", 26), fill=TEXT_MAIN)
    paste_logo(img, W - 80 - 140, 26, height=42)
    d.text((W - 80, 74), "fundle.ai", font=F("mono", 18), fill=TEXT_MUTED, anchor="rm")

    # Insert screenshot centered, scaled to fit within 1760 x 880 area
    shot = Image.open(SHOTS / f"{screenshot_name}.png").convert("RGBA")

    # Mask out the sidebar "SIGNED IN" block that shows the login email
    # The sidebar bottom user block spans y=600..700 in a 1920x1080 shot
    if shot.size[0] >= 1900:
        m = ImageDraw.Draw(shot)
        m.rectangle([(0, 590), (224, 720)], fill=(248, 249, 250, 255))
        m.line([(0, 590), (224, 590)], fill=(225, 228, 232, 255), width=1)

    max_w, max_h = 1760, 880
    ratio = min(max_w / shot.size[0], max_h / shot.size[1])
    new_size = (int(shot.size[0] * ratio), int(shot.size[1] * ratio))
    shot_r = shot.resize(new_size, Image.LANCZOS)
    # subtle shadow
    shadow = Image.new("RGBA", (new_size[0] + 60, new_size[1] + 60), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rectangle([(30, 30), (30 + new_size[0], 30 + new_size[1])], fill=(0, 0, 0, 140))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    sx = (W - new_size[0]) // 2
    sy = 120
    img.alpha_composite(shadow, (sx - 30, sy - 20))
    img.alpha_composite(shot_r, (sx, sy))
    # thin border
    d = ImageDraw.Draw(img)
    d.rectangle([(sx, sy), (sx + new_size[0], sy + new_size[1])], outline=DIVIDER, width=1)

    # Bottom subtitle strip
    d.rectangle([(0, H - 96), (W, H)], fill=(17, 22, 33, 255))
    d.text((80, H - 56), subtitle, font=F("italic", 24), fill=TEXT_MUTED, anchor="lm")
    if callout:
        d.text((W - 80, H - 56), callout, font=F("mono", 22), fill=ACCENT, anchor="rm")
    return img


def save(img, name):
    p = OUT / f"{name}.png"
    img.convert("RGB").save(p, "PNG", optimize=True)
    print(f"  ✓ {name}.png")


def main():
    narr = json.loads((ROOT / "scripts" / "narration.json").read_text())

    product_map = {
        "03_ingest":   ("uploads",         "CHAPTER 03  ·  INGEST",         "Ingest & Canonical Sales Ledger",     "Sales, returns, DTOs, RTOs and cancellations — all normalised into one ledger.", "21,614 lines · < 60 sec"),
        "04_masters":  ("masters",         "CHAPTER 04  ·  MASTERS",        "No-Code Rule Engine",                  "Commission · GT logistics · fixed fees · zone-level return fees — you own the logic.", "Excel round-trip"),
        "05_calc":     ("calculations",    "CHAPTER 05  ·  CALCULATIONS",   "Expected Fee Engine",                  "Commission on NSV − GT. Pre-GST + GST split. Strict matching. No fallbacks.",     "Drill-through · audit-ready"),
        "06_recon":    ("reconciliation",  "CHAPTER 06  ·  RECONCILIATION", "Reconciliation Engine",                "Component-level match. Configurable tolerances. Ranked by financial impact.",     "Actual vs Expected"),
        "07_recovery": ("recovery",        "CHAPTER 07  ·  RECOVERY",       "Recovery Case Management",             "Status · priority · evidence · notes · recovered amount · full audit trail.",     "Nothing gets lost"),
        "08_ai":       ("insights",        "CHAPTER 08  ·  AI INSIGHTS",    "Financial Intelligence, on Autopilot", "Health scores · mapping · leakage · margin · recovery · morning briefs.",         "Powered by frontier LLMs"),
    }

    for seg in narr["segments"]:
        sid = seg["id"]
        if sid == "01_hook":
            save(slide_intro_problem(seg["text"]), sid)
        elif sid == "02_solution":
            save(slide_solution(), sid)
        elif sid == "09_cta":
            save(slide_cta(), sid)
        elif sid in product_map:
            shot, chap, title, sub, callout = product_map[sid]
            save(slide_product(shot, chap, title, sub, callout), sid)
        else:
            print(f"  ! unhandled segment {sid}")

    print(f"\nSlides in {OUT}")


if __name__ == "__main__":
    main()
