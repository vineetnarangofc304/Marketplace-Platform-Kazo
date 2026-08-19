import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import { fmtCurrency, fmtInt, signClass, settlementClass } from "@/lib/format";
import { Search, X, Filter, Download } from "lucide-react";
import PeriodSelector from "@/components/PeriodSelector";
import { SortableTh, nextDir } from "@/components/SortableTable";
import { usePortal } from "@/context/PortalContext";
import { toast } from "sonner";

export default function SalesLedger() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { portalParam } = usePortal();
  const [period, setPeriod] = useState({
    period_type: searchParams.get("period_type") || "month",
    period_value: searchParams.get("period_value") || "",
  });
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState({ net_orders: 0, net_qty: 0, sales_rows: 0, return_rows: 0 });
  const [calcMap, setCalcMap] = useState({});  // sales_id → calc breakdown
  const [search, setSearch] = useState("");
  const [exporting, setExporting] = useState(false);
  const [filters, setFilters] = useState({
    sub_category: searchParams.get("sub_category") || "",
    zone: searchParams.get("zone") || "",
    order_status: "",
    txn_type: "",
  });
  const [sort, setSort] = useState({ by: "order_date", dir: "desc" });
  const [drawer, setDrawer] = useState(null);
  const [calc, setCalc] = useState(null);

  const buildParams = (extra = {}) => ({
    period_type: period.period_type, period_value: period.period_value || undefined,
    portal: portalParam,
    search: search || undefined,
    sub_category: filters.sub_category || undefined,
    zone: filters.zone || undefined,
    order_status: filters.order_status || undefined,
    txn_type: filters.txn_type || undefined,
    ...extra,
  });

  const load = async () => {
    const params = buildParams({ sort_by: sort.by, sort_dir: sort.dir, limit: 500 });
    const [salesRes, summaryRes] = await Promise.all([
      api.get("/sales", { params }),
      api.get("/sales/summary", { params: buildParams() }),
    ]);
    setItems(salesRes.data.items);
    setTotal(salesRes.data.total);
    setSummary(summaryRes.data);
    // Fetch calcs for the visible rows (best-effort) so we can show Level / Price Range on the grid
    const ids = salesRes.data.items.map((r) => r.id);
    if (ids.length) {
      try {
        const calcRes = await api.get("/calculations", { params: { ...buildParams(), limit: 500 } });
        const map = {};
        for (const c of calcRes.data.items) { map[c.sales_id] = c; }
        setCalcMap(map);
      } catch { /* silent */ }
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [period.period_type, period.period_value, portalParam, filters.sub_category, filters.zone, filters.order_status, filters.txn_type, sort.by, sort.dir]);

  useEffect(() => {
    const t = setTimeout(() => { load(); }, 400);
    return () => clearTimeout(t);
    /* eslint-disable-next-line */
  }, [search]);

  const onSort = (key) => setSort((s) => nextDir(s.by, s.dir, key));

  const openDrawer = async (row) => {
    setDrawer(row);
    setCalc(null);
    try {
      const { data } = await api.get(`/calculations/by-sale/${row.id}`);
      setCalc(data.calculation);
    } catch (e) {
      setCalc({ error: "No calculation found — run calculations first." });
    }
  };

  const exportExcel = async () => {
    setExporting(true);
    try {
      const res = await api.get("/sales/export", { params: buildParams(), responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `fundle-sales-ledger-${period.period_value || "all"}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Excel downloaded");
    } catch (e) {
      toast.error("Export failed — " + (e.response?.data?.detail || e.message));
    } finally { setExporting(false); }
  };

  const activeFilterCount = Object.values(filters).filter(Boolean).length + (search ? 1 : 0);
  const clearFilters = () => { setFilters({ sub_category: "", zone: "", order_status: "", txn_type: "" }); setSearch(""); };

  return (
    <div className="p-6 space-y-4" data-testid="sales-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="overline">Canonical Sales Ledger</div>
          <h1 className="text-2xl font-semibold tracking-tight mt-1 text-slate-900">Order Items</h1>
          <p className="text-sm text-slate-500 mt-1 mono" data-testid="sales-summary">
            <span className="font-semibold text-slate-900">{fmtInt(summary.net_orders || 0)}</span> Order Qty (net)
            {" · "}
            <span>{fmtInt(summary.sales_rows || 0)} Sales</span>
            {" − "}
            <span>{fmtInt(summary.return_rows || 0)} Returns</span>
            {" · "}
            <span className="text-slate-400">{fmtInt(total)} rows</span>
          </p>
        </div>
        <div className="flex items-end gap-2 flex-wrap">
          <PeriodSelector value={period} onChange={setPeriod} testIdPrefix="sales-period" />
          <button
            data-testid="btn-export-sales"
            onClick={exportExcel}
            disabled={exporting || total === 0}
            className="btn"
            title="Download the filtered Sales Ledger as Excel with all client-requested columns (Brand, Level, Price Ranges, etc.)"
          >
            <Download size={12} /> {exporting ? "Exporting…" : "Export Excel"}
          </button>
        </div>
      </div>

      <div className="border border-border bg-white p-3 rounded-sm flex items-center gap-2 flex-wrap">
        <div className="inline-flex items-center gap-1 text-xs mono text-slate-500 pr-2 border-r border-border">
          <Filter size={12} /> Filters
          {activeFilterCount > 0 && <span className="chip chip-neutral text-[9px] py-0">{activeFilterCount}</span>}
        </div>
        <div className="relative">
          <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
          <input data-testid="sales-search" value={search} onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            placeholder="Order ID / SKU / Invoice" className="input pl-7 w-52" />
        </div>
        <input data-testid="filter-subcat" value={filters.sub_category} onChange={(e) => setFilters({ ...filters, sub_category: e.target.value })} placeholder="Sub-Category" className="input w-40" />
        <select data-testid="filter-zone" value={filters.zone} onChange={(e) => setFilters({ ...filters, zone: e.target.value })} className="input">
          <option value="">All Zones</option>
          <option value="Local">Local</option>
          <option value="Zonal">Zonal</option>
          <option value="National">National</option>
          <option value="-">— (unset)</option>
        </select>
        <select data-testid="filter-txn" value={filters.txn_type} onChange={(e) => setFilters({ ...filters, txn_type: e.target.value })} className="input">
          <option value="">All Txn Types</option>
          <option value="Sales">Sales</option>
          <option value="Return">Return</option>
        </select>
        <input data-testid="filter-status" value={filters.order_status} onChange={(e) => setFilters({ ...filters, order_status: e.target.value })} placeholder="Order Status" className="input w-32" />
        {activeFilterCount > 0 && <button onClick={clearFilters} className="btn text-xs"><X size={10} /> Clear</button>}
      </div>

      <div className="border border-border bg-white overflow-auto max-h-[calc(100vh-320px)] rounded-sm">
        <table className="w-full text-xs">
          <thead className="grid-header sticky top-0 z-10">
            <tr>
              <SortableTh label="Order ID" sortKey="order_id" sort={sort} onSort={onSort} className="frozen-col" />
              <th className="grid-cell text-left">Brand</th>
              <th className="grid-cell text-left">Sale Type</th>
              <th className="grid-cell text-left">Status</th>
              <th className="grid-cell text-left">Posting Date</th>
              <SortableTh label="Item No" sortKey="sku" sort={sort} onSort={onSort} />
              <th className="grid-cell text-left">Location</th>
              <th className="grid-cell text-left">Main Ctg</th>
              <SortableTh label="Sub-Cat" sortKey="sub_category" sort={sort} onSort={onSort} />
              <th className="grid-cell text-left">Level</th>
              <SortableTh label="Zone" sortKey="zone" sort={sort} onSort={onSort} />
              <SortableTh label="Month" sortKey="month" sort={sort} onSort={onSort} />
              <SortableTh label="Qty" sortKey="qty" sort={sort} onSort={onSort} align="right" />
              <SortableTh label="MRP" sortKey="mrp" sort={sort} onSort={onSort} align="right" />
              <SortableTh label="NSV" sortKey="nsv" sort={sort} onSort={onSort} align="right" />
              <th className="grid-cell text-right">Commission</th>
              <th className="grid-cell text-right">GT</th>
              <th className="grid-cell text-left">Price Range (NSV)</th>
              <th className="grid-cell text-left">Price Range (NSV after GT)</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr><td colSpan={19} className="grid-cell text-center text-slate-400 py-10">No sales rows for this filter. Upload sales data or clear filters.</td></tr>
            ) : items.map((r) => {
              const c = calcMap[r.id] || {};
              const bd = c.breakdown || {};
              const crule = bd.commission_rule || {};
              const gtCell = bd.gt_charge_cell || {};
              return (
                <tr key={r.id} onClick={() => openDrawer(r)} className="grid-row drill" data-testid={`sales-row-${r.id}`}>
                  <td className="grid-cell frozen-col drill-link">{(r.online_order_id || "").slice(0, 14)}…</td>
                  <td className="grid-cell text-slate-500">{r.brand || "—"}</td>
                  <td className="grid-cell text-slate-500">{r.txn_type || "—"}</td>
                  <td className="grid-cell text-slate-500">{r.order_status}</td>
                  <td className="grid-cell text-slate-500">{(r.posting_date || "").slice(0, 10) || "—"}</td>
                  <td className="grid-cell mono">{r.sku}</td>
                  <td className="grid-cell text-slate-500">{r.posting_location_code || "—"}</td>
                  <td className="grid-cell text-slate-500">{r.main_category || "—"}</td>
                  <td className="grid-cell">{r.sub_category}</td>
                  <td className="grid-cell text-slate-500 mono text-[10px]">{bd.level || "—"}</td>
                  <td className="grid-cell text-slate-500">{r.zone}</td>
                  <td className="grid-cell text-slate-500">{r.report_month}</td>
                  <td className="grid-cell text-right">{fmtInt(r.qty)}</td>
                  <td className="grid-cell text-right">{fmtCurrency(r.mrp)}</td>
                  <td className="grid-cell text-right">{fmtCurrency(r.nsv_val)}</td>
                  <td className={`grid-cell text-right ${signClass(c.commission_incl_gst)}`}>{c.commission_incl_gst != null ? fmtCurrency(c.commission_incl_gst) : "—"}</td>
                  <td className={`grid-cell text-right ${signClass(c.gt_charge)}`}>{c.gt_charge != null ? fmtCurrency(c.gt_charge) : "—"}</td>
                  <td className="grid-cell mono text-[10px] text-slate-500">{crule.price_range || "—"}</td>
                  <td className="grid-cell mono text-[10px] text-slate-500">{gtCell.price_range || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {drawer && (
        <div className="fixed inset-0 z-40" data-testid="sales-drawer">
          <div className="absolute inset-0 bg-black/30" onClick={() => setDrawer(null)} />
          <div className="absolute right-0 top-0 h-full w-full max-w-2xl bg-white border-l border-border overflow-auto">
            <div className="p-5 border-b border-border flex items-start justify-between">
              <div>
                <div className="overline">Order Detail</div>
                <div className="text-lg mt-1 mono text-slate-900">{drawer.online_order_id}</div>
                <div className="text-xs text-slate-500 mono">{drawer.sku}</div>
              </div>
              <button onClick={() => setDrawer(null)} className="btn" data-testid="close-drawer"><X size={14} /></button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <div className="overline mb-2">Sales Data</div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs mono border border-border p-3 rounded-sm">
                  {[["Category", drawer.category], ["Sub Category", drawer.sub_category], ["Zone", drawer.zone], ["Status", drawer.order_status],
                    ["Qty", drawer.qty], ["MRP", fmtCurrency(drawer.mrp)], ["Discount", fmtCurrency(drawer.customer_discount)],
                    ["NSV", fmtCurrency(drawer.nsv_val)], ["Month", drawer.report_month], ["Txn Type", drawer.txn_type]].map(([k, v]) => (
                    <div key={k} className="flex justify-between border-b border-border/50 py-1">
                      <span className="text-slate-500">{k}</span><span>{v ?? "—"}</span>
                    </div>
                  ))}
                </div>
              </div>
              {calc?.error ? (
                <div className="border border-amber-300 bg-amber-50 text-amber-700 p-3 text-xs mono rounded-sm">{calc.error}</div>
              ) : calc ? (
                <div>
                  <div className="overline mb-2">Expected Calculation</div>
                  <table className="w-full text-xs mono border border-border">
                    <tbody>
                      {[["Commission", calc.commission_incl_gst],
                        ["Fixed Fee", calc.fixed_fee_incl_gst],
                        ["GT Charge", calc.gt_charge],
                        ["Return Fee (Level/Zone)", calc.return_fee],
                        ["Total Deductions", calc.total_deductions, "sign", true],
                        ["Expected Settlement", calc.expected_settlement, "settlement", true]].map(([k, v, kind, bold]) => {
                        const cls = kind === "settlement" ? settlementClass(v) : signClass(v);
                        return (
                        <tr key={k}>
                          <td className={`px-3 py-2 border-b border-border/40 ${bold ? "font-semibold" : "text-slate-500"}`}>{k}</td>
                          <td className={`px-3 py-2 border-b border-border/40 text-right ${bold ? "font-semibold" : ""} ${cls}`}>{fmtCurrency(v)}</td>
                        </tr>
                      );})}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-xs text-slate-400 mono">Loading calculation…</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
