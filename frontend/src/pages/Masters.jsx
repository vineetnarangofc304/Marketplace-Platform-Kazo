import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Save, Plus, Trash2, Download, Upload, FileSpreadsheet } from "lucide-react";
import { fmtPct } from "@/lib/format";

const TABS = [
  { id: "portals", label: "Portals" },
  { id: "commission", label: "Commission Rules" },
  { id: "fixed", label: "Fixed Fee" },
  { id: "gt", label: "GT (Logistics)" },
  { id: "return", label: "Return Fee" },
  { id: "level", label: "Sub-Cat Levels" },
  { id: "tolerance", label: "Tolerance" },
  { id: "settlement", label: "Settlement Config" },
  { id: "tax", label: "Tax Rates" },
];

export default function Masters() {
  const [tab, setTab] = useState("portals");
  const [importBusy, setImportBusy] = useState(false);

  const exportMasters = async () => {
    try {
      const res = await api.get("/masters/export", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `kazo-commission-masters-${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Masters exported");
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const importMasters = async (file, mode) => {
    if (!file) return;
    if (!window.confirm(`Import "${file.name}" in ${mode.toUpperCase()} mode? ${mode === "replace" ? "This will WIPE and re-load each sheet." : "This will UPSERT rows by id."}`)) return;
    setImportBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post(`/masters/import?mode=${mode}`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const total = (data.sheets || []).reduce((s, x) => s + (x.count || 0), 0);
      toast.success(`Imported ${total} rows across ${(data.sheets || []).length} sheets`);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally { setImportBusy(false); }
  };

  return (
    <div className="p-6 space-y-4" data-testid="masters-page">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="overline">Configuration</div>
          <h1 className="text-2xl font-semibold tracking-tight mt-1">Commission Masters</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Configure Myntra&apos;s complete commission structure. All calculations reference the active rules.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button data-testid="btn-export-masters" onClick={exportMasters} className="btn">
            <Download size={12} /> Download config
          </button>
          <label className="btn cursor-pointer" data-testid="btn-import-masters-replace">
            <Upload size={12} /> {importBusy ? "Importing…" : "Upload (replace)"}
            <input
              data-testid="input-import-masters-replace"
              type="file"
              accept=".xlsx"
              className="hidden"
              disabled={importBusy}
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; importMasters(f, "replace"); }}
            />
          </label>
          <label className="btn cursor-pointer" data-testid="btn-import-masters-merge">
            <FileSpreadsheet size={12} /> Upload (merge)
            <input
              data-testid="input-import-masters-merge"
              type="file"
              accept=".xlsx"
              className="hidden"
              disabled={importBusy}
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; importMasters(f, "merge"); }}
            />
          </label>
        </div>
      </div>

      <div className="border-b border-border flex gap-1 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.id}
            data-testid={`tab-${t.id}`}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-xs mono uppercase tracking-widest border-b-2 -mb-px ${tab === t.id ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "portals" && <PortalsMaster />}
      {tab === "commission" && <CommissionRules />}
      {tab === "fixed" && <FixedFees />}
      {tab === "gt" && <GTCharges />}
      {tab === "return" && <ReturnFees />}
      {tab === "level" && <SubCatLevels />}
      {tab === "tolerance" && <Tolerance />}
      {tab === "settlement" && <SettlementConfig />}
      {tab === "tax" && <TaxRatesConfig />}
    </div>
  );
}

function PortalsMaster() {
  const [portals, setPortals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/portals");
      setPortals(data);
      if (!selected && data.length) setSelected(data[0].code);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const active = portals.find((p) => p.code === selected);

  const save = async (patch) => {
    if (!active) return;
    setSaving(true);
    try {
      await api.post(`/portals/${active.code}`, patch);
      toast.success(`${active.name} saved`);
      await load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  const resetDefaults = async () => {
    if (!window.confirm("Reset all portals to factory defaults? Any custom edits will be lost.")) return;
    try {
      await api.post("/portals/reset-defaults");
      toast.success("Portals reset to defaults");
      await load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  if (loading) return <div className="text-xs mono text-slate-500 py-10">Loading portals…</div>;

  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-[220px_1fr]" data-testid="portals-master">
      {/* Portal list */}
      <div className="border border-border rounded-sm overflow-hidden bg-white">
        <div className="px-3 py-2 border-b border-border overline flex items-center justify-between">
          <span>Marketplaces ({portals.length})</span>
          <button onClick={resetDefaults} className="text-[10px] mono uppercase text-slate-500 hover:text-slate-900" data-testid="btn-reset-portals">Reset</button>
        </div>
        <div className="flex flex-col">
          {portals.map((p) => (
            <button
              key={p.code}
              onClick={() => setSelected(p.code)}
              data-testid={`portal-item-${p.code}`}
              className={`px-3 py-2.5 text-left border-l-2 text-sm ${selected === p.code ? "border-primary bg-slate-50 font-medium" : "border-transparent hover:bg-slate-50"}`}
            >
              <div className="flex items-center gap-2">
                <span className="text-sm truncate flex-1">{p.name}</span>
                {p.status === "live" ? (
                  <span className="text-[9px] mono uppercase bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-sm px-1.5 py-px">LIVE</span>
                ) : (
                  <span className="text-[9px] mono uppercase bg-amber-50 text-amber-700 border border-amber-200 rounded-sm px-1.5 py-px">SOON</span>
                )}
              </div>
              <div className="overline mt-1">{p.sales_count?.toLocaleString?.("en-IN") || 0} rows</div>
            </button>
          ))}
        </div>
      </div>

      {/* Portal detail */}
      {active && (
        <div className="space-y-4 min-w-0">
          <div className="border border-border rounded-sm bg-white p-4">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <div className="overline">{active.code.toUpperCase()}</div>
                <h2 className="text-xl font-semibold tracking-tight mt-1">{active.name}</h2>
                <p className="text-sm text-slate-500 mt-1 max-w-2xl">{active.notes}</p>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={active.status}
                  onChange={(e) => save({ status: e.target.value })}
                  className="text-xs mono uppercase px-2 py-1.5 border border-border rounded-sm bg-white"
                  data-testid={`portal-status-${active.code}`}
                >
                  <option value="live">Live</option>
                  <option value="coming_soon">Coming Soon</option>
                </select>
              </div>
            </div>
          </div>

          {/* Rate card / fee heads */}
          <div className="border border-border rounded-sm bg-white overflow-hidden">
            <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
              <div className="overline">Fee heads · Rate card</div>
              <div className="text-[10px] mono text-slate-500 uppercase tracking-widest">T-1 … T-5</div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 text-slate-500 mono uppercase">
                  <tr>
                    <th className="text-left px-3 py-2 w-16">Key</th>
                    <th className="text-left px-3 py-2">Label</th>
                    <th className="text-right px-3 py-2 w-32">Sale</th>
                    <th className="text-right px-3 py-2 w-32">Return</th>
                    <th className="text-left px-3 py-2 w-24">Unit</th>
                  </tr>
                </thead>
                <tbody>
                  {(active.fee_heads || []).map((f, i) => (
                    <tr key={i} className="border-t border-border hover:bg-slate-50/50">
                      <td className="px-3 py-2 mono font-semibold">{f.key}</td>
                      <td className="px-3 py-2">
                        <input
                          defaultValue={f.label}
                          onBlur={(e) => {
                            if (e.target.value === f.label) return;
                            const next = [...active.fee_heads];
                            next[i] = { ...f, label: e.target.value };
                            save({ fee_heads: next });
                          }}
                          className="w-full bg-transparent border-b border-transparent focus:border-slate-400 outline-none py-0.5"
                          data-testid={`fh-${active.code}-${f.key}-label`}
                        />
                      </td>
                      <td className="px-3 py-2 text-right mono">{fmtValue(f.sale, f.unit)}</td>
                      <td className="px-3 py-2 text-right mono">{fmtValue(f.return, f.unit)}</td>
                      <td className="px-3 py-2 mono text-slate-500">{f.unit}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Case matrix */}
          <div className="border border-border rounded-sm bg-white overflow-hidden">
            <div className="px-4 py-2.5 border-b border-border">
              <div className="overline">Case-type × Fee behaviour</div>
              <div className="text-xs text-slate-500 mt-1">How each fee head behaves across order lifecycles.</div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 text-slate-500 mono uppercase">
                  <tr>
                    <th className="text-left px-3 py-2 w-40">Case Type</th>
                    {(active.fee_heads || []).map((f) => (
                      <th key={f.key} className="text-left px-3 py-2">{f.key}<span className="text-slate-400 normal-case ml-2 font-normal">{f.label}</span></th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {["Delivered", "DTO", "RTO", "InternalCancel"].map((ct) => (
                    <tr key={ct} className="border-t border-border">
                      <td className="px-3 py-2 mono font-medium">{ct}</td>
                      {(active.fee_heads || []).map((f) => {
                        const v = active.case_matrix?.[ct]?.[f.key] || "-";
                        const tone =
                          v.includes("Charged") ? "text-emerald-700" :
                          v.includes("Again")   ? "text-orange-700" :
                          v.includes("Reversal") ? "text-blue-700" :
                          v.includes("null") ? "text-slate-400" : "text-slate-700";
                        return <td key={f.key} className={`px-3 py-2 mono ${tone}`}>{v}</td>;
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="text-[11px] mono text-slate-400 uppercase tracking-widest">
            {saving ? "Saving…" : `${active.updated_at ? "Updated " + new Date(active.updated_at).toLocaleString("en-IN") : ""}`}
          </div>
        </div>
      )}
    </div>
  );
}

function fmtValue(v, unit) {
  if (v === null || v === undefined || v === "-") return "-";
  if (typeof v === "string") return v;
  if (unit === "pct") return `${(v * 100).toFixed(2)}%`;
  if (unit === "flat_inr") return `₹${v}`;
  return String(v);
}

function SettlementConfig() {
  const [s, setS] = useState(null);
  useEffect(() => { api.get("/masters/settlement-settings").then((r) => setS(r.data)); }, []);
  if (!s) return null;
  return (
    <div className="border border-border bg-card p-5 max-w-xl">
      <div className="overline mb-3">Settlement Configuration</div>
      <p className="text-xs text-muted-foreground mb-4">
        When a marketplace file omits or uses a placeholder (e.g. &quot;-&quot;) for zone, this configuration decides how the calculation engine treats it.
      </p>
      <div className="space-y-3 text-sm">
        <label className="block">
          <div className="overline mb-1">Default Zone When Missing</div>
          <select className="bg-secondary border border-border px-2 py-1 w-40 mono" value={s.default_zone_when_missing || ""} onChange={(e) => setS({ ...s, default_zone_when_missing: e.target.value })} data-testid="input-default-zone">
            <option value="">— None —</option>
            <option value="Local">Local</option>
            <option value="Zonal">Zonal</option>
            <option value="National">National</option>
          </select>
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={!!s.treat_dash_as_missing_zone} onChange={(e) => setS({ ...s, treat_dash_as_missing_zone: e.target.checked })} data-testid="input-dash-as-missing" />
          <span className="text-xs">Treat &quot;-&quot; as missing zone (recommended for Myntra files)</span>
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={!!s.apply_default_zone} onChange={(e) => setS({ ...s, apply_default_zone: e.target.checked })} data-testid="input-apply-default-zone" />
          <span className="text-xs">Apply default zone when missing (if off, flag as unmapped)</span>
        </label>
        <button
          data-testid="btn-save-settlement"
          onClick={async () => { await api.post("/masters/settlement-settings", s); toast.success("Settlement config saved. Re-run calculations to apply."); }}
          className="mt-2 bg-primary text-primary-foreground px-4 py-2 text-xs mono uppercase tracking-widest hover:opacity-90"
        >Save Configuration</button>
      </div>
    </div>
  );
}

function TaxRatesConfig() {
  const [t, setT] = useState(null);
  useEffect(() => { api.get("/masters/tax-rates").then((r) => setT(r.data)); }, []);
  if (!t) return null;
  return (
    <div className="border border-border bg-card p-5 max-w-xl">
      <div className="overline mb-3">Tax Rates</div>
      <div className="space-y-3 text-sm">
        <label className="block">
          <div className="overline mb-1">GST Rate (fraction, e.g. 0.18 = 18%)</div>
          <input type="number" step="0.001" className="bg-secondary border border-border px-2 py-1 w-40 mono" value={t.gst_rate} onChange={(e) => setT({ ...t, gst_rate: parseFloat(e.target.value) })} data-testid="input-gst-rate" />
        </label>
        <label className="block">
          <div className="overline mb-1">TCS Rate (fraction, e.g. 0.005 = 0.5%)</div>
          <input type="number" step="0.0001" className="bg-secondary border border-border px-2 py-1 w-40 mono" value={t.tcs_rate} onChange={(e) => setT({ ...t, tcs_rate: parseFloat(e.target.value) })} data-testid="input-tcs-rate" />
        </label>
        <label className="block">
          <div className="overline mb-1">TDS Rate (fraction, e.g. 0.001 = 0.1%)</div>
          <input type="number" step="0.0001" className="bg-secondary border border-border px-2 py-1 w-40 mono" value={t.tds_rate} onChange={(e) => setT({ ...t, tds_rate: parseFloat(e.target.value) })} data-testid="input-tds-rate" />
        </label>
        <button
          data-testid="btn-save-tax-rates"
          onClick={async () => { await api.post("/masters/tax-rates", t); toast.success("Tax rates saved. Re-run calculations to apply."); }}
          className="mt-2 bg-primary text-primary-foreground px-4 py-2 text-xs mono uppercase tracking-widest hover:opacity-90"
        >Save Tax Rates</button>
      </div>
    </div>
  );
}

function CommissionRules() {
  const [items, setItems] = useState([]);
  const load = async () => {
    const { data } = await api.get("/masters/commission-rules");
    setItems(data);
  };
  useEffect(() => { load(); }, []);

  const save = async (row) => {
    try {
      await api.post("/masters/commission-rules", row);
      toast.success("Rule saved");
      load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };
  const del = async (id) => {
    if (!window.confirm("Delete rule?")) return;
    await api.delete(`/masters/commission-rules/${id}`);
    load();
  };
  const add = async () => {
    await save({
      brand: "Kazo", master_category: "APPAREL", sub_category: "Tops", gender: "Women",
      lower_limit: 0, upper_limit: 300, price_range: "0-300",
      commission_model: "Split Commission and Logistics", commission_pct: 0.05, active: true,
    });
  };

  return (
    <div className="border border-border bg-card">
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="overline">{items.length} Rules</div>
        <button onClick={add} data-testid="btn-add-comm" className="border border-border hover:bg-secondary px-3 py-1.5 text-xs mono inline-flex items-center gap-1"><Plus size={12} /> Add Rule</button>
      </div>
      <div className="overflow-auto max-h-[calc(100vh-320px)]">
        <table className="w-full text-xs">
          <thead className="grid-header sticky top-0">
            <tr>
              <th className="grid-cell text-left">Master Cat</th>
              <th className="grid-cell text-left">Sub Cat</th>
              <th className="grid-cell text-left">Gender</th>
              <th className="grid-cell text-right">Lower</th>
              <th className="grid-cell text-right">Upper</th>
              <th className="grid-cell text-left">Range</th>
              <th className="grid-cell text-right">Commission</th>
              <th className="grid-cell text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <RuleRow key={r.id} rule={r} onSave={save} onDelete={() => del(r.id)} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RuleRow({ rule, onSave, onDelete }) {
  const [pct, setPct] = useState(rule.commission_pct);
  const [lo, setLo] = useState(rule.lower_limit);
  const [hi, setHi] = useState(rule.upper_limit);
  return (
    <tr className="grid-row" data-testid={`rule-row-${rule.id}`}>
      <td className="grid-cell">{rule.master_category}</td>
      <td className="grid-cell">{rule.sub_category}</td>
      <td className="grid-cell text-muted-foreground">{rule.gender}</td>
      <td className="grid-cell text-right"><input type="number" value={lo} onChange={(e) => setLo(parseFloat(e.target.value))} className="bg-secondary border border-border px-2 py-1 w-20 text-right text-xs mono" /></td>
      <td className="grid-cell text-right"><input type="number" value={hi} onChange={(e) => setHi(parseFloat(e.target.value))} className="bg-secondary border border-border px-2 py-1 w-24 text-right text-xs mono" /></td>
      <td className="grid-cell">{rule.price_range}</td>
      <td className="grid-cell text-right">
        <input type="number" step="0.001" value={pct} onChange={(e) => setPct(parseFloat(e.target.value))} className="bg-secondary border border-border px-2 py-1 w-20 text-right text-xs mono" />
        <span className="text-muted-foreground ml-1 text-[10px]">({fmtPct(pct)})</span>
      </td>
      <td className="grid-cell text-right">
        <div className="inline-flex gap-1">
          <button data-testid={`btn-save-rule-${rule.id}`} onClick={() => onSave({ ...rule, commission_pct: pct, lower_limit: lo, upper_limit: hi })} className="border border-border hover:bg-secondary p-1"><Save size={10} /></button>
          <button data-testid={`btn-del-rule-${rule.id}`} onClick={onDelete} className="border border-border hover:bg-red-950 hover:text-red-400 p-1"><Trash2 size={10} /></button>
        </div>
      </td>
    </tr>
  );
}

function SimpleTable({ endpoint, columns, title, addTpl }) {
  const [items, setItems] = useState([]);
  const load = async () => {
    const { data } = await api.get(endpoint);
    setItems(data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [endpoint]);

  const save = async (row) => {
    try { await api.post(endpoint, row); toast.success("Saved"); load(); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };
  const del = async (id) => {
    if (!window.confirm("Delete?")) return;
    await api.delete(`${endpoint}/${id}`);
    load();
  };
  const add = async () => save(addTpl);

  return (
    <div className="border border-border bg-card">
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="overline">{title} · {items.length} entries</div>
        {addTpl ? <button onClick={add} className="border border-border hover:bg-secondary px-3 py-1.5 text-xs mono inline-flex items-center gap-1"><Plus size={12} /> Add</button> : null}
      </div>
      <div className="overflow-auto max-h-[calc(100vh-320px)]">
        <table className="w-full text-xs">
          <thead className="grid-header sticky top-0">
            <tr>{columns.map((c) => <th key={c.key} className={`grid-cell ${c.align === "right" ? "text-right" : "text-left"}`}>{c.label}</th>)}<th className="grid-cell text-right">Actions</th></tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <EditableRow key={row.id} row={row} columns={columns} onSave={save} onDelete={() => del(row.id)} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EditableRow({ row, columns, onSave, onDelete }) {
  const [state, setState] = useState(row);
  return (
    <tr className="grid-row">
      {columns.map((c) => (
        <td key={c.key} className={`grid-cell ${c.align === "right" ? "text-right" : ""}`}>
          {c.editable ? (
            c.type === "number" ? (
              <input type="number" value={state[c.key] ?? ""} onChange={(e) => setState({ ...state, [c.key]: e.target.value === "" ? "" : parseFloat(e.target.value) })} className="bg-secondary border border-border px-2 py-1 w-24 text-xs mono text-right" />
            ) : (
              <input type="text" value={state[c.key] ?? ""} onChange={(e) => setState({ ...state, [c.key]: e.target.value })} className="bg-secondary border border-border px-2 py-1 text-xs mono w-32" />
            )
          ) : (
            <span className={c.tone === "muted" ? "text-muted-foreground" : ""}>{state[c.key]}</span>
          )}
        </td>
      ))}
      <td className="grid-cell text-right">
        <div className="inline-flex gap-1">
          <button onClick={() => onSave(state)} className="border border-border hover:bg-secondary p-1"><Save size={10} /></button>
          <button onClick={onDelete} className="border border-border hover:bg-red-950 hover:text-red-400 p-1"><Trash2 size={10} /></button>
        </div>
      </td>
    </tr>
  );
}

function FixedFees() {
  return (
    <SimpleTable
      endpoint="/masters/fixed-fees"
      title="Fixed Fee Slabs"
      columns={[
        { key: "label", label: "Range" },
        { key: "aisp_lower", label: "AISP Lower", align: "right", editable: true, type: "number" },
        { key: "aisp_upper", label: "AISP Upper", align: "right", editable: true, type: "number" },
        { key: "fixed_fee", label: "Fixed Fee (₹)", align: "right", editable: true, type: "number" },
      ]}
      addTpl={{ aisp_lower: 0, aisp_upper: 100, label: "0-100", fixed_fee: 27, active: true }}
    />
  );
}

function GTCharges() {
  return (
    <SimpleTable
      endpoint="/masters/gt-charges"
      title="GT / Logistics Charges (incl. GST)"
      columns={[
        { key: "sub_category", label: "Sub Category" },
        { key: "level", label: "Level" },
        { key: "price_range", label: "Price Range" },
        { key: "price_lower", label: "Lower", align: "right", editable: true, type: "number" },
        { key: "price_upper", label: "Upper", align: "right", editable: true, type: "number" },
        { key: "charge", label: "Charge (₹)", align: "right", editable: true, type: "number" },
      ]}
    />
  );
}

function ReturnFees() {
  return (
    <SimpleTable
      endpoint="/masters/return-fees"
      title="Return Fee Matrix"
      columns={[
        { key: "level", label: "Level" },
        { key: "zone", label: "Zone" },
        { key: "fee", label: "Fee (₹)", align: "right", editable: true, type: "number" },
      ]}
    />
  );
}

function SubCatLevels() {
  return (
    <SimpleTable
      endpoint="/masters/subcat-levels"
      title="Sub-Category → Level Mapping"
      columns={[
        { key: "sub_category", label: "Sub Category" },
        { key: "level", label: "Level", editable: true },
      ]}
    />
  );
}

function Tolerance() {
  const [t, setT] = useState(null);
  useEffect(() => { api.get("/masters/tolerance").then((r) => setT(r.data)); }, []);
  if (!t) return null;
  return (
    <div className="border border-border bg-card p-5 max-w-xl">
      <div className="overline mb-3">Reconciliation Tolerance</div>
      <div className="space-y-3 text-sm">
        <label className="block">
          <div className="overline mb-1">Absolute Tolerance (₹)</div>
          <input type="number" step="0.01" className="bg-secondary border border-border px-2 py-1 w-40 mono" value={t.absolute_inr} onChange={(e) => setT({ ...t, absolute_inr: parseFloat(e.target.value) })} />
        </label>
        <label className="block">
          <div className="overline mb-1">Percentage Tolerance (%)</div>
          <input type="number" step="0.01" className="bg-secondary border border-border px-2 py-1 w-40 mono" value={t.percentage} onChange={(e) => setT({ ...t, percentage: parseFloat(e.target.value) })} />
        </label>
        <label className="block">
          <div className="overline mb-1">Materiality Threshold (₹)</div>
          <input type="number" step="0.01" className="bg-secondary border border-border px-2 py-1 w-40 mono" value={t.materiality_inr} onChange={(e) => setT({ ...t, materiality_inr: parseFloat(e.target.value) })} />
        </label>
        <button
          data-testid="btn-save-tolerance"
          onClick={async () => { await api.post("/masters/tolerance", t); toast.success("Tolerance saved"); }}
          className="mt-2 bg-primary text-primary-foreground px-4 py-2 text-xs mono uppercase tracking-widest hover:opacity-90"
        >Save Tolerance</button>
      </div>
    </div>
  );
}
