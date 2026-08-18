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
from cache_utils import invalidate as invalidate_cache

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
    """Match commission rule by master_category + sub_category (case-insensitive) + ISP band.

    Fallback: if no exact sub_category match, retry against sub_category='ALL'
    for the same master_category. This lets Ops configure a catch-all rate
    per master category instead of having to seed every sub-cat individually.
    """
    if not master_category:
        return None
    mc = master_category.strip().upper()
    sc = (sub_category or "").strip().lower()

    def _match(target_sc: str) -> Optional[Dict]:
        for r in rules:
            if (r.get("master_category") or "").strip().upper() != mc:
                continue
            if (r.get("sub_category") or "").strip().lower() != target_sc:
                continue
            if r.get("lower_limit", 0) <= isp <= r.get("upper_limit", 10**9):
                return r
        return None

    if sc:
        exact = _match(sc)
        if exact:
            return exact
    # Catch-all fallback
    return _match("all")


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


def _classify_order(order_status: Optional[str], txn_type: Optional[str]) -> str:
    """Classify an order-item row into one of:
        sales | return | return_dto | rto | internal_cancel

    Rules (per business, 2026-07):
      - order_status == 'RTO'                    → rto              (nullified; both Sales+RTO and Return+RTO)
      - order_status == 'Internal Cancellation'  → internal_cancel  (nullified; both sides)
      - txn_type == 'Return' AND order_status == 'DTO'
                                                 → return_dto       (only Fixed Fee applies as Return Fee)
      - txn_type == 'Return' (any other status)  → return           (sign-flipped, general return)
      - else                                     → sales            (Sales+Delivered, Sales+DTO, etc.)
    Note: Sales+DTO rows are treated as normal sales; the corresponding
    Return+DTO row (a separate file row) applies the fixed-fee reversal.
    Net effect for a DTO order = seller loses the fixed fee.
    Matching is case-insensitive.
    """
    os_ = (order_status or "").strip().upper()
    tt_ = (txn_type or "").strip().lower()
    is_return_txn = "return" in tt_
    if os_ == "RTO":
        return "rto"
    if os_ == "INTERNAL CANCELLATION":
        return "internal_cancel"
    if is_return_txn and os_ == "DTO":
        return "return_dto"
    if is_return_txn:
        return "return"
    return "sales"


