"""Iteration 36 — report filters (portal), raw upload download, recovery, AI insights."""
import io
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE = base_url.rstrip("/") + "/api"
MONTH = "2026-04"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _login():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": "admin@fundle.ai", "password": "admin123"}, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    tok = r.json().get("token")
    if not tok:
        pytest.fail("no token in login response")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="session")
def client():
    return _login()


# ---------- Bug 1: Report filters (portal scoping) ----------
class TestReportFilters:
    def test_monthly_myntra_has_rows(self, client):
        r = client.get(f"{BASE}/reports/monthly", params={"month": MONTH, "portal": "myntra"}, timeout=120)
        assert r.status_code == 200, r.text[:300]
        kpi = r.json().get("kpi") or {}
        assert (kpi.get("sales_rows") or 0) > 0, f"expected myntra rows, got {kpi}"

    def test_monthly_amazon_scoped_empty(self, client):
        r = client.get(f"{BASE}/reports/monthly", params={"month": MONTH, "portal": "amazon"}, timeout=120)
        assert r.status_code == 200, r.text[:300]
        kpi = r.json().get("kpi") or {}
        assert not kpi.get("sales_rows"), f"amazon should have no/0 rows, got {kpi.get('sales_rows')}"

    def test_export_portal_scoped(self, client):
        r = client.get(f"{BASE}/reports/monthly/export", params={"month": MONTH, "portal": "myntra"}, timeout=180)
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith(XLSX_MIME)
        assert r.content[:2] == b"PK", "not a valid xlsx/zip"
        assert len(r.content) > 100_000, f"file too small: {len(r.content)}"
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd.lower() and MONTH in cd, cd


# ---------- Bug 2: Raw upload download ----------
def _make_xlsx():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Order Date", "Txn Type", "Order Status", "Online Order Id", "Sku", "QTY-Final", "MRP", "NSV VAL.", "Month"])
    ws.append(["2026-04-05", "Sales", "Delivered", "TEST_ORD_36_1", "TEST_SKU_36", 1, 999, 700, "Apr-26"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestUploadDownload:
    upload_id = None
    raw = None

    def test_legacy_upload_returns_410_or_200(self, client):
        docs = client.get(f"{BASE}/uploads", timeout=60).json()
        assert isinstance(docs, list) and len(docs) > 0, "no existing uploads (regression)"
        uid = docs[-1]["id"]
        r = client.get(f"{BASE}/uploads/{uid}/download", timeout=120)
        assert r.status_code in (200, 410), r.status_code
        if r.status_code == 410:
            assert "detail" in r.json()
            assert len(r.json()["detail"]) > 10

    def test_new_upload_then_download(self, client):
        content = _make_xlsx()
        TestUploadDownload.raw = content
        r = client.post(
            f"{BASE}/uploads/sales?portal=myntra",
            files={"file": ("TEST_iter36.xlsx", content, XLSX_MIME)},
            timeout=180,
        )
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        assert data["accepted_count"] == 1, data
        TestUploadDownload.upload_id = data["upload_id"]

        d = client.get(f"{BASE}/uploads/{data['upload_id']}/download", timeout=120)
        assert d.status_code == 200, d.text[:300]
        assert d.headers.get("content-type", "").startswith(XLSX_MIME)
        assert "attachment" in d.headers.get("content-disposition", "").lower()
        assert d.content[:2] == b"PK"
        assert d.content == content, "downloaded bytes differ from uploaded"

    def test_download_unknown_id_404(self, client):
        r = client.get(f"{BASE}/uploads/does-not-exist-36/download", timeout=60)
        assert r.status_code == 404, r.status_code

    @classmethod
    def teardown_class(cls):
        if cls.upload_id:
            _login().delete(f"{BASE}/uploads/{cls.upload_id}", timeout=120)


# ---------- Bug 3: Recovery ----------
class TestRecovery:
    def test_recovery_cases(self, client):
        r = client.get(f"{BASE}/recovery/cases", params={"limit": 5}, timeout=120)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert isinstance(body, dict) and isinstance(body.get("items"), list), body


# ---------- Bug 4: AI Insights ----------
class TestInsights:
    def test_health_score_myntra(self, client):
        r = client.get(f"{BASE}/insights/health-score",
                       params={"period_type": "month", "period_value": MONTH, "portal": "myntra"}, timeout=180)
        assert r.status_code == 200, r.text[:300]
        b = r.json()
        assert "score" in (b.get("health") or {}), b
        m = b.get("metrics") or {}
        for k in ("calc", "disc", "recovery"):
            assert k in m, f"missing metrics.{k}: {list(m.keys())}"

    def test_health_score_portal_scoped_differs(self, client):
        a = client.get(f"{BASE}/insights/health-score",
                       params={"period_type": "month", "period_value": MONTH, "portal": "myntra"}, timeout=180).json()
        b = client.get(f"{BASE}/insights/health-score",
                       params={"period_type": "month", "period_value": MONTH, "portal": "amazon"}, timeout=180).json()
        assert a.get("metrics") != b.get("metrics"), "portal filter has no effect on metrics"

    def test_morning_brief(self, client):
        r = client.post(f"{BASE}/insights/morning-brief",
                        json={"period_type": "month", "period_value": MONTH, "tone": "executive", "portal": "myntra"},
                        timeout=240)
        assert r.status_code == 200, r.text[:300]
        b = r.json()
        assert b.get("source") in ("llm", "rule"), b.get("source")
        assert (b.get("narrative") or "").strip(), "empty narrative"
        # headline is nested under health (frontend reads health.headline)
        headline = b.get("headline") or ((b.get("health") or {}).get("headline"))
        assert (headline or "").strip(), "empty headline"


# ---------- Regression ----------
class TestRegression:
    def test_uploads_listing(self, client):
        r = client.get(f"{BASE}/uploads", timeout=60)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_calculations_query(self, client):
        r = client.get(f"{BASE}/calculations", params={"limit": 5, "portal": "myntra"}, timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert "items" in r.json()
