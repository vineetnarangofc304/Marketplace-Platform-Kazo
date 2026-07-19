"""File uploads: Sales data (Myntra Raw_Online Sale-m) and Settlement report."""
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
import io
import openpyxl

from db import db

router = APIRouter(tags=["uploads"])


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _uid():
    return str(uuid.uuid4())


def _norm_str(v):
    if v is None:
        return None
    return str(v).strip()


def _num(v):
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "").replace("₹", "").strip())
    except Exception:
        return 0.0


def _date_iso(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    try:
        return str(v)
    except Exception:
        return None


# ---------- Sales upload ----------
# Column mapping for Myntra "Raw_Online Sale-m" sheet
SALES_COLUMN_MAP = {
    "Order Date": "order_date",
    "Txn Type": "txn_type",
    "Brand": "brand",
    "Month": "month",
    "Posting Date": "posting_date",
    "Order Status": "order_status",
    "Portal Name": "portal_name",
    "Sales Invoice No": "sales_invoice_no",
    "Online Order Id": "online_order_id",
    "Sku": "sku",
    "Shipped To _ZONE": "zone",
    "QTY-Final": "qty",
    "MRP": "mrp",
    "Total MRP": "total_mrp",
    "Cust. Discount": "customer_discount",
    "NSV VAL.": "nsv_val",
    "NSV/Unit": "nsv_per_unit",
    "Main Category": "main_category",
    "Category": "category",
    "Sub Category_ GTA Charges": "sub_category",
    "GT Amount (Inc. gst)": "actual_gt_amount",
    "Fixed Fee-New": "actual_fixed_fee",
    "Return Fee-New": "actual_return_fee",
    "Commission Value.-New": "actual_commission_value",
}


def _find_header_row(ws, expected_names):
    """Search first 5 rows for a row that contains at least half of the expected header names."""
    exp_lower = {e.lower() for e in expected_names}
    for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=6, values_only=True), start=1):
        vals = [str(v).strip().lower() if v else "" for v in row]
        matches = sum(1 for v in vals if v in exp_lower)
        if matches >= 3:
            return row_idx, row
    return None, None


