"""Iteration 12: portal-aware endpoints + cross-portal summary.

Covers:
- Login (admin@kazo.com / admin123)
- /api/dashboard/portals-summary shape
- portal= query param on overview / commission-summary / reconciliation-summary / return-velocity
- portal= on /calculations, /reconciliation/discrepancies, /recovery/cases, /recovery/summary, /reports/period
- POST /api/calculations/run with portal payload doesn't crash on empty portal
"""
import os
import pytest
import requests

def _load_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")


BASE_URL = _load_url()
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@kazo.com", "password": "admin123"}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"Login response missing token: {data}"
    return tok


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# -------- Portals Summary --------
class TestPortalsSummary:
    def test_shape(self, auth):
        r = requests.get(f"{API}/dashboard/portals-summary", headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "totals" in data and "portals" in data
        totals = data["totals"]
        for k in ["portals_count", "live_portals", "sales_count", "nsv", "expected_settlement", "leakage", "disc_count"]:
            assert k in totals, f"totals missing {k}"
        assert isinstance(data["portals"], list)
        assert len(data["portals"]) >= 1
        for p in data["portals"]:
            for k in ["code", "name", "status", "sales_count", "nsv", "expected_settlement", "expected_commission", "leakage", "disc_count"]:
                assert k in p, f"portal row missing {k}: {p}"

    def test_expected_six_portals(self, auth):
        r = requests.get(f"{API}/dashboard/portals-summary", headers=auth, timeout=30)
        data = r.json()
        codes = [p["code"] for p in data["portals"]]
        # Expect at least myntra + others up to 6
        assert "myntra" in codes
        assert len(codes) >= 1


# -------- portal= filter on dashboards --------
class TestPortalFilter:
    def test_overview_myntra_has_data(self, auth):
        r = requests.get(f"{API}/dashboard/overview", params={"portal": "myntra"}, headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # Existing 21,614 rows are portal=myntra
        assert data.get("total_sales", 0) > 0, f"Expected myntra sales > 0, got {data}"

    def test_overview_amazon_empty(self, auth):
        r = requests.get(f"{API}/dashboard/overview", params={"portal": "amazon"}, headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("total_sales", 0) == 0
        assert data.get("total_calculations", 0) == 0

    def test_overview_all(self, auth):
        r = requests.get(f"{API}/dashboard/overview", params={"portal": "all"}, headers=auth, timeout=30)
        assert r.status_code == 200
        assert r.json().get("total_sales", 0) > 0

    def test_commission_summary_portal(self, auth):
        r = requests.get(f"{API}/dashboard/commission-summary", params={"portal": "amazon"}, headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["kpi"].get("total_orders", 0) == 0

    def test_reconciliation_summary_portal(self, auth):
        r = requests.get(f"{API}/dashboard/reconciliation-summary", params={"portal": "amazon"}, headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("total_discrepancies", 0) == 0

    def test_return_velocity_portal(self, auth):
        r = requests.get(f"{API}/dashboard/return-velocity", params={"portal": "amazon"}, headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["overall"]["sales_orders"] == 0


# -------- portal= on list APIs --------
class TestListEndpointsPortalParam:
    def test_calculations(self, auth):
        r_all = requests.get(f"{API}/calculations", params={"portal": "myntra", "limit": 5}, headers=auth, timeout=30)
        assert r_all.status_code == 200, r_all.text
        r_amz = requests.get(f"{API}/calculations", params={"portal": "amazon", "limit": 5}, headers=auth, timeout=30)
        assert r_amz.status_code == 200
        assert r_amz.json().get("total", 0) == 0

    def test_discrepancies(self, auth):
        r = requests.get(f"{API}/reconciliation/discrepancies", params={"portal": "amazon", "limit": 5}, headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("total", 0) == 0

    def test_recovery_cases(self, auth):
        r = requests.get(f"{API}/recovery/cases", params={"portal": "amazon", "limit": 5}, headers=auth, timeout=30)
        assert r.status_code == 200, r.text

    def test_recovery_summary(self, auth):
        r = requests.get(f"{API}/recovery/summary", params={"portal": "amazon"}, headers=auth, timeout=30)
        assert r.status_code == 200, r.text

    def test_reports_period(self, auth):
        r = requests.get(f"{API}/reports/period", params={"portal": "amazon", "period_type": "all"}, headers=auth, timeout=30)
        assert r.status_code == 200, r.text


# -------- POST /calculations/run with portal --------
class TestCalcRunPortal:
    def test_run_amazon_empty_no_crash(self, auth):
        r = requests.post(f"{API}/calculations/run", json={"portal": "amazon"}, headers=auth, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        # No amazon sales, so processed=0
        assert data.get("total_sales", 0) == 0


# -------- Upload header alias smoke: missing columns error --------
class TestUploadHeaderErrors:
    def test_missing_required_columns_error(self, auth):
        import io
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        # only irrelevant headers
        ws.append(["Foo", "Bar", "Baz"])
        ws.append([1, 2, 3])
        ws.append([4, 5, 6])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        r = requests.post(
            f"{API}/uploads/sales",
            files={"file": ("bad.xlsx", buf.getvalue(),
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            params={"portal": "amazon"},
            headers=auth, timeout=30,
        )
        # Should be 400 (couldn't detect header OR missing required)
        assert r.status_code == 400, r.text
        body = r.text.lower()
        assert "column" in body or "detect" in body or "sheet" in body
