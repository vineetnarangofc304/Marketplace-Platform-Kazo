"""Dashboard aggregates: commission summary, reconciliation summary, top variances."""
from fastapi import APIRouter, Query
from typing import Optional, Dict, Any, List
from db import db

router = APIRouter(tags=["dashboards"])


@router.get("/dashboard/commission-summary")
async def commission_summary(upload_id: Optional[str] = None):
    """KPIs from calculations: Total NSV, Expected Commission, Expected Deductions,
    Expected Settlement, break-down by category."""
    match: Dict[str, Any] = {}
    if upload_id:
        match["upload_id"] = upload_id

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": None,
            "total_orders": {"$sum": 1},
            "total_nsv": {"$sum": {"$ifNull": ["$breakdown.nsv_val", 0]}},
            "expected_commission": {"$sum": "$commission_incl_gst"},
            "expected_fixed_fee": {"$sum": "$fixed_fee_incl_gst"},
            "expected_gt_charge": {"$sum": "$gt_charge"},
            "expected_return_fee": {"$sum": "$return_fee"},
            "expected_tcs": {"$sum": "$tcs"},
            "expected_tds": {"$sum": "$tds"},
            "expected_settlement": {"$sum": "$expected_settlement"},
            "expected_deductions": {"$sum": "$total_deductions"},
        }},
    ]
    agg = await db.calculations.aggregate(pipeline).to_list(1)
    kpi = agg[0] if agg else {}
    if kpi:
        kpi.pop("_id", None)

    # By category
    cat_pipe = [
        {"$match": match},
        {"$group": {
            "_id": "$breakdown.master_category",
            "orders": {"$sum": 1},
            "nsv": {"$sum": {"$ifNull": ["$breakdown.nsv_val", 0]}},
            "commission": {"$sum": "$commission_incl_gst"},
            "gt_charge": {"$sum": "$gt_charge"},
            "expected_settlement": {"$sum": "$expected_settlement"},
        }},
    ]
    by_cat = await db.calculations.aggregate(cat_pipe).to_list(50)

    # By sub-category (top 10 by NSV)
    subcat_pipe = [
        {"$match": match},
        {"$group": {
            "_id": "$breakdown.sub_category",
            "orders": {"$sum": 1},
            "nsv": {"$sum": {"$ifNull": ["$breakdown.nsv_val", 0]}},
            "commission": {"$sum": "$commission_incl_gst"},
            "gt_charge": {"$sum": "$gt_charge"},
            "expected_settlement": {"$sum": "$expected_settlement"},
        }},
        {"$sort": {"nsv": -1}},
        {"$limit": 15},
    ]
    by_subcat = await db.calculations.aggregate(subcat_pipe).to_list(15)

    # By zone
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
async def reconciliation_summary(recon_run_id: Optional[str] = None):
    q: Dict[str, Any] = {}
    if recon_run_id:
        q["recon_run_id"] = recon_run_id

    total = await db.discrepancies.count_documents(q)
    by_sev_pipe = [{"$match": q}, {"$group": {"_id": "$severity", "count": {"$sum": 1}, "recoverable": {"$sum": "$recoverable"}}}]
    by_sev = await db.discrepancies.aggregate(by_sev_pipe).to_list(10)

    by_status_pipe = [{"$match": q}, {"$group": {"_id": "$match_status", "count": {"$sum": 1}}}]
    by_status = await db.discrepancies.aggregate(by_status_pipe).to_list(10)

    # By component
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
    by_component = await db.calculations.database.discrepancies.aggregate(comp_pipe).to_list(20)

    total_recoverable_pipe = [{"$match": q}, {"$group": {"_id": None, "sum": {"$sum": "$recoverable"}}}]
    tr = await db.discrepancies.aggregate(total_recoverable_pipe).to_list(1)
    total_recoverable = tr[0]["sum"] if tr else 0

    # Top 10 discrepancies by recoverable
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
async def overview():
    total_sales = await db.sales.count_documents({})
    total_calcs = await db.calculations.count_documents({})
    total_settle = await db.settlement.count_documents({})
    total_disc = await db.discrepancies.count_documents({})
    open_critical = await db.discrepancies.count_documents({"severity": "critical"})
    latest_run = await db.recon_runs.find({}, {"_id": 0}).sort("created_at", -1).limit(1).to_list(1)
    return {
        "total_sales": total_sales,
        "total_calculations": total_calcs,
        "total_settlement_rows": total_settle,
        "total_discrepancies": total_disc,
        "open_critical": open_critical,
        "latest_run": latest_run[0] if latest_run else None,
    }