def _parse_sales_xlsx(content: bytes) -> Dict[str, Any]:
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)

    # Try preferred sheet name, else pick largest sheet
    target = None
    for sname in wb.sheetnames:
        if "sale" in sname.lower() or "raw" in sname.lower() or "online" in sname.lower():
            target = sname
            break
    if not target:
        target = max(wb.sheetnames, key=lambda s: wb[s].max_row)
    ws = wb[target]

    header_row, header = _find_header_row(ws, list(SALES_COLUMN_MAP.keys()))
    if not header:
        raise HTTPException(400, "Could not detect header row in sales sheet")

    header_norm = [str(h).strip() if h else "" for h in header]
    col_idx = {}
    for i, name in enumerate(header_norm):
        if name in SALES_COLUMN_MAP:
            col_idx[SALES_COLUMN_MAP[name]] = i

    accepted = []
    rejected = []
    for r_no, row in enumerate(ws.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 1):
        if not row or all(v is None for v in row):
            continue
        try:
            rec = {
                "order_date": _date_iso(row[col_idx["order_date"]]) if "order_date" in col_idx else None,
                "txn_type": _norm_str(row[col_idx["txn_type"]]) if "txn_type" in col_idx else None,
                "brand": _norm_str(row[col_idx["brand"]]) if "brand" in col_idx else None,
                "month": _norm_str(row[col_idx["month"]]) if "month" in col_idx else None,
                "posting_date": _date_iso(row[col_idx["posting_date"]]) if "posting_date" in col_idx else None,
                "order_status": _norm_str(row[col_idx["order_status"]]) if "order_status" in col_idx else None,
                "portal_name": _norm_str(row[col_idx["portal_name"]]) if "portal_name" in col_idx else None,
                "sales_invoice_no": _norm_str(row[col_idx["sales_invoice_no"]]) if "sales_invoice_no" in col_idx else None,
                "online_order_id": _norm_str(row[col_idx["online_order_id"]]) if "online_order_id" in col_idx else None,
                "sku": _norm_str(row[col_idx["sku"]]) if "sku" in col_idx else None,
                "zone": _norm_str(row[col_idx["zone"]]) if "zone" in col_idx else None,
                "qty": _num(row[col_idx["qty"]]) if "qty" in col_idx else 0,
                "mrp": _num(row[col_idx["mrp"]]) if "mrp" in col_idx else 0,
                "total_mrp": _num(row[col_idx["total_mrp"]]) if "total_mrp" in col_idx else 0,
                "customer_discount": _num(row[col_idx["customer_discount"]]) if "customer_discount" in col_idx else 0,
                "nsv_val": _num(row[col_idx["nsv_val"]]) if "nsv_val" in col_idx else 0,
                "nsv_per_unit": _num(row[col_idx["nsv_per_unit"]]) if "nsv_per_unit" in col_idx else 0,
                "main_category": _norm_str(row[col_idx["main_category"]]) if "main_category" in col_idx else None,
                "category": _norm_str(row[col_idx["category"]]) if "category" in col_idx else None,
                "sub_category": _norm_str(row[col_idx["sub_category"]]) if "sub_category" in col_idx else None,
                "actual_gt_amount": _num(row[col_idx["actual_gt_amount"]]) if "actual_gt_amount" in col_idx else 0,
                "actual_fixed_fee": _num(row[col_idx["actual_fixed_fee"]]) if "actual_fixed_fee" in col_idx else 0,
                "actual_return_fee": _num(row[col_idx["actual_return_fee"]]) if "actual_return_fee" in col_idx else 0,
                "actual_commission_value": _num(row[col_idx["actual_commission_value"]]) if "actual_commission_value" in col_idx else 0,
                "_row_no": r_no,
            }
            # Basic validation
            if not rec.get("online_order_id") or not rec.get("sku"):
                rejected.append({"row_no": r_no, "reason": "Missing Online Order ID or SKU", "data": rec})
                continue
            if rec.get("nsv_val", 0) < 0:
                rejected.append({"row_no": r_no, "reason": "Negative NSV value", "data": rec})
                continue
            accepted.append(rec)
        except Exception as e:
            rejected.append({"row_no": r_no, "reason": f"Parse error: {e}"})

    return {"accepted": accepted, "rejected": rejected, "sheet": target, "header_row": header_row}


