try:
    await page.set_viewport_size({"width": 1920, "height": 1080})
    base = "https://settlement-intel-1.preview.emergentagent.com"

    print("STEP 1: login as admin@fundle.ai")
    await page.goto(base + "/login", wait_until="domcontentloaded")
    await page.evaluate("localStorage.clear()")
    await page.goto(base + "/login", wait_until="domcontentloaded")
    await page.locator('[data-testid="login-email"]').fill("admin@fundle.ai")
    await page.locator('[data-testid="login-password"]').fill("admin123")
    await page.locator('[data-testid="login-submit"]').click()
    await page.locator('[data-testid="overview-page"]').wait_for(timeout=30000)
    print("PASS: login works and overview loaded")

    print("STEP 2: verify Overview net Order Qty KPI and Cross-Portal Snapshot")
    await page.goto(base + "/?period_type=month&period_value=2026-04&portal=myntra", wait_until="domcontentloaded")
    await page.locator('[data-testid="overview-page"]').wait_for(timeout=30000)
    await page.wait_for_function("""() => {
      const sel = document.querySelector('[data-testid="overview-period-value"]');
      return sel && Array.from(sel.options).some(o => o.value === '2026-04');
    }""", timeout=30000)
    await page.locator('[data-testid="overview-period-value"]').select_option("2026-04")
    await page.wait_for_timeout(2500)

    kpi_text = await page.locator('[data-testid="kpi-nsv"]').inner_text(timeout=15000)
    print(f"Observed kpi-nsv text: {kpi_text}")
    if "6,824 Order Qty (net)" not in kpi_text:
        raise AssertionError(f"Total NSV KPI missing net order label: {kpi_text}")
    if "21,614 orders" in kpi_text:
        raise AssertionError(f"Total NSV KPI still shows gross order count: {kpi_text}")

    widget_text = await page.locator('[data-testid="portals-summary-widget"]').inner_text(timeout=15000)
    print(f"Observed Cross-Portal widget text: {widget_text[:500]}")
    if "6,824 Order Qty (net)" not in widget_text or "₹1,27,02,900" not in widget_text:
        raise AssertionError(f"Cross-Portal totals missing required net qty/NSV text: {widget_text}")

    tile_text = await page.locator('[data-testid="portal-tile-myntra"]').inner_text(timeout=15000)
    print(f"Observed Myntra tile text: {tile_text}")
    if "6,824 order qty (net)" not in tile_text.lower():
        raise AssertionError(f"Myntra portal tile missing net order overline: {tile_text}")
    print("PASS: Overview user-visible net order values are correct")

    print("STEP 3: verify Sales Ledger grid columns and DTO reversal values")
    await page.locator('[data-testid="portal-tile-myntra"]').click(force=True)
    await page.wait_for_timeout(500)
    await page.goto(base + "/sales?period_type=month&period_value=2026-04&portal=myntra", wait_until="domcontentloaded")
    await page.locator('[data-testid="sales-page"]').wait_for(timeout=30000)
    await page.wait_for_function("""() => document.querySelector('[data-testid="sales-summary"]')?.innerText.includes('6,824')""", timeout=30000)
    summary_text = await page.locator('[data-testid="sales-summary"]').inner_text()
    print(f"Observed sales summary: {summary_text}")
    if "6,824" not in summary_text or "Order Qty (net)" not in summary_text:
        raise AssertionError(f"Sales summary does not show net order quantity: {summary_text}")

    headers = await page.locator('thead th').all_inner_texts()
    print(f"Observed Sales Ledger headers: {headers}")
    header_norm = [h.strip().lower() for h in headers]
    idx_nsv = next(i for i, h in enumerate(header_norm) if h.startswith("nsv"))
    idx_commission = next(i for i, h in enumerate(header_norm) if h == "commission")
    idx_gt = next(i for i, h in enumerate(header_norm) if h == "gt")
    idx_price = next(i for i, h in enumerate(header_norm) if h == "price range (nsv)")
    if not (idx_nsv < idx_commission < idx_gt < idx_price):
        raise AssertionError(f"Commission/GT columns are not between NSV and Price Range: {headers}")

    dto_order_id = "83410B8C-556E-465B-96A1-EB3A80DB1DF1"
    dto_sales_id = "a752b5cd-e629-42ec-a383-ad1fa5ce9976"
    await page.locator('[data-testid="sales-search"]').fill(dto_order_id)
    await page.wait_for_selector(f'[data-testid="sales-row-{dto_sales_id}"]', timeout=30000)
    await page.wait_for_timeout(1000)
    dto_row = page.locator(f'[data-testid="sales-row-{dto_sales_id}"]')
    dto_cells = await dto_row.locator("td").all_inner_texts()
    print(f"Observed DTO row cells: {dto_cells}")
    if dto_cells[2].strip() != "Return" or dto_cells[3].strip() != "DTO":
        raise AssertionError(f"Expected Return/DTO row, got cells: {dto_cells}")
    if "₹-279.06" not in dto_cells[15] or "₹-207.00" not in dto_cells[16]:
        raise AssertionError(f"DTO grid Commission/GT are not visibly negative: {dto_cells}")

    await dto_row.click(force=True)
    await page.locator('[data-testid="sales-drawer"]').wait_for(timeout=15000)
    await page.wait_for_function("""() => document.querySelector('[data-testid="sales-drawer"]')?.innerText.toLowerCase().includes('expected calculation')""", timeout=30000)
    drawer_text = await page.locator('[data-testid="sales-drawer"]').inner_text()
    print(f"Observed DTO drawer text snippet: {drawer_text[:600]}")
    if "Commission" not in drawer_text or "₹-279.06" not in drawer_text or "GT Charge" not in drawer_text or "₹-207.00" not in drawer_text:
        raise AssertionError("DTO drawer does not show expected negative Commission/GT reversal values")
    await page.locator('[data-testid="close-drawer"]').click(force=True)
    await page.wait_for_timeout(300)

    sales_order_id = "BA030AAB-E147-4FA2-847F-8B119D06AEC1"
    sales_id = "3fc2c0d5-aca8-448a-91ae-51ecd5e58438"
    await page.locator('[data-testid="sales-search"]').fill(sales_order_id)
    await page.wait_for_selector(f'[data-testid="sales-row-{sales_id}"]', timeout=30000)
    await page.wait_for_timeout(1000)
    sales_row = page.locator(f'[data-testid="sales-row-{sales_id}"]')
    sales_cells = await sales_row.locator("td").all_inner_texts()
    print(f"Observed Sales row cells: {sales_cells}")
    if sales_cells[2].strip() != "Sales":
        raise AssertionError(f"Expected Sales row, got cells: {sales_cells}")
    if "₹871.36" not in sales_cells[15] or "₹266.00" not in sales_cells[16] or "₹-" in sales_cells[15] or "₹-" in sales_cells[16]:
        raise AssertionError(f"Sales grid Commission/GT are not visibly positive: {sales_cells}")
    print("PASS: Sales Ledger grid shows Commission/GT columns and correct DTO vs Sales signs")

    error_text = await page.evaluate("""() => {
      const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
      return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
        print(f"Found error message: {error_text}")
        raise AssertionError(f"Unexpected error text found: {error_text}")
    else:
        print("No error messages found on the page")

    print("UI_VERDICT: passed")
except Exception as e:
    print(f"UI_VERDICT: failed: {e}")
    raise