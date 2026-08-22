"""Marketing Studio — gallery image disk-persistence regression tests.

Simulates the production stateless-container scenario:
  * Scenario A: DB rows intact, gallery/ wiped -> startup must re-materialise
    the PNGs under the SAME image_file/UUID names (no new DB rows).
  * Scenario B: DB collection dropped AND gallery/ wiped -> first-boot path
    must recreate 5 rows + 5 files.
"""
import os
import subprocess
import time
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

backend_env = dotenv_values("/app/backend/.env")
MONGO_URL = backend_env.get("MONGO_URL")
DB_NAME = backend_env.get("DB_NAME")

GALLERY = Path("/app/marketing_assets/gallery")
SEED_TITLES = [
    "Marketplace AutoPilot — Reconcile Every Rupee, Every Marketplace",
    "Inside Marketplace AutoPilot — 8 Purpose-Built Modules",
    "From Excel to Recovered Rupees in 5 Steps",
    "One Ledger. Six Marketplaces. Zero Excel Chaos.",
    "What Marketplace AutoPilot Recovers For You",
]
MKT_EMAIL = "marketing@fundle.ai"
MKT_PASSWORD = "market123"


# ---------- helpers ----------
def mongo_posts():
    client = MongoClient(MONGO_URL)
    try:
        return list(client[DB_NAME].marketing_posts.find({}, {"_id": 0}))
    finally:
        client.close()


def drop_posts():
    client = MongoClient(MONGO_URL)
    try:
        client[DB_NAME].marketing_posts.drop()
    finally:
        client.close()


def wipe_gallery():
    for f in GALLERY.glob("*"):
        if f.is_file():
            f.unlink()


def restart_backend(wait=12):
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=True,
                   capture_output=True)
    deadline = time.time() + 60
    time.sleep(wait)
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/api/", timeout=5)
            if r.status_code < 500:
                return
        except Exception:
            pass
        time.sleep(2)


def marketing_token():
    r = requests.post(f"{BASE_URL}/api/marketing/login",
                      json={"email": MKT_EMAIL, "password": MKT_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"marketing login failed {r.status_code}: {r.text[:300]}"
    tok = r.json().get("token")
    assert tok
    return tok


def auth_headers():
    return {"Authorization": f"Bearer {marketing_token()}"}


def assert_gallery_healthy():
    """5 PNGs on disk, each 500KB-1MB, filenames match DB image_file values."""
    pngs = sorted(p.name for p in GALLERY.glob("*.png"))
    assert len(pngs) == 5, f"expected 5 PNGs in gallery, got {len(pngs)}: {pngs}"
    for name in pngs:
        size = (GALLERY / name).stat().st_size
        assert 500 * 1024 <= size <= 1024 * 1024, f"{name} size {size} out of 500KB-1MB range"
        with (GALLERY / name).open("rb") as f:
            assert f.read(4) == b"\x89PNG", f"{name} is not a PNG"

    posts = mongo_posts()
    seeded = [p for p in posts if p["title"] in SEED_TITLES]
    assert len(seeded) == 5, f"expected 5 seeded DB rows, got {len(seeded)}"
    db_files = sorted(p["image_file"] for p in seeded)
    assert db_files == pngs, f"disk/DB mismatch. disk={pngs} db={db_files}"


def assert_all_images_served():
    h = auth_headers()
    r = requests.get(f"{BASE_URL}/api/marketing/posts", headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    items = r.json()["items"]
    seeded = [i for i in items if i["title"] in SEED_TITLES]
    assert len(seeded) == 5, f"API returned {len(seeded)} seeded posts"
    for post in seeded:
        ir = requests.get(f"{BASE_URL}/api/marketing/posts/{post['id']}/image",
                          headers=h, timeout=60)
        assert ir.status_code == 200, f"{post['title']}: image {ir.status_code}"
        assert ir.headers.get("content-type") == "image/png", ir.headers.get("content-type")
        assert len(ir.content) > 500 * 1024, f"{post['title']}: only {len(ir.content)} bytes"
        assert ir.content[:4] == b"\x89PNG"
    return items


# ---------- Scenario A: disk wiped, DB intact ----------
class TestDiskWipedDbIntact:
    def test_baseline_state(self):
        posts = mongo_posts()
        seeded = [p for p in posts if p["title"] in SEED_TITLES]
        assert len(seeded) == 5, "pre-condition: 5 seeded posts must exist in Mongo"

    def test_wipe_disk_and_restart_rematerialises(self):
        before = {p["title"]: (p["id"], p["image_file"]) for p in mongo_posts()
                  if p["title"] in SEED_TITLES}
        wipe_gallery()
        assert len(list(GALLERY.glob("*.png"))) == 0
        restart_backend()

        assert_gallery_healthy()

        after = {p["title"]: (p["id"], p["image_file"]) for p in mongo_posts()
                 if p["title"] in SEED_TITLES}
        assert after == before, f"UUIDs changed after restart!\nbefore={before}\nafter={after}"

    def test_api_serves_all_images_after_rematerialise(self):
        items = assert_all_images_served()
        assert len(items) == 5, f"total posts should be exactly 5, got {len(items)}"

    def test_brochure_still_ok(self):
        r = requests.get(f"{BASE_URL}/api/marketing/brochure", timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.content[:8] == b"%PDF-1.4", r.content[:20]


# ---------- Scenario B: DB dropped AND disk wiped (first boot) ----------
class TestFirstBootBothEmpty:
    def test_drop_db_and_disk_then_restart(self):
        drop_posts()
        wipe_gallery()
        assert mongo_posts() == []
        assert len(list(GALLERY.glob("*.png"))) == 0
        restart_backend()
        assert_gallery_healthy()

    def test_api_serves_all_images_after_first_boot(self):
        items = assert_all_images_served()
        assert len(items) == 5, f"total posts should be exactly 5, got {len(items)}"

    def test_second_restart_is_idempotent(self):
        before = {p["title"]: (p["id"], p["image_file"]) for p in mongo_posts()}
        restart_backend()
        after = {p["title"]: (p["id"], p["image_file"]) for p in mongo_posts()}
        assert after == before, "restart with everything present must be a no-op"
        assert_gallery_healthy()
