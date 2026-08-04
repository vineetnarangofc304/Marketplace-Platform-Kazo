# Playwright script body used with mcp_browser_automation to reproduce the
# remaining user-visible Location issue on Myntra return rows.

try:
    await page.set_viewport_size({"width": 1920, "height": 1080})
    base = "https://marketplace-recon-1.preview.emergentagent.com"
    await page.goto(base + "/login", wait_until="networkidle")
    if await page.locator('[data-testid="login-form"]').is_visible():
        await page.locator('[data-testid="login-email"]').fill("admin@fundle.ai")
        await page.locator('[data-testid="login-password"]').fill("admin123")
        await page.locator('[data-testid="login-submit"]').click()
        await page.wait_for_url(lambda url: not url.endswith("/login"), timeout=20000)
    await page.evaluate("localStorage.setItem('fundle_portal', 'myntra')")
    await page.goto(base + "/sales?period_type=month&period_value=2026-04&portal=myntra", wait_until="networkidle")
    await page.wait_for_selector('[data-testid="sales-page"]', timeout=30000)
    await page.locator('[data-testid="filter-txn"]').select_option("Return")
    await page.wait_for_timeout(1000)
    await page.wait_for_selector('tr[data-testid^="sales-row-"]', timeout=30000)
    locations = await page.evaluate("""() => Array.from(document.querySelectorAll('tr[data-testid^="sales-row-"]')).slice(0, 10).map(row => {
        const cells = Array.from(row.querySelectorAll('td'));
        return {saleType: (cells[2]?.textContent || '').trim(), invoiceLocation: (cells[6]?.textContent || '').trim()};
    })""")
    print(f"Return-filtered first 10 Sale Type/Location cells: {locations}")
    if any(x.get('invoiceLocation') != 'MYN' for x in locations):
        print("UI_RETURN_LOCATION_RESULT: FAIL_EXPECTED_MYN_BUT_FOUND_NON_MYN")
    else:
        print("UI_RETURN_LOCATION_RESULT: PASS_ALL_MYN")
except Exception as e:
    print(f"UI_RETURN_LOCATION_RESULT: ERROR: {e}")
    raise