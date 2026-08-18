#!/usr/bin/env python3
"""Focused preview backend verification for Google Doc DTO/RTO sign rules.

Does not mutate application data and does not call production.
"""

import json
import sys
from pathlib import Path

import requests


BASE_URL = "https://settlement-intel-1.preview.emergentagent.com"
API = f"{BASE_URL}/api"
OUT = Path("/app/test_reports/bug_verify_dto_rto_signs_iter23_backend_result.json")


def sign_ok(order_type, row):
    commission = row.get("commission_incl_gst")
    fixed_fee = row.get("fixed_fee_incl_gst")
    gt_charge = row.get("gt_charge")
    return_fee = row.get("return_fee")
    if order_type == "return_dto":
        return commission < 0 and fixed_fee == 0 and gt_charge < 0 and return_fee > 0
    if order_type == "rto":
        return commission < 0 and fixed_fee < 0 and gt_charge < 0 and return_fee < 0
    raise AssertionError(f"Unexpected order type {order_type}")


def compact(row):
    return {
        "id": row.get("id"),
        "sales_id": row.get("sales_id"),
        "online_order_id": row.get("online_order_id"),
        "order_type": row.get("order_type"),
        "commission_incl_gst": row.get("commission_incl_gst"),
        "fixed_fee_incl_gst": row.get("fixed_fee_incl_gst"),
        "gt_charge": row.get("gt_charge"),
        "return_fee": row.get("return_fee"),
        "total_deductions": row.get("total_deductions"),
        "expected_settlement": row.get("expected_settlement"),
        "report_month": row.get("report_month"),
        "unmapped": row.get("unmapped"),
    }


def main():
    sess = requests.Session()
    login = sess.post(f"{API}/auth/login", json={"email": "admin@fundle.ai", "password": "admin123"}, timeout=30)
    if login.status_code != 200:
        login = sess.post(f"{API}/auth/login", json={"email": "admin@kazo.com", "password": "admin123"}, timeout=30)
    login.raise_for_status()
    token = login.json().get("access_token")
    if token:
        sess.headers.update({"Authorization": f"Bearer {token}"})

    results = {"base_url": BASE_URL, "production_called": False, "checks": {}}
    failures = []

    for order_type in ["return_dto", "rto"]:
        res = sess.get(
            f"{API}/calculations",
            params={"portal": "myntra", "order_type": order_type, "limit": 25, "sort_by": "settlement", "sort_dir": "desc"},
            timeout=30,
        )
        res.raise_for_status()
        payload = res.json()
        rows = payload.get("items", [])
        sample = rows[:5]
        bad = [compact(r) for r in sample if not sign_ok(order_type, r)]
        if len(sample) < 5:
            failures.append(f"{order_type}: expected at least 5 rows, got {len(sample)}")
        if bad:
            failures.append(f"{order_type}: sign failures in sampled rows")

        by_sale = None
        if sample:
            detail = sess.get(f"{API}/calculations/by-sale/{sample[0]['sales_id']}", timeout=30)
            detail.raise_for_status()
            by_sale_calc = detail.json().get("calculation", {})
            by_sale = compact(by_sale_calc)
            if not sign_ok(order_type, by_sale_calc):
                failures.append(f"{order_type}: /calculations/by-sale detail signs failed for first sample")

        results["checks"][order_type] = {
            "total": payload.get("total"),
            "sample_count": len(sample),
            "all_first_5_match_spec": not bad and len(sample) >= 5,
            "first_5": [compact(r) for r in sample],
            "by_sale_first_row": by_sale,
        }

    results["verdict"] = "pass" if not failures else "fail"
    results["failures"] = failures
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())