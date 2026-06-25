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
// Typed number tokens (share + signed margin) + Option-E margin bar + the
// shared subgrid ruler. The renderer (Row 3) and the national rail (Row 4)
// read these straight onto the SAME grid so the share + margin columns format
// and align IDENTICALLY on every surface. null / undefined / NaN render the
// shared em-dash "-".
// ---------------------------------------------------------------------------

/** One-decimal percent WITH the "%" suffix, e.g. fmtShare(45.04) -> "45.0%".
 *  Unknown (null / undefined / NaN) -> "-". */
export function fmtShare(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return `${n.toFixed(1)}%`;
}

/** One-decimal margin with a LEADING SIGN and NO "%", e.g.
 *  fmtMarginSigned(15.9) -> "+15.9", fmtMarginSigned(-0.36) -> "-0.4" (standard
 *  JS rounding; toFixed already carries the "-" for negatives). Unknown ->
 *  "-". */
export function fmtMarginSigned(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  const fixed = n.toFixed(1);
  return n >= 0 ? `+${fixed}` : fixed;
}

/** Clamp a number to [lo, hi] (no dependency). */
function clamp(value: number, lo: number, hi: number): number {
  return Math.min(Math.max(value, lo), hi);
}

/**
 * The Option-E margin-bar segment for a winner's lead: a magnitude width on a
 * FIXED 0..50pp scale (so a given lead reads the same bar length on every row)
 * plus the shared marginBand() colour for that lead - the bar and the swatch
 * can never drift because they call the SAME band function. An unknown margin
 * yields a zero-width neutral segment (STRIP_OTHER_COLOR, the module's existing
 * slate neutral - no new palette colour is introduced).
 */
export function marginBarSegment(
  margin: number | null | undefined,
): { pct: number; hex: string } {
  if (margin === null || margin === undefined || Number.isNaN(margin)) {
    return { pct: 0, hex: STRIP_OTHER_COLOR };
  }
  const band = marginBand(margin);
  const hex = band ? band.hex : STRIP_OTHER_COLOR;
  const pct = clamp((Math.min(Math.abs(margin), 50) / 50) * 100, 0, 100);
  return { pct, hex };
}

/** The single 6-track subgrid ruler shared by the constituency list renderer
 *  AND the national state rail: glyph | name | context | share | margin | bar.
 *  Defining it ONCE here is what lets the nested rows align column-for-column
 *  across both surfaces (grid-cols-subgrid children inherit this ruler). */
export const GRID_COLS =
  "grid-cols-[1.25rem_minmax(0,1fr)_minmax(0,max-content)_max-content_max-content_max-content]";

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

// ---------------------------------------------------------------------------
// Group assembly - assembly mode (party strip) vs PC mode (header result).
// ---------------------------------------------------------------------------
//
// Row 3 of TODO/20260622-election-constituency-grouping-plan.md adds an
// OPTIONAL parliament/PC mode to the SAME component (schema-is-the-design-
// system: ONE component, behaviour switched by DATA presence). A group is in
// PC mode IFF the caller supplies a `GroupHeaderResult` for that group's key
// in the `group_headers` map; otherwise the group is in assembly mode and
// behaves exactly as before (a proportional party strip in the header + per-
// leaf result chips on the leaves).
//
// Grouping key (see `groupKeyOf`): a leaf groups under `pc_group` when present
// (parliament: the leaf is an AC and `pc_group` is its parent PC name), else
// under `district` (assembly: the leaf is an AC grouped by its LGD district),
// else the shared "All constituencies" fallback. Keeping `district` as the
// leaf's OWN LGD district in BOTH modes lets a PC-mode leaf render its district
// label inline ("-> Krishna") while the group header carries the PC result.

/** The parliament/PC group-header result: the Lok Sabha (MP) outcome for a PC,
 *  rendered in the GROUP HEADER (never on the leaves). Supplied per group via
 *  `buildGroups`' `group_headers` map (keyed by the group key). MUST carry a
 *  party chip, a vote share, a margin, and a child-AC count; `color` +
 *  `reservation` are yen-gov additions so the header chip paints in the
 *  winner's brand colour and shows the PC's SC/ST badge - matching the
 *  assembly-mode leaf chip + Appendix Mode 2 mock. */
export interface GroupHeaderResult {
  /** Winning party short label shown in the header chip (e.g. "TDP"). Never
   *  colour-only - the chip ALWAYS shows this text. */
  readonly chip: string;
  /** Winning party brand colour - the header chip background. */
  readonly color: string;
  /** Winner vote share in percentage points (0..100), or null when unknown. */
  readonly share: number | null;
  /** Winner margin in percentage points (0..100), or null; drives the shared
   *  marginBand() swatch in the header. */
  readonly margin: number | null;
  /** Count of child ACs under this PC (the "N segments" count in the mock). */
  readonly child_count: number;
  /** Optional PC-level reservation ("SC"/"ST") -> rose badge in the header;
   *  GEN / null / undefined renders nothing. */
  readonly reservation?: string | null;
}

