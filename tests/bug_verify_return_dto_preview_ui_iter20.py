# Focused Playwright body for mcp_browser_automation.
# Preview-only verification for return_dto sign convention in Sales Ledger and Calculations drawers.

import json
import re
from pathlib import Path

BASE_URL = "https://settlement-intel-1.preview.emergentagent.com"
ORDER_ID = "83410B8C-556E-465B-96A1-EB3A80DB1DF1"
ORDER_PREFIX = "83410B8C-556E"
SALES_ID = "a752b5cd-e629-42ec-a383-ad1fa5ce9976"
CALC_ID = "18a0debf-2d84-4f01-83dc-488607c4d0a2"
RESULT_PATH = Path("/app/test_reports/return_dto_preview_ui_iter20_result.json")
EXPECTED = {
    "Commission": "₹-279.06",
    "Fixed Fee": "₹61.00",
    "GT Charge": "₹-207.00",
    "Return Fee (Level/Zone)": "₹112.00",
    "Total Deductions": "₹-313.06",
}
FORBIDDEN_TAX_LABELS = ["GST", "TCS", "TDS"]


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


async def assert_expected_drawer(testid, label):
    rows = await extract_charge_rows(testid)
    print(f"{label} drawer rows: {rows}")
    assert rows, f"{label} drawer rows not found"
    row_map = {r["label"]: r for r in rows}
    for expected_label, expected_value in EXPECTED.items():
        assert expected_label in row_map, f"{label} drawer missing {expected_label} row"
        assert row_map[expected_label]["value"] == expected_value, (
            f"{label} drawer {expected_label} expected {expected_value}, got {row_map[expected_label]['value']}"
        )
    labels = " | ".join(row_map.keys())
    for forbidden in FORBIDDEN_TAX_LABELS:
        assert forbidden not in labels, f"{label} drawer unexpectedly includes tax row {forbidden}: {labels}"
    assert row_map["Commission"]["value"].startswith("₹-"), f"{label} Commission is not negative"
    assert row_map["GT Charge"]["value"].startswith("₹-"), f"{label} GT Charge is not negative"
    assert not row_map["Fixed Fee"]["value"].startswith("₹-"), f"{label} Fixed Fee is negative"
    assert not row_map["Return Fee (Level/Zone)"]["value"].startswith("₹-"), f"{label} Return Fee is negative"
    return rows


result = {
    "base_url": BASE_URL,
    "production_touched": "no",
    "checks": [],
    "passed": False,
}

try:
    print("Starting focused return_dto preview UI verification")
    failed_api = []
    page.on(
        "response",
        lambda response: failed_api.append({"url": response.url, "status": response.status})
        if "/api/" in response.url and response.status >= 400 else None,
    )
    await page.set_viewport_size({"width": 1920, "height": 1080})

    # Force preview UI to use Myntra portal via the app's PortalContext localStorage key.
    await page.add_init_script("localStorage.setItem('fundle_portal', 'myntra');")

    await page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
    await page.wait_for_selector('[data-testid="login-form"]', timeout=15000)
    await page.fill('[data-testid="login-email"]', "admin@fundle.ai")
    await page.fill('[data-testid="login-password"]', "admin123")
    await page.click('[data-testid="login-submit"]')
    await page.wait_for_timeout(1200)
    await page.evaluate("localStorage.setItem('fundle_portal', 'myntra');")
    result["checks"].append({"name": "admin login", "passed": True})
    print("Login successful")

    # Sales Ledger: open requested period/portal route, search exact known return_dto row, verify grid and drawer signs.
    await page.goto(
        f"{BASE_URL}/sales?period_type=month&period_value=2026-04&portal=myntra&txn_type=Return&order_status=DTO",
        wait_until="domcontentloaded",
    )
    await page.wait_for_selector('[data-testid="sales-page"]', timeout=20000)
    await page.fill('[data-testid="sales-search"]', ORDER_ID)
    row = page.locator(f'[data-testid="sales-row-{SALES_ID}"]')
    await row.wait_for(state="visible", timeout=20000)
    row_text = normalize_text(await row.inner_text())
    print(f"Sales row text: {row_text}")
    assert ORDER_PREFIX in row_text, "Exact Sales Ledger return_dto row not visible after search"
    assert EXPECTED["Commission"] in row_text, "Sales Ledger grid Commission is not the expected negative value"
    assert EXPECTED["GT Charge"] in row_text, "Sales Ledger grid GT is not the expected negative value"
    result["checks"].append({"name": "Sales Ledger grid return_dto negative Commission/GT", "passed": True, "row_text": row_text})

    await row.click()
    await page.wait_for_selector('[data-testid="sales-drawer"]', timeout=15000)
    await page.wait_for_selector('[data-testid="sales-drawer"] table tbody tr', timeout=15000)
    sales_drawer_rows = await assert_expected_drawer("sales-drawer", "Sales Ledger")
    result["checks"].append({"name": "Sales Ledger drawer sign convention and no tax rows", "passed": True, "rows": sales_drawer_rows})
    await page.click('[data-testid="close-drawer"]')
    await page.wait_for_timeout(300)

    # Calculations page: URL filter order_type=return_dto plus exact search, then same drawer assertion.
    await page.goto(
        f"{BASE_URL}/calculations?period_type=month&period_value=2026-04&portal=myntra&order_type=return_dto&search={ORDER_ID}",
        wait_until="domcontentloaded",
    )
    await page.wait_for_selector('[data-testid="calculations-page"]', timeout=20000)
    calc_row = page.locator(f'[data-testid="calc-row-{CALC_ID}"]')
    await calc_row.wait_for(state="visible", timeout=20000)
    calc_row_text = normalize_text(await calc_row.inner_text())
    print(f"Calculations row text: {calc_row_text}")
    assert EXPECTED["Commission"] in calc_row_text, "Calculations grid Commission is not expected negative value"
    assert EXPECTED["Fixed Fee"] in calc_row_text, "Calculations grid Fixed Fee is not expected positive value"
    assert EXPECTED["GT Charge"] in calc_row_text, "Calculations grid GT is not expected negative value"
    result["checks"].append({"name": "Calculations grid return_dto signs", "passed": True, "row_text": calc_row_text})

    await calc_row.click()
    await page.wait_for_selector('[data-testid="calc-drawer"]', timeout=15000)
    await page.wait_for_selector('[data-testid="calc-drawer"] table tbody tr', timeout=15000)
    calc_drawer_rows = await assert_expected_drawer("calc-drawer", "Calculations")
    result["checks"].append({"name": "Calculations drawer sign convention and no tax rows", "passed": True, "rows": calc_drawer_rows})

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
    result["checks"].append({"name": "no UI/API errors", "passed": True, "error_text": error_text})
    result["passed"] = True
    RESULT_PATH.write_text(json.dumps(result, indent=2, default=str))
    print("UI verification PASSED")
except Exception as e:
    print(f"UI verification FAILED: {e}")
    result["passed"] = False
    result["error"] = str(e)
    RESULT_PATH.write_text(json.dumps(result, indent=2, default=str))
    await page.screenshot(path="/app/test_reports/return_dto_preview_ui_iter20_failure.jpg", quality=40, full_page=False)
    raise