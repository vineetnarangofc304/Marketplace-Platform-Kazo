"""Playwright fragment used with MCP browser automation for iteration 21 DTO/RTO UI verification.

This file is intentionally a fragment because mcp_browser_automation injects it
inside an async function with `page` already available.
"""

try:
    await page.set_viewport_size({"width": 1920, "height": 1080})

    base_url = "https://settlement-intel-1.preview.emergentagent.com"

    async def goto_retry(url):
        last_error = None
        for attempt in range(3):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                return
            except Exception as exc:
                last_error = exc
                print(f"Navigation retry {attempt + 1} failed: {exc}")
                await page.wait_for_timeout(2000 * (attempt + 1))
        raise last_error

    def money_to_float(text):
        cleaned = text.replace("₹", "").replace(",", "").replace("−", "-").strip()
        if cleaned in ("", "—"):
            return None
        return float(cleaned)

    async def get_calc_rows():
        await page.wait_for_function(
            """() => {
                const drawer = document.querySelector('[data-testid="sales-drawer"]');
                if (!drawer || drawer.innerText.includes('Loading calculation')) return false;
                return Array.from(drawer.querySelectorAll('table tbody tr')).some(tr => tr.innerText.includes('Commission'));
            }""",
            timeout=20000,
        )
        rows = await page.evaluate(
            """() => {
                const drawer = document.querySelector('[data-testid="sales-drawer"]');
                return Array.from(drawer.querySelectorAll('table tbody tr')).map(tr => {
                    const tds = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
                    return [tds[0], tds[1]];
                });
            }"""
        )
        data = {label: money_to_float(value) for label, value in rows}
        drawer_text = await page.locator('[data-testid="sales-drawer"]').inner_text()
        return data, drawer_text, rows

    async def wait_for_first_row(txn_type, status):
        for _ in range(30):
            rows = page.locator('[data-testid^="sales-row-"]')
            count = await rows.count()
            if count > 0:
                cells = await rows.first.evaluate("el => Array.from(el.querySelectorAll('td')).map(td => td.innerText.trim())")
                if len(cells) > 3 and cells[2] == txn_type and cells[3] == status:
                    return rows.first
            await page.wait_for_timeout(500)
        raise AssertionError(f"Timed out waiting for first filtered row txn_type={txn_type}, status={status}")

    # Login flow works with the required admin credential.
    await goto_retry(f"{base_url}/login")
    await page.locator('[data-testid="login-email"]').fill("admin@fundle.ai")
    await page.locator('[data-testid="login-password"]').fill("admin123")
    await page.locator('[data-testid="login-submit"]').click()
    await page.wait_for_url("**/", timeout=20000)
    print("Login flow succeeded")

    # Force Myntra portal for the Sales Ledger route; query param is also kept for the requested flow.
    await page.evaluate("localStorage.setItem('fundle_portal', 'myntra')")
    await goto_retry(f"{base_url}/sales?period_type=month&period_value=2026-04&portal=myntra")
    await page.wait_for_selector('[data-testid="sales-page"]', timeout=30000)
    await page.wait_for_selector('[data-testid="sales-summary"]', timeout=30000)
    await page.wait_for_timeout(1500)
    summary_text = await page.locator('[data-testid="sales-summary"]').inner_text()
    print(f"Sales summary visible: {summary_text}")
    if "6,824" not in summary_text:
        raise AssertionError(f"Expected net orders 6,824 in UI summary, got: {summary_text}")

    # DTO: Return + DTO drawer signs.
    await page.locator('[data-testid="filter-txn"]').select_option("Return")
    await page.locator('[data-testid="filter-status"]').fill("DTO")
    dto_row = await wait_for_first_row("Return", "DTO")
    await dto_row.click()
    dto_data, dto_text, dto_rows = await get_calc_rows()
    print(f"DTO drawer calculation rows: {dto_rows}")
    if not (dto_data["Commission"] < 0 and dto_data["Fixed Fee"] == 0 and dto_data["GT Charge"] < 0 and dto_data["Return Fee (Level/Zone)"] > 0):
        raise AssertionError(f"DTO drawer sign convention failed: {dto_data}")
    if any(label in dto_text for label in ["GST", "TCS", "TDS"]):
        raise AssertionError(f"DTO drawer should not show GST/TCS/TDS lines, text={dto_text}")
    await page.locator('[data-testid="close-drawer"]').click()
    await page.wait_for_selector('[data-testid="sales-drawer"]', state="detached", timeout=10000)
    print("DTO UI drawer signs verified")

    # RTO: Sales + RTO drawer signs and zero settlement totals.
    await page.locator('[data-testid="filter-txn"]').select_option("Sales")
    await page.locator('[data-testid="filter-status"]').fill("RTO")
    rto_row = await wait_for_first_row("Sales", "RTO")
    await rto_row.click()
    rto_data, rto_text, rto_rows = await get_calc_rows()
    print(f"RTO drawer calculation rows: {rto_rows}")
    if not (rto_data["Commission"] < 0 and rto_data["Fixed Fee"] < 0 and rto_data["GT Charge"] < 0 and rto_data["Return Fee (Level/Zone)"] < 0):
        raise AssertionError(f"RTO drawer fee-head sign convention failed: {rto_data}")
    if not (rto_data["Total Deductions"] == 0 and rto_data["Expected Settlement"] == 0):
        raise AssertionError(f"RTO drawer expected zero total deductions/settlement, got: {rto_data}")
    if any(label in rto_text for label in ["GST", "TCS", "TDS"]):
        raise AssertionError(f"RTO drawer should not show GST/TCS/TDS lines, text={rto_text}")
    print("RTO UI drawer signs and zero settlement verified")

    # Get error messages using specific selectors
    error_text = await page.evaluate("""() => {
    const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
    return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
        print(f"Found error message: {error_text}")
    else:
        print("No error messages found on the page")

    print("UI DTO/RTO bug verification passed")
except Exception as exc:
    print(f"UI DTO/RTO bug verification failed: {exc}")
    raise