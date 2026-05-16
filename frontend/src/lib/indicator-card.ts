// Pure helpers for IndicatorCard.svelte — extracted so the rank /
// latest-value / suppression logic can be exercised by vitest without
// touching the DOM or fetch.
//
// IndicatorCard is the per-state primitive used on /s/<state>: one card
// per indicator replacing the IndicatorChoropleth + IndicatorRanked +
// IndicatorSmallMultiples trio (which remains in use on /t/<topic>).
//
// Honesty rules honoured here (see docs/concepts/indicator-naming.md §5
// for the comparability ladder and §6 for the renderer_rules vocab):
//   - `renderer_rules` containing "no_rank_table" → suppress rank line.
//   - `comparability` ∈ rank-incompatible set → suppress rank line. The
//     set is: `directional_only` (Hans: read direction-of-change only,
//     a rank would mislead — e.g. WPI across base splices),
//     `comparable_within_state_over_time` (Hans: trace one state, do NOT
//     rank states — e.g. an indicator defined only inside a state's own
//     reporting), and the deprecated `not_comparable_across_states`
//     (v1.4 alias of directional_only). `comparable_across_states_and_time`
//     and `comparable_across_states_snapshot_only` BOTH permit ranking;
//     the snapshot variant should also suppress trend-line views, but
//     that's an IndicatorCard-template rule, not a canShowRank concern.
//   - Series with < 2 distinct time points → suppress sparkline (nothing
//     to draw; same rule IndicatorSmallMultiples applies).
//
// Plan doc: TODO/20260515-state-page-ia-rework-plan.md §2 + §9 row 1.
// Doctrine: docs/concepts/schema-is-the-design-system.md (this is
// composition over the existing renderer set, not a new family).

import type { IndicatorMeta, IndicatorRow } from "./indicators";

/** Latest (most recent) observation for a single entity, or null when the
 *  entity has no non-null rows. Time is compared lexicographically — works
 *  for YYYY, YYYY-MM, YYYY-MM-DD per the schema's time pattern. */
export function latestForEntity(
  rows: readonly IndicatorRow[],
  entity_id: string,
): { time: string; value: number } | null {
  let best: { time: string; value: number } | null = null;
  for (const r of rows) {
    if (r.entity_id !== entity_id) continue;
    if (r.value == null) continue;
    if (!best || r.time > best.time) {
      best = { time: r.time, value: r.value };
    }
  }
  return best;
}

/** Per-entity (time, value) series for one entity, ascending in time.
 *  Multiple rows at the same time are summed (mirrors seriesByEntity). */
export function seriesForEntity(
  rows: readonly IndicatorRow[],
  entity_id: string,
): Array<{ time: string; value: number }> {
  const inner = new Map<string, number>();
  for (const r of rows) {
    if (r.entity_id !== entity_id) continue;
    if (r.value == null) continue;
    inner.set(r.time, (inner.get(r.time) ?? 0) + r.value);
  }
  return [...inner.entries()]
    .map(([time, value]) => ({ time, value }))
    .sort((a, b) => a.time.localeCompare(b.time));
}

/** Rank of `entity_id` against every other entity that has a value at the
 *  same time. Returns `{ rank, total, time }` (1-indexed; 1 = best per
 *  direction) or null when no rank can be computed (entity missing, no
 *  peers, or `can_rank` is false). */
export function rankForEntity(
  rows: readonly IndicatorRow[],
  entity_id: string,
  direction: IndicatorMeta["direction"],
  can_rank: boolean,
): { rank: number; total: number; time: string } | null {
  if (!can_rank) return null;
  const home = latestForEntity(rows, entity_id);
  if (!home) return null;
  // Rank at the home entity's latest time — apples-to-apples with the
  // big number we display.
  const peers = new Map<string, number>();
  for (const r of rows) {
    if (r.time !== home.time) continue;
    if (r.value == null) continue;
    peers.set(r.entity_id, (peers.get(r.entity_id) ?? 0) + r.value);
  }
  if (!peers.has(entity_id)) return null;
  const ascending = direction === "lower_is_better";
  const sorted = [...peers.entries()].sort((a, b) =>
    ascending ? a[1] - b[1] : b[1] - a[1],
  );
  const idx = sorted.findIndex(([code]) => code === entity_id);
  if (idx < 0) return null;
  return { rank: idx + 1, total: sorted.length, time: home.time };
}

/** Whether the card may display a rank line. Honours both the
 *  `renderer_rules` (v1.5) and the `comparability` token. See the file
 *  header for the full set of rank-suppressing comparability values. */
export function canShowRank(meta: IndicatorMeta): boolean {
  const rules = meta.renderer_rules ?? [];
  if (rules.includes("no_rank_table")) return false;
  switch (meta.comparability) {
    case "directional_only":
    case "comparable_within_state_over_time":
    case "not_comparable_across_states": // deprecated v1.4 alias of directional_only
      return false;
    default:
      return true;
  }
}

/** Ordinal English suffix for a rank: 1 → "1st", 2 → "2nd", 23 → "23rd". */
export function ordinal(n: number): string {
  const v = n % 100;
  if (v >= 11 && v <= 13) return `${n}th`;
  switch (n % 10) {
    case 1: return `${n}st`;
    case 2: return `${n}nd`;
    case 3: return `${n}rd`;
    default: return `${n}th`;
  }
}
