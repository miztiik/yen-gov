// election-map-coloring — pure recolour/dim helpers for the PR-B8 filter rail.
//
// The filter rail does NOT add a bespoke widget; it recolours the SAME
// choropleth/cartogram and dims the units that fall outside the active
// party/margin filter. All of that geometry-free decision logic lives here
// so it can be unit-tested without a map or a browser, and reused by both
// the state arm (StateAcMap) and — eventually — the national arm.
//
// Output is keyed by `ac_eci_no` to match StateAcMap's `fills` / `opacities`
// Record shape, so the caller can thread these straight in as overrides.

import type { AcWinner } from "../view-models/state-overview";
import {
  matchesMarginBand,
  type ColourMode,
  type ElectionFilters,
} from "../election-filters";

/** Resolver for a party's hex fill (injected so this module stays store-free). */
export type PartyFill = (
  eci_code: string | null,
  short: string,
) => string;

/** Neutral fill for units with no value in the active continuous mode. */
export const NO_VALUE_FILL = "#e2e8f0"; // slate-200

/** Opacity applied to units filtered OUT by the active party/margin filter. */
export const DIMMED_OPACITY = 0.12;

/** Sequential ramp endpoints (light → dark) for the continuous modes. */
const RAMP: Record<Exclude<ColourMode, "winner">, [string, string]> = {
  // amber-100 → amber-700
  margin: ["#fef3c7", "#b45309"],
  // sky-100 → sky-700
  turnout: ["#e0f2fe", "#0369a1"],
  // violet-100 → violet-700
  age: ["#ede9fe", "#6d28d9"],
};

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}

function rgbToHex(r: number, g: number, b: number): string {
  const c = (n: number) =>
    Math.round(Math.max(0, Math.min(255, n)))
      .toString(16)
      .padStart(2, "0");
  return `#${c(r)}${c(g)}${c(b)}`;
}

/** Linear interpolate two hex colours; t clamped to [0,1]. */
export function lerpColor(from: string, to: string, t: number): string {
  const u = Math.max(0, Math.min(1, t));
  const [r1, g1, b1] = hexToRgb(from);
  const [r2, g2, b2] = hexToRgb(to);
  return rgbToHex(r1 + (r2 - r1) * u, g1 + (g2 - g1) * u, b1 + (b2 - b1) * u);
}

/** The value a continuous mode reads off each winner row (null if absent). */
function valueFor(row: AcWinner, mode: ColourMode): number | null {
  switch (mode) {
    case "margin":
      return row.margin_pct == null ? null : Math.abs(row.margin_pct);
    case "turnout":
      return row.turnout_pct ?? null;
    case "age":
      return row.winner_age ?? null;
    case "winner":
    default:
      return null;
  }
}

/**
 * True when enough winners carry a value for `mode` to justify offering it.
 * Winner mode is always available; turnout/age are affidavit/condition-gated
 * (Max's coverage verdict) — default threshold 0.8 (80% populated).
 */
export function hasModeCoverage(
  rows: AcWinner[],
  mode: ColourMode,
  threshold = 0.8,
): boolean {
  if (mode === "winner") return true;
  if (rows.length === 0) return false;
  const present = rows.filter((r) => valueFor(r, mode) != null).length;
  return present / rows.length >= threshold;
}

/** True when a winner row passes BOTH the party and margin filters. */
export function matchesFilters(row: AcWinner, filters: ElectionFilters): boolean {
  if (filters.parties.length > 0) {
    const code = row.party_eci_code ?? row.party_short;
    if (!filters.parties.includes(code)) return false;
  }
  return matchesMarginBand(row.margin_pct, filters.margin);
}

/**
 * Per-AC fills keyed by `ac_eci_no`.
 *  - winner mode → party palette (via the injected resolver)
 *  - continuous  → sequential ramp over the populated value domain; units
 *    with no value get the neutral NO_VALUE_FILL.
 */
export function buildAcFills(
  rows: AcWinner[],
  mode: ColourMode,
  partyFill: PartyFill,
): Record<number, string> {
  const out: Record<number, string> = {};
  if (mode === "winner") {
    for (const r of rows) {
      out[r.ac_eci_no] = partyFill(r.party_eci_code, r.party_short);
    }
    return out;
  }

  const [from, to] = RAMP[mode];
  const vals = rows
    .map((r) => valueFor(r, mode))
    .filter((v): v is number => v != null);
  const min = vals.length ? Math.min(...vals) : 0;
  const max = vals.length ? Math.max(...vals) : 1;
  const span = max - min || 1;
  for (const r of rows) {
    const v = valueFor(r, mode);
    out[r.ac_eci_no] = v == null ? NO_VALUE_FILL : lerpColor(from, to, (v - min) / span);
  }
  return out;
}

/**
 * Per-AC opacities keyed by `ac_eci_no`.
 *  - units filtered OUT → DIMMED_OPACITY
 *  - winner mode, kept  → margin-based base (matches StateAcMap's formula)
 *  - continuous, kept   → near-opaque (value is carried by the fill)
 */
export function buildAcOpacities(
  rows: AcWinner[],
  mode: ColourMode,
  filters: ElectionFilters,
): Record<number, number> {
  const out: Record<number, number> = {};
  for (const r of rows) {
    if (!matchesFilters(r, filters)) {
      out[r.ac_eci_no] = DIMMED_OPACITY;
      continue;
    }
    if (mode === "winner") {
      const m = Math.max(0, Math.min(30, r.margin_pct ?? 0));
      out[r.ac_eci_no] = 0.35 + (m / 30) * 0.6;
    } else {
      out[r.ac_eci_no] = 0.9;
    }
  }
  return out;
}
