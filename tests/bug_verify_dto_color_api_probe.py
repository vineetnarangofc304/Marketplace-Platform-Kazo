"""
Focused API probe for DTO/RTO colour-verification UI test.

Logs in with the provided admin credentials, fetches representative calculation
rows, and prints row IDs/values that the browser UI test can verify visually.
This does not modify application data.
"""

import json
import os

import requests


BASE = os.environ.get("BACKEND_URL", "https://settlement-intel-1.preview.emergentagent.com")
API = f"{BASE.rstrip('/')}/api"


def login():
    res = requests.post(
        f"{API}/auth/login",
        json={"email": "admin@fundle.ai", "password": "admin123"},
        timeout=30,
    )
    res.raise_for_status()
    return res.json()["token"]


def fetch_calcs(token, order_type, sort_by="settlement", sort_dir="desc", limit=20):
    res = requests.get(
        f"{API}/calculations",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "portal": "myntra",
            "order_type": order_type,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "limit": limit,
        },
        timeout=30,
    )
    res.raise_for_status()
    return res.json()


def fetch_sales(token, txn_type="Sales", limit=20):
    res = requests.get(
        f"{API}/sales",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "portal": "myntra",
            "txn_type": txn_type,
            "sort_by": "order_date",
            "sort_dir": "desc",
            "limit": limit,
        },
        timeout=30,
    )
    res.raise_for_status()
    return res.json()


def row_summary(c):
    return {
        "id": c.get("id"),
        "sales_id": c.get("sales_id"),
        "order_id": c.get("online_order_id"),
        "commission": c.get("commission_incl_gst"),
        "fixed_fee": c.get("fixed_fee_incl_gst"),
        "gt": c.get("gt_charge"),
        "return_fee": c.get("return_fee"),
        "total_deductions": c.get("total_deductions"),
        "expected_settlement": c.get("expected_settlement"),
    }


def main():
    token = login()
    dto = fetch_calcs(token, "return_dto", limit=30)
    rto = fetch_calcs(token, "rto", limit=30)
    sales = fetch_sales(token, "Sales", limit=30)
    payload = {
        "dto_total": dto.get("total"),
        "dto_sample": [row_summary(c) for c in dto.get("items", [])[:5]],
        "rto_total": rto.get("total"),
        "rto_sample": [row_summary(c) for c in rto.get("items", [])[:5]],
        "sales_total": sales.get("total"),
        "sales_sample": [
            {"id": r.get("id"), "order_id": r.get("online_order_id"), "txn_type": r.get("txn_type")}
            for r in sales.get("items", [])[:5]
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()