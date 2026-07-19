import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("admin@kazo.com");
  const [password, setPassword] = useState("admin123");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(email.trim().toLowerCase(), password);
      toast.success("Signed in");
      nav("/");
    } catch (e) {
      const msg = formatApiError(e.response?.data?.detail) || e.message;
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex bg-background text-foreground">
      {/* Left visual panel */}
      <div
        className="hidden md:flex flex-1 relative bg-black"
        style={{
          backgroundImage:
            "linear-gradient(rgba(0,0,0,0.85), rgba(0,0,0,0.85)), url(https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA3MDR8MHwxfHNlYXJjaHwzfHxmaW5hbmNlJTIwZGFzaGJvYXJkJTIwdHJhZGluZyUyMHNjcmVlbnxlbnwwfHx8fDE3ODQ0NzQwNjd8MA&ixlib=rb-4.1.0&q=85)",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="p-10 relative z-10 flex flex-col justify-between h-full">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-primary text-primary-foreground flex items-center justify-center">
              <Sparkles size={14} strokeWidth={2} />
            </div>
            <div className="text-sm tracking-tight font-semibold">KAZO Marketplace Finance</div>
          </div>
          <div className="max-w-md">
            <div className="overline mb-3">Enterprise Reconciliation OS</div>
            <h1 className="text-4xl md:text-5xl font-light tracking-tight leading-tight">
              Recover leakage. <span className="font-semibold">Own your marketplace math.</span>
            </h1>
            <p className="mt-5 text-sm text-muted-foreground leading-relaxed">
              Ingest Myntra reports, calculate expected commissions with configurable logic,
              and reconcile settlements down to the paisa. Discrepancies surface first — by
              severity, financial impact and ageing.
            </p>
            <div className="mt-8 grid grid-cols-3 gap-3">
              {["Commission Engine", "Reconciliation", "Recovery Cases"].map((t) => (
                <div key={t} className="border border-border/60 p-3 bg-black/40">
                  <div className="overline">{t}</div>
                  <div className="mono text-[11px] text-muted-foreground mt-1">Deterministic</div>
                </div>
              ))}
            </div>
          </div>
          <div className="text-[10px] mono text-muted-foreground uppercase tracking-widest">
            © KAZO · Rev 2026.02
          </div>
        </div>
      </div>

      {/* Right form */}
      <div className="flex-1 flex items-center justify-center px-6 py-10">
        <form onSubmit={submit} className="w-full max-w-sm" data-testid="login-form">
          <div className="overline mb-2">Sign In</div>
          <h2 className="text-2xl font-semibold tracking-tight">Marketplace Command Center</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Use your KAZO Finance credentials to continue.
          </p>

          <div className="mt-8">
            <label className="overline block mb-2">Email</label>
            <input
              data-testid="login-email"
              type="email"
              className="w-full bg-secondary border border-border px-3 py-2.5 text-sm outline-none focus:border-foreground/50"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </div>
          <div className="mt-4">
            <label className="overline block mb-2">Password</label>
            <input
              data-testid="login-password"
              type="password"
              className="w-full bg-secondary border border-border px-3 py-2.5 text-sm outline-none focus:border-foreground/50"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          {error ? (
            <div className="mt-4 border border-red-900 bg-red-950/40 text-red-300 text-xs p-3 mono" data-testid="login-error">
              {error}
            </div>
          ) : null}

          <button
            data-testid="login-submit"
            type="submit"
            disabled={loading}
            className="mt-6 w-full bg-primary text-primary-foreground py-2.5 text-sm font-medium tracking-wide hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Authenticating…" : "Sign in →"}
          </button>

          <div className="mt-8 border-t border-border pt-4">
            <div className="overline mb-1">Demo Credentials</div>
            <div className="text-xs mono text-muted-foreground">
              admin@kazo.com · admin123
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
