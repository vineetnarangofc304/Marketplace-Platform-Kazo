"""Commission calculation engine (production).

Strict rule matching — no fallbacks, no hardcoded defaults. If a rule is missing
for any component (commission, fixed fee, GT, return fee, level, zone), the
component is left NULL and the calculation is marked as `unmapped: true` with
`unmapped_reasons: [...]` so operations can fix the masters and rerun.

Tax rates (GST/TCS/TDS) are read from the tax_rates master, not hardcoded.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from db import db

router = APIRouter(tags=["calculations"])

VALID_ZONES = {"Local", "Zonal", "National"}


def _uid():
    return str(uuid.uuid4())


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _normalize_zone(z: Optional[str]) -> Optional[str]:
    """Return canonical zone or None if not resolvable. Never guesses."""
    if not z:
        return None
    zl = str(z).strip().lower()
    if zl in ("local",):
        return "Local"
    if zl in ("zonal", "zone"):
        return "Zonal"
    if zl in ("national", "nat"):
        return "National"
    return None


async def _get_masters() -> Dict[str, Any]:
    commission_rules = await db.commission_rules.find({"active": True}, {"_id": 0}).to_list(5000)
    fixed_fees = await db.fixed_fees.find({"active": True}, {"_id": 0}).to_list(500)
    gt_charges = await db.gt_charges.find({"active": True}, {"_id": 0}).to_list(10000)
    return_fees = await db.return_fees.find({"active": True}, {"_id": 0}).to_list(500)
    subcat_levels = await db.subcat_levels.find({}, {"_id": 0}).to_list(2000)
    tax = await db.tax_rates.find_one({}, {"_id": 0})
    settlement_settings = await db.settlement_settings.find_one({}, {"_id": 0})
    if not tax:
        raise HTTPException(500, "Tax rates master missing. Seed did not run.")
    if not settlement_settings:
        raise HTTPException(500, "Settlement settings missing. Seed did not run.")
    # Case-insensitive level map
    level_map = {}
    for s in subcat_levels:
        key = (s["sub_category"] or "").strip().lower()
        level_map[key] = s["level"]
    return {
        "commission_rules": commission_rules,
        "fixed_fees": fixed_fees,
        "gt_charges": gt_charges,
        "return_fees": return_fees,
        "subcat_level_map": level_map,
        "gst_rate": tax["gst_rate"],
        "tcs_rate": tax["tcs_rate"],
        "tds_rate": tax["tds_rate"],
        "settlement_settings": settlement_settings,
    }


def _match_commission_rule(rules: List[Dict], master_category: str, sub_category: str, isp: float) -> Optional[Dict]:
    """Strict: master_category + sub_category (case-insensitive) + isp within [lower, upper]."""
    if not master_category or not sub_category:
        return None
    mc = master_category.strip().upper()
    sc = sub_category.strip().lower()
    for r in rules:
        if (r.get("master_category") or "").strip().upper() != mc:
            continue
        if (r.get("sub_category") or "").strip().lower() != sc:
            continue
        if r.get("lower_limit", 0) <= isp <= r.get("upper_limit", 10**9):
            return r
    return None


def _match_fixed_fee(slabs: List[Dict], isp: float) -> Optional[Dict]:
    for s in slabs:
        if s.get("aisp_lower", 0) <= isp <= s.get("aisp_upper", 10**9):
            return s
    return None


def _match_gt_charge(gt: List[Dict], sub_category: str, level: str, isp: float) -> Optional[Dict]:
    """Strict: exact sub-category + level + price band. No fallback."""
    if not sub_category or not level:
        return None
    sc = sub_category.strip().lower()
    for c in gt:
        if (c.get("sub_category") or "").strip().lower() != sc:
            continue
        if c.get("level") != level:
            continue
        if c.get("price_lower", 0) <= isp <= c.get("price_upper", 10**9):
            return c
    return None


def _match_return_fee(rfs: List[Dict], level: str, zone: str) -> Optional[Dict]:
    if not level or not zone:
        return None
    for r in rfs:
        if r.get("level") == level and r.get("zone") == zone:
            return r
    return None


def _extract_report_month(sale: Dict[str, Any]) -> Optional[str]:
    """Return 'YYYY-MM' from Month (e.g., 'Apr-26') or posting/order date."""
    # Try 'month' field (e.g., "Apr-26", "Jun-25")
    m = sale.get("month")
    if m and isinstance(m, str):
        try:
            dt = datetime.strptime(m.strip(), "%b-%y")
            return dt.strftime("%Y-%m")
        except ValueError:
            pass
        try:
            dt = datetime.strptime(m.strip(), "%B %Y")
            return dt.strftime("%Y-%m")
        except ValueError:
            pass
    # Fallback to posting_date / order_date if ISO
    for k in ("posting_date", "order_date"):
        v = sale.get(k)
        if v and isinstance(v, str):
            try:
                return v[:7]  # 'YYYY-MM'
            except Exception:
                pass
    return None


def compute_expected(sale: Dict[str, Any], masters: Dict[str, Any]) -> Dict[str, Any]:
    """Strictly compute expected charges. Missing rules → None + unmapped_reasons."""
    reasons: List[str] = []
    qty_raw = sale.get("qty") or 0
    try:
        qty = float(qty_raw) or 1.0
    except Exception:
        qty = 1.0
    nsv_unit = float(sale.get("nsv_per_unit") or 0)
    nsv_val = float(sale.get("nsv_val") or 0)
    isp = nsv_unit if nsv_unit else (nsv_val / qty if qty else 0)

    sub_category = (sale.get("sub_category") or "").strip()
    main_category = (sale.get("main_category") or "").strip()
    zone_raw = sale.get("zone")
    zone = _normalize_zone(zone_raw)

    # Apply configurable default zone if missing / dash placeholder
    ss = masters.get("settlement_settings") or {}
    zone_is_missing = zone is None
    if ss.get("treat_dash_as_missing_zone", True):
        if zone_raw is not None and str(zone_raw).strip() == "-":
            zone_is_missing = True
    if zone_is_missing and ss.get("apply_default_zone", True):
        default_zone = ss.get("default_zone_when_missing")
        if default_zone and default_zone in VALID_ZONES:
            zone = default_zone

    # Master category — normalize from main_category text
    mc_upper = main_category.upper()
    if "APPAREL" in mc_upper:
        master_cat = "APPAREL"
    elif "ACCESS" in mc_upper or "DETAIL" in mc_upper:
        master_cat = "ACCESSORIES"
    else:
        master_cat = None
        reasons.append(f"Unrecognized master_category '{main_category}'")

    level = masters["subcat_level_map"].get(sub_category.lower())
    if not level:
        reasons.append(f"Sub-category '{sub_category}' not in level map")
    if not zone:
        reasons.append(f"Zone '{zone_raw}' not recognized and no default configured")

    breakdown: Dict[str, Any] = {
        "isp": round(isp, 2), "qty": qty, "nsv_val": round(nsv_val, 2),
        "sub_category": sub_category, "master_category": master_cat,
        "zone": zone, "level": level,
        "report_month": _extract_report_month(sale),
    }

    # Commission
    commission_base = None
    commission_gst = None
    commission_incl_gst = None
    commission_pct = None
    crule = None
    if master_cat and sub_category:
        crule = _match_commission_rule(masters["commission_rules"], master_cat, sub_category, isp)
    if crule:
        commission_pct = float(crule["commission_pct"])
        commission_base = nsv_val * commission_pct
        commission_gst = commission_base * masters["gst_rate"]
        commission_incl_gst = commission_base + commission_gst
    else:
        reasons.append(f"No commission rule for {master_cat}/{sub_category} @ ISP ₹{isp}")
    breakdown["commission_rule"] = {
        "id": crule.get("id") if crule else None,
        "commission_pct": commission_pct,
        "price_range": crule.get("price_range") if crule else None,
        "commission_model": crule.get("commission_model") if crule else None,
    }

    # Fixed fee
    ff = _match_fixed_fee(masters["fixed_fees"], isp)
    fixed_fee = float(ff["fixed_fee"]) if ff else None
    fixed_fee_gst = (fixed_fee * masters["gst_rate"]) if fixed_fee is not None else None
    fixed_fee_incl_gst = (fixed_fee + fixed_fee_gst) if fixed_fee is not None else None
    if ff is None:
        reasons.append(f"No fixed fee slab for ISP ₹{isp}")
    breakdown["fixed_fee_slab"] = {
        "id": ff.get("id") if ff else None,
        "label": ff.get("label") if ff else None,
        "fixed_fee": fixed_fee,
    }

    # GT charge
    gt_cell = None
    gt_unit = None
    gt_total = None
    if sub_category and level:
        gt_cell = _match_gt_charge(masters["gt_charges"], sub_category, level, isp)
    if gt_cell:
        gt_unit = float(gt_cell["charge"])
        gt_total = gt_unit * qty
    else:
        reasons.append(f"No GT charge for {sub_category} / {level} @ ISP ₹{isp}")
    breakdown["gt_charge_cell"] = {
        "id": gt_cell.get("id") if gt_cell else None,
        "level": level, "price_range": gt_cell.get("price_range") if gt_cell else None,
        "unit_charge": gt_unit, "qty": qty,
    }

    # Return fee (applicable only when txn is return / order cancelled)
    txn_type = (sale.get("txn_type") or "").lower()
    order_status = (sale.get("order_status") or "").lower()
    is_return = "return" in txn_type or "return" in order_status or "cancel" in order_status
    return_fee_cell = _match_return_fee(masters["return_fees"], level, zone) if (is_return and level and zone) else None
    return_fee = float(return_fee_cell["fee"]) if return_fee_cell else (0.0 if not is_return else None)
    if is_return and return_fee is None:
        reasons.append(f"No return fee for level={level} zone={zone}")
    breakdown["return_fee_cell"] = {
        "id": return_fee_cell.get("id") if return_fee_cell else None,
        "zone": zone, "level": level, "fee": return_fee, "applied": is_return,
    }

    # TCS/TDS (on NSV) — always calculable if NSV known
    tcs = nsv_val * masters["tcs_rate"]
    tds = nsv_val * masters["tds_rate"]

    # Totals — computed only from resolved components (missing → excluded)
    components = [commission_incl_gst, fixed_fee_incl_gst, gt_total, return_fee, tcs, tds]
    total_deductions = None
    expected_settlement = None
    if all(x is not None for x in components):
        total_deductions = sum(components)
        if is_return:
            expected_settlement = -nsv_val + (commission_incl_gst or 0) + (return_fee or 0)
        else:
            expected_settlement = nsv_val - total_deductions

    def _round(v):
        return None if v is None else round(v, 2)

    return {
        "commission_base": _round(commission_base),
        "commission_gst": _round(commission_gst),
        "commission_incl_gst": _round(commission_incl_gst),
        "commission_pct": commission_pct,
        "fixed_fee": _round(fixed_fee),
        "fixed_fee_gst": _round(fixed_fee_gst),
        "fixed_fee_incl_gst": _round(fixed_fee_incl_gst),
        "gt_charge": _round(gt_total),
        "return_fee": _round(return_fee),
        "tcs": _round(tcs),
        "tds": _round(tds),
        "total_deductions": _round(total_deductions),
        "expected_settlement": _round(expected_settlement),
        "is_return": is_return,
        "unmapped": len(reasons) > 0,
        "unmapped_reasons": reasons,
        "breakdown": breakdown,
        "report_month": breakdown["report_month"],
    }


class RunCalcIn(BaseModel):
    upload_id: Optional[str] = None
    report_month: Optional[str] = None
    recalculate: bool = False


@router.post("/calculations/run")
async def run_calculations(payload: RunCalcIn):
    masters = await _get_masters()
    q: Dict[str, Any] = {}
    if payload.upload_id:
        q["upload_id"] = payload.upload_id
    if payload.report_month:
        q["report_month"] = payload.report_month

    total = await db.sales.count_documents(q)
    if total == 0:
        return {"processed": 0, "total_sales": 0, "message": "No sales to process for given filter"}

    if payload.recalculate:
        sales_ids_cur = db.sales.find(q, {"id": 1})
        sales_ids = [s["id"] async for s in sales_ids_cur]
        if sales_ids:
            await db.calculations.delete_many({"sales_id": {"$in": sales_ids}})

    # Fetch existing sales_ids that already have calculations to skip
    existing_ids = set()
    if not payload.recalculate:
        async for c in db.calculations.find({}, {"sales_id": 1}):
            existing_ids.add(c.get("sales_id"))

    processed = 0
    unmapped_count = 0
    batch = []
    async for sale in db.sales.find(q, {"_id": 0}):
        if sale["id"] in existing_ids:
            continue
        result = compute_expected(sale, masters)
        if result["unmapped"]:
            unmapped_count += 1
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

    return {
        "processed": processed,
        "total_sales": total,
        "unmapped_count": unmapped_count,
        "fully_mapped_count": processed - unmapped_count,
    }


@router.get("/calculations")
async def list_calculations(
    upload_id: Optional[str] = None,
    report_month: Optional[str] = None,
    period_type: Optional[str] = None,
    period_value: Optional[str] = None,
    sub_category: Optional[str] = None,
    master_category: Optional[str] = None,
    zone: Optional[str] = None,
    severity_flag: Optional[str] = None,  # 'unmapped' or 'mapped'
    unmapped_only: bool = False,
    limit: int = Query(200, le=2000),
    skip: int = 0,
    search: Optional[str] = None,
    sort_by: str = "computed_at",
    sort_dir: str = "desc",
):
    from period_utils import month_query as _mq
    q: Dict[str, Any] = {}
    if period_type:
        q.update(_mq(period_type, period_value))
    elif report_month:
        q["report_month"] = report_month
    if upload_id:
        q["upload_id"] = upload_id
    if sub_category:
        q["breakdown.sub_category"] = sub_category
    if master_category:
        q["breakdown.master_category"] = master_category
    if zone:
        q["breakdown.zone"] = zone
    if unmapped_only or severity_flag == "unmapped":
        q["unmapped"] = True
    if severity_flag == "mapped":
        q["unmapped"] = {"$ne": True}
    if search:
        q["$or"] = [
            {"online_order_id": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
        ]
    total = await db.calculations.count_documents(q)
    sort_map = {
        "computed_at": "computed_at", "nsv": "breakdown.nsv_val",
        "commission": "commission_incl_gst", "gt_charge": "gt_charge",
        "fixed_fee": "fixed_fee_incl_gst", "deductions": "total_deductions",
        "settlement": "expected_settlement", "sku": "sku", "order_id": "online_order_id",
        "sub_category": "breakdown.sub_category", "month": "report_month",
    }
    sort_field = sort_map.get(sort_by, "computed_at")
    direction = -1 if sort_dir == "desc" else 1
    docs = await db.calculations.find(q, {"_id": 0}).sort(sort_field, direction).skip(skip).limit(limit).to_list(limit)
    return {"total": total, "items": docs}


@router.get("/calculations/by-sale/{sales_id}")
async def get_calc_by_sale(sales_id: str):
    doc = await db.calculations.find_one({"sales_id": sales_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Calculation not found — run calculations first")
    sale = await db.sales.find_one({"id": sales_id}, {"_id": 0})
    return {"calculation": doc, "sale": sale}


@router.get("/calculations/unmapped-summary")
async def unmapped_summary(report_month: Optional[str] = None):
    """Group unmapped calculations by their first reason so ops can fix masters."""
    match = {"unmapped": True}
    if report_month:
        match["report_month"] = report_month
    pipeline = [
        {"$match": match},
        {"$unwind": "$unmapped_reasons"},
        {"$group": {"_id": "$unmapped_reasons", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 50},
    ]
    rows = await db.calculations.aggregate(pipeline).to_list(50)
    return [{"reason": r["_id"], "count": r["count"]} for r in rows]
