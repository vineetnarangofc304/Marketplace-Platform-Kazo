"""
Focused Playwright test for the DTO/RTO value-driven finance colour fix.

Run context: the browser automation harness executes the body of this script
inside an async function with an existing `page` object.
"""

import re


def _numeric(text):
    return float(re.sub(r"[^0-9.\-]", "", text))


async def assert_colour_cell(page, row_selector, cell_index, expected_class, label):
    cell = await page.evaluate(
        """({rowSelector, cellIndex}) => {
            const row = document.querySelector(rowSelector);
            if (!row) throw new Error(`Missing row ${rowSelector}`);
            const cell = row.querySelectorAll('td')[cellIndex];
            if (!cell) throw new Error(`Missing cell ${cellIndex}`);
            return {
              text: cell.textContent.trim(),
              className: cell.className,
              color: getComputedStyle(cell).color
            };
        }""",
        {"rowSelector": row_selector, "cellIndex": cell_index},
    )
    print(f"{label}: {cell}")
    if expected_class:
        assert expected_class in cell["className"], f"{label} expected {expected_class}, got {cell}"
    else:
        assert "fin-pos" not in cell["className"] and "fin-neg" not in cell["className"], f"{label} expected neutral, got {cell}"
    return cell


async def drawer_values(page, drawer_testid):
    await page.wait_for_selector(f'[data-testid="{drawer_testid}"] table tbody tr', timeout=15000)
    await page.wait_for_timeout(500)
    rows = await page.evaluate(
        """(drawerTestId) => {
            const drawer = document.querySelector(`[data-testid="${drawerTestId}"]`);
            if (!drawer) throw new Error(`Missing drawer ${drawerTestId}`);
            const out = {};
            for (const tr of drawer.querySelectorAll('table tbody tr')) {
              const cells = tr.querySelectorAll('td');
              if (cells.length >= 2) {
                const k = cells[0].textContent.trim();
                out[k] = {
                  value: cells[1].textContent.trim(),
                  className: cells[1].className,
                  color: getComputedStyle(cells[1]).color
                };
              }
            }
            return out;
        }""",
        drawer_testid,
    )
    print(f"{drawer_testid} values: {rows}")
    return rows


async def assert_drawer_class(rows, label, expected_class, description):
    assert label in rows, f"Missing drawer row {label}. Available: {list(rows)}"
    row = rows[label]
    print(f"{description}: {row}")
    if expected_class:
        assert expected_class in row["className"], f"{description} expected {expected_class}, got {row}"
    else:
        assert "fin-pos" not in row["className"] and "fin-neg" not in row["className"], f"{description} expected neutral, got {row}"
    return row


