"""Playwright script used via browser automation for focused RTO/DTO UI verification.

This file records the exact browser checks run by the testing agent:
- Login as admin@fundle.ai.
- Open /calculations?order_type=rto and verify drawer fee signs and Return Fee ₹0.00.
- Search a known DTO order in Sales Ledger and verify drawer fee signs/colors.
"""

SCRIPT = r'''
try:
    await page.set_viewport_size({"width": 1920, "height": 1080})
    await page.wait_for_load_state("domcontentloaded")
    await page.evaluate("localStorage.setItem('fundle_portal', 'myntra')")
    if await page.locator('[data-testid="login-form"]').is_visible():
        await page.locator('[data-testid="login-email"]').fill('admin@fundle.ai')
        await page.locator('[data-testid="login-password"]').fill('admin123')
        await page.locator('[data-testid="login-submit"]').click()
        await page.wait_for_url(lambda url: not url.endswith('/login'), timeout=15000)

    await page.goto('https://settlement-intel-1.preview.emergentagent.com/calculations?order_type=rto')
    await page.wait_for_selector('[data-testid="calculations-page"]', timeout=15000)
    await page.wait_for_selector('tr[data-testid^="calc-row-"]', timeout=20000)
    await page.locator('tr[data-testid^="calc-row-"]').first.click()
    await page.wait_for_selector('[data-testid="calc-drawer"]', timeout=15000)
    rto_charges = await page.evaluate("""() => {
        const drawer = document.querySelector('[data-testid="calc-drawer"]');
        const rows = Array.from(drawer.querySelectorAll('tr'));
        const out = {};
        for (const tr of rows) {
            const cells = Array.from(tr.querySelectorAll('td'));
            if (cells.length >= 2) out[cells[0].textContent.trim()] = {text: cells[1].textContent.trim(), className: cells[1].className};
        }
        return out;
    }""")
    assert rto_charges['Commission']['text'].startswith('₹-')
    assert rto_charges['Fixed Fee']['text'].startswith('₹-')
    assert rto_charges['GT Charge']['text'].startswith('₹-')
    assert rto_charges['Return Fee (Level/Zone)']['text'] == '₹0.00'
    assert 'fin-pos' in rto_charges['Commission']['className']
    assert 'fin-pos' in rto_charges['Fixed Fee']['className']
    assert 'fin-pos' in rto_charges['GT Charge']['className']
    assert 'fin-neg' not in rto_charges['Return Fee (Level/Zone)']['className'] and 'fin-pos' not in rto_charges['Return Fee (Level/Zone)']['className']
    assert rto_charges['Expected Settlement']['text'] == '₹0.00'

    await page.locator('[data-testid="close-drawer"]').click()
    await page.goto('https://settlement-intel-1.preview.emergentagent.com/sales')
    await page.wait_for_selector('[data-testid="sales-page"]', timeout=15000)
    await page.locator('[data-testid="sales-search"]').fill('83410B8C-556E-465B-96A1-EB3A80DB1DF1')
    await page.wait_for_selector('tr[data-testid^="sales-row-"]', timeout=20000)
    await page.locator('tr[data-testid^="sales-row-"]').first.click()
    await page.wait_for_selector('[data-testid="sales-drawer"]', timeout=15000)
    dto_charges = await page.evaluate("""() => {
        const drawer = document.querySelector('[data-testid="sales-drawer"]');
        const rows = Array.from(drawer.querySelectorAll('tr'));
        const out = {};
        for (const tr of rows) {
            const cells = Array.from(tr.querySelectorAll('td'));
            if (cells.length >= 2) out[cells[0].textContent.trim()] = {text: cells[1].textContent.trim(), className: cells[1].className};
        }
        return out;
    }""")
    assert dto_charges['Commission']['text'].startswith('₹-') and 'fin-pos' in dto_charges['Commission']['className']
    assert dto_charges['Fixed Fee']['text'] == '₹0.00' and 'fin-neg' not in dto_charges['Fixed Fee']['className'] and 'fin-pos' not in dto_charges['Fixed Fee']['className']
    assert dto_charges['GT Charge']['text'].startswith('₹-') and 'fin-pos' in dto_charges['GT Charge']['className']
    assert dto_charges['Return Fee (Level/Zone)']['text'] == '₹112.00' and 'fin-neg' in dto_charges['Return Fee (Level/Zone)']['className']
    print('UI_TEST_RESULT: PASS')
except Exception as e:
    print(f'UI_TEST_RESULT: FAIL - {type(e).__name__}: {e}')
    raise
'''