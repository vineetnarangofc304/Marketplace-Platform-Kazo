"""Confirm the served brochure.pdf is byte-identical to a fresh render of the current brochure.html."""
import asyncio, hashlib
from pathlib import Path
from playwright.async_api import async_playwright

SRC = Path("/app/marketing_assets/brochure.html").resolve()
SERVED = Path("/app/marketing_assets/brochure.pdf")
TMP = Path("/tmp/brochure_fresh.pdf")


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context()).new_page()
        await pg.goto(f"file://{SRC}", wait_until="networkidle")
        await pg.pdf(path=str(TMP), format="A4", print_background=True,
                     margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        await b.close()
    a = SERVED.read_bytes()
    c = TMP.read_bytes()
    print("served size:", len(a), "fresh size:", len(c))
    print("served sha:", hashlib.sha256(a).hexdigest()[:16])
    print("fresh  sha:", hashlib.sha256(c).hexdigest()[:16])
    print("identical:", a == c)


asyncio.run(main())
