"""Commission calculation engine.
For each sale row (based on brand, category, sub-category, price band, zone),
apply commission rules, fixed-fee slabs, GT charges, return fees, TCS/TDS/GST.
Store calculation record with full breakdown for explainability.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import uuid

from db import db

router = APIRouter(tags=["calculations"])

GST_RATE = 0.18  # 18% on commission & fixed fee
TCS_RATE = 0.005  # 0.5% TCS on gross sales
TDS_RATE = 0.001  # 0.1% TDS on gross sales


def _uid():
    return str(uuid.uuid4())


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _norm_zone(z: Optional[str]) -> str:
    if not z:
        return "Zonal"
    z = z.strip().lower()
    if "local" in z:
        return "Local"
    if "national" in z or "nat" in z:
        return "National"
    return "Zonal"


async def _get_masters() -> Dict[str, Any]:
    commission_rules = await db.commission_rules.find({"active": True}, {"_id": 0}).to_list(2000)
    fixed_fees = await db.fixed_fees.find({"active": True}, {"_id": 0}).to_list(200)
    gt_charges = await db.gt_charges.find({"active": True}, {"_id": 0}).to_list(5000)
    return_fees = await db.return_fees.find({"active": True}, {"_id": 0}).to_list(200)
    subcat_levels = await db.subcat_levels.find({}, {"_id": 0}).to_list(500)

    subcat_level_map = {s["sub_category"]: s["level"] for s in subcat_levels}
    return {
        "commission_rules": commission_rules,
        "fixed_fees": fixed_fees,
        "gt_charges": gt_charges,
        "return_fees": return_fees,
        "subcat_level_map": subcat_level_map,
    }


def _match_commission_rule(rules: List[Dict], sub_category: str, master_category: str, isp: float) -> Optional[Dict]:
    candidates = [
        r for r in rules
        if (r.get("sub_category") or "").lower() == (sub_category or "").lower()
        and (r.get("master_category") or "").upper() == (master_category or "").upper()
        and r.get("lower_limit", 0) <= isp <= r.get("upper_limit", 10**9)
    ]
    if candidates:
        return candidates[0]
    # Fallback by sub_category only
    candidates = [
        r for r in rules
        if (r.get("sub_category") or "").lower() == (sub_category or "").lower()
        and r.get("lower_limit", 0) <= isp <= r.get("upper_limit", 10**9)
    ]
    return candidates[0] if candidates else None


def _match_fixed_fee(slabs: List[Dict], isp: float) -> Optional[Dict]:
    for s in slabs:
        if s.get("aisp_lower", 0) <= isp <= s.get("aisp_upper", 10**9):
            return s
    return None


def _match_gt_charge(gt: List[Dict], sub_category: str, level: str, isp: float) -> Optional[Dict]:
    for c in gt:
        if (c.get("sub_category") or "").lower() == (sub_category or "").lower() \
                and c.get("level") == level \
                and c.get("price_lower", 0) <= isp <= c.get("price_upper", 10**9):
            return c
    # Fallback: any cell for that level+price range (ignore sub_category)
    for c in gt:
        if c.get("level") == level and c.get("price_lower", 0) <= isp <= c.get("price_upper", 10**9):
            return c
    return None


def _match_return_fee(rfs: List[Dict], level: str, zone: str) -> Optional[Dict]:
    for r in rfs:
        if r.get("level") == level and r.get("zone") == zone:
            return r
    return None


def compute_expected(sale: Dict[str, Any], masters: Dict[str, Any]) -> Dict[str, Any]:
    """Compute expected commission & deductions for a single sale row."""
    qty = float(sale.get("qty") or 0) or 1
    nsv_unit = float(sale.get("nsv_per_unit") or 0)
    nsv_val = float(sale.get("nsv_val") or 0)
    isp = nsv_unit if nsv_unit else (nsv_val / qty if qty else 0)
    sub_category = sale.get("sub_category") or ""
    main_category = sale.get("main_category") or ""
    # Normalize master category from main_category
    mc_upper = (main_category or "").upper()
    if "APPAREL" in mc_upper:
        master_cat = "APPAREL"
    else:
        master_cat = "ACCESSORIES"

    zone = _norm_zone(sale.get("zone"))
    level = masters["subcat_level_map"].get(sub_category, "Level 1")

    breakdown: Dict[str, Any] = {
        "isp": round(isp, 2),
        "qty": qty,
        "nsv_val": round(nsv_val, 2),
        "sub_category": sub_category,
        "master_category": master_cat,
        "zone": zone,
        "level": level,
    }

    # Commission (percent of NSV)
    crule = _match_commission_rule(masters["commission_rules"], sub_category, master_cat, isp)
    commission_pct = float(crule["commission_pct"]) if crule else 0.0
    commission_base = nsv_val * commission_pct
    commission_gst = commission_base * GST_RATE
    commission_incl_gst = commission_base + commission_gst
    breakdown["commission_rule"] = {
        "id": crule.get("id") if crule else None,
        "commission_pct": commission_pct,
        "price_range": crule.get("price_range") if crule else None,
        "commission_model": crule.get("commission_model") if crule else None,
    }

    # Fixed fee
    ff = _match_fixed_fee(masters["fixed_fees"], isp)
    fixed_fee = float(ff["fixed_fee"]) if ff else 0.0
    fixed_fee_gst = fixed_fee * GST_RATE
    fixed_fee_incl_gst = fixed_fee + fixed_fee_gst
    breakdown["fixed_fee_slab"] = {
        "id": ff.get("id") if ff else None,
        "label": ff.get("label") if ff else None,
        "fixed_fee": fixed_fee,
    }

    # GT charge (per unit × qty). Charges are inclusive of GST already.
    gt_cell = _match_gt_charge(masters["gt_charges"], sub_category, level, isp)
    gt_unit = float(gt_cell["charge"]) if gt_cell else 0.0
    gt_total = gt_unit * qty
    breakdown["gt_charge_cell"] = {
        "id": gt_cell.get("id") if gt_cell else None,
        "level": level,
        "price_range": gt_cell.get("price_range") if gt_cell else None,
        "unit_charge": gt_unit,
        "qty": qty,
    }

    # Return fee (applicable only if txn is return / order returned)
    txn_type = (sale.get("txn_type") or "").lower()
    order_status = (sale.get("order_status") or "").lower()
    is_return = "return" in txn_type or "return" in order_status or "cancel" in order_status
    return_fee_cell = _match_return_fee(masters["return_fees"], level, zone) if is_return else None
    return_fee = float(return_fee_cell["fee"]) if return_fee_cell else 0.0
    breakdown["return_fee_cell"] = {
        "id": return_fee_cell.get("id") if return_fee_cell else None,
        "zone": zone,
        "level": level,
        "fee": return_fee,
        "applied": is_return,
    }

    # TCS/TDS (on gross NSV)
    tcs = nsv_val * TCS_RATE
    tds = nsv_val * TDS_RATE

    # Forward Settlement:
    # = NSV - Commission(incl GST) - TCS - TDS - Fixed Fee(incl GST) - GT (incl GST already)
    # Reverse Settlement (returns): negative + return fee added
    expected_deductions = commission_incl_gst + fixed_fee_incl_gst + gt_total + tcs + tds
    if is_return:
        expected_deductions += return_fee
        expected_settlement = -nsv_val + commission_incl_gst + return_fee  # marketplace claws back
    else:
        expected_settlement = nsv_val - expected_deductions

    result = {
        "commission_base": round(commission_base, 2),
        "commission_gst": round(commission_gst, 2),
        "commission_incl_gst": round(commission_incl_gst, 2),
        "fixed_fee": round(fixed_fee, 2),
        "fixed_fee_gst": round(fixed_fee_gst, 2),
        "fixed_fee_incl_gst": round(fixed_fee_incl_gst, 2),
        "gt_charge": round(gt_total, 2),
        "return_fee": round(return_fee, 2),
        "tcs": round(tcs, 2),
        "tds": round(tds, 2),
        "total_deductions": round(expected_deductions, 2),
        "expected_settlement": round(expected_settlement, 2),
        "is_return": is_return,
        "breakdown": breakdown,
    }
    return result


class RunCalcIn(BaseModel):
    upload_id: Optional[str] = None
    recalculate: bool = False


@router.post("/calculations/run")
async def run_calculations(payload: RunCalcIn):
    masters = await _get_masters()
    q = {"upload_id": payload.upload_id} if payload.upload_id else {}
    total = await db.sales.count_documents(q)
    if total == 0:
        return {"processed": 0, "message": "No sales to process"}

    processed = 0
    batch = []
    # Optionally clear existing calculations
    if payload.recalculate:
        if payload.upload_id:
            sales_ids = [s["id"] async for s in db.sales.find(q, {"id": 1})]
            if sales_ids:
                await db.calculations.delete_many({"sales_id": {"$in": sales_ids}})
        else:
            await db.calculations.delete_many({})

    async for sale in db.sales.find(q, {"_id": 0}):
        # Skip if calc already exists (unless recalculate=True which already cleared)
        exists = await db.calculations.find_one({"sales_id": sale["id"]}, {"_id": 1})
        if exists and not payload.recalculate:
            continue
        try:
            result = compute_expected(sale, masters)
        except Exception as e:
            continue
        doc = {
            "id": _uid(),
            "sales_id": sale["id"],
            "upload_id": sale.get("upload_id"),
            "online_order_id": sale.get("online_order_id"),
            "sku": sale.get("sku"),
            "computed_at": _iso(),
            **result,
        }
        batch.append(doc)
        if len(batch) >= 500:
            await db.calculations.insert_many(batch)
            processed += len(batch)
            batch = []
    if batch:
        await db.calculations.insert_many(batch)
        processed += len(batch)

    return {"processed": processed, "total_sales": total}


@router.get("/calculations")
async def list_calculations(
    upload_id: Optional[str] = None,
    limit: int = Query(200, le=1000),
    skip: int = 0,
    search: Optional[str] = None,
):
    q: Dict[str, Any] = {}
    if upload_id:
        q["upload_id"] = upload_id
    if search:
        q["$or"] = [
            {"online_order_id": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
        ]
    total = await db.calculations.count_documents(q)
    docs = await db.calculations.find(q, {"_id": 0}).sort("computed_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"total": total, "items": docs}


@router.get("/calculations/by-sale/{sales_id}")
async def get_calc_by_sale(sales_id: str):
    doc = await db.calculations.find_one({"sales_id": sales_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Calculation not found")
    sale = await db.sales.find_one({"id": sales_id}, {"_id": 0})
    return {"calculation": doc, "sale": sale}
