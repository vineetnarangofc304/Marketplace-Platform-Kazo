import json
import requests

BASE = "https://marketplace-recon-1.preview.emergentagent.com"
s = requests.Session()
r = s.post(f"{BASE}/api/auth/login", json={"email": "admin@fundle.ai", "password": "admin123"}, timeout=30)
r.raise_for_status()
s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})

# Filter return rows to prove the location issue is still visible via the API,
# not only in direct DB inspection.
r = s.get(f"{BASE}/api/sales", params={"portal": "myntra", "limit": 10, "txn_type": "Return"}, timeout=60)
r.raise_for_status()
body = r.json()
sample = [
    {
        "id": x.get("id"),
        "txn_type": x.get("txn_type"),
        "order_status": x.get("order_status"),
        "sales_invoice_no": x.get("sales_invoice_no"),
        "posting_location_code": x.get("posting_location_code"),
    }
    for x in body.get("items", [])
]
out = {"total": body.get("total"), "filter": {"portal": "myntra", "txn_type": "Return"}, "sample": sample}
print(json.dumps(out, indent=2))
open("/app/test_reports/bug_verification_14_location_api_window_results.json", "w").write(json.dumps(out, indent=2))