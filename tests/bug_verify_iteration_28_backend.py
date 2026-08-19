#!/usr/bin/env python3
"""Focused backend verification for iteration 28 DTO/RTO rounding/sign fix.

Checks the user-reported contract on the public preview API:
  - sale_dto: commission < 0, fixed = 0, GT < 0, return_fee > 0,
    settlement = 0, and total_deductions exactly equals the sum of the four
    rounded/displayed fee heads across all rows.
  - return_dto/rto/sales/return regressions for signs and arithmetic identity.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


BASE_URL = os.environ.get(
    "BACKEND_URL",
    "https://settlement-intel-1.preview.emergentagent.com",
).rstrip("/")
OUT = Path("/app/test_reports/iteration_28_backend_evidence.json")
LIMIT = 2000
EMAIL = os.environ.get("TEST_EMAIL", "admin@fundle.ai")
PASSWORD = os.environ.get("TEST_PASSWORD", "admin123")
SESSION = requests.Session()


def login() -> None:
    resp = SESSION.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=60,
    )
    resp.raise_for_status()
    token = resp.json().get("token")
    if not token:
        raise RuntimeError("Login succeeded but no token returned")
    SESSION.headers.update({"Authorization": f"Bearer {token}"})


def dec(value: Any) -> Decimal:
    if value is None:
        raise ValueError("value is None")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"not decimal: {value!r}") from exc


def row_ref(row: Dict[str, Any], extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    out = {
        "id": row.get("id"),
        "sales_id": row.get("sales_id"),
        "online_order_id": row.get("online_order_id"),
        "sku": row.get("sku"),
        "order_type": row.get("order_type"),
        "commission_incl_gst": row.get("commission_incl_gst"),
        "commission_base": row.get("commission_base"),
        "fixed_fee_incl_gst": row.get("fixed_fee_incl_gst"),
        "fixed_fee": row.get("fixed_fee"),
        "gt_charge": row.get("gt_charge"),
        "return_fee": row.get("return_fee"),
        "total_deductions": row.get("total_deductions"),
        "nsv_after_gt": row.get("nsv_after_gt"),
        "expected_settlement": row.get("expected_settlement"),
        "report_month": row.get("report_month"),
        "unmapped": row.get("unmapped"),
    }
    if extra:
        out.update(extra)
    return out


def heads(row: Dict[str, Any]) -> Tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    commission_value = row.get("commission_incl_gst", row.get("commission_base"))
    fixed_value = row.get("fixed_fee_incl_gst", row.get("fixed_fee"))
    return (
        dec(commission_value),
        dec(fixed_value),
        dec(row.get("gt_charge")),
        dec(row.get("return_fee")),
        dec(row.get("total_deductions")),
        dec(row.get("nsv_after_gt")),
        dec(row.get("expected_settlement")),
    )


def fetch_all(order_type: str) -> Tuple[int, List[Dict[str, Any]]]:
    items: List[Dict[str, Any]] = []
    total: int | None = None
    skip = 0
    while True:
        resp = SESSION.get(
            f"{BASE_URL}/api/calculations",
            params={"order_type": order_type, "limit": LIMIT, "skip": skip},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        if total is None:
            total = int(data.get("total", 0))
        page = data.get("items", [])
        items.extend(page)
        if len(items) >= total or not page:
            break
        skip += LIMIT
    return total or 0, items


def add_issue(bucket: List[Dict[str, Any]], row: Dict[str, Any], issue: str, extra: Dict[str, Any] | None = None) -> None:
    if len(bucket) < 10:
        bucket.append(row_ref(row, {"issue": issue, **(extra or {})}))


def check_sum(row: Dict[str, Any], issues: List[Dict[str, Any]]) -> bool:
    try:
        comm, ff, gt, rf, total, _nsv, _settlement = heads(row)
    except ValueError as exc:
        add_issue(issues, row, f"non-numeric/null fee head: {exc}")
        return False
    expected_total = comm + ff + gt + rf
    if total != expected_total:
        add_issue(
            issues,
            row,
            "total_deductions != commission + fixed_fee + gt_charge + return_fee",
            {"computed_sum": str(expected_total), "drift": str(total - expected_total)},
        )
        return False
    return True


def check_identity(row: Dict[str, Any], issues: List[Dict[str, Any]]) -> bool:
    try:
        _comm, _ff, _gt, _rf, total, nsv, settlement = heads(row)
    except ValueError as exc:
        add_issue(issues, row, f"non-numeric/null identity value: {exc}")
        return False
    expected_settlement = nsv - total
    if settlement != expected_settlement:
        add_issue(
            issues,
            row,
            "expected_settlement != nsv_after_gt - total_deductions",
            {"computed_settlement": str(expected_settlement), "drift": str(settlement - expected_settlement)},
        )
        return False
    return True


def analyze(order_type: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    sign_issues: List[Dict[str, Any]] = []
    sum_issues: List[Dict[str, Any]] = []
    identity_issues: List[Dict[str, Any]] = []

    for row in rows:
        if row.get("order_type") != order_type:
            add_issue(sign_issues, row, f"wrong order_type returned; expected {order_type}")
            continue

        sum_ok = check_sum(row, sum_issues)
        try:
            comm, ff, gt, rf, _total, _nsv, settlement = heads(row)
        except ValueError as exc:
            add_issue(sign_issues, row, f"non-numeric/null sign value: {exc}")
            continue

        if order_type == "sale_dto":
            if not (comm < 0 and ff == 0 and gt < 0 and rf > 0 and settlement == 0):
                add_issue(sign_issues, row, "sale_dto sign/settlement contract failed")
        elif order_type == "return_dto":
            if not (comm < 0 and ff == 0 and gt < 0 and rf > 0):
                add_issue(sign_issues, row, "return_dto sign contract failed")
            check_identity(row, identity_issues)
        elif order_type == "rto":
            if not (comm < 0 and ff < 0 and gt < 0 and rf == 0 and settlement == 0):
                add_issue(sign_issues, row, "rto sign/return_fee/settlement contract failed")
        elif order_type == "sales":
            if not (comm > 0 and ff > 0 and gt > 0 and rf == 0):
                add_issue(sign_issues, row, "sales positive-fee contract failed")
            check_identity(row, identity_issues)
        elif order_type == "return":
            if not (comm < 0 and ff < 0 and gt < 0 and rf > 0):
                add_issue(sign_issues, row, "return sign-flipped fee contract failed")
            check_identity(row, identity_issues)

        if not sum_ok:
            continue

    return {
        "rows_checked": len(rows),
        "sign_issue_count": len(sign_issues),
        "sum_issue_count": len(sum_issues),
        "identity_issue_count": len(identity_issues),
        "sample_sign_issues": sign_issues,
        "sample_sum_issues": sum_issues,
        "sample_identity_issues": identity_issues,
        "sample_pass_row": row_ref(rows[0]) if rows else None,
    }


def main() -> int:
    results: Dict[str, Any] = {
        "base_url": BASE_URL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": "/api/calculations",
        "skill_lookup": "No relevant testing skill found.",
        "orders": {},
    }
    login()
    results["authenticated_as"] = EMAIL

    expected_counts = {
        "sale_dto": 5210,
        "return_dto": 5443,
        "rto": 3705,
    }
    overall_ok = True
    for order_type in ["sale_dto", "return_dto", "rto", "sales", "return"]:
        total, rows = fetch_all(order_type)
        analysis = analyze(order_type, rows)
        analysis["api_total"] = total
        analysis["fetched_count"] = len(rows)
        if order_type in expected_counts:
            analysis["expected_count"] = expected_counts[order_type]
            analysis["expected_count_match"] = total == expected_counts[order_type] and len(rows) == expected_counts[order_type]
        else:
            analysis["expected_count"] = None
            analysis["expected_count_match"] = True
        results["orders"][order_type] = analysis

        if not analysis["expected_count_match"]:
            overall_ok = False
        if analysis["sign_issue_count"] or analysis["sum_issue_count"] or analysis["identity_issue_count"]:
            overall_ok = False
        if total != len(rows):
            overall_ok = False

    results["overall_ok"] = overall_ok
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())