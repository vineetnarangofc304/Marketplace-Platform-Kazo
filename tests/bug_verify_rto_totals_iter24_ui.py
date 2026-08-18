"""Focused Playwright UI verification for Calculations RTO Total Deductions.

Run through the MCP browser automation tool. The script logs in, pins portal to
Myntra, opens /calculations?order_type=rto, and checks 5 visible rows/drawers.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path


BASE_URL = "https://settlement-intel-1.preview.emergentagent.com"
OUT = Path("/app/test_reports/bug_verify_rto_totals_iter24_ui_result.json")


def parse_money(text):
    cleaned = re.sub(r"[^0-9.\-]", "", text or "")
    if cleaned in ("", "-", "."):
        raise AssertionError(f"Could not parse money from {text!r}")
    return round(float(cleaned), 2)


def near(a, b, tol=0.02):
    return abs(float(a) - float(b)) <= tol


async def run_ui_check(page):
    evidence = {"checked_rows": []}
    failures = []
    status = "passed"

    try:
        await page.set_viewport_size({"width": 1920, "height": 1080})
        print("Opening login page")
        await page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        await page.evaluate("localStorage.clear()")
        await page.reload(wait_until="domcontentloaded")

        await page.get_by_test_id("login-email").fill("admin@fundle.ai")
        await page.get_by_test_id("login-password").fill("admin123")
        await page.get_by_test_id("login-submit").click()
        await page.get_by_test_id("nav-calculations").wait_for(timeout=15000)
        print("Logged in successfully")

        await page.get_by_test_id("portal-switcher-select").select_option("myntra")
        await page.wait_for_timeout(500)
        selected_portal = await page.get_by_test_id("portal-switcher-select").input_value()
        if selected_portal != "myntra":
            raise AssertionError(f"Portal switch did not persist myntra, got {selected_portal}")

        print("Opening Calculations with order_type=rto")
        async with page.expect_response(lambda r: "/api/calculations" in r.url and "order_type=rto" in r.url and r.status == 200, timeout=30000):
            await page.goto(f"{BASE_URL}/calculations?order_type=rto", wait_until="domcontentloaded")
        await page.locator('tr[data-testid^="calc-row-"]').first.wait_for(timeout=20000)
        await page.wait_for_timeout(1000)

        rows = await page.evaluate(
            """() => Array.from(document.querySelectorAll('tr[data-testid^="calc-row-"]')).slice(0, 5).map((tr) => ({
                testid: tr.getAttribute('data-testid'),
                cells: Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
            }))"""
        )
        if len(rows) < 5:
            raise AssertionError(f"Expected 5 visible RTO calculation rows, got {len(rows)}")

        for i, row in enumerate(rows):
            tid = row["testid"]
            cells = row["cells"]
            table_comm = parse_money(cells[5])
            table_fixed = parse_money(cells[6])
            table_gt = parse_money(cells[7])
            table_deductions = parse_money(cells[8])
            table_expected = parse_money(cells[9])
            if not (table_comm < 0 and table_fixed < 0 and table_gt < 0):
                raise AssertionError(f"Visible RTO row signs wrong before drawer for {tid}: comm={table_comm}, fixed={table_fixed}, gt={table_gt}")
            if not near(table_expected, 0):
                raise AssertionError(f"Visible RTO expected payout should be 0 for {tid}, got {table_expected}")

            print(f"Checking RTO drawer row {i + 1}: {tid}")
            await page.locator(f'[data-testid="{tid}"]').click()
            await page.get_by_test_id("calc-drawer").wait_for(timeout=10000)
            await page.wait_for_timeout(300)
            drawer = await page.evaluate(
                """() => {
                    const out = {};
                    const trs = Array.from(document.querySelectorAll('[data-testid="calc-drawer"] table tbody tr'));
                    for (const tr of trs) {
                        const tds = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
                        if (tds.length >= 2) out[tds[0]] = tds[1];
                    }
                    return out;
                }"""
            )
            comm = parse_money(drawer["Commission"])
            fixed = parse_money(drawer["Fixed Fee"])
            gt = parse_money(drawer["GT Charge"])
            ret = parse_money(drawer["Return Fee (Level/Zone)"])
            total = parse_money(drawer["Total Deductions"])
            expected = parse_money(drawer["Expected Settlement"])
            summed = round(comm + fixed + gt + ret, 2)

            if not (comm < 0 and fixed < 0 and gt < 0 and ret < 0):
                raise AssertionError(f"RTO drawer signs wrong for {tid}: comm={comm}, fixed={fixed}, gt={gt}, return={ret}")
            if not near(total, summed):
                raise AssertionError(f"RTO drawer total mismatch for {tid}: total={total}, sum={summed}")
            if not near(table_deductions, total):
                raise AssertionError(f"RTO table/drawer total mismatch for {tid}: table={table_deductions}, drawer={total}")
            if not near(expected, 0):
                raise AssertionError(f"RTO drawer expected settlement should be 0 for {tid}: {expected}")

            evidence["checked_rows"].append({
                "row_testid": tid,
                "table_commission": table_comm,
                "table_fixed_fee": table_fixed,
                "table_gt": table_gt,
                "table_total_deductions": table_deductions,
                "drawer_commission": comm,
                "drawer_fixed_fee": fixed,
                "drawer_gt": gt,
                "drawer_return_fee": ret,
                "component_sum": summed,
                "drawer_total_deductions": total,
                "expected_settlement": expected,
            })
            await page.get_by_test_id("close-drawer").click()
            await page.wait_for_timeout(200)

        # Get error messages using specific selectors
        error_text = await page.evaluate("""() => {
        const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
        return errorElements.map(el => el.textContent).join(", ");
        }""")
        if error_text:
            print(f"Found error message: {error_text}")
            failures.append(f"Unexpected UI error text found: {error_text}")
            status = "failed"
        else:
            print("No error messages found on the page")

        print("UI RTO total deductions verification passed for 5 rows")
    except Exception as e:
        status = "failed"
        failures.append(str(e))
        print(f"UI test failed: {e}")

    result = {
        "status": status,
        "base_url": BASE_URL,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "evidence": evidence,
        "failures": failures,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if status != "passed":
        raise AssertionError("UI verification failed")


await run_ui_check(page)