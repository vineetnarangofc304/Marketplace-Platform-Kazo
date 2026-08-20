"""Reference Playwright flow used for iteration 29 UI verification.

Executed via mcp_browser_automation against preview URL.
Checks Sales Ledger drawer colouring/values for Sales+DTO and Return+DTO.
"""

async def run(page):
    await page.set_viewport_size({"width": 1920, "height": 1080})
    await page.goto("https://settlement-intel-1.preview.emergentagent.com/login", wait_until="networkidle")
    await page.evaluate("localStorage.clear()")
    await page.reload(wait_until="networkidle")
    await page.locator('[data-testid="login-email"]').fill("admin@fundle.ai")
    await page.locator('[data-testid="login-password"]').fill("admin123")
    await page.locator('[data-testid="login-submit"]').click()
    await page.wait_for_url("**/", timeout=15000)

    async def drawer_values():
        return await page.evaluate("""() => {
            const drawer = document.querySelector('[data-testid="sales-drawer"]');
            const calc = {};
            drawer.querySelectorAll('table tbody tr').forEach(tr => {
                const tds = tr.querySelectorAll('td');
                if (tds.length >= 2) calc[tds[0].textContent.trim()] = {value: tds[1].textContent.trim(), className: tds[1].className};
            });
            return {calc, salesText: drawer.innerText};
        }""")

    await page.goto("https://settlement-intel-1.preview.emergentagent.com/sales", wait_until="networkidle")
    await page.locator('[data-testid="filter-txn"]').select_option("Sales")
    await page.locator('[data-testid="filter-status"]').fill("DTO")
    await page.wait_for_timeout(1200)
    await page.locator('tbody tr[data-testid^="sales-row-"]').first.click(force=True)
    dto = await drawer_values()
    assert "Txn Type\nSales" in dto["salesText"] and "Status\nDTO" in dto["salesText"]
    assert "fin-neg" in dto["calc"]["Commission"]["className"] and "-" not in dto["calc"]["Commission"]["value"]
    assert "fin-neg" in dto["calc"]["Fixed Fee"]["className"] and "-" not in dto["calc"]["Fixed Fee"]["value"]
    assert "fin-neg" in dto["calc"]["GT Charge"]["className"] and "-" not in dto["calc"]["GT Charge"]["value"]
    assert dto["calc"]["Return Fee (Level/Zone)"]["value"] == "₹0.00"
    await page.locator('[data-testid="close-drawer"]').click(force=True)

    await page.locator('[data-testid="filter-txn"]').select_option("Return")
    await page.locator('[data-testid="filter-status"]').fill("DTO")
    await page.wait_for_timeout(1200)
    await page.locator('tbody tr[data-testid^="sales-row-"]').first.click(force=True)
    rtd = await drawer_values()
    assert "Txn Type\nReturn" in rtd["salesText"] and "Status\nDTO" in rtd["salesText"]
    assert "fin-pos" in rtd["calc"]["Commission"]["className"] and "-" in rtd["calc"]["Commission"]["value"]
    assert rtd["calc"]["Fixed Fee"]["value"] == "₹0.00"
    assert "fin-pos" in rtd["calc"]["GT Charge"]["className"] and "-" in rtd["calc"]["GT Charge"]["value"]
    assert "fin-neg" in rtd["calc"]["Return Fee (Level/Zone)"]["className"] and "-" not in rtd["calc"]["Return Fee (Level/Zone)"]["value"]