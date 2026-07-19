import { useEffect, useRef, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { UploadCloud, FileSpreadsheet, Trash2, PlayCircle } from "lucide-react";
import { toast } from "sonner";
import { fmtInt } from "@/lib/format";

function UploadDrop({ kind, label, onUploaded }) {
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const inputRef = useRef();

  const doUpload = async (file) => {
    if (!file) return;
    setBusy(true);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post(`/uploads/${kind}`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(data);
      toast.success(`Uploaded ${file.name}: ${data.accepted_count} accepted, ${data.rejected_count} rejected`);
      onUploaded?.(data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border border-border bg-card p-5" data-testid={`upload-drop-${kind}`}>
      <div className="overline">{label}</div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); doUpload(e.dataTransfer.files?.[0]); }}
        className={`mt-3 border border-dashed ${drag ? "border-foreground bg-secondary" : "border-border"} p-8 text-center cursor-pointer`}
        onClick={() => inputRef.current?.click()}
      >
        <UploadCloud size={28} className="mx-auto text-muted-foreground" strokeWidth={1.2} />
        <div className="mt-3 text-sm">
          {busy ? "Processing…" : `Drop .xlsx here or click to select`}
        </div>
        <div className="overline mt-1">Myntra {label}</div>
        <input
          data-testid={`upload-input-${kind}`}
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls"
          className="hidden"
          onChange={(e) => doUpload(e.target.files?.[0])}
        />
      </div>
      {result ? (
        <div className="mt-3 text-xs mono border-t border-border pt-3">
          <div>File: <span className="text-muted-foreground">{result.filename}</span></div>
          <div>Sheet: <span className="text-muted-foreground">{result.sheet}</span></div>
          <div className="mt-1">
            <span className="fin-pos">{result.accepted_count} accepted</span>
            {" · "}
            <span className={result.rejected_count ? "fin-neg" : "text-muted-foreground"}>{result.rejected_count} rejected</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function Uploads() {
  const [uploads, setUploads] = useState([]);
  const [running, setRunning] = useState(false);

  const refresh = async () => {
    const { data } = await api.get("/uploads");
    setUploads(data);
  };

  useEffect(() => { refresh(); }, []);

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
      toast.success(`Calculated ${data.processed} orders`);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="p-6 space-y-6" data-testid="uploads-page">
      <div>
        <div className="overline">Ingestion</div>
        <h1 className="text-2xl font-semibold tracking-tight mt-1">Upload Marketplace Reports</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Sales data → normalized ledger. Settlement report → reconciliation engine.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <UploadDrop kind="sales" label="Sales Data (Myntra)" onUploaded={refresh} />
        <UploadDrop kind="settlement" label="Settlement / Commission Report" onUploaded={refresh} />
      </div>

      <div className="border border-border bg-card">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="overline">Upload History</div>
          <div className="text-xs mono text-muted-foreground">{uploads.length} runs</div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="grid-header">
              <tr>
                <th className="text-left grid-cell">Type</th>
                <th className="text-left grid-cell">Filename</th>
                <th className="text-left grid-cell">Uploaded</th>
                <th className="text-right grid-cell">Accepted</th>
                <th className="text-right grid-cell">Rejected</th>
                <th className="text-right grid-cell">Actions</th>
              </tr>
            </thead>
            <tbody>
              {uploads.length === 0 ? (
                <tr><td colSpan={6} className="grid-cell text-center text-muted-foreground py-8">No uploads yet</td></tr>
              ) : uploads.map((u) => (
                <tr key={u.id} className="grid-row" data-testid={`upload-row-${u.id}`}>
                  <td className="grid-cell">
                    <span className="inline-flex items-center gap-1"><FileSpreadsheet size={12} /> {u.type}</span>
                  </td>
                  <td className="grid-cell truncate max-w-[280px]">{u.filename}</td>
                  <td className="grid-cell text-xs text-muted-foreground">{new Date(u.uploaded_at).toLocaleString()}</td>
                  <td className="grid-cell text-right fin-pos">{fmtInt(u.accepted_count)}</td>
                  <td className="grid-cell text-right fin-neg">{fmtInt(u.rejected_count)}</td>
                  <td className="grid-cell text-right">
                    <div className="inline-flex items-center gap-2">
                      {u.type === "sales" ? (
                        <button
                          disabled={running}
                          onClick={() => runCalcs(u.id)}
                          data-testid={`btn-run-calc-${u.id}`}
                          className="inline-flex items-center gap-1 border border-border hover:bg-secondary px-2 py-1 text-xs mono"
                        >
                          <PlayCircle size={12} /> Run Calc
                        </button>
                      ) : null}
                      <button
                        onClick={() => deleteUpload(u.id)}
                        data-testid={`btn-delete-upload-${u.id}`}
                        className="inline-flex items-center gap-1 border border-border hover:bg-red-950 hover:text-red-400 px-2 py-1 text-xs mono"
                      >
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
