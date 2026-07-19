import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import { fmtCurrency, fmtInt } from "@/lib/format";
import { AlertTriangle, X, Search } from "lucide-react";

export default function Discrepancies() {
  const [params, setParams] = useSearchParams();
  const runId = params.get("run") || "";
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [drawer, setDrawer] = useState(null);

  const load = async () => {
    const { data } = await api.get("/reconciliation/discrepancies", {
      params: {
        recon_run_id: runId || undefined,
        severity: severity || undefined,
        match_status: status || undefined,
        search: search || undefined,
        limit: 300,
      },
    });
    setItems(data.items);
    setTotal(data.total);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [runId, severity, status]);

  return (
    <div className="p-6 space-y-4" data-testid="discrepancies-page">
      <div className="flex items-end justify-between">
        <div>
          <div className="overline">Discrepancy Workbench</div>
          <h1 className="text-2xl font-semibold tracking-tight mt-1 flex items-center gap-2">
            <AlertTriangle size={18} className="text-amber-500" /> {fmtInt(total)} Discrepancies
          </h1>
          <p className="text-sm text-muted-foreground mt-1 mono">
            {runId ? `Run: ${runId.slice(0, 8)}` : "All runs"} · sorted by severity + recoverable
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              data-testid="disc-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load()}
              placeholder="Order ID / SKU"
              className="bg-secondary border border-border pl-7 pr-3 py-1.5 text-xs mono w-56 outline-none"
            />
          </div>
          <select data-testid="filter-severity" value={severity} onChange={(e) => setSeverity(e.target.value)} className="bg-secondary border border-border px-2 py-1.5 text-xs mono">
            <option value="">All severity</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select data-testid="filter-status" value={status} onChange={(e) => setStatus(e.target.value)} className="bg-secondary border border-border px-2 py-1.5 text-xs mono">
            <option value="">All status</option>
            <option value="variance">Variance</option>
            <option value="unmatched">Unmatched</option>
          </select>
          {runId && (
            <button onClick={() => setParams({})} className="border border-border hover:bg-secondary px-2 py-1.5 text-xs mono">Clear run</button>
          )}
        </div>
      </div>

      <div className="border border-border bg-card overflow-auto max-h-[calc(100vh-240px)]">
        <table className="w-full text-xs">
          <thead className="grid-header sticky top-0 z-10">
            <tr>
              <th className="text-left grid-cell">Severity</th>
              <th className="text-left grid-cell">Order ID</th>
              <th className="text-left grid-cell">SKU</th>
              <th className="text-left grid-cell">Status</th>
              <th className="text-left grid-cell">Reason</th>
              <th className="text-right grid-cell">Settle Variance</th>
              <th className="text-right grid-cell">Recoverable</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr><td colSpan={7} className="grid-cell text-center text-muted-foreground py-10">No discrepancies. Run reconciliation from the Reconciliation page.</td></tr>
            ) : items.map((d) => (
              <tr
                key={d.id}
                onClick={() => setDrawer(d)}
                className="grid-row cursor-pointer"
                data-testid={`disc-row-${d.id}`}
                style={{ borderLeft: d.severity === "critical" ? "3px solid #DC2626" : d.severity === "high" ? "3px solid #F59E0B" : d.severity === "medium" ? "3px solid #FBBF24" : "3px solid #38BDF8" }}
              >
                <td className="grid-cell"><span className={`chip chip-${d.severity}`}>{d.severity}</span></td>
                <td className="grid-cell">{(d.online_order_id || "").slice(0, 14)}…</td>
                <td className="grid-cell">{d.sku}</td>
                <td className="grid-cell">
                  <span className={`chip ${d.match_status === "unmatched" ? "chip-unmatched" : "chip-variance"}`}>{d.match_status}</span>
                </td>
                <td className="grid-cell text-muted-foreground truncate max-w-[380px]">{d.reason}</td>
                <td className={`grid-cell text-right ${d.settle_variance > 0 ? "fin-pos" : "fin-neg"}`}>
                  {d.settle_variance !== undefined ? fmtCurrency(d.settle_variance) : "—"}
                </td>
                <td className="grid-cell text-right fin-pos font-semibold">{fmtCurrency(d.recoverable)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {drawer ? <DiscDrawer disc={drawer} onClose={() => setDrawer(null)} /> : null}
    </div>
  );
}

function DiscDrawer({ disc, onClose }) {
  return (
    <div className="fixed inset-0 z-40" data-testid="disc-drawer">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="absolute right-0 top-0 h-full w-full max-w-3xl bg-background border-l border-border overflow-auto">
        <div className="p-5 border-b border-border flex items-start justify-between">
          <div>
            <div className="overline">Discrepancy Detail</div>
            <div className="text-lg mt-1 mono">{disc.online_order_id}</div>
            <div className="text-xs text-muted-foreground mono">{disc.sku}</div>
            <div className="mt-2 flex gap-2">
              <span className={`chip chip-${disc.severity}`}>{disc.severity}</span>
              <span className={`chip ${disc.match_status === "unmatched" ? "chip-unmatched" : "chip-variance"}`}>{disc.match_status}</span>
            </div>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-secondary" data-testid="close-disc-drawer"><X size={16} /></button>
        </div>

        <div className="p-5 space-y-5">
          <div className="border border-border p-4">
            <div className="overline mb-2">Reason</div>
            <div className="text-sm">{disc.reason}</div>
            <div className="mt-3 grid grid-cols-2 gap-3 text-xs mono">
              <div><div className="overline">Recoverable</div><div className="fin-pos text-base mt-1">{fmtCurrency(disc.recoverable)}</div></div>
              <div><div className="overline">Settle Variance</div><div className={`text-base mt-1 ${disc.settle_variance > 0 ? "fin-pos" : "fin-neg"}`}>{fmtCurrency(disc.settle_variance)}</div></div>
            </div>
          </div>

          <div>
            <div className="overline mb-2">Component-Level Compare</div>
            <table className="w-full text-xs mono border border-border">
              <thead className="grid-header">
                <tr>
                  <th className="text-left grid-cell">Component</th>
                  <th className="text-right grid-cell">Expected</th>
                  <th className="text-right grid-cell">Actual</th>
                  <th className="text-right grid-cell">Variance</th>
                  <th className="text-left grid-cell">Status</th>
                </tr>
              </thead>
              <tbody>
                {(disc.components || []).map((c) => (
                  <tr key={c.component} className="grid-row">
                    <td className="grid-cell">{c.component}</td>
                    <td className="grid-cell text-right">{fmtCurrency(c.expected)}</td>
                    <td className="grid-cell text-right">{fmtCurrency(c.actual)}</td>
                    <td className={`grid-cell text-right ${c.variance > 0 ? "fin-pos" : c.variance < 0 ? "fin-neg" : ""}`}>{fmtCurrency(c.variance)}</td>
                    <td className="grid-cell">
                      <span className={`chip ${c.status === "matched" ? "chip-matched" : c.status === "overcharged" ? "chip-variance" : "chip-unmatched"}`}>{c.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <div className="overline mb-2">Marketplace-Reported (Settled)</div>
            <pre className="text-[10px] mono bg-secondary p-3 border border-border overflow-auto">
{JSON.stringify(disc.settled, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
