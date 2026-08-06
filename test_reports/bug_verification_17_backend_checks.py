import json
import os
import tempfile
from pathlib import Path

import openpyxl
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://marketplace-recon-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
OUT = Path("/app/test_reports/bug_verification_17_backend_results.json")


def rupee(v):
    return None if v is None else round(float(v), 2)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    results = {
        "base_url": BASE_URL,
        "checks": [],
        "sample_return_dto": None,
        "sample_sales": None,
        "excel_headers_count": None,
    }
    session = requests.Session()

    login = session.post(f"{API}/auth/login", json={"email": "admin@fundle.ai", "password": "admin123"}, timeout=30)
    results["checks"].append({"name": "login", "status_code": login.status_code})
    assert_true(login.status_code == 200, f"login failed: {login.status_code} {login.text[:300]}")
    token = login.json().get("token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})

    params = {"period_type": "month", "period_value": "2026-04", "portal": "myntra"}

    ps = session.get(f"{API}/dashboard/portals-summary", params={"period_type": "month", "period_value": "2026-04"}, timeout=60)
    results["checks"].append({"name": "portals_summary", "status_code": ps.status_code})
    assert_true(ps.status_code == 200, f"portals-summary failed: {ps.status_code} {ps.text[:300]}")
    psj = ps.json()
    myntra = next((p for p in psj.get("portals", []) if p.get("code") == "myntra"), None)
    results["portals_summary"] = {"totals": psj.get("totals"), "myntra": myntra}
    assert_true(psj.get("totals", {}).get("net_orders") == 6824, f"totals.net_orders expected 6824 got {psj.get('totals', {}).get('net_orders')}")
    assert_true(myntra and myntra.get("net_orders") == 6824, f"myntra.net_orders expected 6824 got {myntra}")
    assert_true(round(float(psj.get("totals", {}).get("nsv", 0)), 2) == 12702900.00, f"totals.nsv expected 12702900 got {psj.get('totals', {}).get('nsv')}")

    ss = session.get(f"{API}/sales/summary", params=params, timeout=60)
    results["checks"].append({"name": "sales_summary", "status_code": ss.status_code})
    assert_true(ss.status_code == 200, f"sales summary failed: {ss.status_code} {ss.text[:300]}")
    ssj = ss.json()
    results["sales_summary"] = ssj
    assert_true(ssj.get("net_orders") == 6824, f"sales_summary.net_orders expected 6824 got {ssj.get('net_orders')}")

    # Verify DTO reversal data exists and is negative in the underlying calculation row used by Sales Ledger grid.
    dto = session.get(f"{API}/calculations", params={**params, "order_type": "return_dto", "limit": 500}, timeout=60)
    results["checks"].append({"name": "calculations_return_dto", "status_code": dto.status_code})
    assert_true(dto.status_code == 200, f"return_dto calculations failed: {dto.status_code} {dto.text[:300]}")
    dto_items = dto.json().get("items", [])
    negative_dto = next((x for x in dto_items if (x.get("commission_incl_gst") or 0) < 0 and (x.get("gt_charge") or 0) < 0), None)
    assert_true(negative_dto is not None, "No return_dto calculation with negative commission and negative GT found in first 500 rows")
    results["sample_return_dto"] = {
        "sales_id": negative_dto.get("sales_id"),
        "online_order_id": negative_dto.get("online_order_id"),
        "order_type": negative_dto.get("order_type"),
        "commission_incl_gst": rupee(negative_dto.get("commission_incl_gst")),
        "gt_charge": rupee(negative_dto.get("gt_charge")),
        "fixed_fee_incl_gst": rupee(negative_dto.get("fixed_fee_incl_gst")),
        "return_fee": rupee(negative_dto.get("return_fee")),
        "tcs": rupee(negative_dto.get("tcs")),
        "tds": rupee(negative_dto.get("tds")),
    }

    by_sale = session.get(f"{API}/calculations/by-sale/{negative_dto['sales_id']}", timeout=60)
    results["checks"].append({"name": "drawer_by_sale_return_dto", "status_code": by_sale.status_code})
    assert_true(by_sale.status_code == 200, f"by-sale failed: {by_sale.status_code} {by_sale.text[:300]}")
    calc = by_sale.json().get("calculation", {})
    assert_true((calc.get("commission_incl_gst") or 0) < 0 and (calc.get("gt_charge") or 0) < 0, "by-sale drawer calc is not negative for DTO commission/GT")

    sales_calc = session.get(f"{API}/calculations", params={**params, "order_type": "sales", "limit": 500}, timeout=60)
    results["checks"].append({"name": "calculations_sales", "status_code": sales_calc.status_code})
    assert_true(sales_calc.status_code == 200, f"sales calculations failed: {sales_calc.status_code} {sales_calc.text[:300]}")
    sales_positive = next((x for x in sales_calc.json().get("items", []) if (x.get("commission_incl_gst") or 0) > 0 and (x.get("gt_charge") or 0) > 0), None)
    assert_true(sales_positive is not None, "No sales calculation with positive commission and positive GT found in first 500 rows")
    results["sample_sales"] = {
        "sales_id": sales_positive.get("sales_id"),
        "online_order_id": sales_positive.get("online_order_id"),
        "order_type": sales_positive.get("order_type"),
        "commission_incl_gst": rupee(sales_positive.get("commission_incl_gst")),
        "gt_charge": rupee(sales_positive.get("gt_charge")),
        "tcs": rupee(sales_positive.get("tcs")),
        "tds": rupee(sales_positive.get("tds")),
    }

    # TCS/TDS regression: check all April Myntra calculation rows by pagination.
    skip = 0
    scanned = 0
    nonzero_tcs_tds = []
    while True:
        page = session.get(f"{API}/calculations", params={**params, "limit": 2000, "skip": skip}, timeout=60)
        assert_true(page.status_code == 200, f"calculations page skip={skip} failed {page.status_code}")
        items = page.json().get("items", [])
        for item in items:
            scanned += 1
            if abs(float(item.get("tcs") or 0)) > 0.0001 or abs(float(item.get("tds") or 0)) > 0.0001:
                nonzero_tcs_tds.append({"sales_id": item.get("sales_id"), "tcs": item.get("tcs"), "tds": item.get("tds")})
        if len(items) < 2000:
            break
        skip += len(items)
    results["tcs_tds_scan"] = {"scanned_rows": scanned, "nonzero_count": len(nonzero_tcs_tds), "samples": nonzero_tcs_tds[:5]}
    assert_true(len(nonzero_tcs_tds) == 0, f"Found non-zero TCS/TDS rows: {nonzero_tcs_tds[:5]}")

    exp = session.get(f"{API}/sales/export", params=params, timeout=120)
    results["checks"].append({"name": "sales_export", "status_code": exp.status_code, "content_type": exp.headers.get("content-type")})
    assert_true(exp.status_code == 200, f"export failed: {exp.status_code} {exp.text[:300]}")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(exp.content)
        tmp_path = tmp.name
    wb = openpyxl.load_workbook(tmp_path, read_only=True)
    ws = wb.active
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    results["excel_headers_count"] = len(headers)
    results["excel_headers"] = headers
    assert_true(len(headers) == 31, f"Excel export expected 31 columns got {len(headers)}")
    assert_true("Commission (Expected)" in headers and "GT Charge (Expected)" in headers, "Excel export missing Commission/GT headers")

    results["verdict"] = "passed"
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        failure = {"base_url": BASE_URL, "verdict": "failed", "error": str(exc)}
        OUT.write_text(json.dumps(failure, indent=2), encoding="utf-8")
        print(json.dumps(failure, indent=2))
        raise