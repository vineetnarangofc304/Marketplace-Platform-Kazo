"""Playwright body used with mcp_browser_automation for bug_verification_15.

This file is an artifact copy of the browser automation steps. The MCP tool
executes the body inside an async function with a pre-created `page` object.
"""

await page.set_viewport_size({"width": 1920, "height": 1080})
await page.goto('https://settlement-intel-1.preview.emergentagent.com/login', wait_until='networkidle')
await page.fill('[data-testid="login-email"]', 'admin@fundle.ai')
await page.fill('[data-testid="login-password"]', 'admin123')
await page.click('[data-testid="login-submit"]')
await page.wait_for_selector('[data-testid="overview-page"]', timeout=20000)
await page.evaluate("""() => localStorage.setItem('fundle_portal', 'myntra')""")

await page.goto('https://settlement-intel-1.preview.emergentagent.com/sales?period_type=month&period_value=2026-04&portal=myntra', wait_until='networkidle')
await page.wait_for_selector('[data-testid="sales-page"]', timeout=20000)
await page.wait_for_function("""() => document.querySelectorAll('tr[data-testid^="sales-row-"]').length >= 20""", timeout=20000)
summary_text = await page.locator('[data-testid="sales-summary"]').inner_text()
sales_info = await page.evaluate("""() => {
  const headers = Array.from(document.querySelectorAll('thead th')).map(th => th.textContent.trim().replace(/\s+/g, ' '));
  const locIdx = headers.indexOf('Location');
  const rows = Array.from(document.querySelectorAll('tr[data-testid^="sales-row-"]')).slice(0, 20).map(tr => Array.from(tr.children).map(td => td.textContent.trim()));
  return {headers, locations: rows.map(r => r[locIdx])};
}""")
assert '6,824' in summary_text
assert all(v == 'MYN' for v in sales_info['locations'])

await page.select_option('[data-testid="filter-txn"]', 'Return')
await page.wait_for_function("""() => {
  const headers = Array.from(document.querySelectorAll('thead th')).map(th => th.textContent.trim().replace(/\s+/g, ' '));
  const locIdx = headers.indexOf('Location');
  const rows = Array.from(document.querySelectorAll('tr[data-testid^="sales-row-"]')).slice(0, 20).map(tr => Array.from(tr.children).map(td => td.textContent.trim()));
  return rows.length >= 20 && rows.every(r => r[2] === 'Return' && r[locIdx] === 'MYSRI');
}""", timeout=20000)

await page.locator('tr[data-testid^="sales-row-"]').first.click()
await page.wait_for_selector('[data-testid="sales-drawer"]', timeout=10000)
await page.wait_for_function("""() => {
  const el = document.querySelector('[data-testid="sales-drawer"]');
  const text = el ? el.textContent : '';
  return text.includes('Expected Calculation') && text.includes('Return Fee') && text.includes('Commission') && !text.includes('Loading calculation');
}""", timeout=15000)
drawer_text = await page.locator('[data-testid="sales-drawer"]').inner_text()
assert not any(word in drawer_text for word in ['GST', 'TCS', 'TDS'])
await page.click('[data-testid="close-drawer"]')

for path, selector in [('/', '[data-testid="overview-page"]'), ('/reports', '[data-testid="reports-page"]'), ('/reconciliation', '[data-testid="recon-page"]')]:
  await page.goto('https://settlement-intel-1.preview.emergentagent.com' + path, wait_until='networkidle')
  await page.wait_for_selector(selector, timeout=20000)