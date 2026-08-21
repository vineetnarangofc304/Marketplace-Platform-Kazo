"""Fundle marketing infographics — v3.

Rebrand: platform name is now "Marketplace AutoPilot" (was "Finance OS").
Logo: Fundle stays as company mark; product name = "Marketplace AutoPilot".

Pipeline
--------
1. Ask Nano Banana to render each infographic AND include an OFF-WHITE
   header pill at the top-left that already contains a placeholder text
   "___LOGO___" (Nano Banana renders the pill; we cover the placeholder
   text with the real Fundle logo).
2. PIL post-pass composites the *dark* Fundle logo variant onto that pill
   so it reads cleanly on the off-white background.

Run: python /app/marketing_assets/generate_infographics.py
"""
import asyncio
import base64
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from PIL import Image, ImageDraw

load_dotenv("/app/backend/.env")

API_KEY = os.getenv("EMERGENT_LLM_KEY")
if not API_KEY:
    print("EMERGENT_LLM_KEY missing")
    sys.exit(1)

OUT_DIR = Path("/app/marketing_assets")
FUNDLE_DARK = OUT_DIR / "logos" / "fundle_dark.png"
FUNDLE_REF = OUT_DIR / "logos" / "fundle.png"

with FUNDLE_REF.open("rb") as f:
    FUNDLE_REF_B64 = base64.b64encode(f.read()).decode("utf-8")

BRAND_SYSTEM = (
    "Enterprise SaaS infographic for LinkedIn (1024x1024 square). "
    "Deep navy #0B1E3B primary background, off-white #F5F1EA header/panels, "
    "coral #FF6B4A accent, mint #6BC7A0 for positives, gold #F1B24A highlights. "
    "Bold sans-serif typography (Nunito Sans style), tight letter-spacing, generous "
    "whitespace, thin 1px borders, subtle drop shadows. No emojis, no photos, no faces."
)

LOGO_RULE = (
    "Every image MUST start with a horizontal OFF-WHITE header bar across the top "
    "(~14% of the height). Inside the header bar, reserve the LEFT 30% as a clean "
    "empty off-white area — do NOT draw the Fundle logo, do NOT draw any text or "
    "icons there. The real Fundle logo PNG will be composited over that reserved "
    "area in post-processing. The RIGHT 70% of the header bar carries the title "
    "text in navy #0B1E3B."
)

MARKETPLACE_STYLE = (
    "Marketplace names appear as brand-style wordmark pills on white backgrounds: "
    "amazon (lowercase black with orange smile arc below), Myntra (hot-pink bold italic), "
    "AJIO (red-black bold uppercase), Nykaa (pink script italic), Tata CLiQ (deep purple), "
    "Flipkart (blue wordmark next to a small yellow shopping bag)."
)

