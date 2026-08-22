"""Marketing router — password-gated /marketing gallery.

Endpoints:
  POST   /api/marketing/login             single-user auth (JWT)
  GET    /api/marketing/posts             list all generated posts
  POST   /api/marketing/posts             generate a new post from keywords
  GET    /api/marketing/posts/{id}/image  serve the PNG bytes
  DELETE /api/marketing/posts/{id}        remove a post

Auth: separate JWT scope (role='marketing') so it doesn't share the admin
session. Marketing user is seeded from env vars MARKETING_EMAIL /
MARKETING_PASSWORD at startup (see server.py).

Images: generated with Gemini Nano Banana (EMERGENT_LLM_KEY) and stored on
disk under /app/marketing_assets/gallery/. LinkedIn copy is drafted with
the same key. The Fundle dark-logo overlay pass runs after each generation
so branding stays pixel-perfect.
"""
import asyncio
import base64
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import bcrypt
import jwt
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from PIL import Image

from db import db

load_dotenv("/app/backend/.env")

# Playwright looks up browsers under $PLAYWRIGHT_BROWSERS_PATH; the container
# actually stores them at /pw-browsers but the env var isn't inherited by the
# supervisor-managed FastAPI process. Pin it here so the on-the-fly brochure
# renderer finds Chromium without requiring an env change.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")

router = APIRouter(prefix="/marketing", tags=["marketing"])

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

ASSETS_DIR = Path("/app/marketing_assets")
GALLERY_DIR = ASSETS_DIR / "gallery"
GALLERY_DIR.mkdir(parents=True, exist_ok=True)
FUNDLE_DARK = ASSETS_DIR / "logos" / "fundle_dark.png"
FUNDLE_REF = ASSETS_DIR / "logos" / "fundle.png"


# ---------- Auth ----------
def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _issue_token(email: str) -> str:
    payload = {
        "sub": email,
        "role": "marketing",
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def marketing_user(authorization: Optional[str] = None) -> str:
    return authorization  # unused stub, kept for backwards import compat


async def _verify_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    if data.get("role") != "marketing":
        raise HTTPException(403, "Marketing role required")
    return data["sub"]


async def require_marketing(authorization: str = None):
    return authorization  # unused stub


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
async def login(payload: LoginIn):
    doc = await db.marketing_users.find_one({"email": payload.email.lower()})
    if not doc:
        raise HTTPException(401, "Invalid credentials")
    if not bcrypt.checkpw(payload.password.encode(), doc["password_hash"].encode()):
        raise HTTPException(401, "Invalid credentials")
    return {"token": _issue_token(doc["email"]), "email": doc["email"]}


# ---------- Post schema ----------
class GenerateIn(BaseModel):
    title: str
    keywords: str                                # comma-separated, natural
    style: str = "infographic"                   # 'infographic' | 'screen_collage'
    tone: str = "founder"                        # 'founder' | 'punchy' | 'data'
    include_stats: bool = True


BRAND_SYSTEM = (
    "Enterprise SaaS infographic for LinkedIn (1024x1024). Deep navy #0B1E3B "
    "background, off-white #F5F1EA panels, coral #FF6B4A accent, mint #6BC7A0, "
    "gold #F1B24A. Bold sans-serif Nunito Sans style, tight letter-spacing, "
    "generous whitespace, thin borders, subtle shadows. No emojis, no faces."
)

LOGO_RULE = (
    "Include an off-white header bar across the top (~14% of height). Reserve "
    "the LEFT 28% of the header as CLEAN EMPTY off-white area — do NOT draw the "
    "Fundle logo or any text/icons there. The real Fundle logo PNG will be "
    "composited over it in post-processing. Put the title text in navy in the "
    "right 70% of the header."
)


def _mkt_prompt(payload: GenerateIn) -> str:
    style_hint = {
        "infographic": (
            "Build a clean infographic. Use one dominant motif — grid, hex diagram, "
            "flow, or big-stat cards — do not mix multiple motifs. All body content "
            "sits on off-white panels or pills."
        ),
        "screen_collage": (
            "Build a COLLAGE composition. Show three or four stylised product-screen "
            "cards (looking like SaaS app screens with faux tables, charts, KPI numbers) "
            "arranged at slight ~5-8 degree tilts, overlapping softly, on a navy "
            "backdrop with a soft coral glow behind them. The screens should suggest a "
            "reconciliation dashboard, a settlement table, and a Morning-Brief AI card. "
            "Do not include real user data — use placeholder rows like '₹1,24,300', "
            "'Myntra · APR-26', 'Variance +2.3%'. Overlay one bold headline pill on top."
        ),
    }.get(payload.style, "")
    kw = ", ".join([k.strip() for k in payload.keywords.split(",") if k.strip()])
    return (
        f"Create a LinkedIn infographic titled '{payload.title}'. "
        f"Keywords to weave into the visual and short copy on the image: {kw}. "
        f"{style_hint} "
        f"Product name on the image is 'Marketplace AutoPilot' (never 'Finance OS')."
    )


async def _generate_image(payload: GenerateIn, out_path: Path) -> None:
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "EMERGENT_LLM_KEY not configured")
    with FUNDLE_REF.open("rb") as f:
        ref_b64 = base64.b64encode(f.read()).decode("utf-8")

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"mkt-{uuid.uuid4()}",
        system_message="You are a senior brand designer for a marketplace-finance SaaS.",
    )
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(
        modalities=["image", "text"]
    )
    prompt = "\n\n".join([_mkt_prompt(payload), LOGO_RULE, BRAND_SYSTEM])
    msg = UserMessage(text=prompt, file_contents=[ImageContent(ref_b64)])
    _, images = await chat.send_message_multimodal_response(msg)
    if not images:
        raise HTTPException(502, "Nano Banana returned no image")
    out_path.write_bytes(base64.b64decode(images[0]["data"]))
    _overlay_dark_logo(out_path)


