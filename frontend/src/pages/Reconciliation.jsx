import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { fmtCurrency, fmtInt } from "@/lib/format";
import { toast } from "sonner";
import { GitCompareArrows, RefreshCw, Play } from "lucide-react";
import { Link } from "react-router-dom";

export default function Reconciliation() {
  const [runs, setRuns] = useState([]);
  const [running, setRunning] = useState(false);

  const load = async () => {
    const { data } = await api.get("/reconciliation/runs");
    setRuns(data);
  };
  useEffect(() => { load(); }, []);

  const runNow = async () => {
    setRunning(true);
    try {
      const { data } = await api.post("/reconciliation/run", {});
      toast.success(`Recon complete: ${data.matched} matched, ${data.variance} variance, ${data.unmatched} unmatched`);
      await load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="p-6 space-y-4" data-testid="recon-page">
      <div className="flex items-end justify-between">
        <div>
          <div className="overline">Reconciliation Engine</div>
          <h1 className="text-2xl font-semibold tracking-tight mt-1">Settlement vs Expected — Runs</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Match settlement rows to sales, compare component by component, and surface discrepancies by severity.
          </p>
        </div>
        <button
          data-testid="btn-run-recon"
          onClick={runNow}
          disabled={running}
          className="border border-primary bg-primary text-primary-foreground hover:opacity-90 px-4 py-2 text-xs mono inline-flex items-center gap-2 disabled:opacity-50"
        >
          <Play size={12} /> {running ? "Reconciling…" : "Run Reconciliation"}
        </button>
      </div>

      <div className="border border-border bg-card">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="overline flex items-center gap-2"><GitCompareArrows size={12} /> Reconciliation Runs</div>
          <button onClick={load} className="border border-border hover:bg-secondary px-2 py-1 text-xs mono inline-flex items-center gap-1"><RefreshCw size={10} /> Refresh</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="grid-header">
              <tr>
                <th className="text-left grid-cell">Run</th>
                <th className="text-left grid-cell">Created</th>
                <th className="text-right grid-cell">Settled Rows</th>
                <th className="text-right grid-cell">Matched</th>
                <th className="text-right grid-cell">Variance</th>
                <th className="text-right grid-cell">Unmatched</th>
                <th className="text-right grid-cell">Recoverable</th>
                <th className="text-right grid-cell">Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr><td colSpan={8} className="grid-cell text-center text-muted-foreground py-10">No reconciliation runs. Upload a settlement file and click &quot;Run Reconciliation&quot;.</td></tr>
              ) : runs.map((r) => (
                <tr key={r.id} className="grid-row" data-testid={`recon-run-${r.id}`}>
                  <td className="grid-cell text-xs">{r.id.slice(0, 8)}</td>
                  <td className="grid-cell text-xs text-muted-foreground">{new Date(r.created_at).toLocaleString()}</td>
                  <td className="grid-cell text-right">{fmtInt(r.total_settled_rows)}</td>
                  <td className="grid-cell text-right fin-pos">{fmtInt(r.matched)}</td>
                  <td className="grid-cell text-right fin-neg">{fmtInt(r.variance)}</td>
                  <td className="grid-cell text-right sev-high">{fmtInt(r.unmatched)}</td>
                  <td className="grid-cell text-right fin-pos font-semibold">{fmtCurrency(r.total_recoverable)}</td>
                  <td className="grid-cell text-right">
                    <Link
                      to={`/discrepancies?run=${r.id}`}
                      data-testid={`view-disc-${r.id}`}
                      className="border border-border hover:bg-secondary px-2 py-1 text-xs mono inline-block"
                    >View Discrepancies</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
