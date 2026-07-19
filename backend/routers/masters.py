"""Commission masters: commission rules, fixed fee slabs, GT charges, return fees,
sub-category level mapping, and tolerance settings."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone

from db import db

router = APIRouter(tags=["masters"])


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _uid():
    return str(uuid.uuid4())


# ---------- Models ----------
class CommissionRule(BaseModel):
    id: str = Field(default_factory=_uid)
    brand: str = "Kazo"
    master_category: str  # APPAREL / ACCESSORIES
    sub_category: str  # e.g. Blazers, Tops, Wallets
    gender: str = "Women"
    lower_limit: float
    upper_limit: float
    price_range: str
    commission_model: str = "Split Commission and Logistics"
    commission_pct: float  # 0.085 = 8.5%
    active: bool = True


class FixedFeeSlab(BaseModel):
    id: str = Field(default_factory=_uid)
    aisp_lower: float
    aisp_upper: float
    label: str  # "0-100", "101-300" etc
    fixed_fee: float
    active: bool = True


class GTChargeCell(BaseModel):
    id: str = Field(default_factory=_uid)
    sub_category: str
    level: str  # Level 1..5
    price_range: str  # "0-100" etc
    price_lower: float
    price_upper: float
    charge: float  # inclusive of GST
    active: bool = True


class ReturnFeeCell(BaseModel):
    id: str = Field(default_factory=_uid)
    level: str  # Level 1..5
    zone: str  # Local / Zonal / National
    fee: float
    active: bool = True


class SubCategoryLevel(BaseModel):
    id: str = Field(default_factory=_uid)
    sub_category: str
    level: str


class ToleranceConfig(BaseModel):
    absolute_inr: float = 1.0  # +/- ₹1 tolerance
    percentage: float = 0.5  # 0.5% tolerance
    materiality_inr: float = 100.0  # only flag as critical above this


# ---------- Default seed data ----------
DEFAULT_FIXED_FEE = [
    {"aisp_lower": 0, "aisp_upper": 100, "label": "0-100", "fixed_fee": 27},
    {"aisp_lower": 101, "aisp_upper": 300, "label": "101-300", "fixed_fee": 27},
    {"aisp_lower": 301, "aisp_upper": 500, "label": "301-500", "fixed_fee": 27},
    {"aisp_lower": 501, "aisp_upper": 1000, "label": "501-1000", "fixed_fee": 27},
    {"aisp_lower": 1001, "aisp_upper": 2000, "label": "1001-2000", "fixed_fee": 45},
    {"aisp_lower": 2001, "aisp_upper": 10000000, "label": ">2000", "fixed_fee": 61},
]

DEFAULT_RETURN_FEE = [
    ("Level 1", "Local", 91), ("Level 1", "Zonal", 112), ("Level 1", "National", 167),
    ("Level 2", "Local", 112), ("Level 2", "Zonal", 153), ("Level 2", "National", 218),
    ("Level 3", "Local", 142), ("Level 3", "Zonal", 194), ("Level 3", "National", 259),
    ("Level 4", "Local", 214), ("Level 4", "Zonal", 276), ("Level 4", "National", 331),
    ("Level 5", "Local", 460), ("Level 5", "Zonal", 542), ("Level 5", "National", 649),
]

# Level -> {price_range: charge}
DEFAULT_GT_LEVELS = {
    "Level 1": [(0, 100, "0-100", 0), (101, 300, "101-300", 59), (301, 500, "301-500", 59),
                (501, 1000, "501-1000", 94), (1001, 2000, "1001-2000", 171),
                (2001, 10000000, ">2000", 207)],
    "Level 2": [(0, 100, "0-100", 0), (101, 300, "101-300", 83), (301, 500, "301-500", 83),
                (501, 1000, "501-1000", 118), (1001, 2000, "1001-2000", 194),
                (2001, 10000000, ">2000", 230)],
    "Level 3": [(0, 100, "0-100", 0), (101, 300, "101-300", 100), (301, 500, "301-500", 106),
                (501, 1000, "501-1000", 148), (1001, 2000, "1001-2000", 230),
                (2001, 10000000, ">2000", 266)],
    "Level 4": [(0, 100, "0-100", 0), (101, 300, "101-300", 100), (301, 500, "301-500", 153),
                (501, 1000, "501-1000", 189), (1001, 2000, "1001-2000", 277),
                (2001, 10000000, ">2000", 313)],
    "Level 5": [(0, 100, "0-100", 0), (101, 300, "101-300", 150), (301, 500, "301-500", 200),
                (501, 1000, "501-1000", 240), (1001, 2000, "1001-2000", 330),
                (2001, 10000000, ">2000", 400)],
}

# From provided data (GTA working sheet)
DEFAULT_SUBCAT_LEVELS = {
    "Wallets": "Level 1", "Tshirts": "Level 1", "Trousers": "Level 1",
    "Travel Accessory": "Level 1", "Tops": "Level 1", "Sweatshirts": "Level 2",
    "Sweaters": "Level 2", "Skirts": "Level 1", "Shrug": "Level 1",
    "Shorts": "Level 1", "Shirts": "Level 1", "Scarves": "Level 1",
    "Jumpsuit": "Level 1", "Jeggings": "Level 1", "Jeans": "Level 1",
    "Jackets": "Level 3", "Handbags": "Level 3", "Duffel Bag": "Level 2",
    "Dresses": "Level 1", "Coats": "Level 4", "Clutches": "Level 1",
    "Caps": "Level 1", "Blazers": "Level 4", "Belts": "Level 1",
    "Backpacks": "Level 3", "Track Pants": "Level 1", "Ring": "Level 1",
    "Necklace and Chains": "Level 1", "Headband": "Level 1",
    "Hair Accessory": "Level 2", "Brooch": "Level 1",
    "Accessory Gift Set": "Level 3", "Tunics": "Level 1",
    "Sunglasses": "Level 2", "Perfume and Body Mist": "Level 2",
    "Earrings": "Level 1", "Corset": "Level 1", "Clothing Set": "Level 3",
    "Bracelet": "Level 1", "Co-Ords": "Level 1",
}

# Default commission rules (percentages by sub-category and price band)
DEFAULT_COMMISSION_RULES = [
    # (master_cat, sub_cat, lower, upper, price_range, pct)
    ("APPAREL", "Blazers", 0, 300, "0-300", 0.01),
    ("APPAREL", "Blazers", 300, 500, "301-500", 0.01),
    ("APPAREL", "Blazers", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Coats", 0, 300, "0-300", 0.15),
    ("APPAREL", "Coats", 300, 500, "301-500", 0.15),
    ("APPAREL", "Coats", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Co-Ords", 0, 300, "0-300", 0.05),
    ("APPAREL", "Co-Ords", 300, 500, "301-500", 0.07),
    ("APPAREL", "Co-Ords", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Dresses", 0, 300, "0-300", 0.06),
    ("APPAREL", "Dresses", 300, 500, "301-500", 0.07),
    ("APPAREL", "Dresses", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Jackets", 0, 300, "0-300", 0.01),
    ("APPAREL", "Jackets", 300, 500, "301-500", 0.05),
    ("APPAREL", "Jackets", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Tops", 0, 300, "0-300", 0.05),
    ("APPAREL", "Tops", 300, 500, "301-500", 0.07),
    ("APPAREL", "Tops", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Tshirts", 0, 300, "0-300", 0.05),
    ("APPAREL", "Tshirts", 300, 500, "301-500", 0.07),
    ("APPAREL", "Tshirts", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Shirts", 0, 500, "0-500", 0.05),
    ("APPAREL", "Shirts", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Trousers", 0, 500, "0-500", 0.05),
    ("APPAREL", "Trousers", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Jeans", 0, 500, "0-500", 0.05),
    ("APPAREL", "Jeans", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Skirts", 0, 500, "0-500", 0.05),
    ("APPAREL", "Skirts", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Shorts", 0, 500, "0-500", 0.05),
    ("APPAREL", "Shorts", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Jumpsuit", 0, 500, "0-500", 0.05),
    ("APPAREL", "Jumpsuit", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Sweaters", 0, 500, "0-500", 0.05),
    ("APPAREL", "Sweaters", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Sweatshirts", 0, 500, "0-500", 0.05),
    ("APPAREL", "Sweatshirts", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Tunics", 0, 500, "0-500", 0.05),
    ("APPAREL", "Tunics", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Shrug", 0, 500, "0-500", 0.05),
    ("APPAREL", "Shrug", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Track Pants", 0, 500, "0-500", 0.05),
    ("APPAREL", "Track Pants", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Jeggings", 0, 500, "0-500", 0.05),
    ("APPAREL", "Jeggings", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Corset", 0, 500, "0-500", 0.05),
    ("APPAREL", "Corset", 500, 10000000, ">500", 0.085),
    ("APPAREL", "Clothing Set", 0, 500, "0-500", 0.05),
    ("APPAREL", "Clothing Set", 500, 10000000, ">500", 0.085),
    # Accessories
    ("ACCESSORIES", "Backpacks", 0, 300, "0-300", 0.01),
    ("ACCESSORIES", "Backpacks", 301, 500, "301-500", 0.05),
    ("ACCESSORIES", "Backpacks", 501, 10000000, ">500", 0.14),
    ("ACCESSORIES", "Belts", 0, 300, "0-300", 0.01),
    ("ACCESSORIES", "Belts", 301, 500, "301-500", 0.05),
    ("ACCESSORIES", "Belts", 501, 10000000, ">500", 0.14),
    ("ACCESSORIES", "Caps", 0, 300, "0-300", 0.01),
    ("ACCESSORIES", "Caps", 301, 500, "301-500", 0.05),
    ("ACCESSORIES", "Caps", 501, 10000000, ">500", 0.14),
    ("ACCESSORIES", "Handbags", 0, 500, "0-500", 0.05),
    ("ACCESSORIES", "Handbags", 500, 10000000, ">500", 0.14),
    ("ACCESSORIES", "Wallets", 0, 500, "0-500", 0.05),
    ("ACCESSORIES", "Wallets", 500, 10000000, ">500", 0.14),
    ("ACCESSORIES", "Clutches", 0, 500, "0-500", 0.05),
    ("ACCESSORIES", "Clutches", 500, 10000000, ">500", 0.14),
    ("ACCESSORIES", "Sunglasses", 0, 500, "0-500", 0.05),
    ("ACCESSORIES", "Sunglasses", 500, 10000000, ">500", 0.14),
    ("ACCESSORIES", "Scarves", 0, 500, "0-500", 0.05),
    ("ACCESSORIES", "Scarves", 500, 10000000, ">500", 0.14),
    ("ACCESSORIES", "Earrings", 0, 500, "0-500", 0.05),
    ("ACCESSORIES", "Earrings", 500, 10000000, ">500", 0.14),
    ("ACCESSORIES", "Ring", 0, 500, "0-500", 0.05),
    ("ACCESSORIES", "Ring", 500, 10000000, ">500", 0.14),
    ("ACCESSORIES", "Necklace and Chains", 0, 500, "0-500", 0.05),
    ("ACCESSORIES", "Necklace and Chains", 500, 10000000, ">500", 0.14),
    ("ACCESSORIES", "Bracelet", 0, 500, "0-500", 0.05),
    ("ACCESSORIES", "Bracelet", 500, 10000000, ">500", 0.14),
    ("ACCESSORIES", "Perfume and Body Mist", 0, 500, "0-500", 0.05),
    ("ACCESSORIES", "Perfume and Body Mist", 500, 10000000, ">500", 0.14),
]


async def seed_defaults(dbh):
    # Fixed fee
    if await dbh.fixed_fees.count_documents({}) == 0:
        await dbh.fixed_fees.insert_many([{**x, "id": _uid(), "active": True} for x in DEFAULT_FIXED_FEE])
    # Return fee
    if await dbh.return_fees.count_documents({}) == 0:
        await dbh.return_fees.insert_many([
            {"id": _uid(), "level": lvl, "zone": z, "fee": f, "active": True}
            for lvl, z, f in DEFAULT_RETURN_FEE
        ])
    # GT
    if await dbh.gt_charges.count_documents({}) == 0:
        docs = []
        # For each level, per sub-category that maps to that level, insert charge cells
        for sub, lvl in DEFAULT_SUBCAT_LEVELS.items():
            for lo, hi, label, ch in DEFAULT_GT_LEVELS[lvl]:
                docs.append({
                    "id": _uid(), "sub_category": sub, "level": lvl,
                    "price_range": label, "price_lower": lo, "price_upper": hi,
                    "charge": ch, "active": True,
                })
        await dbh.gt_charges.insert_many(docs)
    # Sub-category level mapping
    if await dbh.subcat_levels.count_documents({}) == 0:
        await dbh.subcat_levels.insert_many([
            {"id": _uid(), "sub_category": s, "level": l}
            for s, l in DEFAULT_SUBCAT_LEVELS.items()
        ])
    # Commission rules
    if await dbh.commission_rules.count_documents({}) == 0:
        await dbh.commission_rules.insert_many([
            {
                "id": _uid(), "brand": "Kazo", "master_category": mc,
                "sub_category": sc, "gender": "Women", "lower_limit": lo,
                "upper_limit": hi, "price_range": pr, "commission_model": "Split Commission and Logistics",
                "commission_pct": pct, "active": True,
            }
            for (mc, sc, lo, hi, pr, pct) in DEFAULT_COMMISSION_RULES
        ])
    # Tolerance
    if await dbh.tolerances.count_documents({}) == 0:
        await dbh.tolerances.insert_one({
            "id": _uid(), "absolute_inr": 1.0, "percentage": 0.5, "materiality_inr": 100.0,
        })


# ---------- Endpoints ----------
def _clean(d):
    d = dict(d)
    d.pop("_id", None)
    return d


@router.get("/masters/commission-rules")
async def list_commission_rules():
    docs = await db.commission_rules.find({}).sort([("master_category", 1), ("sub_category", 1), ("lower_limit", 1)]).to_list(2000)
    return [_clean(d) for d in docs]


@router.post("/masters/commission-rules")
async def upsert_commission_rule(rule: CommissionRule):
    d = rule.model_dump()
    await db.commission_rules.update_one({"id": d["id"]}, {"$set": d}, upsert=True)
    return _clean(d)


@router.delete("/masters/commission-rules/{rule_id}")
async def delete_commission_rule(rule_id: str):
    await db.commission_rules.delete_one({"id": rule_id})
    return {"ok": True}


@router.get("/masters/fixed-fees")
async def list_fixed_fees():
    docs = await db.fixed_fees.find({}).sort("aisp_lower", 1).to_list(200)
    return [_clean(d) for d in docs]


@router.post("/masters/fixed-fees")
async def upsert_fixed_fee(fee: FixedFeeSlab):
    d = fee.model_dump()
    await db.fixed_fees.update_one({"id": d["id"]}, {"$set": d}, upsert=True)
    return _clean(d)


@router.delete("/masters/fixed-fees/{fee_id}")
async def delete_fixed_fee(fee_id: str):
    await db.fixed_fees.delete_one({"id": fee_id})
    return {"ok": True}


@router.get("/masters/gt-charges")
async def list_gt_charges():
    docs = await db.gt_charges.find({}).sort([("sub_category", 1), ("price_lower", 1)]).to_list(5000)
    return [_clean(d) for d in docs]


@router.post("/masters/gt-charges")
async def upsert_gt_charge(cell: GTChargeCell):
    d = cell.model_dump()
    await db.gt_charges.update_one({"id": d["id"]}, {"$set": d}, upsert=True)
    return _clean(d)


@router.delete("/masters/gt-charges/{cell_id}")
async def delete_gt_charge(cell_id: str):
    await db.gt_charges.delete_one({"id": cell_id})
    return {"ok": True}


@router.get("/masters/return-fees")
async def list_return_fees():
    docs = await db.return_fees.find({}).sort([("level", 1), ("zone", 1)]).to_list(200)
    return [_clean(d) for d in docs]


@router.post("/masters/return-fees")
async def upsert_return_fee(cell: ReturnFeeCell):
    d = cell.model_dump()
    await db.return_fees.update_one({"id": d["id"]}, {"$set": d}, upsert=True)
    return _clean(d)


@router.get("/masters/subcat-levels")
async def list_subcat_levels():
    docs = await db.subcat_levels.find({}).sort("sub_category", 1).to_list(500)
    return [_clean(d) for d in docs]


@router.post("/masters/subcat-levels")
async def upsert_subcat_level(item: SubCategoryLevel):
    d = item.model_dump()
    await db.subcat_levels.update_one({"id": d["id"]}, {"$set": d}, upsert=True)
    return _clean(d)


@router.get("/masters/tolerance")
async def get_tolerance():
    doc = await db.tolerances.find_one({}, {"_id": 0})
    return doc or {"absolute_inr": 1.0, "percentage": 0.5, "materiality_inr": 100.0}


@router.post("/masters/tolerance")
async def set_tolerance(payload: ToleranceConfig):
    d = payload.model_dump()
    await db.tolerances.update_one({}, {"$set": d}, upsert=True)
    return d
