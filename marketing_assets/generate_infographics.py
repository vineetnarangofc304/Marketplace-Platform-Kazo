"""One-off Fundle marketing asset generator — 5 LinkedIn infographics.

Uses Gemini Nano Banana (gemini-3.1-flash-image-preview) via the Emergent
LLM key. Run: `python /app/marketing_assets/generate_infographics.py`.
"""
import asyncio
import base64
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage

load_dotenv("/app/backend/.env")

API_KEY = os.getenv("EMERGENT_LLM_KEY")
if not API_KEY:
    print("EMERGENT_LLM_KEY missing from /app/backend/.env")
    sys.exit(1)

OUT_DIR = Path("/app/marketing_assets")
OUT_DIR.mkdir(exist_ok=True)

# Consistent brand system for every image
BRAND = (
    "Design language: enterprise SaaS infographic for LinkedIn (1200x1200 square, safe margins). "
    "Fundle brand palette — deep navy #0B1E3B primary background, off-white #F5F1EA canvas panels, "
    "vibrant coral accent #FF6B4A, mint green #6BC7A0 for positive metrics, warm gold #F1B24A for highlights. "
    "Typography — bold sans-serif (Nunito Sans style), tight letter-spacing, clear hierarchy. "
    "Style — flat vector, subtle drop shadows, thin 1px borders, generous whitespace, "
    "high-contrast readable numbers, clean geometric icons (no emojis, no photos, no faces). "
    "Include the wordmark 'Powered by Fundle' in the bottom-right in muted gold. "
    "The composition should feel like a Stripe / Notion / Linear marketing card — premium, minimal, confident."
)

POSTS = [
    {
        "slug": "01_platform_overview",
        "title": "Fundle Finance OS at a Glance",
        "prompt": (
            "Hero infographic titled 'Fundle Finance OS — Marketplace Finance, Reconciled'. "
            "Layout: bold headline at top, a large centered hex-shaped diagram in the middle showing 6 marketplace "
            "logos-as-tiles (Myntra, Amazon, AJIO, Nykaa, Tata Cliq, Flipkart) flowing into a single 'Fundle' core "
            "node, which then splits into 4 outcome badges labeled 'Expected Charges', 'Auto Reconciliation', "
            "'Leakage Detected', 'One-Click Recovery'. Bottom strip shows 3 stat pills: '6 marketplaces live', "
            "'21,000+ orders reconciled', '<1% unmapped'. No stock photos, no faces."
        ),
    },
    {
        "slug": "02_modules_inside",
        "title": "Inside the Platform — 8 Modules Every Finance Team Needs",
        "prompt": (
            "Grid infographic titled 'Inside Fundle — 8 Purpose-Built Modules'. "
            "Show a clean 4x2 grid of module cards, each card contains a single vector icon, a module name and one line: "
            "1) Uploads — 'Drop XLSX, we auto-map columns'  "
            "2) Calculations — 'Rule-based expected charges'  "
            "3) Sales Ledger — '31-column drillable ledger'  "
            "4) Reconciliation — 'Match settlement vs expected'  "
            "5) Discrepancies — 'Every rupee of variance surfaced'  "
            "6) Recovery — 'Track claims to closure'  "
            "7) Reports — 'One-click monthly Excel export'  "
            "8) AI Insights — 'Morning Brief for CFOs'. "
            "Consistent icon style throughout — thin-stroke line icons in coral, on white cards, over the navy background."
        ),
    },
    {
        "slug": "03_workflow",
        "title": "The Workflow — From Upload to Recovery",
        "prompt": (
            "Horizontal workflow diagram titled 'From Excel to Recovered Rupees in 5 Steps'. "
            "Left-to-right flow with 5 large numbered pill nodes connected by arrows, each pill has an icon and label: "
            "Step 1 'Upload' (cloud arrow-up), Step 2 'Calculate' (calculator), Step 3 'Reconcile' (two arrows meeting), "
            "Step 4 'Flag Discrepancies' (magnifying glass on rupee), Step 5 'Recover' (checkmark shield). "
            "Below each node a tiny caption: 'Drop XLSX', 'Rule engine', 'Match rows', 'Score variance', 'Close claims'. "
            "Above the flow show a single stat: 'Median cycle time: minutes, not weeks'. Coral arrows on navy."
        ),
    },
    {
        "slug": "04_multi_marketplace",
        "title": "One Platform — Six Marketplaces",
        "prompt": (
            "Infographic titled 'One Ledger. Six Marketplaces. Zero Excel Chaos.'. "
            "Left half — a semicircle radiating from a central 'Fundle' badge, with 6 marketplace name tiles arranged "
            "around it: Myntra, Amazon, AJIO, Nykaa, Tata Cliq, Flipkart. Each tile is a rounded rectangle in off-white "
            "with the marketplace name typeset (no marketplace logos — just typography). "
            "Right half — a comparison card titled 'Before vs After' with two columns: "
            "Before — '6 different XLSX formats', '3 people, 4 days', 'commission errors caught monthly (maybe)'. "
            "After — 'One normalized ledger', '2 clicks, 2 minutes', 'variance caught in real time'. "
            "Use coral tick marks for the After column, muted grey crosses for Before."
        ),
    },
    {
        "slug": "05_benefits_roi",
        "title": "The Benefits — Why Finance Teams Switch",
        "prompt": (
            "Bold stats infographic titled 'What Fundle Recovers For You'. "
            "Show 4 large stat blocks in a 2x2 grid, each with a huge coral number, a short caption, and a mini icon: "
            "Block 1 — '95%+' 'of settlements auto-reconciled' (target icon)  "
            "Block 2 — '<48h' 'from upload to recovery pack' (clock icon)  "
            "Block 3 — '6' 'marketplaces on day one' (globe icon)  "
            "Block 4 — '0' 'lines of Excel formulas required' (spreadsheet crossed out). "
            "Below the grid a single call-to-action strip in coral: 'Book a demo → fundlezone.com'. "
            "Premium enterprise SaaS visual language."
        ),
    },
]


async def generate_one(post: dict) -> None:
    slug = post["slug"]
    out = OUT_DIR / f"{slug}.png"
    if out.exists():
        print(f"[skip] {out.name} already exists")
        return

    chat = LlmChat(
        api_key=API_KEY,
        session_id=f"fundle-marketing-{slug}",
        system_message="You are a senior brand designer producing enterprise SaaS marketing infographics.",
    )
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])

    full_prompt = f"{post['prompt']}\n\n{BRAND}"
    msg = UserMessage(text=full_prompt)
    print(f"[gen ] {slug} ...")
    text, images = await chat.send_message_multimodal_response(msg)
    if not images:
        print(f"[fail] {slug}: no image returned — response preview: {(text or '')[:120]}")
        return
    img = images[0]
    image_bytes = base64.b64decode(img["data"])
    out.write_bytes(image_bytes)
    print(f"[ok  ] {slug} → {out} ({len(image_bytes) // 1024} KB)")


async def main() -> None:
    for post in POSTS:
        await generate_one(post)
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
