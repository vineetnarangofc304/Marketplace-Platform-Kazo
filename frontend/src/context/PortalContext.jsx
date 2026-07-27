import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const PortalContext = createContext(null);

const STORAGE_KEY = "fundle_portal";
const DEFAULT_CODE = "all";

export function PortalProvider({ children }) {
  const { user } = useAuth();
  const [portals, setPortals] = useState([]);
  const [portalCode, setPortalCodeState] = useState(() => localStorage.getItem(STORAGE_KEY) || DEFAULT_CODE);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/portals");
      setPortals(Array.isArray(data) ? data : []);
    } catch (e) {
      /* ignored — unauth pages hit this too */
    } finally {
      setLoading(false);
    }
  }, []);

  // Reload whenever auth user changes (login / logout). Covers "empty after login" bug.
  useEffect(() => {
    if (user) load(); else setPortals([]);
  }, [user, load]);

  const setPortalCode = useCallback((code) => {
    const val = (code || DEFAULT_CODE).toLowerCase();
    localStorage.setItem(STORAGE_KEY, val);
    setPortalCodeState(val);
  }, []);

  const portalParam = portalCode === "all" ? undefined : portalCode;
  const active = portals.find((p) => p.code === portalCode);

  return (
    <PortalContext.Provider value={{ portals, portalCode, setPortalCode, portalParam, active, loading, reload: load }}>
      {children}
    </PortalContext.Provider>
  );
}

export function usePortal() {
  const ctx = useContext(PortalContext);
  if (!ctx) throw new Error("usePortal must be used within PortalProvider");
  return ctx;
}
