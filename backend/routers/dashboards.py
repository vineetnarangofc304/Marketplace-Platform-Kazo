"""Dashboard aggregates — support Month / Quarter / Year / YTD / All periods."""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Query
from db import db
from period_utils import month_query, parse_period

router = APIRouter(tags=["dashboards"])


def _period_filter(period_type: Optional[str], period_value: Optional[str], report_month: Optional[str]) -> Dict[str, Any]:
    """Prefer explicit period_type; fall back to legacy report_month single-value filter."""
    if period_type:
        return month_query(period_type, period_value)
    if report_month:
        return {"report_month": report_month}
    return {}


@router.get("/dashboard/commission-summary")
async def commission_summary(
    upload_id: Optional[str] = None,
    report_month: Optional[str] = None,
    period_type: Optional[str] = None,
    period_value: Optional[str] = None,
):
    match: Dict[str, Any] = _period_filter(period_type, period_value, report_month)
    if upload_id:
        match["upload_id"] = upload_id

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": None,
            "total_orders": {"$sum": 1},
            "total_nsv": {"$sum": {"$ifNull": ["$breakdown.nsv_val", 0]}},
            "expected_commission": {"$sum": {"$ifNull": ["$commission_incl_gst", 0]}},
            "expected_fixed_fee": {"$sum": {"$ifNull": ["$fixed_fee_incl_gst", 0]}},
            "expected_gt_charge": {"$sum": {"$ifNull": ["$gt_charge", 0]}},
            "expected_return_fee": {"$sum": {"$ifNull": ["$return_fee", 0]}},
            "expected_tcs": {"$sum": {"$ifNull": ["$tcs", 0]}},
            "expected_tds": {"$sum": {"$ifNull": ["$tds", 0]}},
            "expected_settlement": {"$sum": {"$ifNull": ["$expected_settlement", 0]}},
            "expected_deductions": {"$sum": {"$ifNull": ["$total_deductions", 0]}},
            "unmapped_orders": {"$sum": {"$cond": ["$unmapped", 1, 0]}},
        }},
    ]
    agg = await db.calculations.aggregate(pipeline).to_list(1)
    kpi = agg[0] if agg else {}
    if kpi:
        kpi.pop("_id", None)

    async def _group(field, sort_field="nsv", limit=50):
        return await db.calculations.aggregate([
            {"$match": match},
            {"$group": {
                "_id": field,
                "orders": {"$sum": 1},
                "nsv": {"$sum": {"$ifNull": ["$breakdown.nsv_val", 0]}},
                "commission": {"$sum": {"$ifNull": ["$commission_incl_gst", 0]}},
                "fixed_fee": {"$sum": {"$ifNull": ["$fixed_fee_incl_gst", 0]}},
                "gt_charge": {"$sum": {"$ifNull": ["$gt_charge", 0]}},
                "return_fee": {"$sum": {"$ifNull": ["$return_fee", 0]}},
                "expected_settlement": {"$sum": {"$ifNull": ["$expected_settlement", 0]}},
            }},
            {"$sort": {sort_field: -1}},
            {"$limit": limit},
        ]).to_list(limit)

    by_cat = await _group("$breakdown.master_category", limit=10)
    by_subcat = await _group("$breakdown.sub_category", limit=25)
    by_zone = await _group("$breakdown.zone", limit=10)
    by_month = await _group("$report_month", sort_field="_id", limit=24)
    # sort by_month ascending
    by_month.sort(key=lambda x: x.get("_id") or "")

    return {
        "kpi": kpi,
        "by_category": [{"category": c["_id"], **{k: v for k, v in c.items() if k != "_id"}} for c in by_cat],
        "by_sub_category": [{"sub_category": c["_id"], **{k: v for k, v in c.items() if k != "_id"}} for c in by_subcat],
        "by_zone": [{"zone": c["_id"], **{k: v for k, v in c.items() if k != "_id"}} for c in by_zone],
        "by_month": [{"month": c["_id"], **{k: v for k, v in c.items() if k != "_id"}} for c in by_month],
    }


