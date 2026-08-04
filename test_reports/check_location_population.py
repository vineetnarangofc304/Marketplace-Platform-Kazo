#!/usr/bin/env python3
"""Check Sales Ledger posting_location_code population through public API."""
import json
import re
from pathlib import Path

import requests

ROOT = Path("/app")
env = (ROOT / "frontend" / ".env").read_text()
base = re.search(r"^REACT_APP_BACKEND_URL=(.+)$", env, re.M).group(1).strip()
api = base.rstrip("/") + "/api"
s = requests.Session()
r = s.post(api + "/auth/login", json={"email": "admin@fundle.ai", "password": "admin123"}, timeout=30)
r.raise_for_status()
s.headers.update({"Authorization": "Bearer " + r.json()["token"]})
total = None
count = 0
non_empty = 0
examples = []
for skip in range(0, 30000, 2000):
    resp = s.get(api + "/sales", params={"period_type": "month", "period_value": "2026-04", "portal": "myntra", "limit": 2000, "skip": skip}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    total = data["total"]
    items = data["items"]
    if not items:
        break
    for row in items:
        count += 1
        value = row.get("posting_location_code")
        if value not in (None, ""):
            non_empty += 1
            if len(examples) < 5:
                examples.append({"id": row.get("id"), "posting_location_code": value})
    if count >= total:
        break
out = {"total": total, "scanned": count, "posting_location_code_non_empty": non_empty, "examples": examples}
print(json.dumps(out, indent=2))
(ROOT / "test_reports" / "location_population_results.json").write_text(json.dumps(out, indent=2))