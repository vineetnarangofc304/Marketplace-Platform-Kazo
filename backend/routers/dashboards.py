"""Dashboard aggregates: commission summary, reconciliation summary, top variances.
All endpoints accept an optional `report_month` filter (YYYY-MM)."""
from typing import Optional, Dict, Any, List
from fastapi import APIRouter
from db import db

router = APIRouter(tags=["dashboards"])


def _apply_month(q: Dict[str, Any], report_month: Optional[str]) -> Dict[str, Any]:
    if report_month:
        q["report_month"] = report_month
    return q


@router.get("/dashboard/commission-summary")
async def commission_summary(
    upload_id: Optional[str] = None,
    report_month: Optional[str] = None,
):
    match: Dict[str, Any] = {}
    if upload_id:
        match["upload_id"] = upload_id
    _apply_month(match, report_month)

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

    cat_pipe = [
        {"$match": match},
        {"$group": {
            "_id": "$breakdown.master_category",
            "orders": {"$sum": 1},
            "nsv": {"$sum": {"$ifNull": ["$breakdown.nsv_val", 0]}},
            "commission": {"$sum": {"$ifNull": ["$commission_incl_gst", 0]}},
            "gt_charge": {"$sum": {"$ifNull": ["$gt_charge", 0]}},
            "expected_settlement": {"$sum": {"$ifNull": ["$expected_settlement", 0]}},
        }},
    ]
    by_cat = await db.calculations.aggregate(cat_pipe).to_list(50)

    subcat_pipe = [
        {"$match": match},
        {"$group": {
            "_id": "$breakdown.sub_category",
            "orders": {"$sum": 1},
            "nsv": {"$sum": {"$ifNull": ["$breakdown.nsv_val", 0]}},
            "commission": {"$sum": {"$ifNull": ["$commission_incl_gst", 0]}},
            "gt_charge": {"$sum": {"$ifNull": ["$gt_charge", 0]}},
            "expected_settlement": {"$sum": {"$ifNull": ["$expected_settlement", 0]}},
        }},
        {"$sort": {"nsv": -1}},
        {"$limit": 15},
    ]
    by_subcat = await db.calculations.aggregate(subcat_pipe).to_list(15)

    zone_pipe = [
        {"$match": match},
        {"$group": {
            "_id": "$breakdown.zone",
            "orders": {"$sum": 1},
            "nsv": {"$sum": {"$ifNull": ["$breakdown.nsv_val", 0]}},
        }},
    ]
    by_zone = await db.calculations.aggregate(zone_pipe).to_list(10)

    return {
        "kpi": kpi,
        "by_category": [{"category": c["_id"], **{k: v for k, v in c.items() if k != "_id"}} for c in by_cat],
        "by_sub_category": [{"sub_category": c["_id"], **{k: v for k, v in c.items() if k != "_id"}} for c in by_subcat],
        "by_zone": [{"zone": c["_id"], **{k: v for k, v in c.items() if k != "_id"}} for c in by_zone],
    }


@router.get("/dashboard/reconciliation-summary")
async def reconciliation_summary(
    recon_run_id: Optional[str] = None,
    report_month: Optional[str] = None,
):
    q: Dict[str, Any] = {}
    if recon_run_id:
        q["recon_run_id"] = recon_run_id
    _apply_month(q, report_month)

    total = await db.discrepancies.count_documents(q)
    by_sev_pipe = [{"$match": q}, {"$group": {"_id": "$severity", "count": {"$sum": 1}, "recoverable": {"$sum": "$recoverable"}}}]
    by_sev = await db.discrepancies.aggregate(by_sev_pipe).to_list(10)

    by_status_pipe = [{"$match": q}, {"$group": {"_id": "$match_status", "count": {"$sum": 1}}}]
    by_status = await db.discrepancies.aggregate(by_status_pipe).to_list(10)

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

    total_recoverable_pipe = [{"$match": q}, {"$group": {"_id": None, "sum": {"$sum": "$recoverable"}}}]
    tr = await db.discrepancies.aggregate(total_recoverable_pipe).to_list(1)
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
async def overview(report_month: Optional[str] = None):
    sales_q: Dict[str, Any] = {}
    _apply_month(sales_q, report_month)
    calc_q = dict(sales_q)
    settle_q: Dict[str, Any] = {}
    _apply_month(settle_q, report_month)
    disc_q = dict(settle_q)

    total_sales = await db.sales.count_documents(sales_q)
    total_calcs = await db.calculations.count_documents(calc_q)
    total_settle = await db.settlement.count_documents(settle_q)
    total_disc = await db.discrepancies.count_documents(disc_q)
    open_critical = await db.discrepancies.count_documents({**disc_q, "severity": "critical"})
    unmapped = await db.calculations.count_documents({**calc_q, "unmapped": True})
    latest_run = await db.recon_runs.find({}, {"_id": 0}).sort("created_at", -1).limit(1).to_list(1)
    return {
        "total_sales": total_sales,
        "total_calculations": total_calcs,
        "total_settlement_rows": total_settle,
        "total_discrepancies": total_disc,
        "open_critical": open_critical,
        "unmapped_calculations": unmapped,
        "latest_run": latest_run[0] if latest_run else None,
    }
