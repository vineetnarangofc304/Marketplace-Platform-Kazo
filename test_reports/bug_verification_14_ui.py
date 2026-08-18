# Playwright script body used with mcp_browser_automation for iteration 14.
# It assumes an async Playwright `page` object is available.

try:
    await page.set_viewport_size({"width": 1920, "height": 1080})
    base = "https://settlement-intel-1.preview.emergentagent.com"
    print("STEP: open login page")
    await page.goto(base + "/login", wait_until="networkidle")

    if await page.locator('[data-testid="login-form"]').is_visible():
        await page.locator('[data-testid="login-email"]').fill("admin@fundle.ai")
        await page.locator('[data-testid="login-password"]').fill("admin123")
        await page.locator('[data-testid="login-submit"]').click()
        await page.wait_for_url(lambda url: not url.endswith("/login"), timeout=20000)
        print("PASS: logged in")
    else:
        print("INFO: already logged in")

    await page.evaluate("localStorage.setItem('fundle_portal', 'myntra')")

    print("STEP: verify Sales Ledger page, summary, and first 20 Location cells")
    await page.goto(base + "/sales?period_type=month&period_value=2026-04&portal=myntra", wait_until="networkidle")
    await page.wait_for_selector('[data-testid="sales-page"]', timeout=30000)
    await page.wait_for_selector('tr[data-testid^="sales-row-"]', timeout=30000)
    summary_text = await page.locator('[data-testid="sales-summary"]').inner_text()
    print(f"Sales summary: {summary_text}")
    if "6,824" not in summary_text or "Order Qty (net)" not in summary_text:
        raise Exception(f"Sales summary did not show 6,824 Order Qty (net): {summary_text}")

    locations = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('tr[data-testid^="sales-row-"]')).slice(0, 20).map(row => {
            const cells = Array.from(row.querySelectorAll('td'));
            return (cells[6]?.textContent || '').trim();
        });
    }""")
    print(f"First 20 Sales Ledger Location cells: {locations}")
    if len(locations) < 20 or any(v != 'MYN' for v in locations):
        raise Exception(f"Expected first 20 Location cells to be MYN, got {locations}")
    print("PASS: Sales Ledger first 20 Location cells are MYN and summary is correct")

    print("STEP: verify Calculations drawer excludes GST/TCS/TDS rows")
    await page.goto(base + "/calculations?period_type=month&period_value=2026-04&portal=myntra", wait_until="networkidle")
    await page.wait_for_selector('[data-testid="calculations-page"]', timeout=30000)
    await page.wait_for_selector('tr[data-testid^="calc-row-"]', timeout=30000)
    await page.locator('tr[data-testid^="calc-row-"]').first.click()
    await page.wait_for_selector('[data-testid="calc-drawer"]', timeout=30000)
    drawer_text = await page.locator('[data-testid="calc-drawer"]').inner_text()
    forbidden = [x for x in ["GST", "TCS", "TDS"] if x in drawer_text]
    print(f"Forbidden calc drawer labels found: {forbidden}")
    if forbidden:
        raise Exception(f"Calculation drawer still shows forbidden tax labels: {forbidden}")
    print("PASS: Calculations drawer has no GST/TCS/TDS rows")

    print("STEP: verify Overview, Reports, Reconciliation pages render")
    render_checks = [
        ("/", '[data-testid="overview-page"]', "Overview"),
        ("/reports", '[data-testid="reports-page"]', "Reports"),
        ("/reconciliation", '[data-testid="recon-page"]', "Reconciliation"),
    ]
    for path, selector, label in render_checks:
        await page.goto(base + path, wait_until="networkidle")
        await page.wait_for_selector(selector, timeout=30000)
        print(f"PASS: {label} rendered")

    error_text = await page.evaluate("""() => {
    const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
    return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
        print(f"Found error message: {error_text}")
    else:
        print("No error messages found on the page")

    print("UI_TEST_RESULT: PASS")
except Exception as e:
    print(f"UI_TEST_RESULT: FAIL: {e}")
    await page.screenshot(path="/app/test_reports/bug_verification_14_ui_failure.jpg", quality=40, full_page=False)
    raise