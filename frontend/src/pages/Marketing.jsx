import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Download, Copy, Trash2, LogOut, Sparkles, FileDown } from "lucide-react";

const BASE = process.env.REACT_APP_BACKEND_URL;
const TOKEN_KEY = "fundle_marketing_token";

// ---------- Login ----------
function MarketingLogin({ onSuccess }) {
  const [email, setEmail] = useState("marketing@fundle.ai");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await axios.post(`${BASE}/api/marketing/login`, { email, password });
      localStorage.setItem(TOKEN_KEY, data.token);
      onSuccess();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: "#0B1E3B" }} data-testid="marketing-login-page">
      <form onSubmit={submit} className="w-full max-w-sm rounded-3xl p-8 space-y-5" style={{ background: "#F5F1EA" }}>
        <div className="space-y-1">
          <div className="text-xs uppercase tracking-widest" style={{ color: "#FF6B4A" }}>Powered by Fundle</div>
          <h1 className="text-3xl font-black text-slate-900">Marketing Studio</h1>
          <p className="text-sm text-slate-500">One user, one workspace, one focused tool.</p>
        </div>
        <label className="block space-y-1">
          <span className="text-xs font-semibold text-slate-700">Email</span>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="marketing-login-email" required />
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-semibold text-slate-700">Password</span>
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} data-testid="marketing-login-password" required />
        </label>
        <Button type="submit" disabled={busy} className="w-full text-white font-semibold rounded-full" style={{ background: "#FF6B4A" }} data-testid="marketing-login-submit">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
}

// ---------- Gallery ----------
function PostCard({ post, onDelete }) {
  const token = localStorage.getItem(TOKEN_KEY);
  const [imgUrl, setImgUrl] = useState(null);

  useEffect(() => {
    let objectUrl = null;
    axios
      .get(`${BASE}/api/marketing/posts/${post.id}/image`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: "blob",
      })
      .then((res) => {
        objectUrl = URL.createObjectURL(res.data);
        setImgUrl(objectUrl);
      });
    return () => objectUrl && URL.revokeObjectURL(objectUrl);
  }, [post.id, token]);

  const copyText = async () => {
    const t = [post.linkedin_text, "", (post.hashtags || []).join(" ")].join("\n");
    try {
      if (!navigator?.clipboard?.writeText) throw new Error("Clipboard API unavailable");
      await navigator.clipboard.writeText(t);
      toast.success("LinkedIn copy copied");
    } catch (err) {
      // Fallback: create a temporary textarea and use document.execCommand
      try {
        const ta = document.createElement("textarea");
        ta.value = t;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        toast.success("LinkedIn copy copied");
      } catch {
        toast.error("Copy failed — please copy manually");
      }
    }
  };

  const download = () => {
    if (!imgUrl) return;
    const a = document.createElement("a");
    a.href = imgUrl;
    a.download = `${post.title.replace(/[^a-z0-9]+/gi, "_").toLowerCase()}.png`;
    a.click();
  };

  return (
    <Card className="overflow-hidden rounded-2xl border border-slate-200/70 bg-white" data-testid={`marketing-post-${post.id}`}>
      <div className="aspect-square bg-slate-100 grid place-items-center">
        {imgUrl ? (
          <img src={imgUrl} alt={post.title} className="w-full h-full object-cover" />
        ) : (
          <div className="text-slate-400 text-xs">Loading…</div>
        )}
      </div>
      <div className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#FF6B4A" }}>
              {post.style === "screen_collage" ? "Screen Collage" : "Infographic"}
            </div>
            <h3 className="text-base font-bold text-slate-900 mt-1 leading-snug">{post.title}</h3>
          </div>
          <button onClick={() => onDelete(post.id)} className="text-slate-400 hover:text-rose-500" data-testid={`marketing-post-delete-${post.id}`} aria-label="Delete">
            <Trash2 size={16} />
          </button>
        </div>
        <p className="text-xs text-slate-600 whitespace-pre-wrap line-clamp-6">{post.linkedin_text}</p>
        <div className="flex flex-wrap gap-1">
          {(post.hashtags || []).slice(0, 8).map((h) => (
            <span key={h} className="text-[10px] font-medium text-slate-600 bg-slate-100 rounded-full px-2 py-0.5">{h}</span>
          ))}
        </div>
        <div className="flex gap-2 pt-1">
          <Button size="sm" variant="outline" onClick={copyText} className="flex-1 rounded-full" data-testid={`marketing-post-copy-${post.id}`}>
            <Copy size={14} className="mr-1" /> Copy
          </Button>
          <Button size="sm" onClick={download} className="flex-1 rounded-full text-white" style={{ background: "#0B1E3B" }} data-testid={`marketing-post-download-${post.id}`}>
            <Download size={14} className="mr-1" /> PNG
          </Button>
        </div>
      </div>
    </Card>
  );
}

