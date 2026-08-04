# Playwright script body used with mcp_browser_automation for focused UI testing.
# It assumes `page` is provided by the harness inside an async function.

try:
    await page.set_viewport_size({"width": 1920, "height": 1080})
    print("STEP: viewport set")

    await page.goto("https://marketplace-recon-1.preview.emergentagent.com/login", wait_until="networkidle")
    print("STEP: login page loaded")
    if await page.get_by_test_id("login-form").count() > 0:
        await page.get_by_test_id("login-email").fill("admin@fundle.ai")
        await page.get_by_test_id("login-password").fill("admin123")
        await page.get_by_test_id("login-submit").click()
        await page.wait_for_url(lambda url: "/login" not in url, timeout=30000)
        print("PASS: admin login completed")
    else:
        print("INFO: already authenticated")

    await page.evaluate("localStorage.setItem('fundle_portal', 'myntra')")
    await page.goto("https://marketplace-recon-1.preview.emergentagent.com/sales?period_type=month&period_value=2026-04", wait_until="networkidle")
    await page.wait_for_selector('[data-testid="sales-page"]', timeout=30000)
    await page.wait_for_timeout(1500)
    print("STEP: sales page loaded")

    if await page.get_by_test_id("portal-switcher-select").count() > 0:
        await page.get_by_test_id("portal-switcher-select").select_option("myntra")
        await page.wait_for_timeout(1500)
        print("STEP: portal set to myntra")

    # Make sure the intended period is active.
    await page.get_by_test_id("sales-period-value").select_option("2026-04")
    await page.wait_for_timeout(2500)

    summary_text = await page.get_by_test_id("sales-summary").inner_text()
    print(f"SALES SUMMARY: {summary_text}")
    if "6,824" in summary_text and "14,219" in summary_text and "7,395" in summary_text and "21,614" in summary_text:
        print("PASS: sales summary shows net Order Qty, not raw row count")
    else:
        print("FAIL: sales summary did not show expected net/sales/returns/row counts")

    header_text = await page.locator("thead").first.inner_text()
    required_headers = ["Brand", "Sale Type", "Posting Date", "Item No", "Location", "Main Ctg", "Sub-Cat", "Level", "Zone", "Month", "Qty", "MRP", "NSV", "Price Range (NSV)", "Price Range (NSV after GT)"]
    missing_headers = [h for h in required_headers if h not in header_text]
    if not missing_headers:
        print("PASS: sales grid contains requested visible headers")
    else:
        print(f"FAIL: sales grid missing headers: {missing_headers}")

    rows = page.locator('tr[data-testid^="sales-row-"]')
    row_count = await rows.count()
    print(f"SALES ROW COUNT VISIBLE: {row_count}")
    grid_samples = []
    join_populated = 0
    location_populated = 0
    sample_limit = min(20, row_count)
    for i in range(sample_limit):
        cells = await rows.nth(i).locator("td").all_inner_texts()
        grid_samples.append(cells)
        # Column indexes from SalesLedger.jsx: 6 Location, 9 Level, 15 Price Range NSV, 16 Price Range after GT.
        if len(cells) >= 17:
            if cells[6].strip() not in ("", "—"):
                location_populated += 1
            if cells[9].strip() not in ("", "—") and cells[15].strip() not in ("", "—") and cells[16].strip() not in ("", "—"):
                join_populated += 1
    print(f"GRID FIRST {sample_limit}: location_populated={location_populated}, joined_level_price_populated={join_populated}")
    print(f"GRID SAMPLE ROW 1: {grid_samples[0] if grid_samples else 'NO ROWS'}")
    if sample_limit >= 20 and join_populated == sample_limit:
        print("PASS: sales grid first 20 rows show joined Level and Price Range values")
    else:
        print("FAIL: sales grid first 20 rows do not consistently show joined Level and Price Range values")

    # Verify Sales Ledger drawer expected-charge rows exclude GST/TCS/TDS.
    if row_count > 0:
        await rows.first.click()
        await page.wait_for_selector('[data-testid="sales-drawer"]', timeout=15000)
        await page.wait_for_timeout(1000)
        drawer_text = await page.get_by_test_id("sales-drawer").inner_text()
        forbidden = ["GST on Commission", "GST on Fixed Fee", "TCS", "TDS"]
        missing_expected = [label for label in ["Commission", "Fixed Fee", "GT Charge", "Return Fee", "Total Deductions", "Expected Settlement"] if label not in drawer_text]
        forbidden_present = [label for label in forbidden if label in drawer_text]
        if not missing_expected and not forbidden_present:
            print("PASS: sales drawer expected charges table has only the allowed rows")
        else:
            print(f"FAIL: sales drawer labels issue missing={missing_expected} forbidden={forbidden_present}")
        await page.get_by_test_id("close-drawer").click()
        await page.wait_for_timeout(500)

    # Verify Export Excel user action downloads an xlsx.
    async with page.expect_download(timeout=120000) as download_info:
        await page.get_by_test_id("btn-export-sales").click()
    download = await download_info.value
    suggested = download.suggested_filename
    print(f"EXPORT DOWNLOAD: {suggested}")
    if suggested.endswith(".xlsx"):
        print("PASS: sales Export Excel downloads an .xlsx file")
    else:
        print("FAIL: sales Export Excel did not download an .xlsx file")

    # Calculations drawer expected-charge rows exclude removed taxes/GST.
    await page.goto("https://marketplace-recon-1.preview.emergentagent.com/calculations?period_type=month&period_value=2026-04&order_type=return_dto", wait_until="networkidle")
    await page.wait_for_selector('[data-testid="calculations-page"]', timeout=30000)
    await page.wait_for_timeout(2000)
    if await page.get_by_test_id("portal-switcher-select").count() > 0:
        await page.get_by_test_id("portal-switcher-select").select_option("myntra")
        await page.wait_for_timeout(1500)
    calc_rows = page.locator('tr[data-testid^="calc-row-"]')
    calc_row_count = await calc_rows.count()
    print(f"CALC ROW COUNT VISIBLE: {calc_row_count}")
    if calc_row_count > 0:
        await calc_rows.first.click()
        await page.wait_for_selector('[data-testid="calc-drawer"]', timeout=15000)
        await page.wait_for_timeout(1000)
        calc_drawer_text = await page.get_by_test_id("calc-drawer").inner_text()
        forbidden_present_calc = [label for label in ["GST on Commission", "GST on Fixed Fee", "TCS", "TDS"] if label in calc_drawer_text]
        missing_expected_calc = [label for label in ["Commission", "Fixed Fee", "GT Charge", "Return Fee", "Total Deductions", "Expected Settlement"] if label not in calc_drawer_text]
        if not forbidden_present_calc and not missing_expected_calc:
            print("PASS: calculations drawer expected charges table has only the allowed rows")
        else:
            print(f"FAIL: calculations drawer labels issue missing={missing_expected_calc} forbidden={forbidden_present_calc}")
        await page.get_by_test_id("close-drawer").click()
        await page.wait_for_timeout(500)
    else:
        print("FAIL: calculations page had no visible return_dto rows")

    # Rebuild button still usable (do not wait for full recalculation here; backend script verified full response).
    await page.get_by_test_id("btn-run-all-calcs").wait_for(timeout=10000)
    run_disabled = await page.get_by_test_id("btn-run-all-calcs").is_disabled()
    if not run_disabled:
        print("PASS: Rebuild/Run Calculations button is enabled")
    else:
        print("FAIL: Rebuild/Run Calculations button is disabled")

    # Smoke render pages that consume calculations.
    for path, selector in [("/", "text=Marketplace Command Center"), ("/reports", '[data-testid="reports-page"]'), ("/reconciliation", '[data-testid="reconciliation-page"]')]:
        await page.goto("https://marketplace-recon-1.preview.emergentagent.com" + path, wait_until="networkidle")
        await page.wait_for_timeout(1200)
        if await page.locator(selector).count() > 0:
            print(f"PASS: page renders {path}")
        else:
            body = (await page.locator("body").inner_text())[:300]
            print(f"FAIL: page did not render expected selector for {path}; body={body}")

    # Get error messages using specific selectors
    error_text = await page.evaluate("""() => {
    const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
    return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
        print(f"Found error message: {error_text}")
    else:
        print("No error messages found on the page")
except Exception as e:
    print(f"FAIL: UI automation exception: {type(e).__name__}: {e}")
    raise