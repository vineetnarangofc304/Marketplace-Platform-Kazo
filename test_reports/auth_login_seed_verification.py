#!/usr/bin/env python3
"""Focused verification for the reported production login bug.

Tests only the admin login/seed flow described in the review request:
- Live preview API login for current and legacy admin credentials.
- Live preview DB contains both seeded admin users.
- Startup hook seeds both admin users into an empty, isolated MongoDB database.
"""

import asyncio
import importlib
import json
import os
import sys
import time
from pathlib import Path

import requests
from motor.motor_asyncio import AsyncIOMotorClient


APP_DIR = Path("/app")
BACKEND_DIR = APP_DIR / "backend"
FRONTEND_ENV = APP_DIR / "frontend" / ".env"
BACKEND_ENV = BACKEND_DIR / ".env"
RESULTS_PATH = APP_DIR / "test_reports" / "auth_login_seed_verification_results.json"

ADMIN_CREDS = [
    {"email": "admin@fundle.ai", "password": "admin123", "label": "current_prefilled_admin"},
    {"email": "admin@kazo.com", "password": "admin123", "label": "legacy_admin"},
]
ADMIN_EMAILS = [c["email"] for c in ADMIN_CREDS]


def parse_env(path: Path) -> dict:
    data = {}
    if not path.exists():
        return data
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        data[key.strip()] = value
    return data


def load_env_defaults(path: Path) -> dict:
    data = parse_env(path)
    for key, value in data.items():
        os.environ.setdefault(key, value)
    return data


def check_live_api(base_url: str) -> dict:
    api_url = base_url.rstrip("/") + "/api"
    results = {"api_url": api_url, "logins": []}
    for cred in ADMIN_CREDS:
        session = requests.Session()
        login_result = {"email": cred["email"], "label": cred["label"]}
        try:
            res = session.post(
                f"{api_url}/auth/login",
                json={"email": cred["email"], "password": cred["password"]},
                timeout=20,
            )
            login_result["status_code"] = res.status_code
            login_result["ok"] = res.status_code == 200
            login_result["set_cookie_access_token"] = "access_token" in res.headers.get("set-cookie", "")
            try:
                payload = res.json()
            except Exception:
                payload = {"raw": res.text[:300]}
            login_result["token_present"] = bool(payload.get("token"))
            user = payload.get("user") if isinstance(payload, dict) else None
            login_result["user"] = {
                "email": user.get("email"),
                "role": user.get("role"),
                "id_present": bool(user.get("id")),
            } if isinstance(user, dict) else None
            if res.status_code == 200:
                me = session.get(f"{api_url}/auth/me", timeout=20)
                login_result["me_status_code"] = me.status_code
                try:
                    me_payload = me.json()
                except Exception:
                    me_payload = {"raw": me.text[:300]}
                login_result["me_email"] = me_payload.get("email") if isinstance(me_payload, dict) else None
                login_result["me_ok"] = me.status_code == 200 and login_result["me_email"] == cred["email"]
            else:
                login_result["error"] = payload
        except Exception as exc:
            login_result["ok"] = False
            login_result["exception"] = repr(exc)
        results["logins"].append(login_result)
    results["all_ok"] = all(
        item.get("ok")
        and item.get("token_present")
        and item.get("user", {}).get("email") == item.get("email")
        and item.get("user", {}).get("role") == "admin"
        and item.get("me_ok")
        for item in results["logins"]
    )
    return results


async def inspect_live_db(mongo_url: str, db_name: str) -> dict:
    client = AsyncIOMotorClient(mongo_url)
    try:
        db = client[db_name]
        docs = await db.users.find(
            {"email": {"$in": ADMIN_EMAILS}},
            {"_id": 0, "email": 1, "role": 1, "name": 1, "id": 1, "password_hash": 1},
        ).to_list(length=10)
        sanitized = []
        for doc in docs:
            sanitized.append({
                "email": doc.get("email"),
                "role": doc.get("role"),
                "name": doc.get("name"),
                "id_present": bool(doc.get("id")),
                "bcrypt_hash_present": isinstance(doc.get("password_hash"), str) and doc.get("password_hash", "").startswith("$2"),
            })
        found = {doc.get("email") for doc in sanitized}
        return {
            "db_name": db_name,
            "admin_users": sorted(sanitized, key=lambda d: d.get("email") or ""),
            "both_admins_present": set(ADMIN_EMAILS).issubset(found),
            "all_are_admin_with_bcrypt": all(
                doc.get("role") == "admin" and doc.get("bcrypt_hash_present") for doc in sanitized if doc.get("email") in ADMIN_EMAILS
            ) and set(ADMIN_EMAILS).issubset(found),
        }
    finally:
        client.close()


