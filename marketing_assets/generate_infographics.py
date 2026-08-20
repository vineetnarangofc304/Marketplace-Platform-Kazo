"""Fundle marketing infographics — v2 with the ACTUAL Fundle logo as a
Gemini Nano Banana reference image, and marketplace names rendered in each
brand's recognizable colour + typographic style.

Run: python /app/marketing_assets/generate_infographics.py
"""
import asyncio
import base64
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

load_dotenv("/app/backend/.env")

API_KEY = os.getenv("EMERGENT_LLM_KEY")
if not API_KEY:
    print("EMERGENT_LLM_KEY missing")
    sys.exit(1)

OUT_DIR = Path("/app/marketing_assets")
LOGO_PATH = OUT_DIR / "logos" / "fundle.png"

# Encode the Fundle logo once — Nano Banana treats it as the mandatory
# reference to preserve exactly.
with LOGO_PATH.open("rb") as f:
    FUNDLE_LOGO_B64 = base64.b64encode(f.read()).decode("utf-8")

BRAND_SYSTEM = (
    "Design language: enterprise SaaS infographic for LinkedIn (square 1024x1024). "
    "Deep navy #0B1E3B primary background, off-white #F5F1EA canvas panels, "
    "coral accent #FF6B4A, mint #6BC7A0 for positives, gold #F1B24A for highlights. "
    "Bold sans-serif typography (Nunito Sans style), tight letter-spacing, clear hierarchy, "
    "generous whitespace, thin 1px borders, subtle drop shadows, geometric line icons. "
    "No emojis, no photos, no faces. Premium Stripe / Linear feel."
)

FUNDLE_LOGO_RULE = (
    "MANDATORY: Leave the specified logo region as a clean solid navy #0B1E3B rectangle. "
    "Do NOT draw the Fundle logo, do NOT draw any text or graphic in the reserved logo area — "
    "we will composite the actual logo file over that area in post-processing. "
    "The attached image is only a colour/style reference for the rest of the composition. "
    "Reserved logo areas per prompt: "
    "01_platform_overview → top-left 320x140 px block; "
    "02_modules_inside → bottom-right 290x110 px block; "
    "03_workflow → top-left 400x210 px block; "
    "04_multi_marketplace → top-left 280x130 px block; "
    "05_benefits_roi → top-left 350x150 px block."
)

MARKETPLACE_STYLE = (
    "Where marketplace names appear (Myntra, Amazon, AJIO, Nykaa, Tata CLiQ, Flipkart), "
    "render each name as a clean brand-styled wordmark in its recognisable brand colour: "
    "  * Myntra — bold hot-pink wordmark 'myntra' with slight italic, on white pill. "
    "  * amazon — lowercase black wordmark 'amazon' with a small orange upward curved arrow "
    "underneath (Amazon smile), on white pill. "
    "  * AJIO — bold uppercase red-black 'AJIO' wordmark on white pill. "
    "  * Nykaa — bold pink italic 'Nykaa' wordmark on white pill. "
    "  * Tata CLiQ — 'Tata CLiQ' wordmark, purple, on white pill. "
    "  * Flipkart — 'Flipkart' wordmark in Flipkart blue, next to a small yellow shopping "
    "bag icon, on white pill. "
    "Do NOT use any copyrighted logo files — these are typographic representations."
)

