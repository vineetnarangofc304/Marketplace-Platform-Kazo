import json
from pathlib import Path

BASE = "https://settlement-intel-1.preview.emergentagent.com"
OUT = Path("/app/test_reports/bug_verification_18_ui_results.json")
RETURN_ORDER = "83410B8C-556E-465B-96A1-EB3A80DB1DF1"
RETURN_ROW_TESTID = "sales-row-a752b5cd-e629-42ec-a383-ad1fa5ce9976"
SALES_ORDER = "BA030AAB-E147-4FA2-847F-8B119D06AEC1"
SALES_ROW_TESTID = "sales-row-3fc2c0d5-aca8-448a-91ae-51ecd5e58438"

results = {"ok": False, "base_url": BASE, "production_touched": False, "steps": [], "evidence": {}}

def record(name, details=None):
    results["steps"].append({"name": name, "details": details or {}})
    print(f"PASS: {name}: {details or {}}")

try:
    await page.set_viewport_size({"width": 1920, "height": 1080})
    if "kazob2b.fundlezone.com" in BASE:
        raise AssertionError("Refusing to test production URL")

    await page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    await page.evaluate("""() => {
        localStorage.setItem('fundle_portal', 'all');
        localStorage.removeItem('kazo_token');
        localStorage.removeItem('kazo_user');
    }""")
    await page.reload(wait_until="domcontentloaded")
    await page.wait_for_selector('[data-testid="login-form"]', timeout=30000)
    await page.locator('[data-testid="login-email"]').fill("admin@fundle.ai")
    await page.locator('[data-testid="login-password"]').fill("admin123")
    await page.locator('[data-testid="login-submit"]').click(force=True)
    await page.wait_for_selector('[data-testid="overview-page"]', timeout=45000)
    record("login and overview load")

    await page.goto(f"{BASE}/?period_type=month&period_value=2026-04&portal=myntra", wait_until="domcontentloaded")
    await page.wait_for_selector('[data-testid="overview-page"]', timeout=30000)
    await page.wait_for_selector('[data-testid="overview-period-value"]', timeout=30000)
    option_values = await page.locator('[data-testid="overview-period-value"] option').evaluate_all("els => els.map(e => e.value)")
    if "2026-04" in option_values:
        await page.select_option('[data-testid="overview-period-value"]', "2026-04")
    await page.wait_for_function("""() => document.querySelector('[data-testid="kpi-nsv"]')?.innerText.includes('6,824')""", timeout=45000)
    kpi_text = await page.locator('[data-testid="kpi-nsv"]').inner_text()
    snapshot_text = await page.locator('[data-testid="portals-summary-widget"]').inner_text()
    tile_text = await page.locator('[data-testid="portal-tile-myntra"]').inner_text()
    results["evidence"]["kpi_nsv_text"] = kpi_text
    results["evidence"]["cross_portal_snapshot_text"] = snapshot_text
    results["evidence"]["myntra_tile_text"] = tile_text
    assert "TOTAL NSV" in kpi_text.upper() and "6,824 Order Qty (net)" in kpi_text, kpi_text
    assert "6,824 Order Qty (net)" in snapshot_text and "₹1,27,02,900" in snapshot_text and "NSV" in snapshot_text, snapshot_text
    assert "6,824" in tile_text and "ORDER QTY (NET)" in tile_text.upper(), tile_text
    record("overview KPI, snapshot and Myntra tile show net Order Qty", {"kpi": kpi_text, "tile": tile_text})

    # Get error messages using specific selectors
    error_text = await page.evaluate("""() => {
    const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
    return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
        print(f"Found error message: {error_text}")
    else:
        print("No error messages found on the page")
    results["evidence"]["overview_error_text"] = error_text

    await page.goto(f"{BASE}/sales?period_type=month&period_value=2026-04&portal=myntra", wait_until="domcontentloaded")
    await page.wait_for_selector('[data-testid="sales-page"]', timeout=30000)
    await page.wait_for_selector('[data-testid="sales-summary"]', timeout=30000)
    await page.wait_for_function("""() => document.querySelector('[data-testid="sales-summary"]')?.innerText.includes('6,824')""", timeout=45000)
    sales_summary = await page.locator('[data-testid="sales-summary"]').inner_text()
    results["evidence"]["sales_summary_text"] = sales_summary
    assert "6,824" in sales_summary and "Order Qty (net)" in sales_summary and "14,219 Sales" in sales_summary and "7,395 Returns" in sales_summary, sales_summary
    header_text = await page.locator('[data-testid="sales-page"] table thead').inner_text()
    results["evidence"]["sales_table_headers"] = header_text
    header_upper = header_text.upper()
    for label in ["Brand", "Sale Type", "Posting Date", "Item No", "Location", "Main Ctg", "Level", "Commission", "GT", "Price Range (NSV)", "Price Range (NSV after GT)"]:
        assert label.upper() in header_upper, f"Missing Sales Ledger header {label}: {header_text}"
    record("sales ledger header and grid columns verified", {"summary": sales_summary})

    await page.locator('[data-testid="sales-search"]').fill(RETURN_ORDER)
    await page.wait_for_timeout(800)
    return_row = page.locator(f'[data-testid="{RETURN_ROW_TESTID}"]')
    await return_row.wait_for(state="visible", timeout=45000)
    return_row_text = await return_row.inner_text()
    results["evidence"]["return_dto_grid_row_text"] = return_row_text
    assert "Return" in return_row_text and "DTO" in return_row_text, return_row_text
    assert "₹-279.06" in return_row_text and "₹-207.00" in return_row_text, return_row_text
    record("return_dto grid row shows negative commission and GT", {"row": return_row_text})

    await return_row.click(force=True)
    await page.wait_for_selector('[data-testid="sales-drawer"]', timeout=30000)
    await page.wait_for_function("""() => document.querySelector('[data-testid="sales-drawer"]')?.innerText.toUpperCase().includes('EXPECTED CALCULATION')""", timeout=30000)
    drawer_text = await page.locator('[data-testid="sales-drawer"]').inner_text()
    results["evidence"]["return_dto_drawer_text"] = drawer_text
    assert "Commission" in drawer_text and "₹-279.06" in drawer_text, drawer_text
    assert "Fixed Fee" in drawer_text and "₹-61.00" in drawer_text, drawer_text
    assert "GT Charge" in drawer_text and "₹-207.00" in drawer_text, drawer_text
    assert "Return Fee" in drawer_text and "₹112.00" in drawer_text, drawer_text
    for forbidden in ["GST", "TCS", "TDS"]:
        assert forbidden not in drawer_text, f"Forbidden tax row {forbidden} appeared in drawer: {drawer_text}"
    record("return_dto drawer values and tax-row removal verified")
    await page.locator('[data-testid="close-drawer"]').click(force=True)
    await page.wait_for_selector('[data-testid="sales-drawer"]', state="hidden", timeout=15000)

    await page.locator('[data-testid="sales-search"]').fill(SALES_ORDER)
    await page.wait_for_timeout(800)
    sales_row = page.locator(f'[data-testid="{SALES_ROW_TESTID}"]')
    await sales_row.wait_for(state="visible", timeout=45000)
    sales_row_text = await sales_row.inner_text()
    results["evidence"]["sales_grid_row_text"] = sales_row_text
    assert "Sales" in sales_row_text and "₹871.36" in sales_row_text and "₹266.00" in sales_row_text, sales_row_text
    record("sales grid row shows positive commission and GT", {"row": sales_row_text})

    # Get error messages using specific selectors
    error_text = await page.evaluate("""() => {
    const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
    return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
        print(f"Found error message: {error_text}")
    else:
        print("No error messages found on the page")
    results["evidence"]["sales_error_text"] = error_text

    results["ok"] = True
except Exception as e:
    results["ok"] = False
    results["error"] = str(e)
    try:
        await page.screenshot(path="/app/test_reports/bug_verification_18_ui_failure.jpg", quality=40, full_page=False)
    except Exception:
        pass
    print(f"FAIL: {e}")
finally:
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))