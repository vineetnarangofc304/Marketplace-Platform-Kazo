"""Iteration 13 — multi-portal calc + Amazon normalizer + Rebuild-All button.

These tests exercise the new pieces:
  1. `_normalize_row_for_portal` maps Amazon MTR statuses to canonical taxonomy.
  2. `_compute_expected_portal` produces correct T1/T2 charges for Amazon
     using the fee-heads matrix (18.7% commission + 11.5% logistic).
  3. `POST /api/calculations/run` accepts `portal` param + `recalculate=true`.
  4. Portals API surfaces all 6 marketplaces as `live`.
"""
import os

import pytest
import requests

# Ensure MONGO_URL / DB_NAME are populated from backend/.env for direct imports
def _load_env():
    envfile = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(envfile):
        return
    with open(envfile) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k.strip(), v)

_load_env()

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


def _login():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "admin@fundle.ai", "password": "admin123"})
    assert r.status_code == 200, r.text
    return s


def test_all_portals_live():
    s = _login()
    r = s.get(f"{API}/portals")
    assert r.status_code == 200
    portals = r.json()
    codes = {p["code"] for p in portals}
    assert codes >= {"myntra", "amazon", "ajio", "nykaa", "tatacliq", "flipkart"}
    for p in portals:
        assert p["status"] == "live", f"{p['code']} should be live, got {p['status']}"


def test_amazon_normalizer_sales():
    """Amazon MTR 'Shipped' rows → txn_type=Sales, order_status=Delivered."""
    from routers.uploads_r import _normalize_row_for_portal

    rec = {"txn_type": None, "order_status": "Shipped", "nsv_val": 1200.0}
    _normalize_row_for_portal(rec, "amazon")
    assert rec["txn_type"] == "Sales"
    assert rec["order_status"] == "Delivered"


def test_amazon_normalizer_refund_becomes_return_dto():
    """Amazon 'Refund' rows with negative principal → txn_type=Return."""
    from routers.uploads_r import _normalize_row_for_portal

    rec = {"txn_type": "Refund", "order_status": "Cancelled", "nsv_val": -1200.0}
    _normalize_row_for_portal(rec, "amazon")
    assert rec["txn_type"] == "Return"
    assert rec["order_status"] == "DTO"


def test_amazon_normalizer_myntra_is_noop():
    from routers.uploads_r import _normalize_row_for_portal

    rec = {"txn_type": "Sales", "order_status": "Delivered", "nsv_val": 1000.0}
    _normalize_row_for_portal(rec, "myntra")
    assert rec["txn_type"] == "Sales"
    assert rec["order_status"] == "Delivered"


def test_amazon_generic_calc_matches_seed_rates():
    """Feed a synthetic Amazon sale into _compute_expected_portal; expect
    Commission=18.7% and Logistic=11.5% of NSV, and expected_settlement to
    match NSV minus those two.
    """
    from routers.calculations import _compute_expected_portal
    from data_portals_seed import PORTALS_SEED

    pdoc = next(p for p in PORTALS_SEED if p["code"] == "amazon")
    sale = {
        "nsv_val": 1000.0,
        "order_status": "Delivered",
        "txn_type": "Sales",
        "qty": 1,
    }
    res = _compute_expected_portal(sale, pdoc)
    assert abs(res["commission"] - 187.0) < 0.01
    assert abs(res["gt_charge"] - 115.0) < 0.01     # logistic head surfaces as gt_charge
    assert abs(res["expected_settlement"] - (1000 - 187 - 115)) < 0.01
    assert res["order_type"] == "sales"
    assert res["unmapped"] is False


def test_amazon_rto_zeroed():
    """Amazon RTO → all fees zero, expected_settlement = NSV (no deductions)."""
    from routers.calculations import _compute_expected_portal
    from data_portals_seed import PORTALS_SEED

    pdoc = next(p for p in PORTALS_SEED if p["code"] == "amazon")
    sale = {"nsv_val": 1000.0, "order_status": "RTO", "txn_type": "Sales", "qty": 1}
    res = _compute_expected_portal(sale, pdoc)
    assert res["commission"] == 0
    assert res["gt_charge"] == 0
    assert res["total_deductions"] == 0


def test_rebuild_all_endpoint_accepts_portal_scope():
    """POST /calculations/run with recalculate=true + portal filter returns 200."""
    s = _login()
    # No sales for amazon yet → processed 0, but endpoint must respond cleanly.
    r = s.post(f"{API}/calculations/run", json={"recalculate": True, "portal": "amazon"})
    assert r.status_code == 200
    body = r.json()
    assert "total_sales" in body
    assert body.get("total_sales") == 0


def test_rebuild_all_myntra_recalculate():
    """Rebuild for myntra should return processed count == total_sales."""
    s = _login()
    r = s.post(f"{API}/calculations/run", json={"recalculate": True, "portal": "myntra"})
    assert r.status_code == 200
    body = r.json()
    assert body["total_sales"] > 0
    assert body["processed"] == body["total_sales"]