POSTS = [
    {
        "slug": "01_platform_overview",
        "prompt": (
            "Hero infographic titled 'Fundle Finance OS — Marketplace Finance, Reconciled'. "
            "Header row: place the attached Fundle logo at the top-left of the title bar "
            "(preserve it exactly). Below the title, a large centered diagram: six "
            "marketplace pill-tiles arranged in a hexagon (Myntra top-left, amazon top, "
            "AJIO top-right, Nykaa bottom-right, Tata CLiQ bottom, Flipkart bottom-left), "
            "each pill flowing an arrow into a central navy diamond labelled 'Finance OS'. "
            "From the central diamond, four outbound arrows lead to four outcome badges on "
            "the right side: 'Expected Charges' (gold), 'Auto Reconciliation' (mint), "
            "'Leakage Detected' (coral), 'One-Click Recovery' (gold). "
            "Bottom strip has three stat pills on off-white: '6 marketplaces live', "
            "'21,000+ orders reconciled', '<1% unmapped'. "
            "Do NOT put the Fundle logo in the centre — only in the top-left header."
        ),
    },
    {
        "slug": "02_modules_inside",
        "prompt": (
            "Grid infographic titled 'Inside Fundle — 8 Purpose-Built Modules'. "
            "Place the attached Fundle logo at the bottom-right sign-off spot on an "
            "off-white pill (preserve exactly). Body: a 4x2 grid of eight module cards on "
            "off-white with thin coral borders. Each card has a single thin-stroke line icon "
            "in coral, a bold module name, and a one-line description: "
            "Uploads — 'Drop XLSX, we auto-map columns'; "
            "Calculations — 'Rule-based expected charges'; "
            "Sales Ledger — '31-column drillable ledger'; "
            "Reconciliation — 'Match settlement vs expected'; "
            "Discrepancies — 'Every rupee of variance surfaced'; "
            "Recovery — 'Track claims to closure'; "
            "Reports — 'One-click monthly Excel export'; "
            "AI Insights — 'Morning Brief for CFOs'. "
            "No marketplace tiles in this one — modules only."
        ),
    },
    {
        "slug": "03_workflow",
        "prompt": (
            "Horizontal workflow diagram titled 'From Excel to Recovered Rupees in 5 Steps'. "
            "Place the attached Fundle logo in the top-left header (preserve exactly). "
            "Subtitle in mint: 'Median cycle time: minutes, not weeks'. "
            "Below the header: five large numbered pill nodes (1..5) in a left-to-right flow, "
            "connected by thick coral arrows. Each pill contains a thin-stroke icon and a bold "
            "label: 1 Upload (cloud arrow-up), 2 Calculate (calculator), 3 Reconcile (two arrows "
            "meeting), 4 Flag (magnifying glass over ₹ symbol), 5 Recover (checkmark shield). "
            "Underneath each pill a tiny caption in muted gold: 'Drop XLSX', 'Rule engine', "
            "'Match rows', 'Score variance', 'Close claims'. "
            "No marketplace tiles."
        ),
    },
    {
        "slug": "04_multi_marketplace",
        "prompt": (
            "Split-composition infographic titled 'One Ledger. Six Marketplaces. Zero Excel "
            "Chaos.'. Place the attached Fundle logo in the top-left of the title bar "
            "(preserve exactly). "
            "Left half: a semicircle radiating out from a central navy circle labelled 'Finance "
            "OS'. Six marketplace name-pills arranged around the semicircle in brand style — "
            "Myntra (hot pink), amazon (with orange smile), AJIO (red-black), Nykaa (pink italic), "
            "Tata CLiQ (purple), Flipkart (blue with yellow bag). Do NOT place the Fundle logo "
            "in this centre circle — the centre must say 'Finance OS' text only. "
            "Right half: a Before-vs-After comparison card with two columns: "
            "Before column (muted grey ✕ marks): '6 different XLSX formats', '3 people, 4 days', "
            "'commission errors caught monthly (maybe)'. "
            "After column (coral ✓ marks): 'One normalised ledger', '2 clicks, 2 minutes', "
            "'variance caught in real time'."
        ),
    },
    {
        "slug": "05_benefits_roi",
        "prompt": (
            "Bold ROI stats infographic titled 'What Fundle Recovers For You'. "
            "Place the attached Fundle logo in the top-left header (preserve exactly, keep its "
            "original colours). Below the header, a 2x2 grid of four large stat cards on "
            "off-white with thin borders. Each card has a HUGE coral number, a caption below, "
            "and a small line icon in the corner: "
            "Card 1 — '95%+' 'of settlements auto-reconciled' (target icon)  "
            "Card 2 — '<48h' 'from upload to recovery pack' (clock icon)  "
            "Card 3 — '6' 'marketplaces on day one' (globe icon)  "
            "Card 4 — '0' 'lines of Excel formulas required' (spreadsheet with slash icon). "
            "Bottom of the composition: a full-width coral CTA strip 'Book a demo → "
            "fundlezone.com' in bold off-white type. "
            "No marketplace tiles."
        ),
    },
]


async def generate_one(post: dict) -> None:
    slug = post["slug"]
    out = OUT_DIR / f"{slug}.png"
    chat = LlmChat(
        api_key=API_KEY,
        session_id=f"fundle-marketing-v2-{slug}",
        system_message="You are a senior brand designer producing enterprise SaaS marketing infographics. Follow logo preservation rules precisely.",
    )
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])

    full_prompt = "\n\n".join([
        post["prompt"],
        FUNDLE_LOGO_RULE,
        MARKETPLACE_STYLE,
        BRAND_SYSTEM,
    ])
    msg = UserMessage(
        text=full_prompt,
        file_contents=[ImageContent(FUNDLE_LOGO_B64)],
    )
    print(f"[gen ] {slug} ...")
    text, images = await chat.send_message_multimodal_response(msg)
    if not images:
        print(f"[fail] {slug}: no image — {(text or '')[:120]}")
        return
    image_bytes = base64.b64decode(images[0]["data"])
    out.write_bytes(image_bytes)
    print(f"[ok  ] {slug} → {out} ({len(image_bytes) // 1024} KB)")


async def main() -> None:
    for post in POSTS:
        await generate_one(post)
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
