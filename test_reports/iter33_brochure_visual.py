"""Visual check: render each A4 page of brochure.html to a JPEG for review."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

SRC = Path("/app/marketing_assets/brochure.html").resolve()
OUT = Path("/app/test_reports/ui_iteration_33")
OUT.mkdir(parents=True, exist_ok=True)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={"width": 1240, "height": 1754})
        await page.goto(f"file://{SRC}", wait_until="networkidle")
        pages = page.locator(".page")
        n = await pages.count()
        print("page elements:", n)
        for i in range(n):
            await pages.nth(i).screenshot(
                path=str(OUT / f"brochure_p{i+1}.jpeg"), quality=45, type="jpeg"
            )
        # overflow detection
        overflow = await page.evaluate(
            """() => Array.from(document.querySelectorAll('.page')).map((el, i) => ({
                i: i+1, sh: el.scrollHeight, ch: el.clientHeight
            })).filter(x => x.sh - x.ch > 4)"""
        )
        print("overflowing pages:", overflow)
        await b.close()


asyncio.run(main())