def compute_expected(sale: Dict[str, Any], masters: Dict[str, Any]) -> Dict[str, Any]:
    """Strictly compute expected charges. Missing rules → None + unmapped_reasons.

    Business rules (2026-08 revision — post client review):
      * TCS and TDS are NOT computed anywhere (removed per client feedback —
        the marketplace deducts these separately; Fundle's expected
        settlement should not include them).
      * GST on commission / fixed fee is NOT computed anywhere. `commission_incl_gst`
        and `fixed_fee_incl_gst` are kept equal to the base amounts so downstream
        consumers keep working, but the *_gst fields are always 0.
      * Base for commission = NSV − GT amount = NSV-after-GT.
      * RTO / Internal Cancellation orders → all fees nullified (settlement = 0).
      * Return + DTO → commission, GT and fixed fee are shown as **negative
        reversals** of the corresponding sales-row charges; the Return Fee
        (Level × Zone) is applied as a positive deduction. Net across the
        matched Sales+Return pair = only the Return Fee is lost.
      * Return (non-DTO) → NSV signed negative; commission / GT / fixed fee
        are sign-flipped and Return Fee is charged.
    """
    reasons: List[str] = []
    qty_raw = sale.get("qty") or 0
    try:
        qty = float(qty_raw) or 1.0
    except Exception:
        qty = 1.0
    nsv_unit = float(sale.get("nsv_per_unit") or 0)
    nsv_val = float(sale.get("nsv_val") or 0)
    isp = nsv_unit if nsv_unit else (nsv_val / qty if qty else 0)
    # For return legs the ISP arrives negative — use magnitude for band lookup.
    isp_abs = abs(isp)

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

    order_type = _classify_order(sale.get("order_status"), sale.get("txn_type"))
    is_return = order_type in ("return", "return_dto")

    breakdown: Dict[str, Any] = {
        "isp": round(isp_abs, 2), "qty": qty, "nsv_val": round(nsv_val, 2),
        "sub_category": sub_category, "master_category": master_cat,
        "zone": zone, "level": level,
        "order_type": order_type,
        "report_month": _extract_report_month(sale),
    }

    # Match all masters up-front so the drawer can show them even for RTO / cancel.
    crule = _match_commission_rule(masters["commission_rules"], master_cat, sub_category, isp_abs) if master_cat else None
    ff = _match_fixed_fee(masters["fixed_fees"], isp_abs)
    gt_cell = _match_gt_charge(masters["gt_charges"], sub_category, level, isp_abs) if (sub_category and level) else None
    return_fee_cell = _match_return_fee(masters["return_fees"], level, zone) if (level and zone) else None

    commission_pct = float(crule["commission_pct"]) if crule else None
    fixed_fee_base = float(ff["fixed_fee"]) if ff else None
    gt_unit = float(gt_cell["charge"]) if gt_cell else None
    gt_total = (gt_unit * qty) if gt_unit is not None else None
    return_fee_master = float(return_fee_cell["fee"]) if return_fee_cell else None

    # Reason accounting (per component missing) — only applies for order types that need them
    if order_type in ("sales", "return", "return_dto") and crule is None:
        reasons.append(f"No commission rule for {master_cat}/{sub_category} @ ISP ₹{isp_abs}")
    if order_type in ("sales", "return") and ff is None:
        reasons.append(f"No fixed fee slab for ISP ₹{isp_abs}")
    if order_type in ("sales", "return", "return_dto") and gt_cell is None:
        reasons.append(f"No GT charge for {sub_category} / {level} @ ISP ₹{isp_abs}")
    if order_type in ("return", "return_dto") and return_fee_cell is None:
        reasons.append(f"No return fee for level={level} zone={zone}")

    breakdown["commission_rule"] = {
        "id": crule.get("id") if crule else None,
        "commission_pct": commission_pct,
        "price_range": crule.get("price_range") if crule else None,
        "commission_model": crule.get("commission_model") if crule else None,
        "matched_sub_category": crule.get("sub_category") if crule else None,
    }
    breakdown["fixed_fee_slab"] = {
        "id": ff.get("id") if ff else None,
        "label": ff.get("label") if ff else None,
        "fixed_fee": fixed_fee_base,
    }
    breakdown["gt_charge_cell"] = {
        "id": gt_cell.get("id") if gt_cell else None,
        "level": level, "price_range": gt_cell.get("price_range") if gt_cell else None,
        "unit_charge": gt_unit, "qty": qty,
    }
    breakdown["return_fee_cell"] = {
        "id": return_fee_cell.get("id") if return_fee_cell else None,
        "zone": zone, "level": level, "fee": return_fee_master,
        "applied": order_type in ("return", "return_dto"),
    }

    # ---- Apply order-type-specific arithmetic ----
    # GST and TCS/TDS are always zero (removed per client feedback 2026-08).
    commission_base = None
    fixed_fee = None
    gt_charge_final = None
    return_fee_final = None
    nsv_after_gt = None
    total_deductions = None
    expected_settlement = None

    if order_type == "rto":
        # RTO (Return To Origin) — undelivered order. Per client spec (2.2),
        # display all four fee heads as NEGATIVE reversals (marketplace refunds
        # all sales-side deductions since the order never completed). Net
        # accounting effect on settlement is zero, but the reversal amounts
        # are shown explicitly so the ledger surfaces WHAT was refunded.
        if commission_pct is not None and gt_total is not None:
            commission_base = -abs(commission_pct * (abs(nsv_val) - abs(gt_total)))
        elif commission_pct is not None:
            commission_base = -abs(commission_pct * abs(nsv_val))
        else:
            commission_base = 0.0
        fixed_fee = -abs(fixed_fee_base) if fixed_fee_base is not None else 0.0
        gt_charge_final = -abs(gt_total) if gt_total is not None else 0.0
        return_fee_final = -abs(return_fee_master) if return_fee_master is not None else 0.0
        nsv_after_gt = 0.0
        # Per client spec (Point 6, 2026-02): RTO Total Deductions must equal
        # the arithmetic sum of the four fee heads (Commission + Fixed Fee +
        # GT + Return Fee) so ops can see WHAT was reversed. Settlement itself
        # still nets to zero because these are refunds, not seller losses.
        total_deductions = commission_base + fixed_fee + gt_charge_final + return_fee_final
        expected_settlement = 0.0
        reasons = []
    elif order_type == "internal_cancel":
        # Internal Cancellation — order cancelled before dispatch. Everything
        # nullified (settlement = 0). No fees shown since nothing was ever
        # charged.
        commission_base = 0.0
        fixed_fee = 0.0
        gt_charge_final = 0.0
        return_fee_final = 0.0
        nsv_after_gt = 0.0
        total_deductions = 0.0
        expected_settlement = 0.0
        reasons = []
    elif order_type == "return_dto":
        # Return + DTO — per client spec (2.1):
        #   * Commission = NEGATIVE reversal
        #   * Fixed Fee  = ZERO (no fixed fee on the return leg — marketplace
        #     doesn't charge a fresh fixed fee for DTO return processing)
        #   * GT Charge  = NEGATIVE reversal
        #   * Return Fee = POSITIVE (fresh Level × Zone reverse-logistics charge)
        #   * GST / TCS / TDS not applicable
        signed_nsv = -abs(nsv_val)
        gt_charge_final = -abs(gt_total) if gt_total is not None else None
        if gt_charge_final is not None:
            nsv_after_gt = signed_nsv - gt_charge_final
        if commission_pct is not None and nsv_after_gt is not None:
            commission_base = -abs(commission_pct * abs(nsv_after_gt))
        # Fixed Fee explicitly ZERO for return_dto per spec
        fixed_fee = 0.0
        return_fee_final = abs(return_fee_master) if return_fee_master is not None else None
        parts = [commission_base, fixed_fee, gt_charge_final, return_fee_final]
        if all(x is not None for x in parts) and nsv_after_gt is not None:
            total_deductions = sum(parts)
            expected_settlement = nsv_after_gt - total_deductions
    elif order_type == "return":
        # Return: signed NSV, all components reversed (except return fee, a new charge)
        signed_nsv = -abs(nsv_val)
        if gt_total is not None:
            gt_charge_final = -abs(gt_total)  # GT reversed
            nsv_after_gt = signed_nsv - gt_charge_final
        if commission_pct is not None and nsv_after_gt is not None:
            commission_base = commission_pct * nsv_after_gt  # sign follows nsv_after_gt
        if fixed_fee_base is not None:
            fixed_fee = -abs(fixed_fee_base)
        return_fee_final = abs(return_fee_master) if return_fee_master is not None else 0.0
        parts = [commission_base, fixed_fee, gt_charge_final, return_fee_final]
        if all(x is not None for x in parts) and nsv_after_gt is not None:
            total_deductions = sum(parts)
            expected_settlement = nsv_after_gt - total_deductions
    else:  # sales
        eff_nsv = abs(nsv_val)
        if gt_total is not None:
            gt_charge_final = abs(gt_total)
            nsv_after_gt = eff_nsv - gt_charge_final
        if commission_pct is not None and nsv_after_gt is not None:
            commission_base = commission_pct * nsv_after_gt
        if fixed_fee_base is not None:
            fixed_fee = abs(fixed_fee_base)
        return_fee_final = 0.0
        parts = [commission_base, fixed_fee, gt_charge_final]
        if all(x is not None for x in parts) and nsv_after_gt is not None:
            total_deductions = sum(parts) + return_fee_final
            expected_settlement = nsv_after_gt - total_deductions

    breakdown["nsv_after_gt"] = None if nsv_after_gt is None else round(nsv_after_gt, 2)

    def _round(v):
        return None if v is None else round(v, 2)

    # GST + TCS/TDS retained in the payload for backwards-compat but always 0.
    return {
        "commission_base": _round(commission_base),
        "commission_gst": 0,
        "commission_incl_gst": _round(commission_base),
        "commission_pct": commission_pct,
        "fixed_fee": _round(fixed_fee),
        "fixed_fee_gst": 0,
        "fixed_fee_incl_gst": _round(fixed_fee),
        "gt_charge": _round(gt_charge_final),
        "return_fee": _round(return_fee_final),
        "tcs": 0,
        "tds": 0,
        "nsv_after_gt": _round(nsv_after_gt),
        "total_deductions": _round(total_deductions),
        "expected_settlement": _round(expected_settlement),
        "order_type": order_type,
        "is_return": is_return,
        "unmapped": len(reasons) > 0,
        "unmapped_reasons": reasons,
        "breakdown": breakdown,
        "report_month": breakdown["report_month"],
    }


