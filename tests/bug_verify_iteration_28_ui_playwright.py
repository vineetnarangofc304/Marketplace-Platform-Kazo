# Playwright body used with mcp_browser_automation for iteration 28 UI spot-check.
# Verifies one sale_dto calculation drawer displays DTO signs and a total matching
# the four displayed fee heads.

try:
    await page.set_viewport_size({"width": 1920, "height": 1080})
    base_url = "https://settlement-intel-1.preview.emergentagent.com"
    sample_order_id = "BA030AAB-E147-4FA2-847F-8B119D06AEC1"
    print("Opening login page")
    await page.goto(f"{base_url}/login", wait_until="networkidle")

    if await page.locator('[data-testid="login-form"]').is_visible():
        print("Logging in with test admin")
        await page.locator('[data-testid="login-email"]').fill("admin@fundle.ai")
        await page.locator('[data-testid="login-password"]').fill("admin123")
        await page.locator('[data-testid="login-submit"]').click()
        await page.wait_for_url(lambda url: "/login" not in url, timeout=20000)
        print("Login succeeded")
    else:
        print("Login form not visible; existing session likely active")

    target_url = f"{base_url}/calculations?order_type=sale_dto&search={sample_order_id}"
    print(f"Opening focused calculations URL: {target_url}")
    await page.goto(target_url, wait_until="networkidle")
    await page.wait_for_selector('[data-testid="calculations-page"]', timeout=20000)
    await page.wait_for_function("""() => document.querySelectorAll('tr[data-testid^="calc-row-"]').length > 0""", timeout=20000)
    rows_count_text = await page.locator('[data-testid="calculations-page"] p').first.text_content()
    print(f"Calculations count text: {rows_count_text}")

    first_row = page.locator('tr[data-testid^="calc-row-"]').first
    row_text = await first_row.text_content()
    print(f"Focused sale_dto table row: {row_text}")
    await first_row.click()
    await page.wait_for_selector('[data-testid="calc-drawer"]', timeout=20000)
    await page.wait_for_timeout(500)

    drawer_rows = await page.evaluate("""() => {
        const drawer = document.querySelector('[data-testid="calc-drawer"]');
        const rows = Array.from(drawer.querySelectorAll('table tr'));
        return rows.map(tr => {
            const cells = Array.from(tr.querySelectorAll('td'));
            return {
                label: (cells[0]?.textContent || '').trim(),
                value: (cells[1]?.textContent || '').trim(),
                valueClass: cells[1]?.className || ''
            };
        });
    }""")
    print(f"Drawer expected charges rows: {drawer_rows}")

    def money_to_float(text):
        return float(text.replace("₹", "").replace(",", "").strip())

    values = {r["label"]: {"value": money_to_float(r["value"]), "class": r["valueClass"]} for r in drawer_rows if r.get("label") and r.get("value", "").startswith("₹")}
    commission = values["Commission"]["value"]
    fixed_fee = values["Fixed Fee"]["value"]
    gt_charge = values["GT Charge"]["value"]
    return_fee = values["Return Fee (Level/Zone)"]["value"]
    total = values["Total Deductions"]["value"]
    settlement = values["Expected Settlement"]["value"]
    computed_total = round(commission + fixed_fee + gt_charge + return_fee, 2)

    assert commission < 0, "UI commission is not negative for sale_dto"
    assert fixed_fee == 0, "UI fixed fee is not zero for sale_dto"
    assert gt_charge < 0, "UI GT charge is not negative for sale_dto"
    assert return_fee > 0, "UI return fee is not positive for sale_dto"
    assert settlement == 0, "UI expected settlement is not zero for sale_dto"
    assert total == computed_total, f"UI total {total} != displayed fee sum {computed_total}"
    assert "fin-pos" in values["Commission"]["class"], "UI commission negative reversal lacks fin-pos class"
    assert "fin-pos" in values["GT Charge"]["class"], "UI GT negative reversal lacks fin-pos class"
    assert "fin-neg" in values["Return Fee (Level/Zone)"]["class"], "UI return fee positive charge lacks fin-neg class"
    print("UI sale_dto drawer signs and displayed total arithmetic passed")

    # Get error messages using specific selectors
    error_text = await page.evaluate("""() => {
    const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
    return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
        print(f"Found error message: {error_text}")
    else:
        print("No error messages found on the page")

except Exception as e:
    print(f"UI sale_dto spot-check failed: {e}")
    raise