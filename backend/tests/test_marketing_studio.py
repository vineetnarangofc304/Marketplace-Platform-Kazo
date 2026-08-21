"""Marketing Studio (/api/marketing/*) backend tests — iteration 30."""
import os
import time

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

MKT_EMAIL = "marketing@fundle.ai"
MKT_PASSWORD = "market123"
GALLERY_DIR = "/app/marketing_assets/gallery"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def mkt_token(client):
    r = client.post(f"{BASE_URL}/api/marketing/login",
                    json={"email": MKT_EMAIL, "password": MKT_PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"marketing login failed {r.status_code}: {r.text[:300]}")
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def auth_headers(mkt_token):
    return {"Authorization": f"Bearer {mkt_token}", "Content-Type": "application/json"}


# ---------- Auth ----------
class TestMarketingAuth:
    def test_login_success(self, client):
        r = client.post(f"{BASE_URL}/api/marketing/login",
                        json={"email": MKT_EMAIL, "password": MKT_PASSWORD}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["email"] == MKT_EMAIL
        assert isinstance(data["token"], str) and len(data["token"]) > 20
        import jwt as pyjwt
        claims = pyjwt.decode(data["token"], options={"verify_signature": False})
        assert claims["role"] == "marketing"
        assert claims["sub"] == MKT_EMAIL

    def test_login_wrong_password(self, client):
        r = client.post(f"{BASE_URL}/api/marketing/login",
                        json={"email": MKT_EMAIL, "password": "wrongpass"}, timeout=30)
        assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text[:200]}"

    def test_posts_requires_auth(self, client):
        r = requests.get(f"{BASE_URL}/api/marketing/posts", timeout=30)
        assert r.status_code == 401, f"expected 401 got {r.status_code}"

    def test_posts_invalid_token(self):
        r = requests.get(f"{BASE_URL}/api/marketing/posts",
                         headers={"Authorization": "Bearer garbage"}, timeout=30)
        assert r.status_code == 401

    def test_marketing_token_cannot_access_admin_me(self, mkt_token):
        """Expected: marketing scope must not access main app auth/me."""
        r = requests.get(f"{BASE_URL}/api/auth/me",
                         headers={"Authorization": f"Bearer {mkt_token}"}, timeout=30)
        assert r.status_code in (401, 403), f"marketing token got {r.status_code} on /api/auth/me"


# ---------- Gallery listing + images ----------
class TestSeededGallery:
    def test_list_seeded_posts(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/marketing/posts", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        items = data["items"]
        assert data["total"] == len(items)
        seeded = [i for i in items if not i["title"].startswith("TEST_")]
        assert len(seeded) == 5, f"expected 5 seeded posts, got {len(seeded)}: {[i['title'] for i in seeded]}"
        required = {"id", "title", "keywords", "style", "linkedin_text", "hashtags",
                    "image_file", "created_at"}
        for it in seeded:
            missing = required - set(it.keys())
            assert not missing, f"post {it.get('title')} missing {missing}"
            assert "_id" not in it
            assert it["linkedin_text"].strip()
            assert len(it["hashtags"]) >= 5

    def test_rebrand_no_finance_os(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/marketing/posts", headers=auth_headers, timeout=30)
        items = r.json()["items"]
        offenders = [i["title"] for i in items
                     if "finance os" in (i["title"] + " " + i["linkedin_text"]).lower()]
        assert not offenders, f"'Finance OS' still present in: {offenders}"

    def test_at_least_one_title_mentions_autopilot(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/marketing/posts", headers=auth_headers, timeout=30)
        items = r.json()["items"]
        blob = " ".join(i["title"] + " " + i["linkedin_text"] for i in items).lower()
        assert "marketplace autopilot" in blob

    def test_all_seeded_images_served(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/marketing/posts", headers=auth_headers, timeout=30)
        items = r.json()["items"]
        failures = []
        for it in items:
            ir = requests.get(f"{BASE_URL}/api/marketing/posts/{it['id']}/image",
                              headers={"Authorization": auth_headers["Authorization"]}, timeout=60)
            if ir.status_code != 200:
                failures.append((it["title"], ir.status_code))
                continue
            if "image/png" not in ir.headers.get("content-type", ""):
                failures.append((it["title"], ir.headers.get("content-type")))
            elif len(ir.content) <= 50 * 1024:
                failures.append((it["title"], f"{len(ir.content)} bytes"))
        assert not failures, f"image failures: {failures}"

    def test_image_requires_auth(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/marketing/posts", headers=auth_headers, timeout=30)
        pid = r.json()["items"][0]["id"]
        nr = requests.get(f"{BASE_URL}/api/marketing/posts/{pid}/image", timeout=30)
        assert nr.status_code == 401

    def test_image_unknown_id_404(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/marketing/posts/does-not-exist/image",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 404


# ---------- Generation + delete ----------
class TestGenerateAndDelete:
    created_id = None
    image_file = None

    def test_create_post_infographic(self, auth_headers):
        payload = {
            "title": "TEST_Recover Marketplace Leakage in Real Time",
            "keywords": "commission variance, GT reversal, month-end close",
            "style": "infographic",
            "tone": "founder",
        }
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/api/marketing/posts", json=payload,
                          headers=auth_headers, timeout=180)
        elapsed = time.time() - t0
        print(f"generation took {elapsed:.1f}s status={r.status_code}")
        if r.status_code in (429, 502, 503):
            pytest.skip(f"Nano Banana transient failure {r.status_code}: {r.text[:200]}")
        assert r.status_code == 200, r.text[:500]
        doc = r.json()
        assert "_id" not in doc
        assert doc["title"] == payload["title"]
        assert doc["style"] == "infographic"
        assert doc["linkedin_text"].strip(), "empty linkedin_text"
        assert len(doc["hashtags"]) >= 5, f"only {len(doc['hashtags'])} hashtags"
        assert all(h.startswith("#") for h in doc["hashtags"]), doc["hashtags"]
        assert doc["image_file"].endswith(".png")
        TestGenerateAndDelete.created_id = doc["id"]
        TestGenerateAndDelete.image_file = doc["image_file"]

        # image downloadable
        ir = requests.get(f"{BASE_URL}/api/marketing/posts/{doc['id']}/image",
                          headers={"Authorization": auth_headers["Authorization"]}, timeout=60)
        assert ir.status_code == 200
        assert "image/png" in ir.headers.get("content-type", "")
        assert len(ir.content) > 50 * 1024, f"{len(ir.content)} bytes"

        # persisted in list
        lr = requests.get(f"{BASE_URL}/api/marketing/posts", headers=auth_headers, timeout=30)
        assert doc["id"] in [i["id"] for i in lr.json()["items"]]

    def test_create_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/marketing/posts",
                          json={"title": "x", "keywords": "y"}, timeout=30)
        assert r.status_code == 401

    def test_create_validation_error(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/marketing/posts", json={"keywords": "only"},
                          headers=auth_headers, timeout=60)
        assert r.status_code == 422, f"expected 422 got {r.status_code}"

    def test_delete_created_post(self, auth_headers):
        pid = TestGenerateAndDelete.created_id
        if not pid:
            pytest.skip("no created post to delete")
        r = requests.delete(f"{BASE_URL}/api/marketing/posts/{pid}",
                            headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json() == {"ok": True}
        # gone from list
        lr = requests.get(f"{BASE_URL}/api/marketing/posts", headers=auth_headers, timeout=30)
        assert pid not in [i["id"] for i in lr.json()["items"]]
        # image 404
        ir = requests.get(f"{BASE_URL}/api/marketing/posts/{pid}/image",
                          headers=auth_headers, timeout=30)
        assert ir.status_code == 404
        # file removed from disk
        assert not os.path.exists(os.path.join(GALLERY_DIR, TestGenerateAndDelete.image_file))

    def test_delete_unknown_404(self, auth_headers):
        r = requests.delete(f"{BASE_URL}/api/marketing/posts/nope-nope",
                            headers=auth_headers, timeout=30)
        assert r.status_code == 404


# ---------- Regression: main app admin login ----------
class TestAdminRegression:
    def test_admin_login_and_me(self, client):
        r = client.post(f"{BASE_URL}/api/auth/login",
                        json={"email": "admin@fundle.ai", "password": "admin123"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        token = data.get("access_token") or data.get("token")
        assert token, data
        me = requests.get(f"{BASE_URL}/api/auth/me",
                          headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert me.status_code == 200, me.text[:300]
        assert "_id" not in me.json()
