import json
import pathlib
import re

results = {"steps": []}

def record(name, passed, detail=""):
    results["steps"].append({"name": name, "passed": passed, "detail": detail})
    print(("PASS" if passed else "FAIL") + f" {name}: {detail}")

def parse_amount(text):
    cleaned = re.sub(r"[^0-9.\-]", "", text or "")
    return float(cleaned) if cleaned not in ("", "-", ".") else None

async def read_charge_table(drawer_testid):
    rows = await page.locator(f'[data-testid="{drawer_testid}"] table').last.locator('tr').evaluate_all("""
        rows => rows.map(r => {
            const cells = Array.from(r.querySelectorAll('td')).map(td => td.textContent.trim());
            return {label: cells[0] || '', value: cells[1] || ''};
        })
    """)
    return {r["label"]: r["value"] for r in rows if r.get("label")}

try:
    base_url = "https://marketplace-recon-1.preview.emergentagent.com"
    assert "kazob2b.fundlezone.com" not in base_url
    order_id = "326D677B-1384-40AD-A823-F0E9D470EC82"

    await page.set_viewport_size({"width": 1920, "height": 1080})
    await page.goto(base_url + "/login", wait_until="domcontentloaded")
    await page.wait_for_timeout(500)

    if await page.get_by_test_id("login-form").is_visible():
        await page.get_by_test_id("login-email").fill("admin@fundle.ai")
        await page.get_by_test_id("login-password").fill("admin123")
        await page.get_by_test_id("login-submit").click(force=True)
        await page.wait_for_timeout(1500)
    record("login", True, "admin credentials accepted or existing session reused")

    # Force the same marketplace context a user would choose in the portal selector.
    await page.evaluate("localStorage.setItem('fundle_portal', 'myntra')")

    await page.goto(base_url + "/sales?period_type=month&period_value=2026-04&portal=myntra", wait_until="networkidle")
    await page.get_by_test_id("sales-page").wait_for(state="visible", timeout=30000)
    await page.get_by_test_id("sales-summary").wait_for(state="visible", timeout=30000)
    summary_text = (await page.get_by_test_id("sales-summary").inner_text()).replace("\u00a0", " ")
    if "6,824" in summary_text and "Order Qty (net)" in summary_text and "14,219 Sales" in summary_text and "7,395 Returns" in summary_text:
        record("sales_summary_net_qty_visible", True, summary_text)
    else:
        raise AssertionError(f"Sales summary did not show expected net math: {summary_text}")

    await page.get_by_test_id("sales-search").fill(order_id)
    await page.get_by_test_id("filter-txn").select_option("Return")
    await page.get_by_test_id("filter-status").fill("DTO")
    await page.wait_for_timeout(1800)
    sales_row = page.locator('tr[data-testid^="sales-row-"]').first
    await sales_row.wait_for(state="visible", timeout=30000)
    await sales_row.click(force=True)
    await page.get_by_test_id("sales-drawer").wait_for(state="visible", timeout=30000)
    await page.get_by_text("Expected Calculation", exact=True).wait_for(state="visible", timeout=30000)
    drawer_text = await page.get_by_test_id("sales-drawer").inner_text()
    if order_id not in drawer_text or "DTO" not in drawer_text or "Return" not in drawer_text:
        raise AssertionError("Sales drawer is not the requested Return+DTO row")
    sales_table = await read_charge_table("sales-drawer")
    results["sales_drawer_table"] = sales_table
    for label in ["Commission", "Fixed Fee", "GT Charge", "Return Fee (Level/Zone)", "Total Deductions", "Expected Settlement"]:
        if label not in sales_table:
            raise AssertionError(f"Sales drawer missing {label}; got {sales_table}")
    for label in ["Commission", "Fixed Fee", "GT Charge"]:
        amt = parse_amount(sales_table[label])
        if amt is None or amt >= 0:
            raise AssertionError(f"Sales drawer {label} must be negative non-zero, got {sales_table[label]}")
    return_amt = parse_amount(sales_table["Return Fee (Level/Zone)"])
    if return_amt is None or return_amt <= 0:
        raise AssertionError(f"Sales drawer Return Fee must be positive, got {sales_table['Return Fee (Level/Zone)']}")
    if any(label in sales_table for label in ["GST", "TCS", "TDS", "Commission GST", "Fixed Fee GST"]):
        raise AssertionError(f"Sales drawer tax rows should not be present: {sales_table}")
    record("sales_drawer_return_dto_reversal", True, json.dumps(sales_table))

    await page.goto(base_url + f"/calculations?period_type=month&period_value=2026-04&portal=myntra&order_type=return_dto&search={order_id}", wait_until="networkidle")
    await page.get_by_test_id("calculations-page").wait_for(state="visible", timeout=30000)
    await page.wait_for_timeout(1200)
    calc_row = page.locator('tr[data-testid^="calc-row-"]').first
    await calc_row.wait_for(state="visible", timeout=30000)
    await calc_row.click(force=True)
    await page.get_by_test_id("calc-drawer").wait_for(state="visible", timeout=30000)
    await page.get_by_text("Expected Charges & Deductions", exact=True).wait_for(state="visible", timeout=30000)
    calc_drawer_text = await page.get_by_test_id("calc-drawer").inner_text()
    if order_id not in calc_drawer_text:
        raise AssertionError("Calculations drawer is not for the same sales row/order id")
    calc_table = await read_charge_table("calc-drawer")
    results["calc_drawer_table"] = calc_table
    for label in ["Commission", "Fixed Fee", "GT Charge", "Return Fee (Level/Zone)", "Total Deductions", "Expected Settlement"]:
        if label not in calc_table:
            raise AssertionError(f"Calculations drawer missing {label}; got {calc_table}")
    for label in ["Commission", "Fixed Fee", "GT Charge"]:
        amt = parse_amount(calc_table[label])
        if amt is None or amt >= 0:
            raise AssertionError(f"Calculations drawer {label} must be negative non-zero, got {calc_table[label]}")
    calc_return_amt = parse_amount(calc_table["Return Fee (Level/Zone)"])
    if calc_return_amt is None or calc_return_amt <= 0:
        raise AssertionError(f"Calculations drawer Return Fee must be positive, got {calc_table['Return Fee (Level/Zone)']}")
    if any(label in calc_table for label in ["GST", "TCS", "TDS", "Commission GST", "Fixed Fee GST"]):
        raise AssertionError(f"Calculations drawer tax rows should not be present: {calc_table}")
    record("calculations_drawer_same_row_return_dto_reversal", True, json.dumps(calc_table))

    error_text = await page.evaluate("""() => {
        const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
        return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
        print(f"Found error message: {error_text}")
    else:
        print("No error messages found on the page")
    results["passed"] = True
except Exception as e:
    results["passed"] = False
    results["error"] = str(e)
    print(f"UI verification failed: {e}")
finally:
    pathlib.Path("/app/test_reports/bug_verification_16_ui_results.json").write_text(json.dumps(results, indent=2))
    if not results.get("passed"):
        raise AssertionError(results.get("error", "UI verification failed"))