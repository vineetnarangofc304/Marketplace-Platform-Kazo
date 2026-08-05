#!/usr/bin/env python3
"""Focused backend verification for Sales Ledger net qty and DTO reversal fixes.

Targets preview only (REACT_APP_BACKEND_URL from /app/frontend/.env), never production.
"""
import json
import pathlib
import re
import sys
from typing import Any, Dict

import requests


ROOT = pathlib.Path("/app")
ENV_PATH = ROOT / "frontend" / ".env"
OUT_PATH = ROOT / "test_reports" / "bug_verification_16_backend_results.json"


def read_backend_url() -> str:
    text = ENV_PATH.read_text()
    m = re.search(r"^REACT_APP_BACKEND_URL=(.+)$", text, re.M)
    if not m:
        raise RuntimeError("REACT_APP_BACKEND_URL not found")
    url = m.group(1).strip().rstrip("/")
    if "kazob2b.fundlezone.com" in url:
        raise RuntimeError(f"Refusing to test production URL: {url}")
    return url


def assert_true(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    backend = read_backend_url()
    api = f"{backend}/api"
    s = requests.Session()
    results: Dict[str, Any] = {"backend_url": backend, "checks": []}

    # Login as requested admin to mirror the real app flow.
    login = s.post(f"{api}/auth/login", json={"email": "admin@fundle.ai", "password": "admin123"}, timeout=30)
    results["login_status"] = login.status_code
    login.raise_for_status()
    token = login.json().get("access_token") or login.json().get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    results["checks"].append({"name": "auth_login", "passed": True, "status": login.status_code})

    # Point 1 API sanity: net_orders must be sales_rows - return_rows for Apr 2026 Myntra.
    summary_url = f"{api}/sales/summary"
    params = {"period_type": "month", "period_value": "2026-04", "portal": "myntra"}
    r = s.get(summary_url, params=params, timeout=60)
    results["sales_summary_status"] = r.status_code
    r.raise_for_status()
    summary = r.json()
    results["sales_summary"] = summary
    assert_true(summary.get("sales_rows") == 14219, f"sales_rows expected 14219 got {summary.get('sales_rows')}")
    assert_true(summary.get("return_rows") == 7395, f"return_rows expected 7395 got {summary.get('return_rows')}")
    assert_true(summary.get("net_orders") == 6824, f"net_orders expected 6824 got {summary.get('net_orders')}")
    assert_true(summary.get("net_orders") == summary.get("sales_rows") - summary.get("return_rows"), "net_orders is not sales_rows-return_rows")
    results["checks"].append({"name": "sales_summary_net_orders", "passed": True, "expected": {"sales_rows": 14219, "return_rows": 7395, "net_orders": 6824}})

    # Find a concrete Return + DTO sales row in the same period, then verify by-sale calculation.
    sales_r = s.get(f"{api}/sales", params={**params, "order_status": "DTO", "txn_type": "Return", "limit": 1}, timeout=60)
    results["return_dto_sales_status"] = sales_r.status_code
    sales_r.raise_for_status()
    sales_payload = sales_r.json()
    results["return_dto_sales_total"] = sales_payload.get("total")
    assert_true(sales_payload.get("total", 0) > 0 and sales_payload.get("items"), "No Return+DTO sales rows found")
    sale = sales_payload["items"][0]
    results["sample_sale"] = {k: sale.get(k) for k in ["id", "online_order_id", "sku", "order_status", "txn_type", "report_month", "portal"]}
    assert_true(sale.get("order_status") == "DTO", f"sample sale status not DTO: {sale.get('order_status')}")
    assert_true(sale.get("txn_type") == "Return", f"sample sale txn_type not Return: {sale.get('txn_type')}")
    results["checks"].append({"name": "found_return_dto_sales_row", "passed": True, "sample_sales_id": sale.get("id")})

    by_sale = s.get(f"{api}/calculations/by-sale/{sale['id']}", timeout=60)
    results["by_sale_status"] = by_sale.status_code
    by_sale.raise_for_status()
    calc = by_sale.json()["calculation"]
    results["sample_by_sale_calc"] = {k: calc.get(k) for k in ["id", "sales_id", "order_type", "commission_incl_gst", "gt_charge", "fixed_fee_incl_gst", "return_fee", "tcs", "tds", "commission_gst", "fixed_fee_gst"]}
    assert_true(calc.get("order_type") == "return_dto", f"by-sale calc order_type expected return_dto got {calc.get('order_type')}")
    assert_true(calc.get("commission_incl_gst") is not None and calc.get("commission_incl_gst") < 0, f"commission_incl_gst must be negative got {calc.get('commission_incl_gst')}")
    assert_true(calc.get("gt_charge") is not None and calc.get("gt_charge") < 0, f"gt_charge must be negative got {calc.get('gt_charge')}")
    assert_true(calc.get("fixed_fee_incl_gst") is not None and calc.get("fixed_fee_incl_gst") < 0, f"fixed_fee_incl_gst must be negative got {calc.get('fixed_fee_incl_gst')}")
    assert_true(calc.get("return_fee") is not None and calc.get("return_fee") > 0, f"return_fee must be positive got {calc.get('return_fee')}")
    assert_true(calc.get("tcs") == 0 and calc.get("tds") == 0 and calc.get("commission_gst") == 0, f"tax fields expected zero got tcs={calc.get('tcs')} tds={calc.get('tds')} commission_gst={calc.get('commission_gst')}")
    results["checks"].append({"name": "by_sale_return_dto_reversal", "passed": True})

    # API sanity exactly requested: /api/calculations?order_type=return_dto&limit=1.
    calc_r = s.get(f"{api}/calculations", params={"order_type": "return_dto", "limit": 1}, timeout=60)
    results["calculations_return_dto_status"] = calc_r.status_code
    calc_r.raise_for_status()
    calc_payload = calc_r.json()
    assert_true(calc_payload.get("items"), "No /calculations return_dto item returned")
    c = calc_payload["items"][0]
    results["sample_calculations_return_dto"] = {k: c.get(k) for k in ["id", "sales_id", "portal", "report_month", "order_type", "commission_incl_gst", "gt_charge", "fixed_fee_incl_gst", "return_fee", "tcs", "tds", "commission_gst"]}
    assert_true(c.get("commission_incl_gst") is not None and c.get("commission_incl_gst") < 0, f"API sample commission must be negative got {c.get('commission_incl_gst')}")
    assert_true(c.get("gt_charge") is not None and c.get("gt_charge") < 0, f"API sample gt_charge must be negative got {c.get('gt_charge')}")
    assert_true(c.get("fixed_fee_incl_gst") is not None and c.get("fixed_fee_incl_gst") < 0, f"API sample fixed fee must be negative got {c.get('fixed_fee_incl_gst')}")
    assert_true(c.get("return_fee") is not None and c.get("return_fee") > 0, f"API sample return_fee must be positive got {c.get('return_fee')}")
    assert_true(c.get("tcs") == 0 and c.get("tds") == 0 and c.get("commission_gst") == 0, "API sample tax fields not zero")
    results["checks"].append({"name": "calculations_endpoint_return_dto_sanity", "passed": True})

    results["passed"] = True
    OUT_PATH.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        payload = {"passed": False, "error": str(e)}
        OUT_PATH.write_text(json.dumps(payload, indent=2))
        print(json.dumps(payload, indent=2), file=sys.stderr)
        raise