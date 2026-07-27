import { usePortal } from "@/context/PortalContext";

const PORTAL_HUE = {
  myntra:   "#E11D74",  // magenta
  amazon:   "#FF9900",
  ajio:     "#111827",
  nykaa:    "#DE237B",
  tatacliq: "#E31E24",
  flipkart: "#2874F0",
};

export default function PortalSwitcher({ compact = false }) {
  const { portals, portalCode, setPortalCode, active } = usePortal();
  const items = [{ code: "all", name: "All Portals", status: "live" }, ...portals];
  const hue = PORTAL_HUE[portalCode] || "#111827";

  return (
    <div className="flex items-center gap-2" data-testid="portal-switcher">
      <span className="overline text-slate-400">Portal</span>
      <div className="relative">
        <span
          className="absolute left-2 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full"
          style={{ background: hue }}
        />
        <select
          value={portalCode}
          onChange={(e) => setPortalCode(e.target.value)}
          className="pl-6 pr-8 h-8 text-xs bg-white border border-slate-200 rounded-sm mono tracking-tight uppercase focus:border-slate-900 focus:outline-none"
          data-testid="portal-switcher-select"
        >
          {items.map((p) => (
            <option key={p.code} value={p.code} data-testid={`portal-option-${p.code}`}>
              {p.name}{p.status === "coming_soon" ? "  ·  soon" : ""}
            </option>
          ))}
        </select>
      </div>
      {!compact && active && active.status === "coming_soon" && (
        <span className="text-[10px] mono uppercase text-amber-600 bg-amber-50 border border-amber-200 rounded-sm px-2 py-0.5">
          Rate card ready · parser next
        </span>
      )}
    </div>
  );
}
