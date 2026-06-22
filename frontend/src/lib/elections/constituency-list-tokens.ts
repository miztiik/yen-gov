// Shared visual-token + pure-logic helpers for the election constituency
// list (Row 2 of TODO/20260622-election-constituency-grouping-plan.md).
//
// This module is the SINGLE home for the constituency list's testable
// logic so the component (`StateEventConstituencyList.svelte`) stays a thin
// renderer and the oracle unit tests exercise the SAME code path the UI
// runs (no divergence, no mocks). Row 6 (`StateOverview.svelte`) re-uses
// `marginBand` + the `ReservationBadge` component built on `reservationKind`
// so the landing page and the event list share ONE colour + badge language
// (schema-is-the-design-system).
//
// ASCII only: use "-", "->", ">=".

// ---------------------------------------------------------------------------
// Margin colour-band (RdYlBu) - the StateOverview legend, lifted verbatim.
// ---------------------------------------------------------------------------

export type MarginBandKey = "nail-biter" | "contestable" | "comfortable";

export interface MarginBand {
  readonly key: MarginBandKey;
  /** RdYlBu hex - IDENTICAL to StateOverview.svelte's per-row swatch so the
   *  two surfaces can never drift. */
  readonly hex: string;
  /** Citizen-readable band label ("nail-biter" / "contestable" /
   *  "comfortable"). */
  readonly label: string;
}

const NAIL_BITER: MarginBand = { key: "nail-biter", hex: "#d7191c", label: "nail-biter" };
const CONTESTABLE: MarginBand = { key: "contestable", hex: "#fdae61", label: "contestable" };
const COMFORTABLE: MarginBand = { key: "comfortable", hex: "#2c7bb6", label: "comfortable" };

/**
 * RdYlBu margin band for a winner's lead in percentage points:
 *   < 5  -> nail-biter  (red    #d7191c)
 *   < 10 -> contestable (orange #fdae61)
 *   >= 10 -> comfortable (blue   #2c7bb6)
 * Returns null when the margin is unknown (no band, no colour) so the
 * renderer can fall back to plain text.
 */
export function marginBand(margin: number | null | undefined): MarginBand | null {
  if (margin === null || margin === undefined || Number.isNaN(margin)) return null;
  if (margin < 5) return NAIL_BITER;
  if (margin < 10) return CONTESTABLE;
  return COMFORTABLE;
}

// ---------------------------------------------------------------------------
// Reservation category.
// ---------------------------------------------------------------------------

export type ReservationKind = "GEN" | "SC" | "ST";

/**
 * Normalises a raw reservation string to one of GEN / SC / ST. Anything that
 * is not explicitly "SC" or "ST" (including null / undefined / "" / "GEN")
 * collapses to GEN, which renders NO badge. Case-insensitive + trimmed so an
 * upstream "sc" or " ST " still resolves.
 */
export function reservationKind(reservation: string | null | undefined): ReservationKind {
  const r = (reservation ?? "").trim().toUpperCase();
  if (r === "SC") return "SC";
  if (r === "ST") return "ST";
  return "GEN";
}

// ---------------------------------------------------------------------------
// Proportional party strip (collapsed group glance).
// ---------------------------------------------------------------------------

/** Minimal row shape the strip needs: which party won, its short label, its
 *  brand colour. */
export interface StripInput {
  readonly winner_party_short: string;
  readonly winner_party_id: string;
  readonly winner_color: string;
}

export interface StripSegment {
  readonly party_short: string;
  readonly party_id: string;
  readonly color: string;
  /** Seats won by this party within the group. */
  readonly count: number;
  /** Proportional segment width as a percentage (0..100). The non-other
   *  segments + the other segment sum to ~100. */
  readonly pct: number;
  /** True for the single aggregated "Other" remainder segment. */
  readonly is_other: boolean;
}

export interface PartyStrip {
  readonly segments: readonly StripSegment[];
  /** Leading-party label of the form "<SHORT> n/N" e.g. "TDP 9/17". Empty
   *  string when the group has no rows. NEVER colour-only - the renderer
   *  ALWAYS shows this text. */
  readonly leader_label: string;
  readonly leader_short: string;
  readonly leader_count: number;
  readonly total: number;
}

/** Top-N winning parties get their own segment; the remainder collapses into
 *  ONE "Other" segment. */
export const STRIP_TOP_N = 4;
/** Neutral remainder colour (slate-300) - distinct from any party brand. */
export const STRIP_OTHER_COLOR = "#cbd5e1";
const STRIP_OTHER_SHORT = "Other";
const STRIP_OTHER_ID = "__other__";

