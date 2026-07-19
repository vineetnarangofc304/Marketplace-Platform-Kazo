import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { fmtCurrency, fmtInt, fmtPct } from "@/lib/format";
import { toast } from "sonner";
import { Download, RefreshCw, Calendar } from "lucide-react";
import StatChip from "@/components/StatChip";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell } from "recharts";

const COLORS = ["#38BDF8", "#10B981", "#F59E0B", "#EF4444", "#A78BFA", "#EC4899", "#818CF8"];

export default function Reports() {
  const [months, setMonths] = useState([]);
  const [month, setMonth] = useState("");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    api.get("/reports/months").then((r) => {
      setMonths(r.data);
      if (r.data.length && !month) setMonth(r.data[r.data.length - 1]);
    });
  }, []);

  useEffect(() => {
    if (!month) return;
    setLoading(true);
    api.get("/reports/monthly", { params: { month } })
      .then((r) => setReport(r.data))
      .catch((e) => toast.error(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false));
  }, [month]);

  const download = async () => {
    if (!month) return;
    setDownloading(true);
    try {
      const backendUrl = process.env.REACT_APP_BACKEND_URL;
      const res = await api.get("/reports/monthly/export", {
        params: { month }, responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `KAZO_Myntra_Report_${month}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Downloaded report for ${month}`);
    } catch (e) {
      toast.error("Download failed");
    } finally {
      setDownloading(false);
    }
  };

  const kpi = report?.kpi || {};
  const marginPct = useMemo(() => {
    const nsv = kpi.total_nsv || kpi.sales_nsv || 0;
    const settlement = kpi.expected_settlement || 0;
    return nsv ? settlement / nsv : 0;
  }, [kpi]);

  return (
    <div className="p-6 space-y-6" data-testid="reports-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="overline">Monthly Report</div>
          <h1 className="text-2xl font-semibold tracking-tight mt-1">
            Marketplace Finance — {month || "Select month"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Executive report for the selected reporting period. Download as Excel with full order detail, discrepancies, and unmapped-orders sheets.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Calendar size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <select
              data-testid="report-month-select"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className="bg-secondary border border-border pl-7 pr-3 py-2 text-xs mono outline-none focus:border-foreground/50 min-w-[140px]"
            >
              <option value="">Select month</option>
              {months.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <button
            data-testid="btn-refresh-report"
            onClick={() => month && setMonth(month)}
            disabled={loading}
            className="border border-border hover:bg-secondary px-3 py-2 text-xs mono inline-flex items-center gap-1"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
          <button
            data-testid="btn-download-report"
            onClick={download}
            disabled={!month || downloading}
            className="bg-primary text-primary-foreground hover:opacity-90 px-4 py-2 text-xs mono inline-flex items-center gap-2 disabled:opacity-50"
          >
            <Download size={12} /> {downloading ? "Preparing…" : "Download Excel"}
          </button>
        </div>
      </div>

      {!month ? (
        <div className="border border-border bg-card p-12 text-center text-muted-foreground text-sm">
          Upload sales data and select a reporting month above.
        </div>
      ) : loading ? (
        <div className="border border-border bg-card p-12 text-center text-muted-foreground mono text-xs uppercase tracking-widest">Loading report…</div>
      ) : report ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatChip
              testId="kpi-nsv"
              label="Total NSV"
              value={fmtCurrency(kpi.total_nsv || kpi.sales_nsv)}
              sub={`${fmtInt(kpi.total_orders || kpi.sales_rows)} orders`}
            />
            <StatChip
              testId="kpi-commission"
              label="Expected Commission"
              value={fmtCurrency(kpi.expected_commission)}
              sub={`Incl 18% GST`}
              tone="negative"
            />
            <StatChip
              testId="kpi-deductions"
              label="Total Deductions"
              value={fmtCurrency(kpi.expected_deductions)}
              sub="Commission + Fixed + GT + Return + TCS/TDS"
              tone="negative"
            />
            <StatChip
              testId="kpi-settlement"
              label="Expected Settlement"
              value={fmtCurrency(kpi.expected_settlement)}
              sub={`Margin: ${fmtPct(marginPct, 1)}`}
              tone="positive"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <div className="lg:col-span-2 border border-border bg-card p-5">
              <div className="overline">Top Sub-Categories — NSV vs Commission</div>
              <div className="h-72 mt-4">
                <ResponsiveContainer>
                  <BarChart data={report.by_sub_category?.slice(0, 10) || []}>
                    <CartesianGrid strokeDasharray="0" stroke="#1a1a1a" />
                    <XAxis dataKey="sub_category" stroke="#9CA3AF" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                    <YAxis stroke="#9CA3AF" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                    <Tooltip contentStyle={{ background: "#0a0a0a", border: "1px solid #2a2a2a", fontFamily: "JetBrains Mono", fontSize: 11 }} />
                    <Bar dataKey="nsv" fill="#38BDF8" name="NSV" />
                    <Bar dataKey="commission" fill="#EF4444" name="Commission" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="border border-border bg-card p-5">
              <div className="overline">Reconciliation — Discrepancy Split</div>
              <div className="h-48 mt-4">
                {report.reconciliation?.by_severity?.length ? (
                  <ResponsiveContainer>
                    <PieChart>
                      <Pie data={report.reconciliation.by_severity} dataKey="count" nameKey="severity" innerRadius={40} outerRadius={70}>
                        {report.reconciliation.by_severity.map((_, idx) => <Cell key={idx} fill={COLORS[idx % COLORS.length]} />)}
                      </Pie>
                      <Tooltip contentStyle={{ background: "#0a0a0a", border: "1px solid #2a2a2a", fontFamily: "JetBrains Mono", fontSize: 11 }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-xs mono text-muted-foreground">
                    No settlement uploaded for {month}
                  </div>
                )}
              </div>
              <div className="mt-3 space-y-1">
                <div className="flex justify-between text-xs mono">
                  <span className="text-muted-foreground">Total Discrepancies</span>
                  <span>{fmtInt(report.reconciliation?.total_discrepancies || 0)}</span>
                </div>
                <div className="flex justify-between text-xs mono">
                  <span className="text-muted-foreground">Total Recoverable</span>
                  <span className="fin-pos">{fmtCurrency(report.reconciliation?.total_recoverable || 0)}</span>
                </div>
                {kpi.unmapped_orders > 0 && (
                  <div className="flex justify-between text-xs mono">
                    <span className="text-muted-foreground">Unmapped Orders</span>
                    <span className="sev-high">{fmtInt(kpi.unmapped_orders)}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="border border-border bg-card">
            <div className="p-4 border-b border-border">
              <div className="overline">Sub-Category Breakdown</div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="grid-header">
                  <tr>
                    <th className="grid-cell text-left">Sub Category</th>
                    <th className="grid-cell text-right">Orders</th>
                    <th className="grid-cell text-right">NSV</th>
                    <th className="grid-cell text-right">Commission (incl GST)</th>
                    <th className="grid-cell text-right">Fixed Fee</th>
                    <th className="grid-cell text-right">GT Charge</th>
                    <th className="grid-cell text-right">Expected Settlement</th>
                    <th className="grid-cell text-right">Margin %</th>
                  </tr>
                </thead>
                <tbody>
                  {(report.by_sub_category || []).map((r) => {
                    const margin = r.nsv ? r.expected_settlement / r.nsv : 0;
                    return (
                      <tr key={r.sub_category} className="grid-row" data-testid={`report-sub-${r.sub_category}`}>
                        <td className="grid-cell">{r.sub_category}</td>
                        <td className="grid-cell text-right">{fmtInt(r.orders)}</td>
                        <td className="grid-cell text-right">{fmtCurrency(r.nsv)}</td>
                        <td className="grid-cell text-right fin-neg">{fmtCurrency(r.commission)}</td>
                        <td className="grid-cell text-right fin-neg">{fmtCurrency(r.fixed_fee)}</td>
                        <td className="grid-cell text-right fin-neg">{fmtCurrency(r.gt_charge)}</td>
                        <td className="grid-cell text-right fin-pos">{fmtCurrency(r.expected_settlement)}</td>
                        <td className={`grid-cell text-right ${margin < 0.5 ? "sev-high" : "fin-pos"}`}>{fmtPct(margin, 1)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
