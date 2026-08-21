"""Build /app/marketing_assets/logos/fundle_dark.png — a dark variant of the
Fundle wordmark suitable for placement on light backgrounds (off-white pills).
Colored icons in the 'u' are preserved; only the grey letters are darkened.
"""
from pathlib import Path
from PIL import Image

SRC = Path("/app/marketing_assets/logos/fundle.png")
DST = Path("/app/marketing_assets/logos/fundle_dark.png")

img = Image.open(SRC).convert("RGBA")
pixels = img.load()
w, h = img.size
# Detect grey letter pixels (R ~ G ~ B, roughly light grey 210..240) and
# darken them to a deep navy so they read on off-white. Keep alpha, keep
# coloured pixels (icons) untouched.
for y in range(h):
    for x in range(w):
        r, g, b, a = pixels[x, y]
        if a == 0:
            continue
        # Grey band? R~G~B and light-ish
        if abs(r - g) < 12 and abs(g - b) < 12 and 180 < r < 250:
            pixels[x, y] = (30, 41, 59, a)  # slate-800

img.save(DST, "PNG", optimize=True)
print(f"[ok] dark variant → {DST}")