/**
 * Builds the proportional segmented strip for a group of seats:
 *   - count seats per winning party,
 *   - sort descending by seat count (tie-break on the short label so the
 *     order is deterministic),
 *   - keep the top STRIP_TOP_N parties as their own segments,
 *   - collapse every remaining party into a single "Other" segment,
 *   - width of each segment is proportional to its seat count.
 * The leading-party label "<SHORT> n/N" always names the winner of the most
 * seats so the strip is never colour-only.
 */
export function buildPartyStrip(rows: readonly StripInput[]): PartyStrip {
  const total = rows.length;
  if (total === 0) {
    return { segments: [], leader_label: "", leader_short: "", leader_count: 0, total: 0 };
  }

  const counts = new Map<string, { short: string; color: string; count: number }>();
  for (const r of rows) {
    const ex = counts.get(r.winner_party_id);
    if (ex) ex.count += 1;
    else counts.set(r.winner_party_id, { short: r.winner_party_short, color: r.winner_color, count: 1 });
  }

  const ranked = [...counts.entries()]
    .map(([id, v]) => ({ id, ...v }))
    .sort((a, b) => b.count - a.count || a.short.localeCompare(b.short, "en"));

  const top = ranked.slice(0, STRIP_TOP_N);
  const rest = ranked.slice(STRIP_TOP_N);

  const segments: StripSegment[] = top.map((p) => ({
    party_short: p.short,
    party_id: p.id,
    color: p.color,
    count: p.count,
    pct: (p.count / total) * 100,
    is_other: false,
  }));

  if (rest.length > 0) {
    const otherCount = rest.reduce((s, p) => s + p.count, 0);
    segments.push({
      party_short: STRIP_OTHER_SHORT,
      party_id: STRIP_OTHER_ID,
      color: STRIP_OTHER_COLOR,
      count: otherCount,
      pct: (otherCount / total) * 100,
      is_other: true,
    });
  }

  const leader = ranked[0];
  return {
    segments,
    leader_label: `${leader.short} ${leader.count}/${total}`,
    leader_short: leader.short,
    leader_count: leader.count,
    total,
  };
}

// ---------------------------------------------------------------------------
// Leaf ordering.
// ---------------------------------------------------------------------------

export type SortMode = "ballot" | "margin";

/** Minimal row shape `sortLeaves` keys on. */
export interface SortableLeaf {
  readonly eci_no?: number | null;
  readonly margin_pct: number | null;
}

/**
 * Returns a NEW sorted array (does not mutate the input). `ballot` orders by
 * ascending eci_no (the order voters saw on the EVM); `margin` orders by
 * ascending margin (nail-biters first). Rows whose sort key is null /
 * undefined / NaN sink to the end while preserving their incoming relative
 * order (stable).
 */
export function sortLeaves<T extends SortableLeaf>(rows: readonly T[], mode: SortMode): T[] {
  const key = (row: T): number | null => {
    const v = mode === "margin" ? row.margin_pct : row.eci_no ?? null;
    if (v === null || v === undefined || Number.isNaN(v)) return null;
    return v;
  };
  return rows
    .map((row, idx) => ({ row, idx, k: key(row) }))
    .sort((a, b) => {
      if (a.k === null && b.k === null) return a.idx - b.idx;
      if (a.k === null) return 1;
      if (b.k === null) return -1;
      if (a.k !== b.k) return a.k - b.k;
      return a.idx - b.idx;
    })
    .map((w) => w.row);
}

// ---------------------------------------------------------------------------
// Filter + count.
// ---------------------------------------------------------------------------

/** Minimal row shape the filter keys on. */
export interface FilterableLeaf {
  readonly entity_name: string;
  readonly reservation?: string | null;
}

/**
 * AND-composes the case-insensitive name search with the Reserved filter.
 * `reserved` is one of "All" / "GEN" / "SC" / "ST"; "All" applies no
 * reservation constraint. Returns a NEW filtered array.
 */
export function applyFilters<T extends FilterableLeaf>(
  rows: readonly T[],
  query: string,
  reserved: ReservationKind | "All",
): T[] {
  const q = query.trim().toLowerCase();
  return rows.filter((r) => {
    if (q && !r.entity_name.toLowerCase().includes(q)) return false;
    if (reserved !== "All" && reservationKind(r.reservation) !== reserved) return false;
    return true;
  });
}

/** Counts distinct district groups, bucketing missing districts under
 *  `fallback` (so an un-wired list still reports "in 1 district"). */
export function distinctDistrictCount<T extends { district?: string | null }>(
  rows: readonly T[],
  fallback = "All constituencies",
): number {
  const set = new Set<string>();
  for (const r of rows) set.add(r.district ?? fallback);
  return set.size;
}

/** "N constituencies in M districts" with singular/plural handling. */
export function formatCountLine(constituencies: number, districts: number): string {
  const c = `${constituencies} ${constituencies === 1 ? "constituency" : "constituencies"}`;
  const d = `${districts} ${districts === 1 ? "district" : "districts"}`;
  return `${c} in ${d}`;
}