async def verify_startup_seed_in_isolated_empty_db(mongo_url: str, original_db_name: str) -> dict:
    temp_db_name = f"{original_db_name}_seed_verify_{int(time.time())}"
    cleanup_client = AsyncIOMotorClient(mongo_url)
    await cleanup_client.drop_database(temp_db_name)
    cleanup_client.close()

    os.environ["DB_NAME"] = temp_db_name
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    result = {"temp_db_name": temp_db_name, "used_isolated_empty_db": True}
    server = None
    try:
        server = importlib.import_module("server")
        await server.db.users.delete_many({})
        before_count = await server.db.users.count_documents({})
        await server.app.router.startup()
        # Inline startup seeding is awaited before readiness; background bootstrap is allowed to finish best-effort.
        await asyncio.sleep(2)
        docs = await server.db.users.find(
            {"email": {"$in": ADMIN_EMAILS}},
            {"_id": 0, "email": 1, "role": 1, "name": 1, "id": 1, "password_hash": 1},
        ).to_list(length=10)
        sanitized = []
        for doc in docs:
            sanitized.append({
                "email": doc.get("email"),
                "role": doc.get("role"),
                "name": doc.get("name"),
                "id_present": bool(doc.get("id")),
                "bcrypt_hash_present": isinstance(doc.get("password_hash"), str) and doc.get("password_hash", "").startswith("$2"),
            })
        found = {doc.get("email") for doc in sanitized}
        result.update({
            "users_before_startup": before_count,
            "seeded_admin_users": sorted(sanitized, key=lambda d: d.get("email") or ""),
            "both_admins_seeded_after_startup": set(ADMIN_EMAILS).issubset(found),
            "all_seeded_admins_valid": all(
                doc.get("role") == "admin" and doc.get("bcrypt_hash_present") for doc in sanitized if doc.get("email") in ADMIN_EMAILS
            ) and set(ADMIN_EMAILS).issubset(found),
        })
    finally:
        if server is not None:
            try:
                await server.app.router.shutdown()
            except Exception as exc:
                result["shutdown_warning"] = repr(exc)
        cleanup_client = AsyncIOMotorClient(mongo_url)
        await cleanup_client.drop_database(temp_db_name)
        cleanup_client.close()
        os.environ["DB_NAME"] = original_db_name
    return result


async def main() -> int:
    frontend_env = load_env_defaults(FRONTEND_ENV)
    backend_env = load_env_defaults(BACKEND_ENV)
    base_url = frontend_env.get("REACT_APP_BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL")
    mongo_url = backend_env.get("MONGO_URL") or os.environ.get("MONGO_URL")
    db_name = backend_env.get("DB_NAME") or os.environ.get("DB_NAME")
    if not base_url or not mongo_url or not db_name:
        raise RuntimeError("Missing REACT_APP_BACKEND_URL, MONGO_URL, or DB_NAME for auth verification")

    results = {
        "scope": "reported login bug only",
        "backend_url": base_url,
        "expected_admin_emails": ADMIN_EMAILS,
        "live_api": check_live_api(base_url),
        "live_db": await inspect_live_db(mongo_url, db_name),
        "isolated_empty_db_startup_seed": await verify_startup_seed_in_isolated_empty_db(mongo_url, db_name),
    }
    results["all_ok"] = bool(
        results["live_api"].get("all_ok")
        and results["live_db"].get("both_admins_present")
        and results["live_db"].get("all_are_admin_with_bcrypt")
        and results["isolated_empty_db_startup_seed"].get("both_admins_seeded_after_startup")
        and results["isolated_empty_db_startup_seed"].get("all_seeded_admins_valid")
    )
    RESULTS_PATH.write_text(json.dumps(results, indent=2, sort_keys=True))
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0 if results["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))