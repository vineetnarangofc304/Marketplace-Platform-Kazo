"""Render /app/marketing_assets/brochure.html to a print-ready A4 PDF.
Uses Playwright (already available in the container)."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

SRC = Path("/app/marketing_assets/brochure.html").resolve()
OUT = Path("/app/marketing_assets/brochure.pdf")


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto(f"file://{SRC}", wait_until="networkidle")
        await page.pdf(
            path=str(OUT),
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        await browser.close()
    print(f"[ok] {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    asyncio.run(main())
