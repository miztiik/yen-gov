// Temporal viewport — pure helpers. No DOM, no Svelte, no state.
//
// Per Phase 1.5 of docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md.
// The brush component (later PR) and the temporal-aware renderers
// (StackedTrendV2, ministerial Gantt, fiscal lines) consume these.
//
// Design notes:
//
//   - Helpers are INDEX-FIRST. The temporal domain is an ordered
//     sequence of `period_id` strings; the window is a (from, to)
//     pair into that sequence. This means the helpers work for both
//     calendar years AND for non-uniform sequences (election cycles,
//     fiscal years, custom labels) without coupling to date math.
//
//   - Date math is APPLIED ON TOP for year-derivable domain kinds.
//     `presetWindow` consults `min_year` / `max_year` for `10y`/`25y`
//     and degrades gracefully for `election_cycle` / `custom`.
//
//   - All helpers return CLAMPED, CANONICAL windows. The brush
//     handler can call `clampWindow(dragWindow, domain)` after every
//     drag tick without writing branchy boundary code itself.
//
//   - Pure functions throw ONLY on programmer error
//     (`buildDomain([])`) — domain-runtime issues like a stale URL
//     hash or missing period_id degrade to the full window.

import type {
  TemporalDomain,
  TemporalDomainKind,
  TemporalPreset,
  TemporalWindow,
  TemporalWindowIndices,
} from "./types";

/** Frozen canonical list of supported presets. Order is informative
 *  (`all` first as the safe default; `recent` second as the most
 *  common citizen choice). */
export const KNOWN_PRESETS = Object.freeze([
  "all",
  "recent",
  "5y",
  "10y",
  "25y",
] as const) satisfies readonly TemporalPreset[];

/** Frozen canonical list of supported domain kinds. */
export const KNOWN_DOMAIN_KINDS = Object.freeze([
  "year",
  "election_cycle",
  "month",
  "fiscal_year",
  "custom",
] as const) satisfies readonly TemporalDomainKind[];

// --- Domain construction ---------------------------------------------

/**
 * Parse the leading 4-digit year out of a period_id. Supports the
 * shapes the codebase uses today:
 *
 *   - `year`        : "1977", "2024"           → 1977 / 2024
 *   - `fiscal_year` : "FY2021", "FY 2021-22"   → 2021
 *   - `month`       : "2024-05", "2024/05"     → 2024
 *
 * Returns `null` for anything that doesn't carry a clean 4-digit year
 * prefix (election cycles like "AcGenMay2023" don't match — the
 * adapter must declare those as `election_cycle` / `custom`).
 *
 * Implementation: matches one of three precise shapes (bare year,
 * year-followed-by-separator, FY-prefixed year). A loose
 * "year-anywhere" regex would over-match — "AcGenMay2023" carries
 * a 4-digit suffix but is structurally an election-event id, NOT a
 * year. The adapter knows the difference; the helper must respect it.
 */
export function parseLeadingYear(period_id: string): number | null {
  // Shape 1: whole-string bare year ("2024").
  let m = period_id.match(/^(\d{4})$/);
  if (m) return guardedYear(Number(m[1]));
  // Shape 2: year followed by separator ("2024-05", "2024/05",
  // "2024 anything").
  m = period_id.match(/^(\d{4})[\s\-_./]/);
  if (m) return guardedYear(Number(m[1]));
  // Shape 3: FY-prefixed year ("FY2021", "FY 2021-22").
  m = period_id.match(/^FY\s?(\d{4})/);
  if (m) return guardedYear(Number(m[1]));
  return null;
}

function guardedYear(y: number): number | null {
  // Sanity: indexable history of Indian governance is 1700+; cap at
  // 2100 to catch obviously-bad ids early. Helpers must not throw on
  // stale data so just degrade to `null`.
  if (!Number.isInteger(y) || y < 1700 || y > 2100) return null;
  return y;
}

