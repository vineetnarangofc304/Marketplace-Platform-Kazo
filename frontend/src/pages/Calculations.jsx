import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { fmtCurrency, fmtInt } from "@/lib/format";
import { toast } from "sonner";
import { PlayCircle, RefreshCw } from "lucide-react";

export default function Calculations() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [running, setRunning] = useState(false);
  const [search, setSearch] = useState("");

  const load = async () => {
    const { data } = await api.get("/calculations", { params: { search: search || undefined, limit: 300 } });
    setItems(data.items);
    setTotal(data.total);
  };
  useEffect(() => { load(); }, []);

  const runAll = async () => {
    setRunning(true);
    try {
      const { data } = await api.post("/calculations/run", { recalculate: true });
      toast.success(`Processed ${data.processed} of ${data.total_sales}`);
      await load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="p-6 space-y-4" data-testid="calculations-page">
      <div className="flex items-end justify-between">
        <div>
          <div className="overline">Calculation Engine</div>
          <h1 className="text-2xl font-semibold tracking-tight mt-1">Expected Commission & Deductions</h1>
          <p className="text-sm text-muted-foreground mt-1 mono">{fmtInt(total)} calculated · component-level breakdown per order-item</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            data-testid="calc-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            placeholder="Search Order ID / SKU"
            className="bg-secondary border border-border px-3 py-1.5 text-xs mono w-64 outline-none focus:border-foreground/50"
          />
          <button onClick={load} data-testid="btn-calc-refresh" className="border border-border hover:bg-secondary px-3 py-1.5 text-xs mono inline-flex items-center gap-1">
            <RefreshCw size={12} /> Refresh
          </button>
          <button
            data-testid="btn-run-all-calcs"
            onClick={runAll}
            disabled={running}
            className="border border-primary bg-primary text-primary-foreground hover:opacity-90 px-3 py-1.5 text-xs mono inline-flex items-center gap-1 disabled:opacity-50"
          >
            <PlayCircle size={12} /> {running ? "Running…" : "Run All Calculations"}
          </button>
        </div>
      </div>

      <div className="border border-border bg-card overflow-auto max-h-[calc(100vh-240px)]">
        <table className="w-full text-xs">
          <thead className="grid-header sticky top-0 z-10">
            <tr>
              <th className="text-left grid-cell frozen-col">Order ID</th>
              <th className="text-left grid-cell">SKU</th>
              <th className="text-left grid-cell">Sub-Cat</th>
              <th className="text-right grid-cell">NSV</th>
              <th className="text-right grid-cell">Comm (incl GST)</th>
              <th className="text-right grid-cell">Fixed Fee</th>
              <th className="text-right grid-cell">GT</th>
              <th className="text-right grid-cell">Return</th>
              <th className="text-right grid-cell">TCS+TDS</th>
              <th className="text-right grid-cell">Deductions</th>
              <th className="text-right grid-cell">Expected Payout</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr><td colSpan={11} className="grid-cell text-center text-muted-foreground py-10">No calculations. Run engine from Uploads or click &quot;Run All Calculations&quot;.</td></tr>
            ) : items.map((c) => (
              <tr key={c.id} className="grid-row" data-testid={`calc-row-${c.id}`}>
                <td className="grid-cell frozen-col">{(c.online_order_id || "").slice(0, 12)}…</td>
                <td className="grid-cell">{c.sku}</td>
                <td className="grid-cell text-muted-foreground">{c.breakdown?.sub_category}</td>
                <td className="grid-cell text-right">{fmtCurrency(c.breakdown?.nsv_val)}</td>
                <td className="grid-cell text-right fin-neg">{fmtCurrency(c.commission_incl_gst)}</td>
                <td className="grid-cell text-right fin-neg">{fmtCurrency(c.fixed_fee_incl_gst)}</td>
                <td className="grid-cell text-right fin-neg">{fmtCurrency(c.gt_charge)}</td>
                <td className="grid-cell text-right fin-neg">{fmtCurrency(c.return_fee)}</td>
                <td className="grid-cell text-right fin-neg">{fmtCurrency((c.tcs || 0) + (c.tds || 0))}</td>
                <td className="grid-cell text-right fin-neg font-semibold">{fmtCurrency(c.total_deductions)}</td>
                <td className="grid-cell text-right fin-pos font-semibold">{fmtCurrency(c.expected_settlement)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
