#!/usr/bin/env python3
"""Focused backend verification for DTO/RTO reversal scoping.

Bug contract: DTO/RTO reversal arithmetic must apply only to Return rows.
Sales rows with order_status DTO/RTO must remain order_type=sales with positive fees.
"""
import json
import math
import os
import sys
from typing import Any, Dict, List

import requests


BASE = os.environ.get("BACKEND_URL", "https://settlement-intel-1.preview.emergentagent.com").rstrip("/")
EMAIL = os.environ.get("TEST_EMAIL", "admin@fundle.ai")
PASSWORD = os.environ.get("TEST_PASSWORD", "admin123")
LIMIT = 2000


def n(v: Any) -> float:
    if v is None:
        return float("nan")
    return float(v)


def close(a: Any, b: Any, tol: float = 0.011) -> bool:
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def api_get_all(sess: requests.Session, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    first = sess.get(f"{BASE}/api{path}", params={**params, "limit": LIMIT, "skip": 0}, timeout=60)
    first.raise_for_status()
    data = first.json()
    total = int(data.get("total", 0))
    items: List[Dict[str, Any]] = list(data.get("items", []))
    for skip in range(LIMIT, total, LIMIT):
        r = sess.get(f"{BASE}/api{path}", params={**params, "limit": LIMIT, "skip": skip}, timeout=60)
        r.raise_for_status()
        items.extend(r.json().get("items", []))
    return {"total": total, "items": items}


def sample_bad(rows: List[Dict[str, Any]], predicate, limit: int = 5) -> List[Dict[str, Any]]:
    bad = []
    for row in rows:
        if predicate(row):
            bad.append({
                "sales_id": row.get("sales_id"),
                "online_order_id": row.get("online_order_id"),
                "order_type": row.get("order_type"),
                "commission": row.get("commission_incl_gst"),
                "fixed_fee": row.get("fixed_fee_incl_gst"),
                "gt_charge": row.get("gt_charge"),
                "return_fee": row.get("return_fee"),
                "total_deductions": row.get("total_deductions"),
                "expected_settlement": row.get("expected_settlement"),
            })
            if len(bad) >= limit:
                break
    return bad


def main() -> int:
    sess = requests.Session()
    login = sess.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    if login.status_code != 200:
        print(json.dumps({"ok": False, "blocker": f"Login failed {login.status_code}: {login.text[:300]}"}, indent=2))
        return 2
    token = login.json().get("token")
    sess.headers.update({"Authorization": f"Bearer {token}"})

    evidence: Dict[str, Any] = {"base": BASE, "login_email": EMAIL, "checks": {}, "failures": []}

    # Core calculation order-type checks.
    for ot in ["sales", "return", "return_dto", "rto", "internal_cancel", "sale_dto"]:
        page = api_get_all(sess, "/calculations", {"order_type": ot})
        evidence["checks"][f"count_{ot}"] = page["total"]
        evidence["checks"][f"rows_fetched_{ot}"] = len(page["items"])
        evidence[f"rows_{ot}"] = page["items"]

    return_dto = evidence.pop("rows_return_dto")
    rto = evidence.pop("rows_rto")
    sales = evidence.pop("rows_sales")
    ret = evidence.pop("rows_return")
    evidence.pop("rows_internal_cancel")
    evidence.pop("rows_sale_dto")

    bad_return_dto = sample_bad(
        return_dto,
        lambda c: not (
            n(c.get("commission_incl_gst")) < 0
            and close(c.get("fixed_fee_incl_gst"), 0)
            and n(c.get("gt_charge")) < 0
            and n(c.get("return_fee")) > 0
            and close(c.get("total_deductions"), n(c.get("commission_incl_gst")) + n(c.get("fixed_fee_incl_gst")) + n(c.get("gt_charge")) + n(c.get("return_fee")))
        ),
    )
    evidence["checks"]["return_dto_sign_total_failures_sample"] = bad_return_dto

    bad_rto = sample_bad(
        rto,
        lambda c: not (
            n(c.get("commission_incl_gst")) < 0
            and n(c.get("fixed_fee_incl_gst")) < 0
            and n(c.get("gt_charge")) < 0
            and close(c.get("return_fee"), 0)
            and close(c.get("expected_settlement"), 0)
        ),
    )
    evidence["checks"]["rto_sign_settlement_failures_sample"] = bad_rto

    bad_sales_negative = sample_bad(
        sales,
        lambda c: any(n(c.get(k)) < 0 for k in ["commission_incl_gst", "fixed_fee_incl_gst", "gt_charge"]),
    )
    bad_sales_return_fee = sample_bad(sales, lambda c: not close(c.get("return_fee"), 0))
    evidence["checks"]["sales_negative_fee_failures_sample"] = bad_sales_negative
    evidence["checks"]["sales_return_fee_nonzero_sample"] = bad_sales_return_fee

    bad_return = sample_bad(
        ret,
        lambda c: not (
            n(c.get("commission_incl_gst")) < 0
            and n(c.get("fixed_fee_incl_gst")) < 0
            and n(c.get("gt_charge")) < 0
            and n(c.get("return_fee")) >= 0
        ),
    )
    evidence["checks"]["return_sign_failures_sample"] = bad_return

    # Sales collection cross-reference through the public API + by-sale endpoint.
    cross_refs = {}
    for status in ["DTO", "RTO"]:
        rows = api_get_all(sess, "/sales", {"txn_type": "Sales", "order_status": status, "limit": 5})
        cross_refs[status] = {"sales_total": rows["total"], "samples": []}
        for sale in rows["items"][:5]:
            rr = sess.get(f"{BASE}/api/calculations/by-sale/{sale['id']}", timeout=30)
            rr.raise_for_status()
            joined = rr.json()
            c = joined["calculation"]
            s = joined["sale"]
            sample = {
                "sales_id": sale["id"],
                "order_id": sale.get("online_order_id"),
                "sale_txn_type": s.get("txn_type"),
                "sale_status": s.get("order_status"),
                "calc_order_type": c.get("order_type"),
                "commission": c.get("commission_incl_gst"),
                "fixed_fee": c.get("fixed_fee_incl_gst"),
                "gt_charge": c.get("gt_charge"),
                "return_fee": c.get("return_fee"),
            }
            ok = (
                s.get("txn_type") == "Sales"
                and s.get("order_status") == status
                and c.get("order_type") == "sales"
                and n(c.get("commission_incl_gst")) > 0
                and n(c.get("fixed_fee_incl_gst")) > 0
                and n(c.get("gt_charge")) > 0
                and close(c.get("return_fee"), 0)
            )
            sample["ok"] = ok
            cross_refs[status]["samples"].append(sample)
            if not ok:
                evidence["failures"].append({"cross_reference_failed": sample})
    evidence["checks"]["sales_dto_rto_cross_refs"] = cross_refs

    if bad_return_dto:
        evidence["failures"].append({"return_dto_failures": bad_return_dto})
    if bad_rto:
        evidence["failures"].append({"rto_failures": bad_rto})
    if bad_sales_negative:
        evidence["failures"].append({"sales_negative_fee_failures": bad_sales_negative})
    if bad_sales_return_fee:
        evidence["failures"].append({"sales_return_fee_nonzero": bad_sales_return_fee})
    if bad_return:
        evidence["failures"].append({"return_failures": bad_return})
    if evidence["checks"]["count_sale_dto"] != 0:
        evidence["failures"].append({"sale_dto_count": evidence["checks"]["count_sale_dto"]})

    # Expected preview counts from handoff; record count drift as evidence but don't hide sign regressions.
    expected_counts = {"sales": 14219, "return": 92, "return_dto": 5443, "rto": 1787, "internal_cancel": 73, "sale_dto": 0}
    count_mismatches = {k: {"expected": v, "actual": evidence["checks"].get(f"count_{k}")} for k, v in expected_counts.items() if evidence["checks"].get(f"count_{k}") != v}
    evidence["checks"]["expected_count_mismatches"] = count_mismatches

    # Keep output compact by not printing thousands of rows.
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 1 if evidence["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())