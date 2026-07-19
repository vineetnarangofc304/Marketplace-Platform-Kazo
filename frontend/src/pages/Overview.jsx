import { useEffect, useState } from "react";
import api from "@/lib/api";
import StatChip from "@/components/StatChip";
import { fmtCurrency, fmtInt, fmtPct } from "@/lib/format";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, CartesianGrid } from "recharts";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowUpRight, Calendar, TrendingDown } from "lucide-react";

const COLORS = ["#DC2626", "#F59E0B", "#FBBF24", "#38BDF8", "#10B981", "#A78BFA"];

export default function Overview() {
  const [months, setMonths] = useState([]);
  const [month, setMonth] = useState("");
  const [overview, setOverview] = useState(null);
  const [commSum, setCommSum] = useState(null);
  const [reconSum, setReconSum] = useState(null);

  useEffect(() => {
    api.get("/reports/months").then((r) => {
      setMonths(r.data);
      if (r.data.length && !month) setMonth(r.data[r.data.length - 1]);
    });
  }, []);

  useEffect(() => {
    const params = month ? { report_month: month } : {};
    api.get("/dashboard/overview", { params }).then((r) => setOverview(r.data));
    api.get("/dashboard/commission-summary", { params }).then((r) => setCommSum(r.data));
    api.get("/dashboard/reconciliation-summary", { params }).then((r) => setReconSum(r.data));
  }, [month]);

  const kpi = commSum?.kpi || {};
  const marginPct = kpi.total_nsv ? (kpi.expected_settlement || 0) / kpi.total_nsv : 0;

  return (
    <div className="p-6 space-y-6" data-testid="overview-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="overline">Executive Overview</div>
          <h1 className="text-2xl font-semibold tracking-tight mt-1">Marketplace Finance Command Center</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Deterministic commission math + settlement reconciliation for Myntra.
            {month ? <> · Filter: <span className="mono">{month}</span></> : null}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Calendar size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <select
              data-testid="overview-month-select"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className="bg-secondary border border-border pl-7 pr-3 py-2 text-xs mono outline-none focus:border-foreground/50 min-w-[160px]"
            >
              <option value="">All months</option>
              {months.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatChip testId="kpi-total-sales" label="Sales Rows" value={fmtInt(overview?.total_sales)} sub="Order-item rows" />
        <StatChip testId="kpi-total-calcs" label="Calculated" value={fmtInt(overview?.total_calculations)} sub={overview?.unmapped_calculations ? `${overview.unmapped_calculations} unmapped` : "All mapped"} tone={overview?.unmapped_calculations ? "warning" : "neutral"} />
        <StatChip testId="kpi-total-settle" label="Settlement Rows" value={fmtInt(overview?.total_settlement_rows)} sub="Marketplace-reported" />
        <StatChip
          testId="kpi-open-critical"
          label="Critical Discrepancies"
          value={fmtInt(overview?.open_critical)}
          sub="Requires review"
          tone={overview?.open_critical > 0 ? "critical" : "neutral"}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="lg:col-span-2 border border-border bg-card p-5">
          <div className="flex items-center justify-between">
            <div>
              <div className="overline">Commission Summary</div>
              <div className="text-sm mt-1">Expected Deductions vs Settlement · Margin {fmtPct(marginPct, 1)}</div>
            </div>
            <Link to="/reports" className="text-xs mono text-muted-foreground hover:text-foreground inline-flex items-center gap-1" data-testid="link-view-reports">
              View monthly report <ArrowUpRight size={12} />
            </Link>
          </div>
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div><div className="overline">Total NSV</div><div className="mono mt-1">{fmtCurrency(kpi.total_nsv)}</div></div>
            <div><div className="overline">Commission (incl GST)</div><div className="mono mt-1 fin-neg">{fmtCurrency(kpi.expected_commission)}</div></div>
            <div><div className="overline">GT + Fixed + Fees</div><div className="mono mt-1 fin-neg">{fmtCurrency((kpi.expected_gt_charge || 0) + (kpi.expected_fixed_fee || 0) + (kpi.expected_return_fee || 0))}</div></div>
            <div><div className="overline">Expected Settlement</div><div className="mono mt-1 fin-pos">{fmtCurrency(kpi.expected_settlement)}</div></div>
          </div>

          <div className="mt-6 h-64">
            <ResponsiveContainer>
              <BarChart data={commSum?.by_sub_category?.slice(0, 10) || []}>
                <CartesianGrid strokeDasharray="0" stroke="#1a1a1a" />
                <XAxis dataKey="sub_category" stroke="#9CA3AF" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                <YAxis stroke="#9CA3AF" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                <Tooltip contentStyle={{ background: "#0a0a0a", border: "1px solid #2a2a2a", fontFamily: "JetBrains Mono", fontSize: 11 }} />
                <Bar dataKey="commission" fill="#EF4444" name="Commission" />
                <Bar dataKey="gt_charge" fill="#F59E0B" name="GT Charge" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="border border-border bg-card p-5">
          <div className="overline">Reconciliation Status</div>
          <div className="text-sm mt-1">Discrepancies by severity</div>
          <div className="mt-4 h-48">
            {reconSum?.by_severity?.length ? (
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={reconSum.by_severity} dataKey="count" nameKey="severity" innerRadius={40} outerRadius={70}>
                    {reconSum.by_severity.map((_, idx) => <Cell key={idx} fill={COLORS[idx % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#0a0a0a", border: "1px solid #2a2a2a", fontFamily: "JetBrains Mono", fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs mono text-muted-foreground">
                No reconciliation runs yet
              </div>
            )}
          </div>
          <div className="mt-2 space-y-1">
            {(reconSum?.by_severity || []).map((s, i) => (
              <div key={s.severity} className="flex items-center justify-between text-xs mono">
                <span className="flex items-center gap-2">
                  <span className="w-2 h-2" style={{ background: COLORS[i % COLORS.length] }} />
                  {s.severity?.toUpperCase()}
                </span>
                <span>{s.count} · {fmtCurrency(s.recoverable)}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 border-t border-border pt-3">
            <div className="overline">Total Recoverable</div>
            <div className="mono text-lg fin-pos mt-1">{fmtCurrency(reconSum?.total_recoverable)}</div>
          </div>
        </div>
      </div>

      {reconSum?.top_discrepancies?.length ? (
        <div className="border border-border bg-card">
          <div className="p-4 border-b border-border flex items-center gap-2">
            <AlertTriangle size={14} className="text-amber-500" />
            <div className="overline">Top Recoverable — By Order</div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="grid-header">
                <tr>
                  <th className="text-left grid-cell">Order ID</th>
                  <th className="text-left grid-cell">SKU</th>
                  <th className="text-left grid-cell">Severity</th>
                  <th className="text-left grid-cell">Reason</th>
                  <th className="text-right grid-cell">Recoverable</th>
                </tr>
              </thead>
              <tbody>
                {reconSum.top_discrepancies.map((d) => (
                  <tr key={d.id} className="grid-row">
                    <td className="grid-cell">{d.online_order_id}</td>
                    <td className="grid-cell">{d.sku}</td>
                    <td className="grid-cell"><span className={`chip chip-${d.severity}`}>{d.severity}</span></td>
                    <td className="grid-cell text-muted-foreground text-xs">{d.reason}</td>
                    <td className="grid-cell text-right fin-pos">{fmtCurrency(d.recoverable)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {overview?.unmapped_calculations > 0 && (
        <div className="border border-amber-900 bg-amber-950/20 p-4 flex items-start gap-3" data-testid="unmapped-banner">
          <TrendingDown size={16} className="text-amber-500 mt-0.5" />
          <div className="text-sm">
            <div className="font-semibold text-amber-400">{fmtInt(overview.unmapped_calculations)} orders are unmapped</div>
            <div className="text-xs text-muted-foreground mt-1">Missing commission rule / GT charge / level mapping / zone. Open the <Link to="/calculations?unmapped=1" className="underline">Calculations page</Link> to review, or edit masters in <Link to="/masters" className="underline">Commission Masters</Link>.</div>
          </div>
        </div>
      )}
    </div>
  );
}
