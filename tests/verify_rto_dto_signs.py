#!/usr/bin/env python3
"""Focused backend verification for RTO and DTO fee sign conventions."""

import json
import math
import os
import sys
from pathlib import Path

import requests


ROOT = Path("/app")
OUT = ROOT / "test_reports" / "rto_dto_backend_evidence.json"


def read_frontend_base_url():
    env_path = ROOT / "frontend" / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().strip('"')
    return "http://localhost:8001"


BASE = os.environ.get("BACKEND_URL", read_frontend_base_url()).rstrip("/")
API = f"{BASE}/api"
EMAIL = os.environ.get("TEST_EMAIL", "admin@fundle.ai")
PASSWORD = os.environ.get("TEST_PASSWORD", "admin123")


def approx_equal(a, b, eps=0.011):
    return math.isclose(float(a), float(b), abs_tol=eps)


def fetch(session, order_type, limit=25):
    resp = session.get(
        f"{API}/calculations",
        params={"portal": "myntra", "order_type": order_type, "limit": limit, "sort_by": "computed_at", "sort_dir": "desc"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["total"], data["items"]


def compact(row):
    return {
        "id": row.get("id"),
        "sales_id": row.get("sales_id"),
        "online_order_id": row.get("online_order_id"),
        "sku": row.get("sku"),
        "order_type": row.get("order_type"),
        "commission_incl_gst": row.get("commission_incl_gst"),
        "fixed_fee_incl_gst": row.get("fixed_fee_incl_gst"),
        "gt_charge": row.get("gt_charge"),
        "return_fee": row.get("return_fee"),
        "total_deductions": row.get("total_deductions"),
        "expected_settlement": row.get("expected_settlement"),
    }


def check_rto(rows):
    violations = []
    for i, row in enumerate(rows[:5], 1):
        c = row.get("commission_incl_gst")
        f = row.get("fixed_fee_incl_gst")
        gt = row.get("gt_charge")
        rf = row.get("return_fee")
        td = row.get("total_deductions")
        st = row.get("expected_settlement")
        expected_total = float(c) + float(f) + float(gt) + 0.0
        if not (c < 0):
            violations.append(f"RTO sample {i}: commission not negative ({c})")
        if not (f < 0):
            violations.append(f"RTO sample {i}: fixed fee not negative ({f})")
        if not (gt < 0):
            violations.append(f"RTO sample {i}: GT charge not negative ({gt})")
        if not approx_equal(rf, 0.0):
            violations.append(f"RTO sample {i}: return fee not exactly zero ({rf})")
        if not approx_equal(td, expected_total):
            violations.append(f"RTO sample {i}: total_deductions {td} != commission+fixed+gt+0 {expected_total}")
        if not approx_equal(st, 0.0):
            violations.append(f"RTO sample {i}: settlement not zero ({st})")
    return violations


def check_dto(rows):
    violations = []
    for i, row in enumerate(rows[:5], 1):
        c = row.get("commission_incl_gst")
        f = row.get("fixed_fee_incl_gst")
        gt = row.get("gt_charge")
        rf = row.get("return_fee")
        if not (c < 0):
            violations.append(f"DTO sample {i}: commission not negative ({c})")
        if not approx_equal(f, 0.0):
            violations.append(f"DTO sample {i}: fixed fee not exactly zero ({f})")
        if not (gt < 0):
            violations.append(f"DTO sample {i}: GT charge not negative ({gt})")
        if not (rf > 0):
            violations.append(f"DTO sample {i}: return fee not positive ({rf})")
    return violations


def check_sales_return_smoke(session):
    smoke = {}
    violations = []
    for typ in ("sales", "return"):
        total, rows = fetch(session, typ, limit=5)
        smoke[typ] = {"total": total, "sample": [compact(r) for r in rows[:3]]}
        for i, row in enumerate(rows[:3], 1):
            c = row.get("commission_incl_gst")
            f = row.get("fixed_fee_incl_gst")
            gt = row.get("gt_charge")
            rf = row.get("return_fee")
            if typ == "sales":
                if not (c is not None and c >= 0 and f is not None and f >= 0 and gt is not None and gt >= 0 and approx_equal(rf, 0.0)):
                    violations.append(f"sales smoke sample {i}: expected positive/zero fee pattern, got {compact(row)}")
            else:
                if not (c is not None and c < 0 and f is not None and f < 0 and gt is not None and gt < 0 and rf is not None and rf > 0):
                    violations.append(f"return smoke sample {i}: expected reversal + positive return-fee pattern, got {compact(row)}")
    return smoke, violations


def main():
    session = requests.Session()
    login = session.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    login.raise_for_status()
    token = login.json().get("token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})

    rto_total, rto_rows = fetch(session, "rto", limit=25)
    dto_total, dto_rows = fetch(session, "return_dto", limit=25)
    evidence = {
        "api_base": API,
        "rto_total": rto_total,
        "return_dto_total": dto_total,
        "rto_sample_5": [compact(r) for r in rto_rows[:5]],
        "return_dto_sample_5": [compact(r) for r in dto_rows[:5]],
        "violations": [],
    }
    if len(rto_rows) < 5:
        evidence["violations"].append(f"Only {len(rto_rows)} RTO rows available; need 5")
    if len(dto_rows) < 5:
        evidence["violations"].append(f"Only {len(dto_rows)} DTO rows available; need 5")
    evidence["violations"].extend(check_rto(rto_rows))
    evidence["violations"].extend(check_dto(dto_rows))
    smoke, smoke_violations = check_sales_return_smoke(session)
    evidence["sales_return_smoke"] = smoke
    evidence["violations"].extend(smoke_violations)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))
    return 1 if evidence["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())