class RunCalcIn(BaseModel):
    upload_id: Optional[str] = None
    report_month: Optional[str] = None
    portal: Optional[str] = None
    recalculate: bool = False


# --------------------------------------------------------------------------
# Generic portal calc — flat-rate T1..T5 fee heads from the portals catalog.
# Used for all portals EXCEPT myntra (which has the detailed rule engine above).
# --------------------------------------------------------------------------
_ORDER_TYPE_TO_CASE = {
    "sales":           "Delivered",
    "return":          "Delivered",     # negative NSV row → treat as reversal case (Delivered w/ negative sign already)
    "return_dto":      "DTO",
    "rto":             "RTO",
    "internal_cancel": "InternalCancel",
}


def _compute_expected_portal(sale: Dict[str, Any], portal_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Portal-agnostic calc using T1..T5 fee heads.

    For each fee head:
      * sale/return leg → sale['nsv_val'] × pct (or flat_inr / etc.)
      * case_matrix rewrites: 'All null' → 0, 'Again Charged' → same sign as sale-leg,
                              'Reversal' → flip sign, 'No reversal' → 0
    """
    nsv_val = float(sale.get("nsv_val") or 0)
    order_type = _classify_order(sale.get("order_status"), sale.get("txn_type"))
    case = _ORDER_TYPE_TO_CASE.get(order_type, "Delivered")

    heads = portal_doc.get("fee_heads") or []
    matrix = portal_doc.get("case_matrix") or {}
    reasons: List[str] = []

    total_charges = 0.0
    charges: List[Dict[str, Any]] = []

    is_return = order_type in ("return", "return_dto")

    for h in heads:
        key = h.get("key")
        unit = h.get("unit")
        base = h.get("sale") if not is_return else h.get("return")
        behaviour = (matrix.get(case) or {}).get(key, "Charged")

        # Resolve base value
        val = 0.0
        if isinstance(base, (int, float)):
            if unit == "pct":
                val = nsv_val * base
            elif unit == "flat_inr":
                val = float(base)
            else:
                val = float(base)
        elif isinstance(base, str) and base not in ("-", "table", "category", "reversed", "again_charged"):
            # placeholder — unhandled string
            reasons.append(f"Head {key} base '{base}' not evaluable")

        # Behaviour override
        if behaviour == "All null":
            val = 0.0
        elif behaviour == "No reversal":
            val = 0.0
        elif behaviour == "Reversal":
            val = -abs(val)
        elif behaviour == "Again Charged":
            val = abs(val)

        charges.append({
            "key": key, "label": h.get("label"), "value": round(val, 2),
            "behaviour": behaviour, "unit": unit,
        })
        total_charges += val

    expected_settlement = nsv_val - total_charges
    # Try to identify a commission-like head for classic KPI fields
    commission_head = next((c for c in charges if "commission" in (c.get("label") or "").lower()), None)
    logistic_head   = next((c for c in charges if "logistic" in (c.get("label") or "").lower()), None)

    return {
        "commission": round(commission_head["value"], 2) if commission_head else 0,
        "commission_gst": 0,
        "commission_incl_gst": round(commission_head["value"], 2) if commission_head else 0,
        "commission_pct": None,
        "fixed_fee": 0,
        "fixed_fee_gst": 0,
        "fixed_fee_incl_gst": 0,
        "gt_charge": round(logistic_head["value"], 2) if logistic_head else 0,
        "return_fee": 0,
        "tcs": 0,
        "tds": 0,
        "nsv_after_gt": round(nsv_val, 2),
        "total_deductions": round(total_charges, 2),
        "expected_settlement": round(expected_settlement, 2),
        "order_type": order_type,
        "is_return": is_return,
        "unmapped": len(reasons) > 0,
        "unmapped_reasons": reasons,
        "breakdown": {
            "isp": None,
            "qty": sale.get("qty") or 1,
            "nsv_val": round(nsv_val, 2),
            "sub_category": sale.get("sub_category"),
            "master_category": sale.get("main_category"),
            "zone": sale.get("zone"),
            "level": None,
            "order_type": order_type,
            "report_month": _extract_report_month(sale),
            "portal": portal_doc.get("code"),
            "portal_charges": charges,
        },
        "report_month": _extract_report_month(sale),
    }


@router.post("/calculations/run")
async def run_calculations(payload: RunCalcIn):
    q: Dict[str, Any] = {}
    if payload.upload_id:
        q["upload_id"] = payload.upload_id
    if payload.report_month:
        q["report_month"] = payload.report_month
    if payload.portal and payload.portal.lower() != "all":
        q["portal"] = payload.portal.lower()

    total = await db.sales.count_documents(q)
    if total == 0:
        return {"processed": 0, "total_sales": 0, "message": "No sales to process for given filter"}

    if payload.recalculate:
        sales_ids_cur = db.sales.find(q, {"id": 1})
        sales_ids = [s["id"] async for s in sales_ids_cur]
        if sales_ids:
            await db.calculations.delete_many({"sales_id": {"$in": sales_ids}})

    # Load portal catalog once
    portal_docs: Dict[str, Dict[str, Any]] = {p["code"]: p async for p in db.portals.find({}, {"_id": 0})}
    # Myntra masters loaded lazily
    myntra_masters = None

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
        portal_code = (sale.get("portal") or "myntra").lower()
        if portal_code == "myntra":
            if myntra_masters is None:
                myntra_masters = await _get_masters()
            result = compute_expected(sale, myntra_masters)
        else:
            pdoc = portal_docs.get(portal_code)
            if not pdoc:
                # Fallback: mark unmapped
                result = {
                    "commission": 0, "commission_gst": 0, "commission_incl_gst": 0, "commission_pct": None,
                    "fixed_fee": 0, "fixed_fee_gst": 0, "fixed_fee_incl_gst": 0,
                    "gt_charge": 0, "return_fee": 0, "tcs": 0, "tds": 0,
                    "nsv_after_gt": 0, "total_deductions": 0, "expected_settlement": 0,
                    "order_type": _classify_order(sale.get("order_status"), sale.get("txn_type")),
                    "is_return": False, "unmapped": True,
                    "unmapped_reasons": [f"Unknown portal '{portal_code}'"],
                    "breakdown": {"nsv_val": float(sale.get("nsv_val") or 0)},
                    "report_month": _extract_report_month(sale),
                }
            else:
                result = _compute_expected_portal(sale, pdoc)
        if result["unmapped"]:
            unmapped_count += 1
        doc = {
            "id": _uid(),
            "sales_id": sale["id"],
            "upload_id": sale.get("upload_id"),
            "online_order_id": sale.get("online_order_id"),
            "sku": sale.get("sku"),
            "portal": portal_code,
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

    invalidate_cache()

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
    portal: Optional[str] = None,
    sub_category: Optional[str] = None,
    master_category: Optional[str] = None,
    zone: Optional[str] = None,
    order_type: Optional[str] = None,   # sales | return_dto | return | rto | internal_cancel
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
    if portal and portal.lower() != "all":
        q["portal"] = portal.lower()
    if upload_id:
        q["upload_id"] = upload_id
    if sub_category:
        q["breakdown.sub_category"] = sub_category
    if master_category:
        q["breakdown.master_category"] = master_category
    if zone:
        q["breakdown.zone"] = zone
    if order_type:
        q["order_type"] = order_type
    if unmapped_only or severity_flag == "unmapped":
        q["unmapped"] = True
    if severity_flag == "mapped":
        q["unmapped"] = {"$ne": True}
    if search:
        import re as _re
        s = _re.escape(search.strip())
        q["$or"] = [
            {"online_order_id": {"$regex": s, "$options": "i"}},
            {"sku": {"$regex": s, "$options": "i"}},
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
