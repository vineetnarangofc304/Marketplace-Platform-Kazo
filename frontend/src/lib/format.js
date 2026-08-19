export const fmt = (v, decimals = 2) => {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "number" ? v : parseFloat(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
};

export const fmtInt = (v) => {
  if (v === null || v === undefined) return "—";
  const n = typeof v === "number" ? v : parseFloat(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
};

export const fmtCurrency = (v) => {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "number" ? v : parseFloat(v);
  if (Number.isNaN(n)) return String(v);
  return `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

/**
 * Return the accounting-color class for a fee/deduction value.
 *  - Positive number  → charge/cost to the seller → red (fin-neg)
 *  - Negative number  → reversal/credit to the seller → green (fin-pos)
 *  - Zero / null      → neutral (no colour)
 * Use this for Commission / Fixed Fee / GT / Return Fee / Total Deductions
 * so DTO rows visually flip: reversed commission (-₹279) shows GREEN,
 * fresh return fee (+₹112) shows RED, matching accounting intuition.
 */
export const signClass = (v) => {
  const n = typeof v === "number" ? v : parseFloat(v);
  if (!Number.isFinite(n) || n === 0) return "";
  return n > 0 ? "fin-neg" : "fin-pos";
};

/**
 * Colour class for a net-settlement value. Positive = seller receives (green),
 * Negative = seller pays out (red).
 */
export const settlementClass = (v) => {
  const n = typeof v === "number" ? v : parseFloat(v);
  if (!Number.isFinite(n) || n === 0) return "";
  return n > 0 ? "fin-pos" : "fin-neg";
};

export const fmtPct = (v, decimals = 2) => {
  if (v === null || v === undefined) return "—";
  const n = typeof v === "number" ? v : parseFloat(v);
  if (Number.isNaN(n)) return String(v);
  return `${(n * 100).toFixed(decimals)}%`;
};