try:
    await page.set_viewport_size({"width": 1920, "height": 1080})
    base_url = "https://settlement-intel-1.preview.emergentagent.com"
    dto_order_id = "C1256672-9678-4D76-8486-6DAE59C0CAA8"

    print("Step 1: log in as admin@fundle.ai")
    await page.goto(f"{base_url}/login", wait_until="networkidle")
    if await page.locator('[data-testid="login-form"]').is_visible(timeout=5000):
        await page.fill('[data-testid="login-email"]', "admin@fundle.ai")
        await page.fill('[data-testid="login-password"]', "admin123")
        await page.click('[data-testid="login-submit"]')
    await page.wait_for_selector('[data-testid="nav-calculations"]', timeout=20000)

    print("Step 2: set portal to Myntra")
    try:
        await page.wait_for_function("document.querySelector('[data-testid=portal-switcher-select] option[value=myntra]')", timeout=10000)
        await page.select_option('[data-testid="portal-switcher-select"]', "myntra")
        await page.wait_for_timeout(700)
    except Exception as e:
        print(f"Portal select fallback via localStorage: {e}")
        await page.evaluate("localStorage.setItem('fundle_portal', 'myntra')")
        await page.reload(wait_until="networkidle")
        await page.wait_for_selector('[data-testid="nav-calculations"]', timeout=15000)

    print("Step 3: calculations DTO table colour semantics")
    await page.goto(f"{base_url}/calculations?order_type=return_dto", wait_until="networkidle")
    await page.wait_for_selector('[data-testid="calculations-page"]', timeout=15000)
    await page.wait_for_selector('tr[data-testid^="calc-row-"]', timeout=20000)
    dto_row = 'tr[data-testid^="calc-row-"]'
    await assert_colour_cell(page, dto_row, 5, "fin-pos", "DTO Commission negative reversal is green")
    await assert_colour_cell(page, dto_row, 6, "", "DTO Fixed Fee zero is neutral")
    await assert_colour_cell(page, dto_row, 7, "fin-pos", "DTO GT negative reversal is green")
    dto_total = await assert_colour_cell(page, dto_row, 8, "fin-neg", "DTO positive Total Deductions is red")
    assert _numeric(dto_total["text"]) > 0, f"DTO sample total should be positive for this assertion: {dto_total}"
    dto_settlement = await assert_colour_cell(page, dto_row, 9, "fin-neg", "DTO negative Expected Settlement is red")
    assert _numeric(dto_settlement["text"]) < 0, f"DTO sample settlement should be negative for this assertion: {dto_settlement}"

    print("Step 4: calculations DTO drawer colour semantics")
    await page.click(dto_row, force=True)
    dto_drawer = await drawer_values(page, "calc-drawer")
    await assert_drawer_class(dto_drawer, "Commission", "fin-pos", "DTO drawer commission negative is green")
    await assert_drawer_class(dto_drawer, "Fixed Fee", "", "DTO drawer fixed fee zero is neutral")
    await assert_drawer_class(dto_drawer, "GT Charge", "fin-pos", "DTO drawer GT negative is green")
    await assert_drawer_class(dto_drawer, "Return Fee (Level/Zone)", "fin-neg", "DTO drawer return fee positive charge is red")
    await assert_drawer_class(dto_drawer, "Total Deductions", "fin-neg", "DTO drawer positive total deductions is red")
    await assert_drawer_class(dto_drawer, "Expected Settlement", "fin-neg", "DTO drawer negative settlement is red")
    await page.click('[data-testid="close-drawer"]', force=True)

    print("Step 5: RTO regression table + drawer colour semantics")
    await page.goto(f"{base_url}/calculations?order_type=rto", wait_until="networkidle")
    await page.wait_for_selector('tr[data-testid^="calc-row-"]', timeout=20000)
    rto_row = 'tr[data-testid^="calc-row-"]'
    await assert_colour_cell(page, rto_row, 5, "fin-pos", "RTO Commission negative is green")
    await assert_colour_cell(page, rto_row, 6, "fin-pos", "RTO Fixed Fee negative is green")
    await assert_colour_cell(page, rto_row, 7, "fin-pos", "RTO GT negative is green")
    await assert_colour_cell(page, rto_row, 8, "fin-pos", "RTO Total Deductions negative is green")
    await assert_colour_cell(page, rto_row, 9, "", "RTO Expected Settlement zero is neutral")
    await page.click(rto_row, force=True)
    rto_drawer = await drawer_values(page, "calc-drawer")
    await assert_drawer_class(rto_drawer, "Return Fee (Level/Zone)", "fin-pos", "RTO drawer return fee negative is green")
    await assert_drawer_class(rto_drawer, "Expected Settlement", "", "RTO drawer zero settlement is neutral")
    await page.click('[data-testid="close-drawer"]', force=True)

    print("Step 6: sales-type calculations still show positive charges in red")
    await page.goto(f"{base_url}/calculations?order_type=sales", wait_until="networkidle")
    await page.wait_for_selector('tr[data-testid^="calc-row-"]', timeout=20000)
    sales_calc_row = 'tr[data-testid^="calc-row-"]'
    await assert_colour_cell(page, sales_calc_row, 5, "fin-neg", "Sales Commission positive charge is red")
    await assert_colour_cell(page, sales_calc_row, 6, "fin-neg", "Sales Fixed Fee positive charge is red")
    await assert_colour_cell(page, sales_calc_row, 7, "fin-neg", "Sales GT positive charge is red")
    await assert_colour_cell(page, sales_calc_row, 8, "fin-neg", "Sales Total Deductions positive is red")
    await assert_colour_cell(page, sales_calc_row, 9, "fin-pos", "Sales positive Expected Settlement is green")

    print("Step 7: Sales Ledger DTO row + drawer colour semantics")
    await page.goto(f"{base_url}/sales", wait_until="networkidle")
    await page.wait_for_selector('[data-testid="sales-page"]', timeout=15000)
    await page.fill('[data-testid="sales-search"]', dto_order_id)
    await page.wait_for_timeout(1200)
    await page.wait_for_selector('tr[data-testid^="sales-row-"]', timeout=20000)
    await assert_colour_cell(page, 'tr[data-testid^="sales-row-"]', 15, "fin-pos", "Sales Ledger DTO table commission negative is green")
    await assert_colour_cell(page, 'tr[data-testid^="sales-row-"]', 16, "fin-pos", "Sales Ledger DTO table GT negative is green")
    await page.click('tr[data-testid^="sales-row-"]', force=True)
    sales_drawer = await drawer_values(page, "sales-drawer")
    await assert_drawer_class(sales_drawer, "Commission", "fin-pos", "Sales Ledger DTO drawer commission negative is green")
    await assert_drawer_class(sales_drawer, "Fixed Fee", "", "Sales Ledger DTO drawer fixed fee zero is neutral")
    await assert_drawer_class(sales_drawer, "GT Charge", "fin-pos", "Sales Ledger DTO drawer GT negative is green")
    await assert_drawer_class(sales_drawer, "Return Fee (Level/Zone)", "fin-neg", "Sales Ledger DTO drawer return fee positive is red")

    error_text = await page.evaluate("""() => {
      const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
      return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
        print(f"Found error message: {error_text}")
    else:
        print("No error messages found on the page")

    print("PASS: DTO/RTO/sales value-driven finance colour semantics verified end-to-end in UI")
except Exception as e:
    print(f"FAIL: DTO colour verification failed: {e}")
    await page.screenshot(path="/app/test_reports/dto_colour_failure.jpg", quality=40, full_page=False)
    raise