/** The minimal leaf shape `buildGroups` keys on: the winner trio for the
 *  assembly strip (StripInput), the sort keys (SortableLeaf), plus the two
 *  grouping fields. `SeatRow` satisfies this structurally. */
export interface GroupableLeaf extends StripInput, SortableLeaf {
  /** The leaf's own LGD district name. In assembly mode this is the group
   *  key; in PC mode it is shown inline on the leaf. */
  readonly district?: string | null;
  /** Parliament-mode grouping override: the parent PC name. When present the
   *  leaf groups under this instead of `district`. Absent in assembly mode. */
  readonly pc_group?: string | null;
}

export interface ConstituencyGroup<T> {
  /** The group label (PC name in PC mode, LGD district in assembly mode, or
   *  the "All constituencies" fallback). Also the fold/expand key. */
  readonly group_key: string;
  /** Leaves in this group, sorted per the active SortMode. */
  readonly rows: T[];
  /** "pc" iff a GroupHeaderResult was supplied for this group key, else
   *  "assembly". The renderer switches the header (result vs strip) and the
   *  leaves (district label vs result chip) on this single flag. */
  readonly mode: "pc" | "assembly";
  /** PC-mode group-header result; null in assembly mode. */
  readonly header_result: GroupHeaderResult | null;
  /** Assembly-mode proportional party strip; null in PC mode. */
  readonly strip: PartyStrip | null;
}

/** The single source of truth for a leaf's group key: `pc_group` (parliament)
 *  -> `district` (assembly) -> the shared fallback. */
export function groupKeyOf(
  leaf: GroupableLeaf,
  fallback = "All constituencies",
): string {
  return leaf.pc_group ?? leaf.district ?? fallback;
}

/** The unlinked-AC bucket label: in PC mode an AC whose parent PC is unknown
 *  (`pc_group == null`) groups here, and this group is always forced to sort
 *  LAST (never wedged mid-list). Assembly mode never produces it. */
export const PENDING_GROUP = "Parliament seat pending";

/**
 * Groups leaves into ordered ConstituencyGroups, attaching either an
 * assembly-mode party strip OR a PC-mode header result per group. PC mode is
 * selected PER GROUP by the presence of a `group_headers[group_key]` entry, so
 * one component instance can render assembly groups and PC groups from DATA
 * alone (schema-is-the-design-system). In PC mode (a `group_headers` map is
 * supplied) a leaf with no parent PC (`pc_group == null`) routes into the
 * shared PENDING_GROUP bucket instead of the district / "All constituencies"
 * fallback, and that bucket is forced to sort LAST; assembly mode (no
 * `group_headers`) keeps the `pc_group -> district -> "All constituencies"`
 * chain UNCHANGED. Groups are otherwise sorted by their key (locale "en");
 * leaves are sorted by the given SortMode. Pure - never mutates input.
 */
export function buildGroups<T extends GroupableLeaf>(
  rows: readonly T[],
  sort_mode: SortMode,
  group_headers?: Record<string, GroupHeaderResult> | null,
  fallback = "All constituencies",
): ConstituencyGroup<T>[] {
  // PC mode for this call IFF the caller supplies a group-header map. In PC
  // mode an unlinked AC (`pc_group == null`) pools into PENDING_GROUP (the
  // district is NOT a PC-mode grouping fallback - so a 70/70 all-pending state
  // collapses into ONE bucket); assembly mode keeps the
  // `pc_group -> district -> "All constituencies"` chain via groupKeyOf.
  const pc_mode = group_headers != null;
  const by_key = new Map<string, T[]>();
  for (const r of rows) {
    const key = pc_mode ? r.pc_group ?? PENDING_GROUP : groupKeyOf(r, fallback);
    const list = by_key.get(key);
    if (list) list.push(r);
    else by_key.set(key, [r]);
  }
  const out: ConstituencyGroup<T>[] = [];
  for (const [group_key, groupRows] of by_key) {
    const header = group_headers?.[group_key] ?? null;
    out.push({
      group_key,
      rows: sortLeaves(groupRows, sort_mode),
      mode: header ? "pc" : "assembly",
      header_result: header,
      strip: header ? null : buildPartyStrip(groupRows),
    });
  }
  // Sort by key (locale "en"), but force PENDING_GROUP to the very end
  // regardless of localeCompare (D5 - the unlinked-AC bucket is never wedged
  // mid-list, even ahead of a group whose key sorts after it alphabetically).
  out.sort((a, b) => {
    if (a.group_key === PENDING_GROUP) return b.group_key === PENDING_GROUP ? 0 : 1;
    if (b.group_key === PENDING_GROUP) return -1;
    return a.group_key.localeCompare(b.group_key, "en");
  });
  return out;
}