@router.post("/uploads/sales")
async def upload_sales(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Only .xlsx files are supported")
    content = await file.read()
    parsed = _parse_sales_xlsx(content)
    upload_id = _uid()
    total_accepted = len(parsed["accepted"])
    total_rejected = len(parsed["rejected"])

    # Persist sales rows
    if parsed["accepted"]:
        docs = []
        for r in parsed["accepted"]:
            d = dict(r)
            d.pop("_row_no", None)
            d.update({
                "id": _uid(), "upload_id": upload_id,
                "uploaded_at": _iso(),
                "source_file": file.filename,
            })
            docs.append(d)
        # Chunk insert
        for i in range(0, len(docs), 1000):
            await db.sales.insert_many(docs[i:i + 1000])

    # Save upload record
    upload_doc = {
        "id": upload_id, "type": "sales", "filename": file.filename,
        "uploaded_at": _iso(), "sheet": parsed["sheet"],
        "accepted_count": total_accepted, "rejected_count": total_rejected,
        "rejections_sample": parsed["rejected"][:50],
        "status": "processed",
    }
    await db.uploads.insert_one({**upload_doc})

    return {
        "upload_id": upload_id,
        "accepted_count": total_accepted,
        "rejected_count": total_rejected,
        "rejections_sample": parsed["rejected"][:20],
        "sheet": parsed["sheet"],
        "filename": file.filename,
    }


# ---------- Settlement upload ----------
# Common Myntra settlement columns (heuristic — will attempt to match)
SETTLEMENT_COLUMN_MAP = {
    "Order Id": "online_order_id", "Online Order Id": "online_order_id",
    "Order ID": "online_order_id", "OrderId": "online_order_id",
    "Sku": "sku", "SKU": "sku", "sku": "sku",
    "Settlement Date": "settlement_date", "Settled Date": "settlement_date",
    "Commission": "settled_commission", "Marketplace Fee": "settled_commission",
    "Commission Amount": "settled_commission",
    "Fixed Fee": "settled_fixed_fee", "Closing Fee": "settled_fixed_fee",
    "GT Charges": "settled_gt_charge", "Logistics": "settled_gt_charge",
    "Logistics Fee": "settled_gt_charge",
    "Return Fee": "settled_return_fee", "Return Shipping Fee": "settled_return_fee",
    "TCS": "settled_tcs", "TDS": "settled_tds",
    "Settlement Value": "settled_amount", "Payout": "settled_amount",
    "Net Settlement": "settled_amount",
    "Selling Price": "selling_price", "MRP": "mrp",
    "Order Status": "order_status", "Zone": "zone",
}


def _parse_settlement_xlsx(content: bytes) -> Dict[str, Any]:
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    target = None
    for s in wb.sheetnames:
        if "settle" in s.lower() or "payout" in s.lower() or "commission" in s.lower():
            target = s
            break
    if not target:
        target = max(wb.sheetnames, key=lambda s: wb[s].max_row)
    ws = wb[target]

    header_row, header = _find_header_row(ws, list(SETTLEMENT_COLUMN_MAP.keys()))
    if not header:
        raise HTTPException(400, "Could not detect header row in settlement sheet")

    header_norm = [str(h).strip() if h else "" for h in header]
    col_idx = {}
    for i, name in enumerate(header_norm):
        if name in SETTLEMENT_COLUMN_MAP:
            col_idx[SETTLEMENT_COLUMN_MAP[name]] = i

    if "online_order_id" not in col_idx or "sku" not in col_idx:
        raise HTTPException(400, "Settlement file must have Order ID and SKU columns")

    accepted = []
    rejected = []
    for r_no, row in enumerate(ws.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 1):
        if not row or all(v is None for v in row):
            continue
        try:
            rec = {
                "online_order_id": _norm_str(row[col_idx["online_order_id"]]),
                "sku": _norm_str(row[col_idx["sku"]]),
                "settlement_date": _date_iso(row[col_idx["settlement_date"]]) if "settlement_date" in col_idx else None,
                "settled_commission": _num(row[col_idx["settled_commission"]]) if "settled_commission" in col_idx else 0,
                "settled_fixed_fee": _num(row[col_idx["settled_fixed_fee"]]) if "settled_fixed_fee" in col_idx else 0,
                "settled_gt_charge": _num(row[col_idx["settled_gt_charge"]]) if "settled_gt_charge" in col_idx else 0,
                "settled_return_fee": _num(row[col_idx["settled_return_fee"]]) if "settled_return_fee" in col_idx else 0,
                "settled_tcs": _num(row[col_idx["settled_tcs"]]) if "settled_tcs" in col_idx else 0,
                "settled_tds": _num(row[col_idx["settled_tds"]]) if "settled_tds" in col_idx else 0,
                "settled_amount": _num(row[col_idx["settled_amount"]]) if "settled_amount" in col_idx else 0,
                "selling_price": _num(row[col_idx["selling_price"]]) if "selling_price" in col_idx else 0,
                "zone": _norm_str(row[col_idx["zone"]]) if "zone" in col_idx else None,
                "order_status": _norm_str(row[col_idx["order_status"]]) if "order_status" in col_idx else None,
                "_row_no": r_no,
            }
            if not rec["online_order_id"] or not rec["sku"]:
                rejected.append({"row_no": r_no, "reason": "Missing Order ID/SKU"})
                continue
            accepted.append(rec)
        except Exception as e:
            rejected.append({"row_no": r_no, "reason": f"Parse error: {e}"})
    return {"accepted": accepted, "rejected": rejected, "sheet": target, "header_row": header_row}


@router.post("/uploads/settlement")
async def upload_settlement(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Only .xlsx files are supported")
    content = await file.read()
    parsed = _parse_settlement_xlsx(content)
    upload_id = _uid()

    if parsed["accepted"]:
        docs = []
        for r in parsed["accepted"]:
            d = dict(r)
            d.pop("_row_no", None)
            d.update({
                "id": _uid(), "upload_id": upload_id,
                "uploaded_at": _iso(),
                "source_file": file.filename,
            })
            docs.append(d)
        for i in range(0, len(docs), 1000):
            await db.settlement.insert_many(docs[i:i + 1000])

    upload_doc = {
        "id": upload_id, "type": "settlement", "filename": file.filename,
        "uploaded_at": _iso(), "sheet": parsed["sheet"],
        "accepted_count": len(parsed["accepted"]),
        "rejected_count": len(parsed["rejected"]),
        "rejections_sample": parsed["rejected"][:50],
        "status": "processed",
    }
    await db.uploads.insert_one(upload_doc)

    return {
        "upload_id": upload_id,
        "accepted_count": len(parsed["accepted"]),
        "rejected_count": len(parsed["rejected"]),
        "rejections_sample": parsed["rejected"][:20],
        "sheet": parsed["sheet"],
        "filename": file.filename,
    }


@router.get("/uploads")
async def list_uploads(kind: Optional[str] = Query(None)):
    q = {}
    if kind:
        q["type"] = kind
    docs = await db.uploads.find(q, {"_id": 0}).sort("uploaded_at", -1).to_list(200)
    return docs


@router.delete("/uploads/{upload_id}")
async def delete_upload(upload_id: str):
    up = await db.uploads.find_one({"id": upload_id})
    if not up:
        raise HTTPException(404, "Upload not found")
    coll = "sales" if up["type"] == "sales" else "settlement"
    await db[coll].delete_many({"upload_id": upload_id})
    if coll == "sales":
        # also delete related calculations
        sales_ids = [s["id"] async for s in db.sales.find({"upload_id": upload_id}, {"id": 1})]
        if sales_ids:
            await db.calculations.delete_many({"sales_id": {"$in": sales_ids}})
    await db.uploads.delete_one({"id": upload_id})
    return {"ok": True}


@router.get("/sales")
async def list_sales(
    upload_id: Optional[str] = None,
    search: Optional[str] = None,
    zone: Optional[str] = None,
    category: Optional[str] = None,
    sub_category: Optional[str] = None,
    order_status: Optional[str] = None,
    limit: int = Query(200, le=1000),
    skip: int = 0,
):
    q: Dict[str, Any] = {}
    if upload_id:
        q["upload_id"] = upload_id
    if zone:
        q["zone"] = zone
    if category:
        q["category"] = category
    if sub_category:
        q["sub_category"] = sub_category
    if order_status:
        q["order_status"] = order_status
    if search:
        q["$or"] = [
            {"online_order_id": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
            {"sales_invoice_no": {"$regex": search, "$options": "i"}},
        ]
    total = await db.sales.count_documents(q)
    docs = await db.sales.find(q, {"_id": 0}).sort("uploaded_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"total": total, "items": docs}


@router.get("/settlement")
async def list_settlement(
    upload_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(200, le=1000),
    skip: int = 0,
):
    q: Dict[str, Any] = {}
    if upload_id:
        q["upload_id"] = upload_id
    if search:
        q["$or"] = [
            {"online_order_id": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
        ]
    total = await db.settlement.count_documents(q)
    docs = await db.settlement.find(q, {"_id": 0}).sort("uploaded_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"total": total, "items": docs}
