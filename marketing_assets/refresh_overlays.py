"""Re-apply the corrected Fundle logo overlay on all gallery images.
Paints an off-white patch over the entire top-left header logo zone first,
then places the fresh dark-variant logo. Idempotent when run repeatedly.
"""
from pathlib import Path
from PIL import Image, ImageDraw

BASE = Path("/app/marketing_assets")
GALLERY = BASE / "gallery"
DARK = BASE / "logos" / "fundle_dark.png"

OFFWHITE = (245, 241, 234, 255)


def redo_overlay(img_path: Path) -> None:
    img = Image.open(img_path).convert("RGBA")
    W, H = img.size

    # Wipe the entire top-left header logo zone with off-white so any prior
    # overlay is erased before we paste the new logo. Zone is tight — 26%
    # width, 14% height — so title text starting past ~26% width stays intact.
    wipe_box = (0, 0, int(W * 0.26), int(H * 0.14))
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle(wipe_box, fill=OFFWHITE)
    img = Image.alpha_composite(img, overlay)

    dark = Image.open(DARK).convert("RGBA")
    bbox = dark.getbbox()
    if bbox:
        dark = dark.crop(bbox)
    header_h = int(H * 0.14)
    logo_area = (int(W * 0.05), int(header_h * 0.20), int(W * 0.28), int(header_h * 0.80))
    x1, y1, x2, y2 = logo_area
    aw, ah = x2 - x1, y2 - y1
    scale = min(aw / dark.width, ah / dark.height)
    lw, lh = int(dark.width * scale), int(dark.height * scale)
    logo = dark.resize((lw, lh), Image.LANCZOS)
    img.paste(logo, (x1, y1 + (ah - lh) // 2), logo)
    img.convert("RGB").save(img_path, "PNG", optimize=True)


for p in list(BASE.glob("0*.png")) + list(GALLERY.glob("*.png")):
    redo_overlay(p)
    print(f"[ok] {p.name}")
