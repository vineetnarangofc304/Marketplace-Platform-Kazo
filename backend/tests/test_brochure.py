"""Brochure endpoint tests — public PDF download (GET /api/marketing/brochure)."""
import os
import re

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")


@pytest.fixture(scope="module")
def brochure_response():
    last = None
    for _ in range(2):
        try:
            last = requests.get(f"{BASE_URL}/api/marketing/brochure", timeout=120)
            if last.status_code == 200:
                return last
        except requests.RequestException as exc:
            last = exc
    if isinstance(last, Exception):
        pytest.fail(f"Brochure request failed: {last}")
    return last


class TestBrochurePublic:
    def test_status_200_no_auth(self, brochure_response):
        assert brochure_response.status_code == 200, brochure_response.text[:300]

    def test_content_type_pdf(self, brochure_response):
        assert "application/pdf" in brochure_response.headers.get("Content-Type", "")

    def test_content_disposition_filename(self, brochure_response):
        cd = brochure_response.headers.get("Content-Disposition", "")
        assert "attachment" in cd.lower(), cd
        assert "Fundle-Marketplace-AutoPilot-Brochure.pdf" in cd, cd

    def test_pdf_magic_and_size(self, brochure_response):
        body = brochure_response.content
        assert body[:5] == b"%PDF-", body[:20]
        assert len(body) >= 300 * 1024, f"only {len(body)} bytes"

    def test_pdf_page_count_is_5(self, brochure_response):
        pages = len(re.findall(rb"/Type\s*/Page[^s]", brochure_response.content))
        assert pages == 5, f"expected 5 pages, found {pages}"

    def test_ignores_bogus_bearer_token(self):
        r = requests.get(
            f"{BASE_URL}/api/marketing/brochure",
            headers={"Authorization": "Bearer not-a-real-token"},
            timeout=120,
        )
        assert r.status_code == 200
        assert r.content[:5] == b"%PDF-"


class TestMarketingGalleryRegression:
    """Regression: seeded gallery still lists 5 posts and images load."""

    @pytest.fixture(scope="class")
    def token(self):
        r = requests.post(
            f"{BASE_URL}/api/marketing/login",
            json={"email": "marketing@fundle.ai", "password": "market123"},
            timeout=60,
        )
        if r.status_code != 200:
            pytest.fail(f"marketing login failed {r.status_code}: {r.text[:300]}")
        tok = r.json().get("token")
        assert tok
        return tok

    def test_posts_listed(self, token):
        r = requests.get(
            f"{BASE_URL}/api/marketing/posts",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 5, data["total"]
        assert len(data["items"]) == data["total"]
        for item in data["items"]:
            assert "_id" not in item
            assert item["id"] and item["title"]

    def test_images_load(self, token):
        headers = {"Authorization": f"Bearer {token}"}
        items = requests.get(
            f"{BASE_URL}/api/marketing/posts", headers=headers, timeout=60
        ).json()["items"][:5]
        for item in items:
            r = requests.get(
                f"{BASE_URL}/api/marketing/posts/{item['id']}/image",
                headers=headers,
                timeout=60,
            )
            assert r.status_code == 200, item["title"]
            assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


class TestMainAppLoginRegression:
    def test_admin_login(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@fundle.ai", "password": "admin123"},
            timeout=60,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        token = data.get("access_token") or data.get("token")
        assert token, data
        me = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        assert me.status_code == 200
        assert me.json().get("email") == "admin@fundle.ai"
