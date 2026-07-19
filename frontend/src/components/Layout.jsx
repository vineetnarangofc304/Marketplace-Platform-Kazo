import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, Upload, Table2, Calculator, GitCompareArrows,
  AlertTriangle, Settings2, LogOut, Sparkles, FileText,
} from "lucide-react";

const nav = [
  { to: "/", label: "Overview", icon: LayoutDashboard, testId: "nav-overview" },
  { to: "/reports", label: "Monthly Report", icon: FileText, testId: "nav-reports" },
  { to: "/uploads", label: "Uploads", icon: Upload, testId: "nav-uploads" },
  { to: "/sales", label: "Sales Ledger", icon: Table2, testId: "nav-sales" },
  { to: "/calculations", label: "Calculations", icon: Calculator, testId: "nav-calculations" },
  { to: "/reconciliation", label: "Reconciliation", icon: GitCompareArrows, testId: "nav-recon" },
  { to: "/discrepancies", label: "Discrepancies", icon: AlertTriangle, testId: "nav-disc" },
  { to: "/masters", label: "Commission Masters", icon: Settings2, testId: "nav-masters" },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const nav_ = useNavigate();
  const loc = useLocation();

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      {/* Sidebar */}
      <aside className="w-60 border-r border-border bg-card flex flex-col shrink-0">
        <div className="px-5 py-6 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-primary text-primary-foreground flex items-center justify-center">
              <Sparkles size={14} strokeWidth={2} />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight">KAZO Finance</div>
              <div className="overline">Marketplace OS</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 py-4 flex flex-col">
          {nav.map((n) => {
            const active = loc.pathname === n.to || (n.to !== "/" && loc.pathname.startsWith(n.to));
            const Icon = n.icon;
            return (
              <NavLink
                key={n.to}
                to={n.to}
                data-testid={n.testId}
                className={`flex items-center gap-3 px-5 py-2.5 text-sm border-l-2 ${active ? "border-primary bg-secondary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground hover:bg-secondary"}`}
              >
                <Icon size={16} strokeWidth={1.5} />
                <span>{n.label}</span>
              </NavLink>
            );
          })}
        </nav>
        <div className="p-4 border-t border-border">
          <div className="overline mb-2">Signed in</div>
          <div className="text-sm truncate">{user?.email}</div>
          <div className="overline mt-0.5">{user?.role}</div>
          <button
            data-testid="btn-logout"
            className="mt-3 w-full inline-flex items-center gap-2 justify-center text-xs py-2 border border-border hover:bg-secondary"
            onClick={async () => { await logout(); nav_("/login"); }}
          >
            <LogOut size={12} /> Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 min-w-0 flex flex-col">
        <header className="h-14 border-b border-border bg-card flex items-center justify-between px-6">
          <div className="text-xs uppercase tracking-widest text-muted-foreground mono">
            {loc.pathname === "/" ? "Overview / Command Center" : loc.pathname.slice(1).replace(/\//g, " / ")}
          </div>
          <div className="text-xs mono text-muted-foreground">
            Myntra · KAZO · {new Date().toLocaleDateString("en-IN")}
          </div>
        </header>
        <div className="flex-1 overflow-auto">{children}</div>
      </main>
    </div>
  );
}
