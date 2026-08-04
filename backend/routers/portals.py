"""Multi-marketplace Portals router.

Endpoints
  GET  /api/portals                      → list portals (any user)
  GET  /api/portals/{code}               → single portal detail
  POST /api/portals/{code}               → upsert portal (admin only)
  POST /api/portals/reset-defaults       → re-seed from PORTALS_SEED (admin)
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db import db
from deps import require_role
from data_portals_seed import PORTALS_SEED

router = APIRouter(tags=["portals"])


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


async def bootstrap_portals():
    """Seed the portals collection if empty. Idempotent.

    Also refreshes `status` and `fee_heads` from the seed for portals that
    already exist so status upgrades (coming_soon → live) flow to prod
    without requiring a manual reset.
    """
    count = await db.portals.count_documents({})
    if count == 0:
        docs = []
        for p in PORTALS_SEED:
            docs.append({**p, "created_at": _now_iso(), "updated_at": _now_iso()})
        await db.portals.insert_many(docs)
        print(f"[portals] seeded {len(docs)} portals")
    else:
        # Sync status from seed (upgrades non-Myntra portals from coming_soon to live
        # once the calc engine can handle them). Do NOT overwrite user-customised
        # fee_heads / case_matrix / notes.
        for p in PORTALS_SEED:
            await db.portals.update_one(
                {"code": p["code"]},
                {"$set": {"status": p["status"], "updated_at": _now_iso()},
                 "$setOnInsert": {"code": p["code"], "name": p["name"],
                                    "fee_heads": p.get("fee_heads", []),
                                    "case_matrix": p.get("case_matrix", {}),
                                    "notes": p.get("notes", ""),
                                    "created_at": _now_iso()}},
                upsert=True,
            )
    # Ensure existing sales / calculations rows have portal = 'myntra' if missing
    r1 = await db.sales.update_many({"portal": {"$exists": False}}, {"$set": {"portal": "myntra"}})
    r2 = await db.calculations.update_many({"portal": {"$exists": False}}, {"$set": {"portal": "myntra"}})
    r3 = await db.uploads.update_many({"portal": {"$exists": False}}, {"$set": {"portal": "myntra"}})
    if r1.modified_count or r2.modified_count or r3.modified_count:
        print(f"[portals] back-filled portal=myntra on {r1.modified_count} sales, {r2.modified_count} calcs, {r3.modified_count} uploads")

    # Back-fill posting_location_code from the sales_invoice_no prefix for
    # historical rows that were ingested before the alias was added. This is
    # lossless: it uses only what already exists on the doc (invoice prefix
    # is the marketplace/warehouse code — "MYN" for Myntra, etc.).
    pipeline = [
        {"$match": {"$and": [
            {"$or": [{"posting_location_code": {"$exists": False}}, {"posting_location_code": None}, {"posting_location_code": ""}]},
            {"sales_invoice_no": {"$ne": None}},
        ]}},
        {"$limit": 100000},
    ]
    to_backfill = [d async for d in db.sales.aggregate(pipeline)]
    if to_backfill:
        from pymongo import UpdateOne
        ops = []
        for d in to_backfill:
            inv = str(d.get("sales_invoice_no") or "")
            prefix = inv.split("/")[0].strip() if "/" in inv else inv[:6]
            if prefix:
                ops.append(UpdateOne({"_id": d["_id"]}, {"$set": {"posting_location_code": prefix.upper()}}))
        for i in range(0, len(ops), 1000):
            if ops[i:i+1000]:
                await db.sales.bulk_write(ops[i:i+1000])
        print(f"[portals] back-filled posting_location_code on {len(ops)} sales rows")


class PortalUpsert(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None      # 'live' | 'coming_soon'
    notes: Optional[str] = None
    fee_heads: Optional[List[Dict[str, Any]]] = None
    case_matrix: Optional[Dict[str, Dict[str, str]]] = None


@router.get("/portals")
async def list_portals():
    docs = await db.portals.find({}, {"_id": 0}).sort("code", 1).to_list(50)
    # Enrich with data-volume stats per portal
    for d in docs:
        d["sales_count"] = await db.sales.count_documents({"portal": d["code"]})
        d["upload_count"] = await db.uploads.count_documents({"portal": d["code"]})
    return docs


@router.get("/portals/{code}")
async def get_portal(code: str):
    doc = await db.portals.find_one({"code": code.lower()}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"Portal '{code}' not found")
    return doc


@router.post("/portals/reset-defaults")
async def reset_portals(user=Depends(require_role("admin"))):
    await db.portals.delete_many({})
    docs = [{**p, "created_at": _now_iso(), "updated_at": _now_iso()} for p in PORTALS_SEED]
    await db.portals.insert_many(docs)
    return {"reseeded": len(docs), "codes": [p["code"] for p in PORTALS_SEED]}


@router.post("/portals/{code}")
async def upsert_portal(code: str, payload: PortalUpsert, user=Depends(require_role("admin"))):
    code = code.lower().strip()
    update = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    update["updated_at"] = _now_iso()
    r = await db.portals.update_one({"code": code}, {"$set": update, "$setOnInsert": {"code": code, "created_at": _now_iso()}}, upsert=True)
    doc = await db.portals.find_one({"code": code}, {"_id": 0})
    return {"upserted": bool(r.upserted_id), "portal": doc}
