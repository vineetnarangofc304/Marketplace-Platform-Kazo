"""Backend tests for multi-marketplace Portals feature."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://settlement-intel-1.preview.emergentagent.com").rstrip("/")
EXPECTED_CODES = {"myntra", "amazon", "ajio", "nykaa", "tatacliq", "flipkart"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@fundle.ai", "password": "admin123"}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# -- Portals CRUD --------------------------------------------------------
class TestPortalsCRUD:
    def test_list_portals_returns_6(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/portals", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) == 6
        codes = {p["code"] for p in data}
        assert codes == EXPECTED_CODES
        for p in data:
            assert "fee_heads" in p and isinstance(p["fee_heads"], list) and len(p["fee_heads"]) >= 1
            assert "case_matrix" in p and isinstance(p["case_matrix"], dict)
            assert set(p["case_matrix"].keys()) >= {"Delivered", "DTO", "RTO", "InternalCancel"}
            assert p["status"] in ("live", "coming_soon")
            assert "sales_count" in p and "upload_count" in p
        # myntra live, others coming_soon
        by_code = {p["code"]: p for p in data}
        assert by_code["myntra"]["status"] == "live"
        for c in EXPECTED_CODES - {"myntra"}:
            assert by_code[c]["status"] == "coming_soon", f"{c} should be coming_soon"

    def test_get_single_portal(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/portals/amazon", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["code"] == "amazon"
        assert d["name"] == "Amazon"

    def test_get_unknown_portal_404(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/portals/doesnotexist", headers=admin_headers, timeout=15)
        assert r.status_code == 404

    def test_upsert_portal_notes_persists(self, admin_headers):
        marker = "TEST_marker_notes_xyz"
        r = requests.post(f"{BASE_URL}/api/portals/ajio", headers=admin_headers, json={"notes": marker}, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["portal"]["notes"] == marker
        # GET again to confirm persistence
        r2 = requests.get(f"{BASE_URL}/api/portals/ajio", headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["notes"] == marker

    def test_upsert_portal_requires_admin(self):
        # no auth
        r = requests.post(f"{BASE_URL}/api/portals/amazon", json={"notes": "hack"}, timeout=15)
        assert r.status_code in (401, 403)

    def test_reset_defaults(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/portals/reset-defaults", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body["reseeded"] == 6
        assert set(body["codes"]) == EXPECTED_CODES
        # AJIO notes should be back to default (not the TEST_marker)
        r2 = requests.get(f"{BASE_URL}/api/portals/ajio", headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        assert "TEST_marker_notes_xyz" not in (r2.json().get("notes") or "")


# -- Portal filtering on existing endpoints ------------------------------
class TestPortalFiltering:
    def test_sales_backfilled_with_myntra(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/sales?limit=5", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        data = r.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        assert len(items) >= 1
        for row in items:
            assert row.get("portal") == "myntra", f"row missing portal=myntra: {row}"

    def test_sales_filter_myntra(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/sales?portal=myntra&limit=5", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        data = r.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        assert len(items) >= 1
        for row in items:
            assert row.get("portal") == "myntra"

    def test_sales_filter_amazon_empty(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/sales?portal=amazon&limit=5", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        data = r.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        total = data.get("total") if isinstance(data, dict) else None
        assert len(items) == 0
        if total is not None:
            assert total == 0

    def test_sales_filter_all_is_no_filter(self, admin_headers):
        r_all = requests.get(f"{BASE_URL}/api/sales?portal=all&limit=5", headers=admin_headers, timeout=20)
        r_none = requests.get(f"{BASE_URL}/api/sales?limit=5", headers=admin_headers, timeout=20)
        assert r_all.status_code == 200 and r_none.status_code == 200
        a = r_all.json(); b = r_none.json()
        ta = a.get("total") if isinstance(a, dict) else len(a)
        tb = b.get("total") if isinstance(b, dict) else len(b)
        assert ta == tb

    def test_uploads_filter_myntra(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/uploads?portal=myntra", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        # all returned should be myntra (or empty)
        for row in items:
            assert row.get("portal") == "myntra"

    def test_uploads_no_filter_returns_all(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/uploads", headers=admin_headers, timeout=20)
        assert r.status_code == 200


# -- Regression: calc/recon still work -----------------------------------
class TestRegression:
    def test_dashboard_overview_still_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/dashboard/overview", headers=admin_headers, timeout=20)
        assert r.status_code == 200

    def test_calculations_list_still_works(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/calculations?limit=5", headers=admin_headers, timeout=30)
        assert r.status_code == 200

    def test_openapi_upload_accepts_portal_param(self):
        r = requests.get(f"{BASE_URL}/openapi.json", timeout=15)
        if r.status_code != 200:
            pytest.skip("openapi not exposed")
        spec = r.json()
        paths = spec.get("paths", {})
        # find /api/uploads/sales POST
        target = None
        for p in paths:
            if p.endswith("/uploads/sales"):
                target = paths[p]
                break
        assert target is not None, "uploads/sales endpoint not in OpenAPI"
        params = target.get("post", {}).get("parameters", [])
        names = [p.get("name") for p in params]
        assert "portal" in names, f"portal query param missing; got {names}"