def _overlay_dark_logo(img_path: Path) -> None:
    img = Image.open(img_path).convert("RGBA")
    W, H = img.size
    dark = Image.open(FUNDLE_DARK).convert("RGBA")
    bbox = dark.getbbox()
    if bbox:
        dark = dark.crop(bbox)
    # Header pill is ~14% of height. Give the logo comfortable left padding
    # (5%) so the 'f' doesn't get clipped by the pill's rounded corner.
    header_h = int(H * 0.14)
    logo_area = (int(W * 0.05), int(header_h * 0.20), int(W * 0.28), int(header_h * 0.80))
    x1, y1, x2, y2 = logo_area
    aw, ah = x2 - x1, y2 - y1
    scale = min(aw / dark.width, ah / dark.height)
    lw, lh = int(dark.width * scale), int(dark.height * scale)
    logo = dark.resize((lw, lh), Image.LANCZOS)
    img.paste(logo, (x1, y1 + (ah - lh) // 2), logo)  # left-align inside area
    img.convert("RGB").save(img_path, "PNG", optimize=True)


async def _generate_copy(payload: GenerateIn) -> Dict[str, Any]:
    """LinkedIn post copy: hook + body + hashtags."""
    if not EMERGENT_LLM_KEY:
        return {
            "linkedin_text": f"{payload.title}\n\nMarketplace AutoPilot by Fundle.",
            "hashtags": ["#MarketplaceFinance", "#Fundle", "#Reconciliation"],
        }
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"mkt-copy-{uuid.uuid4()}",
        system_message=(
            "You write LinkedIn posts for enterprise SaaS. Voice: confident founder / "
            "product lead, calm, specific. Short paragraphs. Never generic. Never "
            "clickbait. Product name is 'Marketplace AutoPilot' (Fundle)."
        ),
    )
    chat.with_model("gemini", "gemini-3.6-flash").with_params(temperature=0.7)
    user_msg = (
        f"Draft a LinkedIn post based on the following brief.\n\n"
        f"Title on the infographic: {payload.title}\n"
        f"Keywords / talking points: {payload.keywords}\n"
        f"Tone: {payload.tone}\n\n"
        f"Rules:\n"
        f"- First line is a hook that survives LinkedIn truncation (~140 chars).\n"
        f"- 3–5 short paragraphs.\n"
        f"- End with a CTA to fundlezone.com.\n"
        f"- Then a separate line with 10–14 relevant hashtags, space-separated, all starting with #.\n"
        f"- Do NOT invent metrics we didn't provide. If unsure, keep it qualitative.\n"
        f"- Return exactly two sections separated by a line of three dashes '---':\n"
        f"  POST_BODY\n---\n#hashtag1 #hashtag2 ...\n"
    )
    resp = await chat.send_message(UserMessage(text=user_msg))
    text = (resp or "").strip()
    if "---" in text:
        body, tags = text.split("---", 1)
    else:
        body, tags = text, ""
    hashtags = [t for t in tags.split() if t.startswith("#")]
    return {"linkedin_text": body.strip(), "hashtags": hashtags}


# ---------- Endpoints ----------
from fastapi import Header


async def _auth(authorization: Optional[str] = Header(None)) -> str:
    return await _verify_token(authorization)


@router.get("/posts")
async def list_posts(_: str = Depends(_auth)):
    rows: List[Dict[str, Any]] = []
    async for d in db.marketing_posts.find({}, {"_id": 0}).sort("created_at", -1):
        rows.append(d)
    return {"total": len(rows), "items": rows}


@router.post("/posts")
async def create_post(payload: GenerateIn, _: str = Depends(_auth)):
    pid = str(uuid.uuid4())
    fname = f"{pid}.png"
    out = GALLERY_DIR / fname
    await _generate_image(payload, out)
    copy = await _generate_copy(payload)
    doc = {
        "id": pid,
        "title": payload.title,
        "keywords": payload.keywords,
        "style": payload.style,
        "tone": payload.tone,
        "linkedin_text": copy["linkedin_text"],
        "hashtags": copy["hashtags"],
        "image_file": fname,
        "created_at": _iso(),
    }
    await db.marketing_posts.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc


@router.get("/posts/{post_id}/image")
async def get_image(post_id: str, _: str = Depends(_auth)):
    doc = await db.marketing_posts.find_one({"id": post_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    path = GALLERY_DIR / doc["image_file"]
    if not path.exists():
        raise HTTPException(404, "Image missing on disk")
    return FileResponse(str(path), media_type="image/png")


@router.delete("/posts/{post_id}")
async def delete_post(post_id: str, _: str = Depends(_auth)):
    doc = await db.marketing_posts.find_one({"id": post_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    path = GALLERY_DIR / doc["image_file"]
    if path.exists():
        path.unlink()
    await db.marketing_posts.delete_one({"id": post_id})
    return {"ok": True}


@router.get("/brochure")
async def get_brochure():
    """Public download for the platform e-brochure (no auth — shareable with
    prospects). Returns the pre-built PDF; if the file is missing on disk it
    is built on the fly via Playwright."""
    pdf = ASSETS_DIR / "brochure.pdf"
    if not pdf.exists():
        try:
            from playwright.async_api import async_playwright  # local import; heavy
            html_path = ASSETS_DIR / "brochure.html"
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await (await browser.new_context()).new_page()
                await page.goto(f"file://{html_path.resolve()}", wait_until="networkidle")
                await page.pdf(
                    path=str(pdf),
                    format="A4",
                    print_background=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                )
                await browser.close()
        except Exception as e:
            raise HTTPException(503, f"Brochure build failed: {e}")
    if not pdf.exists():
        raise HTTPException(404, "Brochure missing")
    return FileResponse(
        str(pdf),
        media_type="application/pdf",
        filename="Fundle-Marketplace-AutoPilot-Brochure.pdf",
    )


# ---------- Seed helpers (called from server.py startup) ----------
async def seed_marketing_user() -> None:
    email = (os.environ.get("MARKETING_EMAIL") or "marketing@fundle.ai").lower()
    password = os.environ.get("MARKETING_PASSWORD") or "market123"
    existing = await db.marketing_users.find_one({"email": email})
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    if existing:
        await db.marketing_users.update_one(
            {"email": email},
            {"$set": {"password_hash": pw_hash, "updated_at": _iso()}},
        )
    else:
        await db.marketing_users.insert_one(
            {"email": email, "password_hash": pw_hash, "created_at": _iso()}
        )


async def seed_existing_infographics() -> None:
    """Ensure the 5 pre-built LinkedIn infographics are always available on
    disk AND in the DB. This runs on every startup and is idempotent:

    * If neither DB row nor disk file exists → create both.
    * If DB row exists but disk file is missing (e.g. fresh production
      container where the volume was wiped) → re-materialise the disk file
      under the existing image_file name so /image endpoints keep working.
    * If both exist → do nothing.
    """
    existing_by_title: Dict[str, Dict[str, Any]] = {
        d["title"]: d async for d in db.marketing_posts.find({}, {"_id": 0, "title": 1, "image_file": 1})
    }
    seeds = [
        (
            "01_platform_overview",
            "Marketplace AutoPilot — Reconcile Every Rupee, Every Marketplace",
            "hero, six marketplaces, expected charges, auto reconciliation, leakage, one-click recovery",
            "infographic",
        ),
        (
            "02_modules_inside",
            "Inside Marketplace AutoPilot — 8 Purpose-Built Modules",
            "uploads, calculations, sales ledger, reconciliation, discrepancies, recovery, reports, ai insights",
            "infographic",
        ),
        (
            "03_workflow",
            "From Excel to Recovered Rupees in 5 Steps",
            "upload, calculate, reconcile, flag, recover, workflow, cycle time",
            "infographic",
        ),
        (
            "04_multi_marketplace",
            "One Ledger. Six Marketplaces. Zero Excel Chaos.",
            "myntra, amazon, ajio, nykaa, tata cliq, flipkart, before after, normalized ledger",
            "infographic",
        ),
        (
            "05_benefits_roi",
            "What Marketplace AutoPilot Recovers For You",
            "95% auto-reconciled, 48h recovery, 6 marketplaces, zero excel, roi, cta",
            "infographic",
        ),
    ]
    for src_slug, title, keywords, style in seeds:
        src = ASSETS_DIR / f"{src_slug}.png"
        if not src.exists():
            continue
        existing = existing_by_title.get(title)
        if existing:
            # DB row already there — just ensure the image file is on disk.
            dst = GALLERY_DIR / existing["image_file"]
            if not dst.exists():
                dst.write_bytes(src.read_bytes())
            continue
        # New row: create both DB entry and disk file.
        pid = str(uuid.uuid4())
        fname = f"{pid}.png"
        dst = GALLERY_DIR / fname
        dst.write_bytes(src.read_bytes())
        doc = {
            "id": pid,
            "title": title,
            "keywords": keywords,
            "style": style,
            "tone": "founder",
            "linkedin_text": _seed_copy_for(src_slug, title),
            "hashtags": _seed_hashtags_for(src_slug),
            "image_file": fname,
            "created_at": _iso(),
        }
        await db.marketing_posts.insert_one(doc.copy())


def _seed_copy_for(slug: str, title: str) -> str:
    copy_by_slug = {
        "01_platform_overview": (
            "Marketplace finance shouldn't need a spreadsheet-army.\n\n"
            "Every marketplace hands you a different XLSX, different cutoff, "
            "different fee structure. We built Marketplace AutoPilot so finance "
            "teams can stop chasing rupees and start owning them.\n\n"
            "One platform. Six marketplaces. Every settlement reconciled against "
            "what you were supposed to be paid — not what you were paid.\n\n"
            "→ Book a walkthrough: fundlezone.com"
        ),
        "02_modules_inside": (
            "We didn't build another dashboard. We built the finance stack a "
            "marketplace seller actually needs — end to end.\n\n"
            "Uploads. Calculations. Sales Ledger. Reconciliation. Discrepancies. "
            "Recovery. Reports. AI Insights.\n\n"
            "Eight modules, one operating system. Monday morning suddenly looks "
            "different for the finance team.\n\n"
            "→ See it live: fundlezone.com"
        ),
        "03_workflow": (
            "From Excel to recovered rupees — in 5 steps.\n\n"
            "Upload → Calculate → Reconcile → Flag → Recover. That's the whole "
            "pitch. The rule engine computes what each order should have settled "
            "at, and the recovery pack exports straight to the marketplace claims "
            "format.\n\n"
            "Median cycle time? Minutes, not weeks.\n\n"
            "→ Talk to us: fundlezone.com"
        ),
        "04_multi_marketplace": (
            "One ledger. Six marketplaces. Zero Excel chaos.\n\n"
            "Ask any D2C finance lead the last time their marketplace numbers tied "
            "out to the settlement, on the first try, without a manual VLOOKUP. "
            "The answer was uncomfortable.\n\n"
            "Before Marketplace AutoPilot: 3 people, 4 days. After: 2 clicks, 2 "
            "minutes. Variance caught in real time.\n\n"
            "→ fundlezone.com"
        ),
        "05_benefits_roi": (
            "The finance team math for switching to Marketplace AutoPilot.\n\n"
            "95%+ of settlements auto-reconciled. Under 48 hours from upload to "
            "recovery pack. 6 marketplaces on day one. Zero lines of Excel formulas "
            "required, ever again.\n\n"
            "Marketplace leakage is a slow bleed — you don't feel the individual "
            "rupee, but at year-end it's a real number on a real P&L.\n\n"
            "→ Book a demo: fundlezone.com"
        ),
    }
    return copy_by_slug.get(slug, title)


def _seed_hashtags_for(slug: str) -> List[str]:
    common = ["#MarketplaceFinance", "#Reconciliation", "#Fundle", "#SaaS",
              "#IndianEcommerce", "#CFO", "#D2C", "#FinanceOps",
              "#MarketplaceAutoPilot", "#Myntra", "#Amazon", "#Flipkart"]
    return common
