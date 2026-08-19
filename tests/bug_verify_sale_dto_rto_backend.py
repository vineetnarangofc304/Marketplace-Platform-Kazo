#!/usr/bin/env python3
"""Focused backend verification for 19-Aug-2026 DTO/RTO calculation bug.

Checks existing preview calculation rows only (does not run/recalculate) so stale
rows would be detected.
"""
import json
import math
import os
import sys
from pathlib import Path

import requests


BASE = os.environ.get("TEST_BACKEND_URL", "https://settlement-intel-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
PERIOD = {"period_type": "month", "period_value": "2026-04", "portal": "myntra"}
OUT = Path("/app/test_reports/sale_dto_rto_backend_evidence.json")


def approx(a, b, tol=0.01):
    return math.isclose(float(a or 0), float(b or 0), abs_tol=tol)


def login(session: requests.Session):
    r = session.post(f"{API}/auth/login", json={"email": "admin@fundle.ai", "password": "admin123"}, timeout=30)
    r.raise_for_status()
    return r.json()["user"]


def get_json(session: requests.Session, path: str, params=None):
    r = session.get(f"{API}{path}", params=params or {}, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_all_calcs(session: requests.Session, order_type: str):
    rows = []
    skip = 0
    while True:
        data = get_json(session, "/calculations", {**PERIOD, "order_type": order_type, "limit": 2000, "skip": skip})
        if skip == 0:
            total = data["total"]
        batch = data["items"]
        rows.extend(batch)
        if len(rows) >= total or not batch:
            return total, rows
        skip += len(batch)


def calc_parts(c):
    return [
        c.get("commission_incl_gst"),
        c.get("fixed_fee_incl_gst"),
        c.get("gt_charge"),
        c.get("return_fee"),
    ]


def assert_sample_sales_shape(session, rows, expected_status, expected_txn, label):
    samples = []
    for c in rows[:5]:
        detail = get_json(session, f"/calculations/by-sale/{c['sales_id']}")
        sale = detail["sale"]
        samples.append({
            "order_id": sale.get("online_order_id"),
            "sales_id": c.get("sales_id"),
            "order_status": sale.get("order_status"),
            "txn_type": sale.get("txn_type"),
            "order_type": c.get("order_type"),
            "commission": c.get("commission_incl_gst"),
            "fixed_fee": c.get("fixed_fee_incl_gst"),
            "gt_charge": c.get("gt_charge"),
            "return_fee": c.get("return_fee"),
            "total_deductions": c.get("total_deductions"),
            "expected_settlement": c.get("expected_settlement"),
        })
        if sale.get("order_status") != expected_status:
            raise AssertionError(f"{label} sample {c['sales_id']} status {sale.get('order_status')} != {expected_status}")
        if expected_txn is not None and sale.get("txn_type") != expected_txn:
            raise AssertionError(f"{label} sample {c['sales_id']} txn {sale.get('txn_type')} != {expected_txn}")
    return samples


def main():
    evidence = {"base_url": BASE, "period": PERIOD, "checks": {}, "violations": {}}
    failures = []
    try:
      with requests.Session() as s:
        evidence["login_user"] = login(s)

        # Count parity proves all affected Sales rows have corresponding classified calc rows.
        sales_dto_total = get_json(s, "/sales", {**PERIOD, "order_status": "DTO", "txn_type": "Sales", "limit": 1})["total"]
        return_dto_sales_total = get_json(s, "/sales", {**PERIOD, "order_status": "DTO", "txn_type": "Return", "limit": 1})["total"]
        rto_sales_total = get_json(s, "/sales", {**PERIOD, "order_status": "RTO", "limit": 1})["total"]
        delivered_sales_total = get_json(s, "/sales", {**PERIOD, "order_status": "Delivered", "txn_type": "Sales", "limit": 1})["total"]

        sale_dto_total, sale_dto = fetch_all_calcs(s, "sale_dto")
        return_dto_total, return_dto = fetch_all_calcs(s, "return_dto")
        rto_total, rto = fetch_all_calcs(s, "rto")
        sales_total, sales_rows = fetch_all_calcs(s, "sales")

        evidence["checks"]["count_parity"] = {
            "sales_status_DTO_txn_Sales": sales_dto_total,
            "calc_order_type_sale_dto": sale_dto_total,
            "sales_status_DTO_txn_Return": return_dto_sales_total,
            "calc_order_type_return_dto": return_dto_total,
            "sales_status_RTO_any_txn": rto_sales_total,
            "calc_order_type_rto": rto_total,
            "sales_status_Delivered_txn_Sales": delivered_sales_total,
            "calc_order_type_sales": sales_total,
        }
        if sales_dto_total != sale_dto_total:
            raise AssertionError("DTO Sales row count does not match sale_dto calculations count")
        if return_dto_sales_total != return_dto_total:
            raise AssertionError("DTO Return row count does not match return_dto calculations count")
        if rto_sales_total != rto_total:
            raise AssertionError("RTO sales row count does not match rto calculations count")
        if delivered_sales_total != sales_total:
            raise AssertionError("Delivered Sales row count does not match sales calculations count")

        evidence["checks"]["sale_dto_samples"] = assert_sample_sales_shape(s, sale_dto, "DTO", "Sales", "sale_dto")
        evidence["checks"]["return_dto_samples"] = assert_sample_sales_shape(s, return_dto, "DTO", "Return", "return_dto")
        evidence["checks"]["rto_samples"] = assert_sample_sales_shape(s, rto, "RTO", None, "rto")
        evidence["checks"]["sales_samples"] = assert_sample_sales_shape(s, sales_rows, "Delivered", "Sales", "sales")

        sale_dto_violations = []
        sale_dto_violation_count = 0
        for c in sale_dto:
            comm, fixed, gt, ret = calc_parts(c)
            expected_sum = sum(float(v or 0) for v in (comm, fixed, gt, ret))
            total_matches_displayed_parts = round(float(c.get("total_deductions") or 0), 2) == round(expected_sum, 2)
            if not (comm is not None and comm < 0 and fixed == 0 and gt is not None and gt < 0 and ret is not None and ret > 0 and c.get("expected_settlement") == 0 and total_matches_displayed_parts):
                sale_dto_violation_count += 1
                if len(sale_dto_violations) < 20:
                    sale_dto_violations.append({"sales_id": c.get("sales_id"), "values": calc_parts(c), "total_deductions": c.get("total_deductions"), "displayed_parts_sum": round(expected_sum, 2), "expected_settlement": c.get("expected_settlement")})

        return_dto_violations = []
        return_dto_violation_count = 0
        for c in return_dto:
            comm, fixed, gt, ret = calc_parts(c)
            if not (comm is not None and comm < 0 and fixed == 0 and gt is not None and gt < 0 and ret is not None and ret > 0):
                return_dto_violation_count += 1
                if len(return_dto_violations) < 20:
                    return_dto_violations.append({"sales_id": c.get("sales_id"), "values": calc_parts(c)})

        rto_violations = []
        rto_violation_count = 0
        for c in rto:
            comm, fixed, gt, ret = calc_parts(c)
            if not (comm is not None and comm < 0 and fixed is not None and fixed < 0 and gt is not None and gt < 0 and ret == 0 and c.get("expected_settlement") == 0):
                rto_violation_count += 1
                if len(rto_violations) < 20:
                    rto_violations.append({"sales_id": c.get("sales_id"), "values": calc_parts(c), "expected_settlement": c.get("expected_settlement")})

        sales_violations = []
        sales_violation_count = 0
        for c in sales_rows:
            comm, fixed, gt, ret = calc_parts(c)
            if not (comm is not None and comm > 0 and fixed is not None and fixed > 0 and gt is not None and gt > 0 and ret == 0):
                sales_violation_count += 1
                if len(sales_violations) < 20:
                    sales_violations.append({"sales_id": c.get("sales_id"), "values": calc_parts(c)})

        evidence["violations"] = {
            "sale_dto": {"count": sale_dto_violation_count, "samples": sale_dto_violations},
            "return_dto": {"count": return_dto_violation_count, "samples": return_dto_violations},
            "rto": {"count": rto_violation_count, "samples": rto_violations},
            "sales": {"count": sales_violation_count, "samples": sales_violations},
        }
        for key, vals in evidence["violations"].items():
            if vals["count"]:
                failures.append(f"{key} violations found: {vals['count']} (samples in evidence file)")
    except Exception as exc:
        failures.append(str(exc))
        evidence["exception"] = repr(exc)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps({"ok": not failures, "failures": failures, "evidence_file": str(OUT), "counts": evidence.get("checks", {}).get("count_parity")}, indent=2))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()