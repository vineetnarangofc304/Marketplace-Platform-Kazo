#!/usr/bin/env python3
"""Focused preview API verification for return_dto sign convention.

Does not touch production. Uses REACT_APP_BACKEND_URL from /app/frontend/.env.
"""
import io
import json
import os
import time
from pathlib import Path

import openpyxl
import requests


ROOT = Path("/app")
RESULT_PATH = ROOT / "test_reports" / "return_dto_preview_api_iter20_result.json"


def read_backend_url() -> str:
    env_path = ROOT / "frontend" / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE_URL = read_backend_url()
API = f"{BASE_URL}/api"
CREDS = {"email": "admin@fundle.ai", "password": "admin123"}


def request_with_retry(session: requests.Session, method: str, url: str, **kwargs):
    last_exc = None
    for attempt in range(1, 4):
        try:
            resp = session.request(method, url, timeout=45, **kwargs)
            if resp.status_code in (502, 503, 504):
                last_exc = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                time.sleep(attempt)
                continue
            return resp
        except Exception as exc:  # noqa: BLE001 - test utility
            last_exc = exc
            time.sleep(attempt)
    raise last_exc


def assert_status(resp: requests.Response, expected: int = 200):
    if resp.status_code != expected:
        raise AssertionError(f"Expected HTTP {expected} for {resp.url}, got {resp.status_code}: {resp.text[:500]}")


def is_zero(v) -> bool:
    return float(v or 0) == 0.0


def main():
    result = {
        "base_url": BASE_URL,
        "production_touched": "no",
        "checks": [],
        "samples": {},
        "passed": False,
    }
    session = requests.Session()

    try:
        health = request_with_retry(session, "GET", f"{API}/health")
        assert_status(health)
        result["checks"].append({"name": "preview health", "passed": True, "status": health.json()})

        login = request_with_retry(session, "POST", f"{API}/auth/login", json=CREDS)
        assert_status(login)
        token = login.json()["token"]
        session.headers.update({"Authorization": f"Bearer {token}"})
        result["checks"].append({"name": "admin login", "passed": True, "user": login.json().get("user")})

        # Exact API probe requested by the reviewer: no production URL, no extra filters.
        calc_params = {"order_type": "return_dto", "limit": 10}
        calc_resp = request_with_retry(session, "GET", f"{API}/calculations", params=calc_params)
        assert_status(calc_resp)
        calc_data = calc_resp.json()
        rows = calc_data.get("items") or []
        if not rows:
            raise AssertionError("No return_dto calculation rows returned from preview")
        failures = []
        for idx, row in enumerate(rows):
            checks = {
                "commission_incl_gst < 0": row.get("commission_incl_gst") is not None and float(row["commission_incl_gst"]) < 0,
                "gt_charge < 0": row.get("gt_charge") is not None and float(row["gt_charge"]) < 0,
                "fixed_fee_incl_gst > 0": row.get("fixed_fee_incl_gst") is not None and float(row["fixed_fee_incl_gst"]) > 0,
                "return_fee > 0": row.get("return_fee") is not None and float(row["return_fee"]) > 0,
                "tcs == 0": is_zero(row.get("tcs")),
                "tds == 0": is_zero(row.get("tds")),
                "commission_gst == 0": is_zero(row.get("commission_gst")),
            }
            if not all(checks.values()):
                failures.append({
                    "idx": idx,
                    "id": row.get("id"),
                    "sales_id": row.get("sales_id"),
                    "checks": checks,
                    "values": {k: row.get(k) for k in [
                        "commission_incl_gst", "gt_charge", "fixed_fee_incl_gst", "return_fee", "tcs", "tds", "commission_gst"
                    ]},
                })
        if failures:
            raise AssertionError(f"return_dto sign convention failures: {failures}")
        result["checks"].append({
            "name": "return_dto API sign convention",
            "passed": True,
            "total": calc_data.get("total"),
            "tested_rows": len(rows),
        })
        result["samples"]["return_dto_first"] = {
            "id": rows[0].get("id"),
            "sales_id": rows[0].get("sales_id"),
            "online_order_id": rows[0].get("online_order_id"),
            "commission_incl_gst": rows[0].get("commission_incl_gst"),
            "fixed_fee_incl_gst": rows[0].get("fixed_fee_incl_gst"),
            "gt_charge": rows[0].get("gt_charge"),
            "return_fee": rows[0].get("return_fee"),
            "tcs": rows[0].get("tcs"),
            "tds": rows[0].get("tds"),
            "commission_gst": rows[0].get("commission_gst"),
        }

        summary_params = {"period_type": "month", "period_value": "2026-04", "portal": "myntra"}
        summary_resp = request_with_retry(session, "GET", f"{API}/sales/summary", params=summary_params)
        assert_status(summary_resp)
        summary = summary_resp.json()
        if summary.get("net_orders") != 6824:
            raise AssertionError(f"Expected net_orders=6824, got {summary.get('net_orders')} ({summary})")
        result["checks"].append({"name": "sales summary net_orders regression", "passed": True, "summary": summary})

        sales_calc_resp = request_with_retry(session, "GET", f"{API}/calculations", params={
            "order_type": "sales", "period_type": "month", "period_value": "2026-04", "portal": "myntra", "limit": 10
        })
        assert_status(sales_calc_resp)
        sales_rows = sales_calc_resp.json().get("items") or []
        if not sales_rows:
            raise AssertionError("No sales calculation rows returned for regression check")
        sales_failures = []
        for idx, row in enumerate(sales_rows):
            checks = {
                "commission_incl_gst > 0": row.get("commission_incl_gst") is not None and float(row["commission_incl_gst"]) > 0,
                "gt_charge > 0": row.get("gt_charge") is not None and float(row["gt_charge"]) > 0,
                "fixed_fee_incl_gst > 0": row.get("fixed_fee_incl_gst") is not None and float(row["fixed_fee_incl_gst"]) > 0,
            }
            if not all(checks.values()):
                sales_failures.append({"idx": idx, "id": row.get("id"), "checks": checks})
        if sales_failures:
            raise AssertionError(f"sales-side positive sign failures: {sales_failures}")
        result["checks"].append({"name": "sales-side positive sign regression", "passed": True, "tested_rows": len(sales_rows)})
        result["samples"]["sales_first"] = {
            "id": sales_rows[0].get("id"),
            "commission_incl_gst": sales_rows[0].get("commission_incl_gst"),
            "fixed_fee_incl_gst": sales_rows[0].get("fixed_fee_incl_gst"),
            "gt_charge": sales_rows[0].get("gt_charge"),
        }

        export_resp = request_with_retry(session, "GET", f"{API}/sales/export", params=summary_params)
        assert_status(export_resp)
        wb = openpyxl.load_workbook(io.BytesIO(export_resp.content), read_only=True, data_only=True)
        ws = wb.active
        headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
        if len(headers) != 31:
            raise AssertionError(f"Expected 31 export columns, got {len(headers)}: {headers}")
        result["checks"].append({"name": "sales export column count", "passed": True, "column_count": len(headers), "headers": headers})

        result["passed"] = True
    except Exception as exc:  # noqa: BLE001 - write deterministic test report details
        result["passed"] = False
        result["error"] = str(exc)

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps(result, indent=2, default=str))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()