@router.get("/dashboard/reconciliation-summary")
async def reconciliation_summary(
    recon_run_id: Optional[str] = None,
    report_month: Optional[str] = None,
    period_type: Optional[str] = None,
    period_value: Optional[str] = None,
):
    q: Dict[str, Any] = _period_filter(period_type, period_value, report_month)
    if recon_run_id:
        q["recon_run_id"] = recon_run_id

    total = await db.discrepancies.count_documents(q)
    by_sev = await db.discrepancies.aggregate([
        {"$match": q},
        {"$group": {"_id": "$severity", "count": {"$sum": 1}, "recoverable": {"$sum": "$recoverable"}}},
    ]).to_list(10)
    by_status = await db.discrepancies.aggregate([
        {"$match": q},
        {"$group": {"_id": "$match_status", "count": {"$sum": 1}}},
    ]).to_list(10)
    comp_pipe = [
        {"$match": q},
        {"$unwind": "$components"},
        {"$match": {"components.status": {"$in": ["overcharged", "undercharged"]}}},
        {"$group": {
            "_id": "$components.component",
            "count": {"$sum": 1},
            "variance_sum": {"$sum": {"$abs": "$components.variance"}},
        }},
        {"$sort": {"variance_sum": -1}},
    ]
    by_component = await db.discrepancies.aggregate(comp_pipe).to_list(20)
    tr = await db.discrepancies.aggregate([{"$match": q}, {"$group": {"_id": None, "sum": {"$sum": "$recoverable"}}}]).to_list(1)
    total_recoverable = tr[0]["sum"] if tr else 0
    top = await db.discrepancies.find(q, {"_id": 0}).sort("recoverable", -1).limit(10).to_list(10)

    return {
        "total_discrepancies": total,
        "total_recoverable": round(total_recoverable or 0, 2),
        "by_severity": [{"severity": s["_id"], "count": s["count"], "recoverable": round(s.get("recoverable", 0), 2)} for s in by_sev],
        "by_match_status": [{"status": s["_id"], "count": s["count"]} for s in by_status],
        "by_component": [{"component": c["_id"], "count": c["count"], "variance_sum": round(c["variance_sum"], 2)} for c in by_component],
        "top_discrepancies": top,
    }


@router.get("/dashboard/overview")
async def overview(
    report_month: Optional[str] = None,
    period_type: Optional[str] = None,
    period_value: Optional[str] = None,
):
    q = _period_filter(period_type, period_value, report_month)
    total_sales = await db.sales.count_documents(q)
    total_calcs = await db.calculations.count_documents(q)
    total_settle = await db.settlement.count_documents(q)
    total_disc = await db.discrepancies.count_documents(q)
    open_critical = await db.discrepancies.count_documents({**q, "severity": "critical"})
    open_high = await db.discrepancies.count_documents({**q, "severity": "high"})
    unmapped = await db.calculations.count_documents({**q, "unmapped": True})
    latest_run = await db.recon_runs.find({}, {"_id": 0}).sort("created_at", -1).limit(1).to_list(1)
    return {
        "total_sales": total_sales,
        "total_calculations": total_calcs,
        "total_settlement_rows": total_settle,
        "total_discrepancies": total_disc,
        "open_critical": open_critical,
        "open_high": open_high,
        "unmapped_calculations": unmapped,
        "latest_run": latest_run[0] if latest_run else None,
    }


@router.get("/dashboard/periods")
async def available_periods():
    """Return available period options based on report_month values present."""
    months = set()
    async for r in db.sales.aggregate([
        {"$match": {"report_month": {"$ne": None}}},
        {"$group": {"_id": "$report_month"}},
    ]):
        months.add(r["_id"])
    months_list = sorted(list(months))
    years = sorted({m[:4] for m in months_list})
    quarters = sorted({f"{m[:4]}-Q{((int(m[5:7]) - 1) // 3) + 1}" for m in months_list})
    return {
        "months": months_list,
        "quarters": quarters,
        "years": years,
    }
