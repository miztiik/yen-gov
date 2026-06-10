// Pure derivation for YearPillStrip.svelte (PR-W4a, 2026-06-10).
//
// Extracted from the Svelte component for the same reason as
// alliance-totals-model / inline-swing-model: vitest runs in node-env
// and mounting Svelte components needs jsdom + @testing-library/svelte,
// which the project intentionally does not install. The pure derivation
// tests cover the sort order + active-pill flag + year extraction —
// everything the template renders is a 1:1 echo of these fields.
//
// The strip is DISCRETE tap-to-jump per the election-experience-overhaul
// plan's anti-leakage rule: continuous sliders are reserved for socio-econ
// time series (frontend/src/lib/charts/...), election years are pills.

import type { ElectionEventRow } from "../election-events";

/** Derived view of one event row, with the active-pill flag baked in
 *  alongside the year so the template can stay declarative. Sort order
 *  is oldest-first (left-to-right reads as time-moving-forward, matching
 *  the indiavotes.com convention the plan-doc cites). */
export interface PillState {
  event_id: string;
  year: number;
  is_active: boolean;
}

/** Stable copy + sort by polled_on ASC (lexicographic comparison is
 *  safe for ISO YYYY-MM-DD). Never mutates the caller's array. */
export function sortEventsByPolledOn(
  events: readonly ElectionEventRow[],
): ElectionEventRow[] {
  return [...events].sort((a, b) => a.polled_on.localeCompare(b.polled_on));
}

/** Project the active flag + year for one row. Year is extracted from
 *  the ISO date string head so the helper does not need Date math (UTC
 *  edge cases around year boundaries do not bite for ISO YYYY heads). */
export function pillStateFor(
  event: ElectionEventRow,
  active_event_id: string,
): PillState {
  return {
    event_id: event.event_id,
    year: yearOfPolledOn(event.polled_on),
    is_active: event.event_id === active_event_id,
  };
}

/** Sort + project in one pass. The template's `{#each}` reads this
 *  array directly. */
export function deriveStrip(
  events: readonly ElectionEventRow[],
  active_event_id: string,
): PillState[] {
  return sortEventsByPolledOn(events).map((e) => pillStateFor(e, active_event_id));
}

function yearOfPolledOn(polled_on: string): number {
  const head = polled_on.slice(0, 4);
  const yr = Number(head);
  // `polled_on` is hand-authored ISO YYYY-MM-DD per the
  // election_events.schema.json contract; a non-numeric head is a
  // schema break, not a runtime concern — surface 0 so the pill still
  // renders something rather than NaN.
  return Number.isFinite(yr) ? yr : 0;
}
