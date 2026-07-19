export default function StatChip({ label, value, sub, tone = "neutral", testId }) {
  const toneClass = {
    neutral: "border-border",
    positive: "border-emerald-800 text-emerald-400",
    negative: "border-red-800 text-red-400",
    warning: "border-amber-800 text-amber-400",
    critical: "border-red-800 text-red-400 bg-red-950/20",
  }[tone];
  return (
    <div className={`border ${toneClass} bg-card p-4`} data-testid={testId}>
      <div className="overline">{label}</div>
      <div className="kpi-value mt-1">{value}</div>
      {sub ? <div className="text-xs text-muted-foreground mt-1 mono">{sub}</div> : null}
    </div>
  );
}
