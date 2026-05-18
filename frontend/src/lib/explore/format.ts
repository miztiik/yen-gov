// Result-table formatting helpers. Pure functions, no Svelte.
//
// Heuristics-only: we infer "this is a numeric column" / "this is a percentage
// column" from the column name because sql.js doesn't carry column types
// across the SELECT projection. The heuristics target the names we actually
// emit from `presets.ts` plus the conventional names used in candidate /
// constituency / party_totals views (votes, seats, margin, share, _pct, …).

const PCT_RE     = /(_pct|_share|share_pct)$/i;
const NUMERIC_RE = /(votes|seats|margin|count|contested|won|rate|avg|min|max|share|pct|spread|first|second|third|wins|contests)/i;

export function isPctCol(name: string): boolean {
  return PCT_RE.test(name);
}

export function isNumericCol(name: string): boolean {
  return NUMERIC_RE.test(name);
}

export function fmtCell(value: unknown, col: string): string {
  if (value === null || value === undefined) return "—";
  // DuckDB-WASM surfaces BIGINT as JS bigint. Promote to number for the
  // thousand-separator path; safe because vote / seat counts comfortably
  // fit Number.MAX_SAFE_INTEGER.
  if (typeof value === "bigint") return Number(value).toLocaleString();
  if (typeof value === "number") {
    if (isPctCol(col)) return `${value.toFixed(2)}%`;
    if (Number.isInteger(value)) return value.toLocaleString();
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return String(value);
}
