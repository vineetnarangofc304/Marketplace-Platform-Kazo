#!/usr/bin/env python3
"""Focused preview backend verification for DTO/RTO sign conventions (iteration 22).

This test intentionally targets the preview URL only. It does not call the
production kazob2b.fundlezone.com host.
"""
import io
import json
import os
import time
from pathlib import Path

import openpyxl
import requests
from pymongo import MongoClient


BASE_URL = os.environ.get("PREVIEW_BASE_URL", "https://settlement-intel-1.preview.emergentagent.com")
assert "kazob2b.fundlezone.com" not in BASE_URL, "Refusing to test production URL"
API = BASE_URL.rstrip("/") + "/api"
OUT = Path("/app/test_reports/bug_verify_dto_rto_signs_iter22_backend_result.json")
SESSION = requests.Session()


def request(method, path, **kwargs):
    url = API + path
    assert "kazob2b.fundlezone.com" not in url, "Refusing to test production URL"
    last = None
    for attempt in range(1, 4):
        try:
            resp = SESSION.request(method, url, timeout=90, **kwargs)
            if resp.status_code in (502, 503, 504):
                last = f"{resp.status_code} {resp.text[:200]}"
                time.sleep(2 * attempt)
                continue
            resp.raise_for_status()
            return resp
        except Exception as exc:  # test artifact should preserve failure text
            last = str(exc)
            time.sleep(2 * attempt)
    raise AssertionError(f"{method} {path} failed after retries: {last}")


def login():
    resp = SESSION.post(API + "/auth/login", json={"email": "admin@fundle.ai", "password": "admin123"}, timeout=60)
    resp.raise_for_status()
    token = resp.json().get("token")
    if not token:
        raise AssertionError(f"Login did not return token: {resp.text[:200]}")
    SESSION.headers.update({"Authorization": f"Bearer {token}"})
    return resp.json().get("user")


def slim(row):
    keys = [
        "online_order_id", "sales_id", "order_type", "commission_incl_gst",
        "fixed_fee_incl_gst", "gt_charge", "return_fee", "tcs", "tds",
        "commission_gst", "fixed_fee_gst", "total_deductions", "expected_settlement",
        "unmapped", "report_month", "portal",
    ]
    return {k: row.get(k) for k in keys}


def assert_all(rows, predicate, message):
    bad = [r for r in rows if not predicate(r)]
    if bad:
        raise AssertionError(f"{message}; bad_count={len(bad)} sample={list(map(slim, bad[:5]))}")


def calc_rows(order_type, limit=25, extra_params=None):
    params = {"order_type": order_type, "limit": limit}
    if extra_params:
        params.update(extra_params)
    data = request("GET", "/calculations", params=params).json()
    rows = data.get("items", [])
    if not rows:
        raise AssertionError(f"No calculation rows returned for order_type={order_type}, params={params}")
    if len(rows) != min(limit, data.get("total", limit)):
        raise AssertionError(f"Expected {min(limit, data.get('total', limit))} rows for {params}, got {len(rows)}")
    return data, rows


