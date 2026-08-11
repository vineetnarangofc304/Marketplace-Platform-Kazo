# Focused Playwright body for mcp_browser_automation.
# Verifies exact return_dto order signs on Sales Ledger grid/drawer and Calculations drawer.

import re

ORDER_ID = "83410B8C-556E-465B-96A1-EB3A80DB1DF1"
ORDER_PREFIX = "83410B8C-556E"
SALES_ID = "a752b5cd-e629-42ec-a383-ad1fa5ce9976"
CALC_ID = "18a0debf-2d84-4f01-83dc-488607c4d0a2"
EXPECTED = {
    "Commission": "₹-279.06",
    "Fixed Fee": "₹61.00",
    "GT Charge": "₹-207.00",
    "Return Fee (Level/Zone)": "₹112.00",
    "Total Deductions": "₹-313.06",
}


def normalize_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


async def extract_charge_rows(testid):
    return await page.evaluate(
        """(testid) => {
          const drawer = document.querySelector(`[data-testid="${testid}"]`);
          if (!drawer) return null;
          return Array.from(drawer.querySelectorAll('table tbody tr')).map((tr) => {
            const cells = Array.from(tr.querySelectorAll('td'));
            return {
              label: (cells[0]?.textContent || '').trim(),
              value: (cells[1]?.textContent || '').trim(),
              valueClass: cells[1]?.className || ''
            };
          });
        }""",
        testid,
    )


try:
    print("Starting focused return_dto UI verification")
    failed_api = []
    page.on("response", lambda response: failed_api.append({"url": response.url, "status": response.status}) if "/api/" in response.url and response.status >= 400 else None)
    await page.set_viewport_size({"width": 1920, "height": 1080})

    # Force Myntra portal in the PortalContext-backed localStorage before the app loads.
    await page.add_init_script("localStorage.setItem('fundle_portal', 'myntra');")

    await page.goto("https://marketplace-recon-1.preview.emergentagent.com/login", wait_until="domcontentloaded")
    await page.wait_for_selector('[data-testid="login-form"]', timeout=15000)
    await page.fill('[data-testid="login-email"]', "admin@fundle.ai")
    await page.fill('[data-testid="login-password"]', "admin123")
    await page.click('[data-testid="login-submit"]')
    await page.wait_for_timeout(1000)
    await page.evaluate("localStorage.setItem('fundle_portal', 'myntra');")
    print("Login submitted")

    # Sales Ledger grid + drawer for exact return_dto row.
    await page.goto("https://marketplace-recon-1.preview.emergentagent.com/sales?period_type=month&period_value=2026-04&portal=myntra", wait_until="domcontentloaded")
    await page.wait_for_selector('[data-testid="sales-page"]', timeout=20000)
    await page.fill('[data-testid="sales-search"]', ORDER_ID)
    row = page.locator(f'[data-testid="sales-row-{SALES_ID}"]')
    await row.wait_for(state="visible", timeout=20000)
    row_text = normalize_text(await row.inner_text())
    print(f"Sales row text: {row_text}")
    assert ORDER_PREFIX in row_text, "Exact Sales Ledger row not visible after search"
    assert EXPECTED["Commission"] in row_text, "Sales Ledger grid Commission is not the expected negative value"
    assert EXPECTED["GT Charge"] in row_text, "Sales Ledger grid GT is not the expected negative value"
    print("Sales Ledger grid shows negative Commission and GT")

    await row.click()
    await page.wait_for_selector('[data-testid="sales-drawer"]', timeout=15000)
    await page.wait_for_selector('[data-testid="sales-drawer"] table tbody tr', timeout=15000)
    sales_drawer_rows = await extract_charge_rows("sales-drawer")
    print(f"Sales drawer rows: {sales_drawer_rows}")
    sales_map = {r["label"]: r for r in sales_drawer_rows}
    for label, expected_value in EXPECTED.items():
        assert label in sales_map, f"Sales drawer missing {label} row"
        assert sales_map[label]["value"] == expected_value, f"Sales drawer {label} expected {expected_value}, got {sales_map[label]['value']}"
    assert "fin-neg" in sales_map["Commission"]["valueClass"], "Sales drawer Commission is not styled as red/deduction"
    assert "fin-neg" in sales_map["Fixed Fee"]["valueClass"], "Sales drawer Fixed Fee is not styled as deduction"
    assert not sales_map["Fixed Fee"]["value"].startswith("₹-"), "Sales drawer Fixed Fee still shows negative"
    assert not sales_map["Return Fee (Level/Zone)"]["value"].startswith("₹-"), "Sales drawer Return Fee shows negative"
    print("Sales Ledger drawer shows Commission/GT negative and Fixed/Return positive with deduction styling")

    await page.click('[data-testid="close-drawer"]')
    await page.wait_for_timeout(300)

    # Calculations page drawer for same order.
    await page.goto(f"https://marketplace-recon-1.preview.emergentagent.com/calculations?period_type=month&period_value=2026-04&order_type=return_dto&search={ORDER_ID}", wait_until="domcontentloaded")
    await page.wait_for_selector('[data-testid="calculations-page"]', timeout=20000)
    calc_row = page.locator(f'[data-testid="calc-row-{CALC_ID}"]')
    try:
        await calc_row.wait_for(state="visible", timeout=10000)
    except Exception:
        calc_row = page.locator('tbody tr').filter(has_text=EXPECTED["Commission"]).first
        await calc_row.wait_for(state="visible", timeout=20000)
    calc_row_text = normalize_text(await calc_row.inner_text())
    print(f"Calculations row text: {calc_row_text}")
    assert EXPECTED["Commission"] in calc_row_text, "Calculations grid Commission is not expected negative value"
    assert EXPECTED["Fixed Fee"] in calc_row_text, "Calculations grid Fixed Fee is not expected positive value"
    assert EXPECTED["GT Charge"] in calc_row_text, "Calculations grid GT is not expected negative value"
    await calc_row.click()
    await page.wait_for_selector('[data-testid="calc-drawer"]', timeout=15000)
    await page.wait_for_selector('[data-testid="calc-drawer"] table tbody tr', timeout=15000)
    calc_drawer_rows = await extract_charge_rows("calc-drawer")
    print(f"Calculations drawer rows: {calc_drawer_rows}")
    calc_map = {r["label"]: r for r in calc_drawer_rows}
    for label, expected_value in EXPECTED.items():
        assert label in calc_map, f"Calculations drawer missing {label} row"
        assert calc_map[label]["value"] == expected_value, f"Calculations drawer {label} expected {expected_value}, got {calc_map[label]['value']}"
    assert "fin-neg" in calc_map["Commission"]["valueClass"], "Calculations drawer Commission is not styled as red/deduction"
    assert "fin-neg" in calc_map["Fixed Fee"]["valueClass"], "Calculations drawer Fixed Fee is not styled as deduction"
    assert not calc_map["Fixed Fee"]["value"].startswith("₹-"), "Calculations drawer Fixed Fee still shows negative"
    assert not calc_map["Return Fee (Level/Zone)"]["value"].startswith("₹-"), "Calculations drawer Return Fee shows negative"
    print("Calculations drawer shows same sign convention")

    # Required focused error scan.
    error_text = await page.evaluate("""() => {
    const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
    return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
        print(f"Found error message: {error_text}")
    else:
        print("No error messages found on the page")
    assert not failed_api, f"Unexpected API failures during UI flow: {failed_api}"
    print("UI verification PASSED")
except Exception as e:
    print(f"UI verification FAILED: {e}")
    await page.screenshot(path="/app/test_reports/return_dto_ui_failure.jpg", quality=40, full_page=False)
    raise