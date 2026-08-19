"""Playwright steps for focused UI verification of sale_dto DTO signs.

This file mirrors the script sent to the browser automation tool. It assumes an
async Playwright `page` object is already available.
"""

BASE_URL = "https://settlement-intel-1.preview.emergentagent.com"

async def run(page):
    await page.set_viewport_size({"width": 1920, "height": 1080})
    await page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
    await page.evaluate("localStorage.setItem('fundle_portal', 'myntra')")
    await page.get_by_test_id("login-email").fill("admin@fundle.ai")
    await page.get_by_test_id("login-password").fill("admin123")
    await page.get_by_test_id("login-submit").click()
    await page.wait_for_load_state("networkidle")

    async def drawer_rows(test_id):
        return await page.evaluate(
            """(testId) => {
              const drawer = document.querySelector(`[data-testid="${testId}"]`);
              if (!drawer) return null;
              const rows = Array.from(drawer.querySelectorAll('tr'));
              const out = {};
              for (const tr of rows) {
                const cells = Array.from(tr.querySelectorAll('td'));
                if (cells.length >= 2) {
                  out[cells[0].textContent.trim()] = {
                    value: cells[1].textContent.trim(),
                    className: cells[1].className
                  };
                }
              }
              const detail = {};
              for (const div of Array.from(drawer.querySelectorAll('.grid.grid-cols-2 > div'))) {
                const spans = div.querySelectorAll('span');
                if (spans.length >= 2) detail[spans[0].textContent.trim()] = spans[1].textContent.trim();
              }
              return {rows: out, detail};
            }""",
            test_id,
        )

    def check_sale_dto_signs(data, context):
        rows = data["rows"]
        required = ["Commission", "Fixed Fee", "GT Charge", "Return Fee (Level/Zone)", "Expected Settlement"]
        missing = [r for r in required if r not in rows]
        assert not missing, f"{context}: missing drawer rows {missing}; got {list(rows.keys())}"
        assert "₹-" in rows["Commission"]["value"] and "fin-pos" in rows["Commission"]["className"], f"{context}: Commission not green negative: {rows['Commission']}"
        assert rows["Fixed Fee"]["value"] == "₹0.00" and "fin-pos" not in rows["Fixed Fee"]["className"] and "fin-neg" not in rows["Fixed Fee"]["className"], f"{context}: Fixed Fee not neutral zero: {rows['Fixed Fee']}"
        assert "₹-" in rows["GT Charge"]["value"] and "fin-pos" in rows["GT Charge"]["className"], f"{context}: GT not green negative: {rows['GT Charge']}"
        assert "₹-" not in rows["Return Fee (Level/Zone)"]["value"] and rows["Return Fee (Level/Zone)"]["value"] != "₹0.00" and "fin-neg" in rows["Return Fee (Level/Zone)"]["className"], f"{context}: Return Fee not red positive: {rows['Return Fee (Level/Zone)']}"
        assert rows["Expected Settlement"]["value"] == "₹0.00", f"{context}: Expected Settlement not zero: {rows['Expected Settlement']}"

    # Sales Ledger: filter to DTO + Sales, open row drawer.
    await page.goto(f"{BASE_URL}/sales?period_type=month&period_value=2026-04", wait_until="domcontentloaded")
    await page.wait_for_selector('[data-testid="sales-page"]')
    await page.get_by_test_id("filter-status").fill("DTO")
    await page.get_by_test_id("filter-txn").select_option("Sales")
    await page.wait_for_timeout(1000)
    await page.locator('tr[data-testid^="sales-row-"]').first.click()
    await page.wait_for_selector('[data-testid="sales-drawer"]')
    sales_drawer = await drawer_rows("sales-drawer")
    assert sales_drawer["detail"].get("Status") == "DTO", f"Sales drawer status wrong: {sales_drawer['detail']}"
    assert sales_drawer["detail"].get("Txn Type") == "Sales", f"Sales drawer txn wrong: {sales_drawer['detail']}"
    check_sale_dto_signs(sales_drawer, "Sales Ledger sale_dto")
    await page.get_by_test_id("close-drawer").click()

    # Calculations page: order_type=sale_dto from query string, open drawer.
    await page.goto(f"{BASE_URL}/calculations?period_type=month&period_value=2026-04&order_type=sale_dto", wait_until="domcontentloaded")
    await page.wait_for_selector('[data-testid="calculations-page"]')
    await page.wait_for_selector('tr[data-testid^="calc-row-"]')
    await page.locator('tr[data-testid^="calc-row-"]').first.click()
    await page.wait_for_selector('[data-testid="calc-drawer"]')
    calc_drawer = await drawer_rows("calc-drawer")
    assert calc_drawer["detail"].get("Order Status") == "DTO", f"Calc drawer status wrong: {calc_drawer['detail']}"
    check_sale_dto_signs(calc_drawer, "Calculations sale_dto")

    print({"ok": True, "sales_drawer": sales_drawer, "calc_drawer": calc_drawer})