#!/usr/bin/env python3
"""Focused backend/API verification for return_dto sign convention bug.

Checks April 2026 Myntra return_dto calculations, regression summary/export,
sales-row signs, unmapped count, and runtime use of commission ALL fallback.
"""

import io
import json
import os
from pathlib import Path

import openpyxl
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


APP = Path("/app")
FRONTEND_ENV = dotenv_values(APP / "frontend" / ".env")
BACKEND_ENV = dotenv_values(APP / "backend" / ".env")
BASE = FRONTEND_ENV["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
ORDER_ID = "83410B8C-556E-465B-96A1-EB3A80DB1DF1"
OUT = APP / "test_reports" / "return_dto_signs_api_result.json"


def approx(a, b, tol=0.02):
    return abs((a or 0) - (b or 0)) <= tol


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    s = requests.Session()
    evidence = {"base_url": BASE, "checks": []}

    login = s.post(f"{API}/auth/login", json={"email": "admin@fundle.ai", "password": "admin123"}, timeout=30)
    assert_true(login.status_code == 200, f"login failed: {login.status_code} {login.text[:200]}")
    token = login.json()["token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    evidence["checks"].append({"name": "login", "status": "passed", "email": "admin@fundle.ai"})

    params = {"period_type": "month", "period_value": "2026-04", "portal": "myntra", "order_type": "return_dto", "limit": 5}
    r = s.get(f"{API}/calculations", params=params, timeout=60)
    assert_true(r.status_code == 200, f"return_dto calculations failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    rows = data["items"]
    assert_true(rows, "No return_dto calculation rows returned")
    samples = []
    for c in rows:
        oid = c.get("online_order_id")
        assert_true(c.get("commission_incl_gst") < 0, f"{oid}: commission_incl_gst not negative")
        assert_true(c.get("gt_charge") < 0, f"{oid}: gt_charge not negative")
        assert_true(c.get("fixed_fee_incl_gst") > 0, f"{oid}: fixed_fee_incl_gst not positive")
        assert_true(c.get("return_fee") > 0, f"{oid}: return_fee not positive")
        assert_true(c.get("tcs") == 0 and c.get("tds") == 0 and c.get("commission_gst") == 0, f"{oid}: taxes/GST not zero")
        expected_total = c.get("commission_incl_gst") + c.get("fixed_fee_incl_gst") + c.get("gt_charge") + c.get("return_fee")
        assert_true(approx(c.get("total_deductions"), expected_total), f"{oid}: total_deductions {c.get('total_deductions')} != component sum {expected_total}")
        samples.append({
            "online_order_id": oid,
            "sales_id": c.get("sales_id"),
            "commission_incl_gst": c.get("commission_incl_gst"),
            "gt_charge": c.get("gt_charge"),
            "fixed_fee_incl_gst": c.get("fixed_fee_incl_gst"),
            "return_fee": c.get("return_fee"),
            "total_deductions": c.get("total_deductions"),
            "taxes": {"tcs": c.get("tcs"), "tds": c.get("tds"), "commission_gst": c.get("commission_gst")},
        })
    evidence["checks"].append({"name": "return_dto_signs_limit_5", "status": "passed", "total": data.get("total"), "samples": samples})

    exact = s.get(f"{API}/calculations", params={**params, "search": ORDER_ID, "limit": 1}, timeout=60)
    assert_true(exact.status_code == 200, f"exact order calculation search failed: {exact.status_code} {exact.text[:200]}")
    exact_rows = exact.json().get("items", [])
    assert_true(exact_rows, f"Exact return_dto order not found in calculations: {ORDER_ID}")
    e = exact_rows[0]
    assert_true(e.get("commission_incl_gst") < 0 and e.get("gt_charge") < 0 and e.get("fixed_fee_incl_gst") > 0 and e.get("return_fee") > 0, "Exact order signs incorrect")
    by_sale = s.get(f"{API}/calculations/by-sale/{e['sales_id']}", timeout=60)
    assert_true(by_sale.status_code == 200, f"by-sale failed: {by_sale.status_code} {by_sale.text[:200]}")
    bc = by_sale.json()["calculation"]
    assert_true(bc["online_order_id"] == ORDER_ID, "by-sale returned different order")
    assert_true(bc.get("commission_incl_gst") == e.get("commission_incl_gst") and bc.get("fixed_fee_incl_gst") == e.get("fixed_fee_incl_gst") and bc.get("gt_charge") == e.get("gt_charge") and bc.get("return_fee") == e.get("return_fee"), "by-sale amounts differ from calculation list")
    evidence["exact_order"] = {
        "online_order_id": ORDER_ID,
        "sales_id": e["sales_id"],
        "calculation_id": e["id"],
        "commission_incl_gst": e.get("commission_incl_gst"),
        "gt_charge": e.get("gt_charge"),
        "fixed_fee_incl_gst": e.get("fixed_fee_incl_gst"),
        "return_fee": e.get("return_fee"),
        "total_deductions": e.get("total_deductions"),
    }

    summary = s.get(f"{API}/sales/summary", params={"period_type": "month", "period_value": "2026-04", "portal": "myntra"}, timeout=60)
    assert_true(summary.status_code == 200, f"sales summary failed: {summary.status_code} {summary.text[:200]}")
    summary_json = summary.json()
    assert_true(summary_json.get("net_orders") == 6824, f"net_orders expected 6824, got {summary_json.get('net_orders')}")
    evidence["checks"].append({"name": "sales_summary_net_orders", "status": "passed", "summary": summary_json})

    sales_calc = s.get(f"{API}/calculations", params={"period_type": "month", "period_value": "2026-04", "portal": "myntra", "order_type": "sales", "limit": 5}, timeout=60)
    assert_true(sales_calc.status_code == 200, f"sales calculation sample failed: {sales_calc.status_code} {sales_calc.text[:200]}")
    sales_rows = sales_calc.json().get("items", [])
    assert_true(sales_rows, "No sales calculation rows returned")
    sales_samples = []
    for c in sales_rows:
        oid = c.get("online_order_id")
        assert_true(c.get("commission_incl_gst") > 0, f"sales {oid}: commission not positive")
        assert_true(c.get("gt_charge") > 0, f"sales {oid}: GT not positive")
        assert_true(c.get("fixed_fee_incl_gst") > 0, f"sales {oid}: fixed fee not positive")
        assert_true(c.get("return_fee") == 0, f"sales {oid}: return fee not zero")
        sales_samples.append({"online_order_id": oid, "commission_incl_gst": c.get("commission_incl_gst"), "gt_charge": c.get("gt_charge"), "fixed_fee_incl_gst": c.get("fixed_fee_incl_gst"), "return_fee": c.get("return_fee")})
    evidence["checks"].append({"name": "sales_row_signs_limit_5", "status": "passed", "samples": sales_samples})

    unmapped = s.get(f"{API}/calculations", params={"period_type": "month", "period_value": "2026-04", "portal": "myntra", "severity_flag": "unmapped", "limit": 1}, timeout=60)
    assert_true(unmapped.status_code == 200, f"unmapped check failed: {unmapped.status_code} {unmapped.text[:200]}")
    assert_true(unmapped.json().get("total") == 0, f"unmapped_count expected 0, got {unmapped.json().get('total')}")
    evidence["checks"].append({"name": "unmapped_count", "status": "passed", "unmapped_total": 0})

    export = s.get(f"{API}/sales/export", params={"period_type": "month", "period_value": "2026-04", "portal": "myntra"}, timeout=120)
    assert_true(export.status_code == 200, f"Excel export failed: {export.status_code} {export.text[:200]}")
    wb = openpyxl.load_workbook(io.BytesIO(export.content), read_only=True)
    ws = wb.active
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    assert_true(len(headers) == 31, f"Excel export expected 31 columns, got {len(headers)}")
    evidence["checks"].append({"name": "excel_export_columns", "status": "passed", "column_count": len(headers), "headers": headers})

    mongo = MongoClient(BACKEND_ENV["MONGO_URL"])
    db = mongo[BACKEND_ENV["DB_NAME"]]
    fallback_count = db.calculations.count_documents({
        "report_month": "2026-04",
        "portal": "myntra",
        "breakdown.commission_rule.matched_sub_category": {"$regex": "^all$", "$options": "i"},
    })
    assert_true(fallback_count > 0, "No calculations found using commission matched_sub_category=ALL fallback")
    fallback_doc = db.calculations.find_one({
        "report_month": "2026-04",
        "portal": "myntra",
        "breakdown.commission_rule.matched_sub_category": {"$regex": "^all$", "$options": "i"},
    }, {"_id": 0, "online_order_id": 1, "sku": 1, "order_type": 1, "breakdown.commission_rule": 1})
    evidence["checks"].append({"name": "commission_all_fallback_runtime", "status": "passed", "count": fallback_count, "sample": fallback_doc})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
    print(json.dumps(evidence, indent=2, default=str))


if __name__ == "__main__":
    main()