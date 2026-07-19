import { useEffect, useState } from "react";
import api from "@/lib/api";
import { fmtCurrency, fmtInt } from "@/lib/format";
import { Search, X } from "lucide-react";

export default function SalesLedger() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [drawer, setDrawer] = useState(null);
  const [calc, setCalc] = useState(null);

  const load = async () => {
    const { data } = await api.get("/sales", { params: { search: search || undefined, limit: 300 } });
    setItems(data.items);
    setTotal(data.total);
  };

  useEffect(() => { load(); }, []);

  const openDrawer = async (row) => {
    setDrawer(row);
    setCalc(null);
    try {
      const { data } = await api.get(`/calculations/by-sale/${row.id}`);
      setCalc(data.calculation);
    } catch (e) {
      setCalc({ error: "No calculation. Run 'Run Calc' on this upload first." });
    }
  };

  return (
    <div className="p-6 space-y-4" data-testid="sales-page">
      <div className="flex items-end justify-between">
        <div>
          <div className="overline">Canonical Sales Ledger</div>
          <h1 className="text-2xl font-semibold tracking-tight mt-1">Order Items</h1>
          <p className="text-sm text-muted-foreground mt-1 mono">{fmtInt(total)} rows · click any row to view calculation breakdown</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              data-testid="sales-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load()}
              placeholder="Search Order ID / SKU / Invoice"
              className="bg-secondary border border-border pl-7 pr-3 py-1.5 text-xs mono w-72 outline-none focus:border-foreground/50"
            />
          </div>
          <button onClick={load} className="border border-border hover:bg-secondary px-3 py-1.5 text-xs mono">Search</button>
        </div>
      </div>

      <div className="border border-border bg-card overflow-auto max-h-[calc(100vh-260px)]">
        <table className="w-full text-xs">
          <thead className="grid-header sticky top-0 z-10">
            <tr>
              <th className="text-left grid-cell frozen-col">Order ID</th>
              <th className="text-left grid-cell">SKU</th>
              <th className="text-left grid-cell">Status</th>
              <th className="text-left grid-cell">Cat</th>
              <th className="text-left grid-cell">Sub-Cat</th>
              <th className="text-left grid-cell">Zone</th>
              <th className="text-right grid-cell">Qty</th>
              <th className="text-right grid-cell">MRP</th>
              <th className="text-right grid-cell">Disc</th>
              <th className="text-right grid-cell">NSV</th>
              <th className="text-right grid-cell">GT (Act)</th>
              <th className="text-right grid-cell">Comm (Act)</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr><td colSpan={12} className="grid-cell text-center text-muted-foreground py-10">No sales rows. Upload sales data to populate.</td></tr>
            ) : items.map((r) => (
              <tr key={r.id} onClick={() => openDrawer(r)} className="grid-row cursor-pointer" data-testid={`sales-row-${r.id}`}>
                <td className="grid-cell frozen-col text-foreground">{(r.online_order_id || "").slice(0, 16)}…</td>
                <td className="grid-cell">{r.sku}</td>
                <td className="grid-cell text-muted-foreground">{r.order_status}</td>
                <td className="grid-cell text-muted-foreground">{r.category}</td>
                <td className="grid-cell">{r.sub_category}</td>
                <td className="grid-cell text-muted-foreground">{r.zone}</td>
                <td className="grid-cell text-right">{fmtInt(r.qty)}</td>
                <td className="grid-cell text-right">{fmtCurrency(r.mrp)}</td>
                <td className="grid-cell text-right fin-neg">{fmtCurrency(r.customer_discount)}</td>
                <td className="grid-cell text-right">{fmtCurrency(r.nsv_val)}</td>
                <td className="grid-cell text-right text-muted-foreground">{fmtCurrency(r.actual_gt_amount)}</td>
                <td className="grid-cell text-right text-muted-foreground">{fmtCurrency(r.actual_commission_value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {drawer ? <CalcDrawer sale={drawer} calc={calc} onClose={() => setDrawer(null)} /> : null}
    </div>
  );
}

function CalcDrawer({ sale, calc, onClose }) {
  return (
    <div className="fixed inset-0 z-40" data-testid="calc-drawer">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="absolute right-0 top-0 h-full w-full max-w-2xl bg-background border-l border-border overflow-auto">
        <div className="p-5 border-b border-border flex items-start justify-between">
          <div>
            <div className="overline">Calculation Explainer</div>
            <div className="text-lg mt-1 mono">{sale.online_order_id}</div>
            <div className="text-xs text-muted-foreground mono">{sale.sku}</div>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-secondary" data-testid="close-drawer"><X size={16} /></button>
        </div>

        <div className="p-5 space-y-6">
          <section>
            <div className="overline mb-2">Source (Sales Row)</div>
            <div className="grid grid-cols-2 gap-2 text-xs mono">
              <KV label="Category" value={sale.category} />
              <KV label="Sub Category" value={sale.sub_category} />
              <KV label="Zone" value={sale.zone} />
              <KV label="Order Status" value={sale.order_status} />
              <KV label="Qty" value={fmtInt(sale.qty)} />
              <KV label="MRP" value={fmtCurrency(sale.mrp)} />
              <KV label="Customer Discount" value={fmtCurrency(sale.customer_discount)} tone="neg" />
              <KV label="NSV" value={fmtCurrency(sale.nsv_val)} />
            </div>
          </section>

          {calc?.error ? (
            <div className="border border-amber-900 bg-amber-950/30 text-amber-300 p-3 text-xs mono">
              {calc.error}
            </div>
          ) : calc ? (
            <>
              <section>
                <div className="overline mb-2">Matched Rules</div>
                <div className="grid grid-cols-1 gap-2 text-xs mono">
                  <KV label={`Commission @ ${((calc.breakdown?.commission_rule?.commission_pct || 0) * 100).toFixed(2)}%`} value={`${calc.breakdown?.commission_rule?.price_range || "—"} (${calc.breakdown?.commission_rule?.commission_model || "—"})`} />
                  <KV label="Fixed Fee Slab" value={`${calc.breakdown?.fixed_fee_slab?.label || "—"} → ₹${calc.breakdown?.fixed_fee_slab?.fixed_fee || 0}`} />
                  <KV label={`GT Level ${calc.breakdown?.level}`} value={`${calc.breakdown?.gt_charge_cell?.price_range || "—"} × ${calc.breakdown?.gt_charge_cell?.qty || 0} → ₹${calc.breakdown?.gt_charge_cell?.unit_charge || 0}/unit`} />
                  <KV label={`Return Fee Zone ${calc.breakdown?.zone}`} value={calc.breakdown?.return_fee_cell?.applied ? `Applied · ₹${calc.breakdown?.return_fee_cell?.fee}` : "Not applied"} />
                </div>
              </section>

              <section>
                <div className="overline mb-2">Expected Charges & Deductions</div>
                <table className="w-full text-xs mono border border-border">
                  <tbody>
                    <Row k="Commission (base)" v={fmtCurrency(calc.commission_base)} />
                    <Row k="Commission GST 18%" v={fmtCurrency(calc.commission_gst)} tone="neg" />
                    <Row k="Commission (incl GST)" v={fmtCurrency(calc.commission_incl_gst)} tone="neg" bold />
                    <Row k="Fixed Fee" v={fmtCurrency(calc.fixed_fee)} />
                    <Row k="Fixed Fee GST 18%" v={fmtCurrency(calc.fixed_fee_gst)} tone="neg" />
                    <Row k="Fixed Fee (incl GST)" v={fmtCurrency(calc.fixed_fee_incl_gst)} tone="neg" bold />
                    <Row k="GT Charge (incl GST)" v={fmtCurrency(calc.gt_charge)} tone="neg" />
                    <Row k="Return Fee" v={fmtCurrency(calc.return_fee)} tone="neg" />
                    <Row k="TCS 0.5%" v={fmtCurrency(calc.tcs)} tone="neg" />
                    <Row k="TDS 0.1%" v={fmtCurrency(calc.tds)} tone="neg" />
                    <Row k="Total Deductions" v={fmtCurrency(calc.total_deductions)} tone="neg" bold sep />
                    <Row k="Expected Settlement" v={fmtCurrency(calc.expected_settlement)} tone="pos" bold sep />
                  </tbody>
                </table>
              </section>
            </>
          ) : (
            <div className="text-xs mono text-muted-foreground">Loading calculation…</div>
          )}
        </div>
      </div>
    </div>
  );
}

function KV({ label, value, tone }) {
  return (
    <div className="flex justify-between gap-2 border-b border-border/50 py-1">
      <span className="text-muted-foreground">{label}</span>
      <span className={tone === "neg" ? "fin-neg" : tone === "pos" ? "fin-pos" : ""}>{value ?? "—"}</span>
    </div>
  );
}

function Row({ k, v, tone, bold, sep }) {
  return (
    <tr className={sep ? "border-t border-border" : ""}>
      <td className={`px-3 py-2 border-b border-border/40 ${bold ? "font-semibold" : "text-muted-foreground"}`}>{k}</td>
      <td className={`px-3 py-2 border-b border-border/40 text-right ${bold ? "font-semibold" : ""} ${tone === "neg" ? "fin-neg" : tone === "pos" ? "fin-pos" : ""}`}>{v}</td>
    </tr>
  );
}