function CreatePostDialog({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ title: "", keywords: "", style: "infographic", tone: "founder" });

  const submit = async () => {
    if (!form.title.trim() || !form.keywords.trim()) {
      toast.error("Title and keywords are required");
      return;
    }
    setBusy(true);
    try {
      const token = localStorage.getItem(TOKEN_KEY);
      const { data } = await axios.post(`${BASE}/api/marketing/posts`, form, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success("Post created");
      onCreated(data);
      setOpen(false);
      setForm({ title: "", keywords: "", style: "infographic", tone: "founder" });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Generation failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="rounded-full text-white font-semibold shadow-lg" style={{ background: "#FF6B4A" }} data-testid="marketing-create-open">
          <Plus size={16} className="mr-1" /> Create post
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Sparkles size={18} style={{ color: "#FF6B4A" }} /> Generate a LinkedIn post</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <label className="block space-y-1">
            <span className="text-xs font-semibold text-slate-700">Title / headline (goes on the infographic)</span>
            <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Recover ₹2 crore of hidden Myntra leakage" data-testid="marketing-create-title" />
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-semibold text-slate-700">Keywords / talking points (comma-separated)</span>
            <Textarea rows={3} value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} placeholder="e.g. commission variance, GT reversal, month-end close, reconciliation" data-testid="marketing-create-keywords" />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block space-y-1">
              <span className="text-xs font-semibold text-slate-700">Style</span>
              <Select value={form.style} onValueChange={(v) => setForm({ ...form, style: v })}>
                <SelectTrigger data-testid="marketing-create-style"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="infographic">Infographic</SelectItem>
                  <SelectItem value="screen_collage">Screen Collage</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-semibold text-slate-700">Tone</span>
              <Select value={form.tone} onValueChange={(v) => setForm({ ...form, tone: v })}>
                <SelectTrigger data-testid="marketing-create-tone"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="founder">Founder</SelectItem>
                  <SelectItem value="punchy">Punchy</SelectItem>
                  <SelectItem value="data">Data-led</SelectItem>
                </SelectContent>
              </Select>
            </label>
          </div>
          <p className="text-[11px] text-slate-500">
            Generation takes ~15–30s. The Fundle logo is composited pixel-perfect. Screen-collage style renders faux product screens tilted on navy.
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={busy} className="rounded-full">Cancel</Button>
          <Button onClick={submit} disabled={busy} className="rounded-full text-white" style={{ background: "#0B1E3B" }} data-testid="marketing-create-submit">
            {busy ? "Generating…" : "Generate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function Marketing() {
  const [authed, setAuthed] = useState(!!localStorage.getItem(TOKEN_KEY));
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem(TOKEN_KEY);
      const { data } = await axios.get(`${BASE}/api/marketing/posts`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPosts(data.items || []);
    } catch (err) {
      if (err?.response?.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        setAuthed(false);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (authed) load(); }, [authed]);

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setAuthed(false);
  };

  const onDelete = async (id) => {
    if (!window.confirm("Delete this post?")) return;
    const token = localStorage.getItem(TOKEN_KEY);
    await axios.delete(`${BASE}/api/marketing/posts/${id}`, { headers: { Authorization: `Bearer ${token}` } });
    toast.success("Deleted");
    setPosts(posts.filter((p) => p.id !== id));
  };

  if (!authed) return <MarketingLogin onSuccess={() => setAuthed(true)} />;

  return (
    <div className="min-h-screen" style={{ background: "#F5F1EA" }} data-testid="marketing-gallery-page">
      <header className="sticky top-0 z-10 backdrop-blur bg-white/70 border-b border-slate-200/70">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-widest" style={{ color: "#FF6B4A" }}>Powered by Fundle</div>
            <h1 className="text-2xl font-black text-slate-900">Marketing Studio</h1>
          </div>
          <div className="flex items-center gap-3">
            <a
              href={`${BASE}/api/marketing/brochure`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-sm font-semibold text-slate-700 hover:text-slate-900 rounded-full px-4 py-2 border border-slate-300 bg-white"
              data-testid="marketing-download-brochure"
            >
              <FileDown size={16} /> Brochure
            </a>
            <CreatePostDialog onCreated={(p) => setPosts([p, ...posts])} />
            <button onClick={logout} className="text-slate-500 hover:text-slate-900" data-testid="marketing-logout" aria-label="Logout">
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-6 py-8">
        {loading ? (
          <div className="text-slate-400">Loading gallery…</div>
        ) : posts.length === 0 ? (
          <div className="text-slate-400">No posts yet. Click <b>Create post</b> to generate one.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="marketing-gallery-grid">
            {posts.map((p) => <PostCard key={p.id} post={p} onDelete={onDelete} />)}
          </div>
        )}
      </main>
    </div>
  );
}
