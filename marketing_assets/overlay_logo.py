"""Re-run: regenerate the 5 infographics AND cleanly overlay the actual
Fundle logo (which is a light/white variant meant for dark backgrounds).

Strategy: tell Nano Banana to leave a clear NAVY rectangle in the corner
where the logo goes (no logo drawn), then PIL pastes the real PNG in.
"""
import subprocess
from pathlib import Path
from PIL import Image

OUT = Path("/app/marketing_assets")
LOGO_PATH = OUT / "logos" / "fundle.png"

# 1) Regenerate backgrounds
print("Regenerating backgrounds...")
subprocess.run(["python", str(OUT / "generate_infographics.py")], check=True)

# 2) Overlay clean logo directly on navy (no light pill).
src = Image.open(LOGO_PATH).convert("RGBA")
bbox = src.getbbox()
if bbox:
    src = src.crop(bbox)

# Each entry: (filename, cover_box for AI-drawn logo, target_logo_box)
# cover_box: paint a solid navy rectangle to hide the AI's approximation
# target_logo_box: where the real logo lives (may be smaller than cover_box)
NAVY = (11, 30, 59, 255)  # #0B1E3B
LAYOUTS = [
    # slug, cover_box, target_logo_box
    ("01_platform_overview.png", (10,  20, 320, 140), ( 30,  40, 300, 130)),
    ("02_modules_inside.png",    (720, 900,1010,1010), (740, 910, 990, 1000)),
    ("03_workflow.png",          (10,  30, 400, 210), ( 30,  50, 380, 180)),
    ("04_multi_marketplace.png", (10,  20, 280, 130), ( 30,  40, 260, 120)),
    ("05_benefits_roi.png",      (10,  30, 350, 150), ( 30,  50, 330, 140)),
]

for slug, cover_box, target_box in LAYOUTS:
    img_path = OUT / slug
    if not img_path.exists():
        print(f"[skip] {slug}")
        continue
    img = Image.open(img_path).convert("RGBA")

    # Paint navy over the AI-drawn logo area
    from PIL import ImageDraw
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle(cover_box, fill=NAVY)
    img = Image.alpha_composite(img, overlay)

    # Fit the real logo inside target_box, preserving aspect ratio
    tx1, ty1, tx2, ty2 = target_box
    tw, th = tx2 - tx1, ty2 - ty1
    scale = min(tw / src.width, th / src.height)
    lw, lh = int(src.width * scale), int(src.height * scale)
    logo = src.resize((lw, lh), Image.LANCZOS)
    px = tx1 + (tw - lw) // 2
    py = ty1 + (th - lh) // 2
    img.paste(logo, (px, py), logo)

    img.convert("RGB").save(img_path, "PNG", optimize=True)
    print(f"[ok  ] {slug}  logo {lw}x{lh} at ({px},{py})")