POSTS = [
    {
        "slug": "01_platform_overview",
        "title_text": "Marketplace AutoPilot — Reconcile Every Rupee, Every Marketplace.",
        "prompt": (
            "Hero infographic. Title bar reads 'Marketplace AutoPilot — Reconcile Every "
            "Rupee, Every Marketplace.' Below the header, a large centred diagram: six "
            "marketplace pill-tiles arranged in a hexagon around a central navy diamond "
            "labelled 'Marketplace AutoPilot' (two lines). Order top-to-bottom clockwise: "
            "amazon top, AJIO top-right, Nykaa bottom-right, Tata CLiQ bottom, Flipkart "
            "bottom-left, Myntra top-left. Arrows from each pill flow into the diamond. "
            "Four outbound arrows from the diamond lead to outcome badges on the right: "
            "'Expected Charges' (gold), 'Auto Reconciliation' (mint), 'Leakage Detected' "
            "(coral), 'One-Click Recovery' (gold). "
            "Bottom strip on off-white: three stat pills — '6 marketplaces live', "
            "'21,000+ orders reconciled', '<1% unmapped'."
        ),
    },
    {
        "slug": "02_modules_inside",
        "title_text": "Inside Marketplace AutoPilot — 8 Purpose-Built Modules.",
        "prompt": (
            "Grid infographic. Title bar reads 'Inside Marketplace AutoPilot — 8 "
            "Purpose-Built Modules.' Body: a 4x2 grid of eight module cards on off-white "
            "with thin coral borders. Each card: single thin-stroke line icon in coral, "
            "bold module name, one-line description: "
            "Uploads — 'Drop XLSX, we auto-map columns'; "
            "Calculations — 'Rule-based expected charges'; "
            "Sales Ledger — '31-column drillable ledger'; "
            "Reconciliation — 'Match settlement vs expected'; "
            "Discrepancies — 'Every rupee of variance surfaced'; "
            "Recovery — 'Track claims to closure'; "
            "Reports — 'One-click monthly Excel export'; "
            "AI Insights — 'Morning Brief for CFOs'. "
            "No marketplace tiles."
        ),
    },
    {
        "slug": "03_workflow",
        "title_text": "From Excel to Recovered Rupees in 5 Steps.",
        "prompt": (
            "Horizontal workflow diagram. Title bar reads 'From Excel to Recovered Rupees "
            "in 5 Steps.' Sub-caption in mint below the title: 'Median cycle time: minutes, "
            "not weeks.' Body: five large numbered pill nodes (1..5) in a left-to-right "
            "flow on off-white, connected by thick coral arrows. Each pill contains a "
            "thin-stroke icon and a bold label: 1 Upload (cloud arrow-up), 2 Calculate "
            "(calculator), 3 Reconcile (two arrows meeting), 4 Flag (magnifying glass over "
            "₹ symbol), 5 Recover (checkmark shield). Below each pill a tiny gold caption: "
            "'Drop XLSX', 'Rule engine', 'Match rows', 'Score variance', 'Close claims'. "
            "No marketplace tiles."
        ),
    },
    {
        "slug": "04_multi_marketplace",
        "title_text": "One Ledger. Six Marketplaces. Zero Excel Chaos.",
        "prompt": (
            "Split-composition infographic. Title bar reads 'One Ledger. Six Marketplaces. "
            "Zero Excel Chaos.' "
            "Left half: a semicircle radiating out from a central navy circle labelled "
            "'Marketplace AutoPilot' (two lines, centred). Six marketplace name-pills "
            "arranged around the semicircle in brand style — Myntra, amazon, AJIO, Nykaa, "
            "Tata CLiQ, Flipkart. "
            "Right half: a Before-vs-After comparison card in off-white with two columns: "
            "Before column with muted grey X marks: '6 different XLSX formats', "
            "'3 people, 4 days', 'commission errors caught monthly (maybe)'. "
            "After column with coral tick marks: 'One normalised ledger', "
            "'2 clicks, 2 minutes', 'variance caught in real time'."
        ),
    },
    {
        "slug": "05_benefits_roi",
        "title_text": "What Marketplace AutoPilot Recovers For You.",
        "prompt": (
            "Bold ROI stats infographic. Title bar reads 'What Marketplace AutoPilot "
            "Recovers For You.' Body: a 2x2 grid of four large stat cards on off-white "
            "with thin borders. Each card: HUGE coral number, caption below, small line "
            "icon in the corner. "
            "Card 1 — '95%+' 'of settlements auto-reconciled' (target icon). "
            "Card 2 — '<48h' 'from upload to recovery pack' (clock icon). "
            "Card 3 — '6' 'marketplaces on day one' (globe icon). "
            "Card 4 — '0' 'lines of Excel formulas required' (spreadsheet with slash icon). "
            "Below the grid a full-width coral CTA strip: 'Book a demo → fundlezone.com'. "
            "No marketplace tiles."
        ),
    },
]


async def render_one(post: dict) -> Path:
    slug = post["slug"]
    out = OUT_DIR / f"{slug}.png"
    chat = LlmChat(
        api_key=API_KEY,
        session_id=f"fundle-mkt-v3-{slug}",
        system_message="You are a senior brand designer for a marketplace-finance SaaS.",
    )
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(
        modalities=["image", "text"]
    )
    prompt = "\n\n".join([post["prompt"], LOGO_RULE, MARKETPLACE_STYLE, BRAND_SYSTEM])
    msg = UserMessage(text=prompt, file_contents=[ImageContent(FUNDLE_REF_B64)])
    print(f"[gen ] {slug}")
    _, images = await chat.send_message_multimodal_response(msg)
    if not images:
        raise RuntimeError(f"no image for {slug}")
    out.write_bytes(base64.b64decode(images[0]["data"]))
    return out


def overlay_dark_logo(img_path: Path) -> None:
    """Paste the dark Fundle logo onto the top-left header pill."""
    img = Image.open(img_path).convert("RGBA")
    W, H = img.size
    dark = Image.open(FUNDLE_DARK).convert("RGBA")
    bbox = dark.getbbox()
    if bbox:
        dark = dark.crop(bbox)

    # Header pill occupies top ~14% of height. Left-align with 5% left padding
    # so the leading 'f' isn't clipped by the rounded corner.
    header_h = int(H * 0.14)
    logo_area = (int(W * 0.05), int(header_h * 0.20), int(W * 0.28), int(header_h * 0.80))
    x1, y1, x2, y2 = logo_area
    aw, ah = x2 - x1, y2 - y1
    scale = min(aw / dark.width, ah / dark.height)
    lw, lh = int(dark.width * scale), int(dark.height * scale)
    logo = dark.resize((lw, lh), Image.LANCZOS)
    px = x1
    py = y1 + (ah - lh) // 2
    img.paste(logo, (px, py), logo)
    img.convert("RGB").save(img_path, "PNG", optimize=True)


async def main() -> None:
    for post in POSTS:
        try:
            path = await render_one(post)
            overlay_dark_logo(path)
            print(f"[ok  ] {post['slug']} → {path}")
        except Exception as e:
            print(f"[fail] {post['slug']}: {e}")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
