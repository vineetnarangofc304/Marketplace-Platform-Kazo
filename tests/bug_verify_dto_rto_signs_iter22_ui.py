"""Playwright fragment for focused DTO/RTO UI verification (iteration 22).

Executed by mcp_browser_automation, which injects this into an async function
with a Playwright `page` object. Preview URL only; production is explicitly
blocked by assertions.
"""

try:
    await page.set_viewport_size({"width": 1920, "height": 1080})
    base_url = "https://marketplace-recon-1.preview.emergentagent.com"
    assert "kazob2b.fundlezone.com" not in base_url, "Refusing to test production URL"

    seen_urls = []
    page.on("request", lambda request: seen_urls.append(request.url))

    async def goto_retry(url):
        assert "kazob2b.fundlezone.com" not in url, "Refusing to test production URL"
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

    async def get_drawer_calc_rows(label):
        await page.wait_for_function(
            """() => {
                const drawer = document.querySelector('[data-testid="sales-drawer"]');
                if (!drawer || drawer.innerText.includes('Loading calculation')) return false;
                return Array.from(drawer.querySelectorAll('table tbody tr')).some(tr => tr.innerText.includes('Commission'));
            }""",
            timeout=25000,
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
        data = {row[0]: money_to_float(row[1]) for row in rows}
        drawer_text = await page.locator('[data-testid="sales-drawer"]').inner_text()
        print(f"{label} drawer rows: {rows}")
        return data, drawer_text, rows

    async def wait_for_first_filtered_row(txn_type, status):
        for _ in range(40):
            rows = page.locator('[data-testid^="sales-row-"]')
            count = await rows.count()
            if count > 0:
                cells = await rows.first.evaluate("el => Array.from(el.querySelectorAll('td')).map(td => td.innerText.trim())")
                if len(cells) > 3 and cells[2] == txn_type and cells[3] == status:
                    print(f"First filtered row found for {txn_type}+{status}: {cells[:6]}")
                    return rows.first
            await page.wait_for_timeout(500)
        raise AssertionError(f"Timed out waiting for first filtered row txn_type={txn_type}, status={status}")

    # Login with required admin credential.
    await goto_retry(f"{base_url}/login")
    await page.locator('[data-testid="login-email"]').fill("admin@fundle.ai")
    await page.locator('[data-testid="login-password"]').fill("admin123")
    await page.locator('[data-testid="login-submit"]').click()
    await page.wait_for_url("**/", timeout=25000)
    print("Login flow succeeded")

    # Force the requested Myntra portal and reload into the requested Sales Ledger URL.
    await page.evaluate("localStorage.setItem('fundle_portal', 'myntra')")
    await goto_retry(f"{base_url}/sales?period_type=month&period_value=2026-04&portal=myntra")
    await page.wait_for_selector('[data-testid="sales-page"]', timeout=30000)
    await page.wait_for_selector('[data-testid="sales-summary"]', timeout=30000)
    await page.wait_for_timeout(1500)
    summary_text = await page.locator('[data-testid="sales-summary"]').inner_text()
    print(f"Sales summary: {summary_text}")
    if "6,824" not in summary_text:
        raise AssertionError(f"Expected UI summary net orders 6,824, got: {summary_text}")

    # DTO UI: Return + DTO must show commission negative, fixed fee ₹0.00, GT negative, return fee positive.
    await page.locator('[data-testid="filter-txn"]').select_option("Return")
    await page.locator('[data-testid="filter-status"]').fill("DTO")
    dto_row = await wait_for_first_filtered_row("Return", "DTO")
    await dto_row.click()
    dto_data, dto_text, _ = await get_drawer_calc_rows("DTO")
    if not (dto_data.get("Commission") < 0 and dto_data.get("Fixed Fee") == 0 and dto_data.get("GT Charge") < 0 and dto_data.get("Return Fee (Level/Zone)") > 0):
        raise AssertionError(f"DTO drawer Point 2.1 signs failed: {dto_data}")
    if any(label in dto_text for label in ["GST", "TCS", "TDS"]):
        raise AssertionError(f"DTO drawer should not show GST/TCS/TDS rows, text={dto_text}")
    print("DTO drawer Point 2.1 verified")
    await page.locator('[data-testid="close-drawer"]').click()
    await page.wait_for_selector('[data-testid="sales-drawer"]', state="detached", timeout=10000)

    # RTO UI: Sales + RTO must show all four fee heads negative and zero totals/settlement.
    await page.locator('[data-testid="filter-txn"]').select_option("Sales")
    await page.locator('[data-testid="filter-status"]').fill("RTO")
    rto_row = await wait_for_first_filtered_row("Sales", "RTO")
    await rto_row.click()
    rto_data, rto_text, _ = await get_drawer_calc_rows("RTO")
    if not (rto_data.get("Commission") < 0 and rto_data.get("Fixed Fee") < 0 and rto_data.get("GT Charge") < 0 and rto_data.get("Return Fee (Level/Zone)") < 0):
        raise AssertionError(f"RTO drawer Point 2.2 fee-head signs failed: {rto_data}")
    if not (rto_data.get("Total Deductions") == 0 and rto_data.get("Expected Settlement") == 0):
        raise AssertionError(f"RTO drawer expected Total Deductions/Expected Settlement ₹0.00, got: {rto_data}")
    if any(label in rto_text for label in ["GST", "TCS", "TDS"]):
        raise AssertionError(f"RTO drawer should not show GST/TCS/TDS rows, text={rto_text}")
    print("RTO drawer Point 2.2 verified")

    prod_calls = [u for u in seen_urls if "kazob2b.fundlezone.com" in u]
    if prod_calls:
        raise AssertionError(f"Unexpected production URL calls detected: {prod_calls[:5]}")

    # Get error messages using specific selectors
    error_text = await page.evaluate("""() => {
    const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
    return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
        print(f"Found error message: {error_text}")
    else:
        print("No error messages found on the page")

    print("UI DTO/RTO preview verification passed")
except Exception as exc:
    print(f"UI DTO/RTO preview verification failed: {exc}")
    raise