/**
 * Build a `TemporalDomain` from an ordered list of period_ids and an
 * explicit `domain_kind`. The adapter knows the kind; the helper does
 * NOT try to sniff (sniffing is wrong as often as it's right — e.g.
 * a custom dimension whose ids happen to look like years).
 *
 * Throws on `period_ids.length === 0` because that is a programmer
 * error: the brush primitive cannot operate on an empty domain. The
 * adapter must filter to a non-empty domain before calling.
 *
 * `min_year` / `max_year` are filled iff `domain_kind` is year-
 * derivable (`year`, `fiscal_year`, `month`); otherwise `null`. Even
 * for derivable kinds, both are `null` if NO id in the sequence
 * parses (defensive: brushes still work on the index axis).
 */
export function buildDomain(
  period_ids: readonly string[],
  domain_kind: TemporalDomainKind,
): TemporalDomain {
  if (period_ids.length === 0) {
    throw new Error("buildDomain: period_ids must be non-empty");
  }
  // Freeze a copy so callers can't mutate the canonical sequence
  // after construction.
  const ordered_period_ids = Object.freeze(period_ids.slice());

  const year_derivable =
    domain_kind === "year" ||
    domain_kind === "fiscal_year" ||
    domain_kind === "month";

  if (!year_derivable) {
    return Object.freeze({
      domain_kind,
      ordered_period_ids,
      min_year: null,
      max_year: null,
    });
  }

  let min_year: number | null = null;
  let max_year: number | null = null;
  for (const id of ordered_period_ids) {
    const y = parseLeadingYear(id);
    if (y == null) continue;
    if (min_year === null || y < min_year) min_year = y;
    if (max_year === null || y > max_year) max_year = y;
  }
  return Object.freeze({
    domain_kind,
    ordered_period_ids,
    min_year,
    max_year,
  });
}

// --- Window helpers --------------------------------------------------

/**
 * The full-domain window: first..last period_id. The renderer's
 * default state and the `all` preset's output.
 */
export function fullWindow(domain: TemporalDomain): TemporalWindow {
  const ids = domain.ordered_period_ids;
  return Object.freeze({
    from_period_id: ids[0]!,
    to_period_id: ids[ids.length - 1]!,
  });
}

/** True iff `window` matches the full-domain window. */
export function isFullWindow(
  window: TemporalWindow,
  domain: TemporalDomain,
): boolean {
  const full = fullWindow(domain);
  return (
    window.from_period_id === full.from_period_id &&
    window.to_period_id === full.to_period_id
  );
}

/**
 * Resolve `window` into a `{from_idx, to_idx}` pair of indices into
 * the parent `domain.ordered_period_ids`. Returns `{-1, -1}` when
 * either end cannot be located — the brush handler then degrades to
 * the full window rather than throwing.
 */
export function windowIndices(
  window: TemporalWindow,
  domain: TemporalDomain,
): TemporalWindowIndices {
  const ids = domain.ordered_period_ids;
  const from_idx = ids.indexOf(window.from_period_id);
  const to_idx = ids.indexOf(window.to_period_id);
  if (from_idx === -1 || to_idx === -1) {
    return { from_idx: -1, to_idx: -1 };
  }
  return { from_idx, to_idx };
}

/**
 * Clamp `window` to the parent domain. Operations performed (in
 * order):
 *
 *   1. Unknown `from_period_id` or `to_period_id` → return
 *      `fullWindow(domain)`. The brush handler treats this as the
 *      "reset to full" fallback.
 *
 *   2. Reversed window (from later than to) → swap. The brush UI
 *      naturally produces reversed pairs while the user drags one
 *      handle past the other.
 *
 *   3. Otherwise return the input verbatim (already canonical).
 *
 * Note: a single-period window (from === to) is VALID and preserved
 * — the brush UI can collapse to a single bar selection.
 */
export function clampWindow(
  window: TemporalWindow,
  domain: TemporalDomain,
): TemporalWindow {
  const { from_idx, to_idx } = windowIndices(window, domain);
  if (from_idx === -1 || to_idx === -1) {
    return fullWindow(domain);
  }
  if (from_idx > to_idx) {
    return Object.freeze({
      from_period_id: window.to_period_id,
      to_period_id: window.from_period_id,
    });
  }
  return Object.freeze({
    from_period_id: window.from_period_id,
    to_period_id: window.to_period_id,
  });
}

