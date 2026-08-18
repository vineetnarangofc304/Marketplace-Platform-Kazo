import re


BASE_URL = "https://settlement-intel-1.preview.emergentagent.com"


def parse_money(text):
    cleaned = re.sub(r"[^0-9.\-]", "", text or "")
    return float(cleaned) if cleaned not in ("", "-", ".") else 0.0


async def run(page):
    try:
        await page.set_viewport_size({"width": 1920, "height": 1080})
        print("Step 1: Open preview login")
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle")

        if await page.get_by_test_id("login-form").is_visible():
            await page.get_by_test_id("login-email").fill("admin@fundle.ai")
            await page.get_by_test_id("login-password").fill("admin123")
            await page.get_by_test_id("login-submit").click()
            await page.wait_for_url(lambda url: not url.endswith("/login"), timeout=15000)
            print("Step 1 PASS: login succeeded")
        else:
            print("Step 1 PASS: already authenticated")

        await page.evaluate("localStorage.setItem('fundle_portal', 'myntra')")
        await page.goto(f"{BASE_URL}/", wait_until="networkidle")
        print("Step 1B PASS: portal context pinned to myntra for UI verification")

        async def api_first(order_type):
            return await page.evaluate(
                """async (orderType) => {
                    const token = localStorage.getItem('kazo_token');
                    const res = await fetch(`/api/calculations?portal=myntra&order_type=${orderType}&limit=5&sort_by=settlement&sort_dir=desc`, {
                        headers: token ? { Authorization: `Bearer ${token}` } : {}
                    });
                    if (!res.ok) throw new Error(`API ${orderType} failed ${res.status}`);
                    const data = await res.json();
                    return data.items[0];
                }""",
                order_type,
            )

        async def verify_calculations_page(order_type):
            print(f"Step 2: Verify Calculations table for {order_type}")
            await page.goto(f"{BASE_URL}/calculations?order_type={order_type}", wait_until="networkidle")
            await page.wait_for_selector('[data-testid="calculations-page"]', timeout=15000)
            await page.wait_for_function("document.querySelectorAll('tr[data-testid^=\"calc-row-\"]').length >= 5", timeout=15000)
            rows = await page.evaluate(
                """() => Array.from(document.querySelectorAll('tr[data-testid^="calc-row-"]')).slice(0, 5).map(tr =>
                    Array.from(tr.querySelectorAll('td')).map(td => td.textContent.trim()))"""
            )
            for idx, cells in enumerate(rows):
                commission = parse_money(cells[5])
                fixed_fee = parse_money(cells[6])
                gt_charge = parse_money(cells[7])
                if order_type == "return_dto":
                    assert commission < 0, f"DTO row {idx+1} commission not negative: {cells[5]}"
                    assert fixed_fee == 0, f"DTO row {idx+1} fixed fee not zero: {cells[6]}"
                    assert gt_charge < 0, f"DTO row {idx+1} GT not negative: {cells[7]}"
                else:
                    assert commission < 0, f"RTO row {idx+1} commission not negative: {cells[5]}"
                    assert fixed_fee < 0, f"RTO row {idx+1} fixed fee not negative: {cells[6]}"
                    assert gt_charge < 0, f"RTO row {idx+1} GT not negative: {cells[7]}"
            print(f"Step 2 PASS: Calculations table first 5 {order_type} rows have expected commission/fixed/GT signs")

            print(f"Step 3: Verify Calculations drawer for {order_type}")
            await page.locator('tr[data-testid^="calc-row-"]').first.click()
            await page.wait_for_selector('[data-testid="calc-drawer"]', timeout=15000)
            await page.wait_for_function("document.querySelector('[data-testid=\"calc-drawer\"]')?.innerText.includes('Commission')", timeout=15000)
            drawer = await page.evaluate(
                """() => {
                    const out = {};
                    for (const tr of document.querySelectorAll('[data-testid="calc-drawer"] table tr')) {
                        const tds = Array.from(tr.querySelectorAll('td')).map(td => td.textContent.trim());
                        if (tds.length >= 2) out[tds[0]] = tds[1];
                    }
                    return out;
                }"""
            )
            assert parse_money(drawer["Commission"]) < 0, f"{order_type} drawer commission sign wrong: {drawer}"
            assert parse_money(drawer["GT Charge"]) < 0, f"{order_type} drawer GT sign wrong: {drawer}"
            if order_type == "return_dto":
                assert parse_money(drawer["Fixed Fee"]) == 0, f"DTO drawer fixed fee not zero: {drawer}"
                assert parse_money(drawer["Return Fee (Level/Zone)"]) > 0, f"DTO drawer return fee not positive: {drawer}"
            else:
                assert parse_money(drawer["Fixed Fee"]) < 0, f"RTO drawer fixed fee not negative: {drawer}"
                assert parse_money(drawer["Return Fee (Level/Zone)"]) < 0, f"RTO drawer return fee not negative: {drawer}"
            await page.get_by_test_id("close-drawer").click()
            await page.wait_for_selector('[data-testid="calc-drawer"]', state="detached", timeout=10000)
            print(f"Step 3 PASS: Calculations drawer {order_type} signs match spec: {drawer}")

        async def verify_sales_drawer(order_type):
            sample = await api_first(order_type)
            print(f"Step 4: Verify Sales Ledger drawer for {order_type} order {sample['online_order_id']}")
            await page.goto(f"{BASE_URL}/sales", wait_until="networkidle")
            await page.wait_for_selector('[data-testid="sales-page"]', timeout=15000)
            await page.get_by_test_id("sales-search").fill(sample["online_order_id"])
            await page.wait_for_timeout(700)
            await page.wait_for_function("document.querySelectorAll('tr[data-testid^=\"sales-row-\"]').length >= 1", timeout=15000)
            await page.locator('tr[data-testid^="sales-row-"]').first.click()
            await page.wait_for_selector('[data-testid="sales-drawer"]', timeout=15000)
            await page.wait_for_function("document.querySelectorAll('[data-testid=\"sales-drawer\"] table tr').length >= 6", timeout=15000)
            drawer = await page.evaluate(
                """() => {
                    const out = {};
                    for (const tr of document.querySelectorAll('[data-testid="sales-drawer"] table tr')) {
                        const tds = Array.from(tr.querySelectorAll('td')).map(td => td.textContent.trim());
                        if (tds.length >= 2) out[tds[0]] = tds[1];
                    }
                    return out;
                }"""
            )
            assert parse_money(drawer["Commission"]) < 0, f"Sales drawer {order_type} commission sign wrong: {drawer}"
            assert parse_money(drawer["GT Charge"]) < 0, f"Sales drawer {order_type} GT sign wrong: {drawer}"
            if order_type == "return_dto":
                assert parse_money(drawer["Fixed Fee"]) == 0, f"Sales drawer DTO fixed fee not zero: {drawer}"
                assert parse_money(drawer["Return Fee (Level/Zone)"]) > 0, f"Sales drawer DTO return fee not positive: {drawer}"
            else:
                assert parse_money(drawer["Fixed Fee"]) < 0, f"Sales drawer RTO fixed fee not negative: {drawer}"
                assert parse_money(drawer["Return Fee (Level/Zone)"]) < 0, f"Sales drawer RTO return fee not negative: {drawer}"
            await page.get_by_test_id("close-drawer").click()
            await page.wait_for_selector('[data-testid="sales-drawer"]', state="detached", timeout=10000)
            print(f"Step 4 PASS: Sales Ledger drawer {order_type} signs match spec: {drawer}")

        await verify_calculations_page("return_dto")
        await verify_calculations_page("rto")
        await verify_sales_drawer("return_dto")
        await verify_sales_drawer("rto")

        error_text = await page.evaluate("""() => {
        const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
        return errorElements.map(el => el.textContent).join(", ");
        }""")
        if error_text:
            print(f"Found error message: {error_text}")
        else:
            print("No error messages found on the page")
        print("UI VERDICT: PASS")
    except Exception as e:
        error_text = await page.evaluate("""() => {
        const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
        return errorElements.map(el => el.textContent).join(", ");
        }""")
        if error_text:
            print(f"Found error message: {error_text}")
        else:
            print("No error messages found on the page")
        print(f"UI VERDICT: FAIL - {e}")
        raise