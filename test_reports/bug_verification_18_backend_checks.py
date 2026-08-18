"""
Focused backend/API verification for Google Doc points 1-5 on PREVIEW only.

Test plan:
- Login with documented admin credentials against REACT_APP_BACKEND_URL.
- Prove Point 1 via /api/sales/summary and /api/dashboard/portals-summary net_orders=6824.
- Prove Point 2 via calculation rows/by-sale detail for return_dto negative reversals and sales positive charges.
- Prove regressions: TCS/TDS/GST=0 scan, 31-column Sales Ledger Excel export, and ALL fallback/no-unmapped status.
- Do not call production kazob2b.fundlezone.com.
"""
import json
import os
from io import BytesIO
from pathlib import Path

import openpyxl
import requests


OUT = Path("/app/test_reports/bug_verification_18_backend_results.json")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://settlement-intel-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
PARAMS = {"period_type": "month", "period_value": "2026-04", "portal": "myntra"}


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def rupee_round(v):
    return None if v is None else round(float(v), 2)


def main():
    results = {
        "base_url": BASE_URL,
        "production_touched": "kazob2b.fundlezone.com" in BASE_URL,
        "checks": [],
        "samples": {},
    }
    assert_true("kazob2b.fundlezone.com" not in BASE_URL, "Refusing to test production URL")

    s = requests.Session()
    health = requests.get(f"{API}/health", timeout=30)
    results["checks"].append({"name": "health", "status": health.status_code, "body": health.json()})
    assert_true(health.status_code == 200 and health.json().get("status") == "ok", "Preview API health failed")

    login = s.post(f"{API}/auth/login", json={"email": "admin@fundle.ai", "password": "admin123"}, timeout=30)
    results["checks"].append({"name": "login", "status": login.status_code})
    assert_true(login.status_code == 200, f"Login failed: {login.status_code} {login.text[:300]}")

    summary = s.get(f"{API}/sales/summary", params=PARAMS, timeout=60)
    assert_true(summary.status_code == 200, f"sales/summary failed: {summary.status_code} {summary.text[:300]}")
    summary_json = summary.json()
    results["samples"]["sales_summary"] = summary_json
    assert_true(summary_json.get("net_orders") == 6824, f"sales_summary net_orders expected 6824 got {summary_json.get('net_orders')}")
    assert_true(summary_json.get("sales_rows") == 14219, f"sales_rows expected 14219 got {summary_json.get('sales_rows')}")
    assert_true(summary_json.get("return_rows") == 7395, f"return_rows expected 7395 got {summary_json.get('return_rows')}")

    portals = s.get(f"{API}/dashboard/portals-summary", params={"period_type": "month", "period_value": "2026-04"}, timeout=60)
    assert_true(portals.status_code == 200, f"portals-summary failed: {portals.status_code} {portals.text[:300]}")
    portals_json = portals.json()
    myntra_portal = next((p for p in portals_json.get("portals", []) if p.get("code") == "myntra"), {})
    results["samples"]["portals_summary_totals"] = portals_json.get("totals")
    results["samples"]["myntra_portal"] = myntra_portal
    assert_true(portals_json.get("totals", {}).get("net_orders") == 6824, "portals-summary totals.net_orders is not 6824")
    assert_true(myntra_portal.get("net_orders") == 6824, "Myntra portal net_orders is not 6824")
    assert_true(rupee_round(portals_json.get("totals", {}).get("nsv")) == 12702900.00, "portals-summary totals.nsv is not 12702900.00")

    sales_header = s.get(f"{API}/sales/summary", params=PARAMS, timeout=60).json()
    expected_header = f"{sales_header['net_orders']:,} Order Qty (net) · {sales_header['sales_rows']:,} Sales − {sales_header['return_rows']:,} Returns"
    results["samples"]["expected_sales_ledger_header"] = expected_header
    assert_true(expected_header == "6,824 Order Qty (net) · 14,219 Sales − 7,395 Returns", expected_header)

    rtd = s.get(f"{API}/calculations", params={**PARAMS, "order_type": "return_dto", "limit": 50, "sort_by": "computed_at"}, timeout=60)
    assert_true(rtd.status_code == 200, f"return_dto calculations failed: {rtd.status_code} {rtd.text[:300]}")
    rtd_items = rtd.json().get("items", [])
    assert_true(len(rtd_items) > 0, "No return_dto rows found")
    rtd_sample = next((x for x in rtd_items if (x.get("commission_incl_gst") or 0) < 0 and (x.get("gt_charge") or 0) < 0 and (x.get("fixed_fee_incl_gst") or 0) < 0 and (x.get("return_fee") or 0) > 0), None)
    assert_true(rtd_sample is not None, "No return_dto sample found with commission/GT/fixed negative and return_fee positive")
    results["samples"]["return_dto_calc"] = {
        "id": rtd_sample.get("id"),
        "sales_id": rtd_sample.get("sales_id"),
        "online_order_id": rtd_sample.get("online_order_id"),
        "commission_incl_gst": rtd_sample.get("commission_incl_gst"),
        "fixed_fee_incl_gst": rtd_sample.get("fixed_fee_incl_gst"),
        "gt_charge": rtd_sample.get("gt_charge"),
        "return_fee": rtd_sample.get("return_fee"),
        "tcs": rtd_sample.get("tcs"),
        "tds": rtd_sample.get("tds"),
        "commission_gst": rtd_sample.get("commission_gst"),
    }
    assert_true(rtd_sample.get("commission_gst") == 0 and rtd_sample.get("tcs") == 0 and rtd_sample.get("tds") == 0, "return_dto tax fields are not zero")
    detail = s.get(f"{API}/calculations/by-sale/{rtd_sample['sales_id']}", timeout=60)
    assert_true(detail.status_code == 200, f"by-sale return_dto failed: {detail.status_code} {detail.text[:300]}")
    dcalc = detail.json()["calculation"]
    assert_true(dcalc["commission_incl_gst"] < 0 and dcalc["fixed_fee_incl_gst"] < 0 and dcalc["gt_charge"] < 0 and dcalc["return_fee"] > 0, "Drawer/by-sale return_dto values do not have required signs")

    sales = s.get(f"{API}/calculations", params={**PARAMS, "order_type": "sales", "limit": 100}, timeout=60)
    assert_true(sales.status_code == 200, f"sales calculations failed: {sales.status_code} {sales.text[:300]}")
    sales_sample = next((x for x in sales.json().get("items", []) if (x.get("commission_incl_gst") or 0) > 0 and (x.get("gt_charge") or 0) > 0), None)
    assert_true(sales_sample is not None, "No sales sample found with positive commission and GT")
    results["samples"]["sales_calc"] = {
        "id": sales_sample.get("id"),
        "sales_id": sales_sample.get("sales_id"),
        "online_order_id": sales_sample.get("online_order_id"),
        "commission_incl_gst": sales_sample.get("commission_incl_gst"),
        "gt_charge": sales_sample.get("gt_charge"),
    }

    total_scanned = 0
    tax_violations = []
    all_fallback_sample = None
    skip = 0
    while True:
        page = s.get(f"{API}/calculations", params={**PARAMS, "limit": 2000, "skip": skip}, timeout=120)
        assert_true(page.status_code == 200, f"calculations page failed at skip {skip}: {page.status_code} {page.text[:300]}")
        items = page.json().get("items", [])
        if not items:
            break
        for x in items:
            total_scanned += 1
            if x.get("tcs") not in (0, 0.0) or x.get("tds") not in (0, 0.0) or x.get("commission_gst") not in (0, 0.0):
                tax_violations.append({"id": x.get("id"), "tcs": x.get("tcs"), "tds": x.get("tds"), "commission_gst": x.get("commission_gst")})
                if len(tax_violations) >= 5:
                    break
            matched = (((x.get("breakdown") or {}).get("commission_rule") or {}).get("matched_sub_category") or "").strip().lower()
            if matched == "all" and all_fallback_sample is None:
                all_fallback_sample = {"id": x.get("id"), "online_order_id": x.get("online_order_id"), "sub_category": (x.get("breakdown") or {}).get("sub_category"), "matched_sub_category": matched}
        assert_true(not tax_violations, f"Tax violations found: {tax_violations}")
        skip += len(items)
        if len(items) < 2000:
            break
    results["samples"]["tax_scan"] = {"total_scanned": total_scanned, "violations": tax_violations}
    assert_true(total_scanned >= 21614, f"Expected at least 21614 April Myntra calculations, scanned {total_scanned}")

    unmapped = s.get(f"{API}/calculations", params={**PARAMS, "severity_flag": "unmapped", "limit": 1}, timeout=60)
    assert_true(unmapped.status_code == 200, f"unmapped query failed: {unmapped.status_code} {unmapped.text[:300]}")
    results["samples"]["unmapped_total"] = unmapped.json().get("total")
    assert_true(unmapped.json().get("total") == 0, f"Unmapped total expected 0 got {unmapped.json().get('total')}")
    rules = s.get(f"{API}/masters/commission-rules", timeout=60)
    assert_true(rules.status_code == 200, f"commission rules failed: {rules.status_code}")
    has_all_rule = any((r.get("sub_category") or "").strip().lower() == "all" for r in rules.json())
    results["samples"]["all_fallback"] = {"has_all_rule": has_all_rule, "sample_calc": all_fallback_sample}
    assert_true(has_all_rule, "No active commission rule with sub_category=ALL found")

    export = s.get(f"{API}/sales/export", params=PARAMS, timeout=180)
    assert_true(export.status_code == 200, f"sales export failed: {export.status_code} {export.text[:300]}")
    wb = openpyxl.load_workbook(BytesIO(export.content), read_only=True, data_only=True)
    ws = wb.active
    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    required_headers = [
        "Brand", "Sale Type", "Posting Date", "Item No (SKU)", "Posting_Location Code",
        "Main Ctg", "Level No", "Price Range - Key (NSV)", "Price Range - Key (NSV after GT)",
    ]
    missing = [h for h in required_headers if h not in headers]
    results["samples"]["export"] = {"column_count": len(headers), "required_missing": missing, "headers": headers}
    assert_true(len(headers) == 31, f"Expected 31 export columns got {len(headers)}")
    assert_true(not missing, f"Missing export headers: {missing}")

    results["ok"] = True
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        failure = {"base_url": BASE_URL, "ok": False, "error": str(e)}
        OUT.write_text(json.dumps(failure, indent=2), encoding="utf-8")
        print(json.dumps(failure, indent=2))
        raise