// --- Preset windows --------------------------------------------------

export interface PresetWindowOptions {
  /** Number of trailing periods for the `recent` preset. Defaults to
   *  `5` — citizen tested at the 2026-05-22 review as the most
   *  common "show me the last few" reading. */
  readonly recent_count?: number;
}

/**
 * Compute the window for a named `preset`. Returns `null` when the
 * preset is not meaningful for this domain (e.g. `10y` on an
 * `election_cycle` domain where year arithmetic doesn't apply).
 *
 * Algorithm per preset:
 *
 *   - `all`       → `fullWindow(domain)`.
 *
 *   - `recent`    → last `recent_count` periods (default 5). If
 *                   the domain is shorter than `recent_count`, returns
 *                   the full domain. Always works regardless of
 *                   `domain_kind`.
 *
 *   - `5y/10y/25y` → year-window-based. Requires
 *                    `domain.max_year !== null`. Returns the contiguous
 *                    sub-window whose ids parse to a year >=
 *                    `max_year - N + 1`. If the resulting window
 *                    would be empty (no qualifying ids), clamps to
 *                    the last id of the domain. Returns `null` when
 *                    `max_year` is null.
 */
export function presetWindow(
  preset: TemporalPreset,
  domain: TemporalDomain,
  opts: PresetWindowOptions = {},
): TemporalWindow | null {
  if (preset === "all") return fullWindow(domain);

  const ids = domain.ordered_period_ids;
  if (preset === "recent") {
    const count = Math.max(1, opts.recent_count ?? 5);
    const start = Math.max(0, ids.length - count);
    return Object.freeze({
      from_period_id: ids[start]!,
      to_period_id: ids[ids.length - 1]!,
    });
  }

  // Year-arithmetic presets from here down.
  if (domain.max_year === null) return null;
  const span = preset === "5y" ? 5 : preset === "10y" ? 10 : 25;
  const cutoff = domain.max_year - span + 1;
  let first_qualifying_idx = -1;
  for (let i = 0; i < ids.length; i += 1) {
    const y = parseLeadingYear(ids[i]!);
    if (y != null && y >= cutoff) {
      first_qualifying_idx = i;
      break;
    }
  }
  if (first_qualifying_idx === -1) {
    // No period in the year-window. Citizen-facing chart must not
    // disappear; clamp to the last bar.
    return Object.freeze({
      from_period_id: ids[ids.length - 1]!,
      to_period_id: ids[ids.length - 1]!,
    });
  }
  return Object.freeze({
    from_period_id: ids[first_qualifying_idx]!,
    to_period_id: ids[ids.length - 1]!,
  });
}

// --- Filtering -------------------------------------------------------

/**
 * Return the subset of `items` whose period_id (extracted via the
 * supplied getter) falls inside the inclusive `window` per the parent
 * `domain`. Generic so the same helper covers `StackedTrendV2Bar`,
 * gantt rows, fiscal-line points, etc.
 *
 * Items whose period_id is NOT in the domain are dropped (defensive
 * — the adapter should have filtered already, but a stale URL hash
 * could trigger the case). Items remain in input order; the function
 * is stable for equal indices.
 */
export function filterItemsToWindow<T>(
  items: readonly T[],
  getPeriodId: (item: T) => string,
  window: TemporalWindow,
  domain: TemporalDomain,
): readonly T[] {
  const { from_idx, to_idx } = windowIndices(window, domain);
  if (from_idx === -1 || to_idx === -1) return items.slice();
  const idx_of = new Map<string, number>();
  for (let i = 0; i < domain.ordered_period_ids.length; i += 1) {
    idx_of.set(domain.ordered_period_ids[i]!, i);
  }
  return items.filter(item => {
    const i = idx_of.get(getPeriodId(item));
    return i !== undefined && i >= from_idx && i <= to_idx;
  });
}
