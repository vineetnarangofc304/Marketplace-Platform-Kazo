"""Capture real page screenshots from Preview via Playwright."""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv("/app/frontend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
OUT = Path("/app/marketing/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("login",          "/login",          6.0, False),
    ("overview",       "/",               8.0, True),
    ("insights",       "/insights",       8.0, True),
    ("uploads",        "/uploads",        6.0, True),
    ("sales_ledger",   "/sales",          8.0, True),
    ("masters",        "/masters",        8.0, True),
    ("calculations",   "/calculations",   9.0, True),
    ("reconciliation", "/reconciliation", 8.0, True),
    ("discrepancies",  "/discrepancies",  8.0, True),
    ("recovery",       "/recovery",       8.0, True),
    ("reports",        "/reports",        6.0, True),
]

EMAIL = "admin@fundle.ai"
PASSWORD = "admin123"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page = await ctx.new_page()

        # Login flow
        print("→ opening login")
        await page.goto(f"{BASE}/login", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        # Screenshot login before auth
        await page.screenshot(path=str(OUT / "login.png"), full_page=False)
        print("  captured login")

        await page.fill('[data-testid="login-email"]', EMAIL)
        await page.fill('[data-testid="login-password"]', PASSWORD)
        await page.click('[data-testid="login-submit"]')
        await page.wait_for_url(lambda u: "/login" not in u, timeout=15000)
        await asyncio.sleep(3)

        for name, path, wait, auth in PAGES[1:]:
            print(f"→ capturing {name} ({path})")
            try:
                await page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=30000)
            except Exception as e:
                print(f"  navigation timeout, continuing: {e}")
            await asyncio.sleep(wait)
            await page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
            print(f"  ✓ {name}.png")

        # Try to open the Calculations drawer for a rich shot
        try:
            print("→ trying to open calculations drawer")
            await page.goto(f"{BASE}/calculations", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(4)
            # Click first row if exists
            row = page.locator("table tbody tr").first
            if await row.count() > 0:
                await row.click()
                await asyncio.sleep(2)
                await page.screenshot(path=str(OUT / "calculations_drawer.png"), full_page=False)
                print("  ✓ calculations_drawer.png")
        except Exception as e:
            print(f"  drawer skip: {e}")

        await browser.close()
    print("\nDone. Screenshots in", OUT)


if __name__ == "__main__":
    asyncio.run(main())
