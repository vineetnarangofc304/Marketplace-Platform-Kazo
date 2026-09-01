import { useEffect, useRef, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { UploadCloud, FileSpreadsheet, Trash2, PlayCircle, AlertTriangle, Download } from "lucide-react";
import { toast } from "sonner";
import { fmtInt } from "@/lib/format";
import { usePortal } from "@/context/PortalContext";

function UploadDrop({ kind, label, hint, onUploaded, portal, portalName, isCompatible }) {
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const inputRef = useRef();

  const doUpload = async (file) => {
    if (!file) return;
    if (!portal) { toast.error("Please pick a marketplace first"); return; }
    if (!isCompatible &&
        !window.confirm(
          `${portalName} uses a different file schema.\n\n` +
          `The file will be stored with portal="${portal}", but rows may be rejected or parsed incorrectly ` +
          `until the ${portalName}-specific parser is enabled in an upcoming release.\n\nProceed anyway?`
        )) return;
    setBusy(true);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post(`/uploads/${kind}?portal=${portal}`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(data);
      toast.success(`${file.name}: ${data.accepted_count} accepted, ${data.rejected_count} rejected`);
      onUploaded?.(data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border border-border bg-white p-5 rounded-sm" data-testid={`upload-drop-${kind}`}>
      <div className="overline">{label}</div>
      {hint && <div className="text-xs text-slate-500 mt-1">{hint}</div>}
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); doUpload(e.dataTransfer.files?.[0]); }}
        className={`mt-3 border border-dashed ${drag ? "border-slate-500 bg-slate-50" : "border-slate-300"} p-8 text-center cursor-pointer rounded-sm hover:bg-slate-50`}
        onClick={() => inputRef.current?.click()}
      >
        <UploadCloud size={28} className="mx-auto text-slate-400" strokeWidth={1.2} />
        <div className="mt-3 text-sm text-slate-700">{busy ? "Processing…" : "Drop .xlsx here or click to select"}</div>
        <div className="overline mt-1">{portalName || "—"}  ·  {label}</div>
        <input data-testid={`upload-input-${kind}`} ref={inputRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={(e) => doUpload(e.target.files?.[0])} />
      </div>
      {!isCompatible && portal && (
        <div className="mt-3 flex items-start gap-2 text-[11px] mono bg-amber-50 text-amber-800 border border-amber-200 rounded-sm px-3 py-2">
          <AlertTriangle size={12} className="mt-px shrink-0" />
          <span><strong>{portalName}</strong> parser is on our roadmap. Uploads will be stored & tagged; parsing may be partial until we ship the native parser for this portal.</span>
        </div>
      )}
      {result ? (
        <div className="mt-3 text-xs mono border-t border-border pt-3 space-y-0.5">
          <div>File: <span className="text-slate-500">{result.filename}</span></div>
          <div>Sheet: <span className="text-slate-500">{result.sheet}</span></div>
          <div>
            <span className="fin-pos">{result.accepted_count} accepted</span>
            {" · "}
            <span className={result.rejected_count ? "fin-neg" : "text-slate-500"}>{result.rejected_count} rejected</span>
          </div>
          {result.months && Object.keys(result.months).length > 0 && (
            <div>Months: {Object.entries(result.months).map(([m, n]) => <span key={m} className="chip chip-neutral mr-1">{m} · {n}</span>)}</div>
          )}
        </div>
      ) : null}
    </div>
  );
}

export default function Uploads() {
  const { portals, portalCode, setPortalCode, portalParam } = usePortal();
  const [uploads, setUploads] = useState([]);
  const [running, setRunning] = useState(false);
  // Portal ingest-selector — separate from global filter. Defaults to global unless "all".
  const [ingestPortal, setIngestPortal] = useState(portalCode === "all" ? "myntra" : portalCode);
  useEffect(() => { if (portalCode !== "all") setIngestPortal(portalCode); }, [portalCode]);

  const ingestPortalObj = portals.find((p) => p.code === ingestPortal);
  // Any 'live' portal has a working parser (Myntra native + generic portal engine
  // covering Amazon/AJIO/Nykaa/Tata Cliq/Flipkart via the fee-heads matrix).
  const isCompatible = ingestPortalObj?.status === "live";

  const refresh = async () => {
    const q = portalParam ? `?portal=${portalParam}` : "";
    const { data } = await api.get(`/uploads${q}`);
    setUploads(data);
  };
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [portalParam]);

  const deleteUpload = async (id) => {
    if (!window.confirm("Delete this upload and its data?")) return;
    await api.delete(`/uploads/${id}`);
    await refresh();
    toast.success("Deleted");
  };

  const runCalcs = async (upload_id) => {
    setRunning(true);
    try {
      const { data } = await api.post("/calculations/run", { upload_id, recalculate: true });
      toast.success(`${data.fully_mapped_count} mapped · ${data.unmapped_count} unmapped`);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setRunning(false);
    }
  };

  const downloadRaw = async (upload_id, filename) => {
    try {
      const res = await api.get(`/uploads/${upload_id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || `upload_${upload_id}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      // Server errors come back as a Blob (because we asked for blob response).
      // Try to read the blob as JSON to surface the FastAPI detail message.
      let msg = "Download failed";
      try {
        if (e.response?.data instanceof Blob) {
          const t = await e.response.data.text();
          try { msg = JSON.parse(t).detail || t; }
          catch { msg = t || msg; }
        } else {
          msg = formatApiError(e.response?.data?.detail) || msg;
        }
      } catch { /* keep default */ }
      toast.error(msg);
    }
  };

  const rebuildAll = async () => {
    const scope = portalParam ? `${ingestPortalObj?.name || portalParam}` : "ALL portals";
    if (!window.confirm(
      `Rebuild expected charges for ${scope}?\n\n` +
      `This wipes existing calculations and re-runs the engine using the current masters. ` +
      `Safe to run — no source data is modified.`
    )) return;
    setRunning(true);
    try {
      const body = { recalculate: true };
      if (portalParam) body.portal = portalParam;
      const { data } = await api.post("/calculations/run", body);
      toast.success(
        `Rebuilt ${data.processed?.toLocaleString?.("en-IN") || data.processed} rows · ` +
        `${data.fully_mapped_count?.toLocaleString?.("en-IN") || data.fully_mapped_count} mapped · ` +
        `${data.unmapped_count?.toLocaleString?.("en-IN") || data.unmapped_count} unmapped`,
        { duration: 6000 }
      );
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="p-6 space-y-5" data-testid="uploads-page">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="overline">Ingestion</div>
          <h1 className="text-2xl font-semibold tracking-tight mt-1 text-slate-900">Upload Marketplace Reports</h1>
          <p className="text-sm text-slate-500 mt-1">
            Every upload is tagged with the selected marketplace + month. Repeat monthly per portal.
          </p>
        </div>
        <button
          data-testid="btn-rebuild-all-calculations"
          onClick={rebuildAll}
          disabled={running}
          className="btn"
          title="Wipe & recompute expected charges for the selected portal scope using the latest masters."
        >
          <PlayCircle size={12} /> {running ? "Rebuilding…" : `Rebuild Calculations${portalParam ? ` · ${ingestPortalObj?.name || portalParam}` : " · All Portals"}`}
        </button>
      </div>

      {/* Portal picker for ingestion */}
      <div className="border border-border bg-white rounded-sm p-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="overline">Ingest for marketplace</div>
            <div className="text-xs text-slate-500 mt-1">Pick the marketplace this file belongs to before dropping.</div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {portals.map((p) => (
              <button
                key={p.code}
                onClick={() => { setIngestPortal(p.code); if (portalCode !== "all") setPortalCode(p.code); }}
                data-testid={`ingest-portal-${p.code}`}
                className={`px-3 py-1.5 text-xs mono uppercase tracking-wider border rounded-sm ${
                  ingestPortal === p.code
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-200 text-slate-600 hover:border-slate-400"
                }`}
              >
                {p.name}
                {p.status === "coming_soon" && <span className="ml-1.5 text-[9px] opacity-60">SOON</span>}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <UploadDrop
          kind="sales" label="Sales Data"
          hint="Raw sales report from the marketplace — one row per order-item."
          portal={ingestPortal} portalName={ingestPortalObj?.name}
          isCompatible={isCompatible}
          onUploaded={refresh}
        />
        <UploadDrop
          kind="settlement" label="Settlement / Commission Report"
          hint="Payout / settlement statement for the same month."
          portal={ingestPortal} portalName={ingestPortalObj?.name}
          isCompatible={isCompatible}
          onUploaded={refresh}
        />
      </div>

      <div className="border border-border bg-white rounded-sm">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="overline">Upload History{portalParam ? ` · ${ingestPortalObj?.name || portalParam}` : " · All Portals"}</div>
          <div className="text-xs mono text-slate-500">{uploads.length} uploads</div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="grid-header">
              <tr>
                <th className="grid-cell text-left">Portal</th>
                <th className="grid-cell text-left">Type</th>
                <th className="grid-cell text-left">Filename</th>
                <th className="grid-cell text-left">Months</th>
                <th className="grid-cell text-left">Uploaded</th>
                <th className="grid-cell text-right">Accepted</th>
                <th className="grid-cell text-right">Rejected</th>
                <th className="grid-cell text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {uploads.length === 0 ? (
                <tr><td colSpan={8} className="grid-cell text-center text-slate-400 py-8">No uploads yet</td></tr>
              ) : uploads.map((u) => (
                <tr key={u.id} className="grid-row" data-testid={`upload-row-${u.id}`}>
                  <td className="grid-cell mono text-xs uppercase">{u.portal || "myntra"}</td>
                  <td className="grid-cell"><span className="inline-flex items-center gap-1"><FileSpreadsheet size={12} /> {u.type}</span></td>
                  <td className="grid-cell truncate max-w-[240px]">{u.filename}</td>
                  <td className="grid-cell text-xs">{u.months ? Object.keys(u.months).join(", ") : "—"}</td>
                  <td className="grid-cell text-xs text-slate-500">{new Date(u.uploaded_at).toLocaleString()}</td>
                  <td className="grid-cell text-right fin-pos">{fmtInt(u.accepted_count)}</td>
                  <td className="grid-cell text-right fin-neg">{fmtInt(u.rejected_count)}</td>
                  <td className="grid-cell text-right">
                    <div className="inline-flex items-center gap-2">
                      {u.type === "sales" ? (
                        <button disabled={running} onClick={() => runCalcs(u.id)} data-testid={`btn-run-calc-${u.id}`} className="btn text-xs">
                          <PlayCircle size={12} /> Run Calc
                        </button>
                      ) : null}
                      <button onClick={() => downloadRaw(u.id, u.filename)} data-testid={`btn-download-upload-${u.id}`} className="btn text-xs" title="Download original file">
                        <Download size={12} />
                      </button>
                      <button onClick={() => deleteUpload(u.id)} data-testid={`btn-delete-upload-${u.id}`} className="btn btn-danger text-xs">
                        <Trash2 size={12} />
                      </button>
                    </div>
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