def read_db_config():
    mongo_url = "mongodb://localhost:27017"
    db_name = "test_database"
    env_path = Path("/app/backend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("MONGO_URL="):
                mongo_url = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("DB_NAME="):
                db_name = line.split("=", 1)[1].strip().strip('"')
    return mongo_url, db_name


def main():
    result = {"base_url": BASE_URL, "checks": [], "failures": []}
    try:
        user = login()
        result["checks"].append({"name": "preview_admin_login", "user": user})

        # Exact requested endpoints: unfiltered preview API, limit=25.
        dto_data, dto_rows = calc_rows("return_dto", 25)
        assert_all(dto_rows, lambda r: r.get("commission_incl_gst") is not None and r["commission_incl_gst"] < 0, "DTO commission_incl_gst must be negative")
        assert_all(dto_rows, lambda r: r.get("fixed_fee_incl_gst") == 0.0, "DTO fixed_fee_incl_gst must be exactly 0.0")
        assert_all(dto_rows, lambda r: r.get("gt_charge") is not None and r["gt_charge"] < 0, "DTO gt_charge must be negative")
        assert_all(dto_rows, lambda r: r.get("return_fee") is not None and r["return_fee"] > 0, "DTO return_fee must be positive")
        assert_all(dto_rows, lambda r: r.get("tcs") == 0 and r.get("tds") == 0 and r.get("commission_gst") == 0, "DTO tax fields tcs/tds/commission_gst must be zero")
        result["checks"].append({
            "name": "api_return_dto_limit25_point_2_1",
            "total": dto_data.get("total"),
            "rows_checked": len(dto_rows),
            "first_row": slim(dto_rows[0]),
        })

        rto_data, rto_rows = calc_rows("rto", 25)
        assert_all(rto_rows, lambda r: r.get("commission_incl_gst") is not None and r["commission_incl_gst"] < 0, "RTO commission_incl_gst must be negative")
        assert_all(rto_rows, lambda r: r.get("fixed_fee_incl_gst") is not None and r["fixed_fee_incl_gst"] < 0, "RTO fixed_fee_incl_gst must be negative")
        assert_all(rto_rows, lambda r: r.get("gt_charge") is not None and r["gt_charge"] < 0, "RTO gt_charge must be negative")
        assert_all(rto_rows, lambda r: r.get("return_fee") is not None and r["return_fee"] < 0, "RTO return_fee must be negative")
        assert_all(rto_rows, lambda r: r.get("tcs") == 0 and r.get("tds") == 0 and r.get("commission_gst") == 0, "RTO tax fields tcs/tds/commission_gst must be zero")
        assert_all(rto_rows, lambda r: r.get("expected_settlement") == 0 and r.get("total_deductions") == 0, "RTO expected_settlement and total_deductions must be zero")
        result["checks"].append({
            "name": "api_rto_limit25_point_2_2",
            "total": rto_data.get("total"),
            "rows_checked": len(rto_rows),
            "first_row": slim(rto_rows[0]),
        })

        # April Myntra samples are the backend source for the required UI flow.
        april = {"period_type": "month", "period_value": "2026-04", "portal": "myntra"}
        _, dto_april = calc_rows("return_dto", 25, april)
        _, rto_april = calc_rows("rto", 25, april)
        assert_all(dto_april, lambda r: r["commission_incl_gst"] < 0 and r["fixed_fee_incl_gst"] == 0.0 and r["gt_charge"] < 0 and r["return_fee"] > 0, "April/Myntra DTO signs must match Point 2.1")
        assert_all(rto_april, lambda r: r["commission_incl_gst"] < 0 and r["fixed_fee_incl_gst"] < 0 and r["gt_charge"] < 0 and r["return_fee"] < 0 and r["expected_settlement"] == 0 and r["total_deductions"] == 0, "April/Myntra RTO signs must match Point 2.2")
        result["checks"].append({"name": "api_april_myntra_limit25", "dto_first": slim(dto_april[0]), "rto_first": slim(rto_april[0])})

        # Regression checks requested in the review request.
        _, sales_rows = calc_rows("sales", 25, april)
        assert_all(sales_rows, lambda r: r.get("commission_incl_gst") is not None and r["commission_incl_gst"] > 0, "Sales commission must remain positive")
        assert_all(sales_rows, lambda r: r.get("fixed_fee_incl_gst") is not None and r["fixed_fee_incl_gst"] > 0, "Sales fixed fee must remain positive")
        assert_all(sales_rows, lambda r: r.get("gt_charge") is not None and r["gt_charge"] > 0, "Sales GT charge must remain positive")
        assert_all(sales_rows, lambda r: r.get("return_fee") == 0, "Sales return fee must be zero")
        result["checks"].append({"name": "api_sales_rows_regression_limit25", "first_row": slim(sales_rows[0])})

        summary = request("GET", "/sales/summary", params=april).json()
        if summary.get("net_orders") != 6824:
            raise AssertionError(f"Expected /api/sales/summary net_orders=6824, got {summary}")
        result["checks"].append({"name": "api_sales_summary_net_orders", "summary": summary})

        unmapped = request("GET", "/calculations", params={**april, "severity_flag": "unmapped", "limit": 1}).json()
        if unmapped.get("total") != 0:
            raise AssertionError(f"Expected April/Myntra unmapped=0, got total={unmapped.get('total')} sample={unmapped.get('items')}")
        result["checks"].append({"name": "api_april_myntra_unmapped_zero", "total": unmapped.get("total")})

        export_resp = request("GET", "/sales/export", params=april)
        wb = openpyxl.load_workbook(io.BytesIO(export_resp.content), read_only=True)
        ws = wb.active
        headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        if len(headers) != 31:
            raise AssertionError(f"Expected 31 Excel export columns, got {len(headers)}: {headers}")
        result["checks"].append({"name": "api_sales_export_31_columns", "column_count": len(headers), "first_last_headers": [headers[0], headers[-1]]})

        mongo_url, db_name = read_db_config()
        db = MongoClient(mongo_url)[db_name]
        all_fallback = db.calculations.find_one({
            "portal": "myntra",
            "report_month": "2026-04",
            "breakdown.commission_rule.matched_sub_category": {"$regex": "^ALL$", "$options": "i"},
            "commission_incl_gst": {"$ne": None},
        }, {"_id": 0, "online_order_id": 1, "sku": 1, "commission_incl_gst": 1, "breakdown.commission_rule": 1})
        if not all_fallback:
            raise AssertionError("No April/Myntra calculation found using commission sub_category=ALL fallback")
        result["checks"].append({"name": "mongo_commission_all_fallback_active", "sample": all_fallback})

        result["verdict"] = "passed"
    except Exception as exc:
        result["verdict"] = "failed"
        result["failures"].append(str(exc))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps(result, indent=2, default=str))
    if result["verdict"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()