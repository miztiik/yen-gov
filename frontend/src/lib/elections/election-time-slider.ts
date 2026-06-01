// PR-B6 — pure stop-derivation for the snapping election time-slider.
//
// The slider scrubs the constituency map/cartogram across a state's
// consecutive SAME-GRAIN elections. It SNAPS to real election dates — there
// is no interpolation and no autoplay (Jony: a half-position between two
// elections has no meaning, so the control must only ever rest on a cohort
// that actually exists on disk).
//
// This module owns the (testable, node-safe) derivation of the discrete
// stops from a list of `ElectionEventRow`s. The Svelte component
// (`ElectionTimeSlider.svelte`) is a thin shell over the array this returns.

import type { ElectionEventRow } from "../election-events";

export interface ElectionSliderStop {
  /** The ECI cohort id — the value persisted to the route + used to reload. */
  event_id: string;
  /** Citizen-facing tick label. The 4-digit poll year (e.g. "2021"). */
  label: string;
  /** Canonical ISO poll date, kept for ordering + the aria description. */
  polled_on: string;
  /** Full event display string for the active-stop readout + tooltip. */
  display: string;
}

/**
 * Build the ordered, de-duplicated list of slider stops from a state's
 * events.
 *
 * Rules:
 *   - Stops are sorted CHRONOLOGICALLY ASCENDING (oldest → newest) so the
 *     slider reads left=past, right=present like every timeline.
 *   - `polled_on` is ISO `YYYY-MM-DD`, so lexicographic sort == chronological.
 *   - Duplicate `event_id`s collapse to one stop (first occurrence wins);
 *     the catalogue is hand-authored and a stray repeat must not double-tick.
 *   - The tick label is the 4-digit poll year. Two elections in the same
 *     year are rare but legal; both keep their own stop (deduped only by id),
 *     and the readout below the slider disambiguates by full `display`.
 *
 * Pure / sync / does not mutate the input.
 */
export function buildSliderStops(
  events: readonly ElectionEventRow[],
): ElectionSliderStop[] {
  const seen = new Set<string>();
  const stops: ElectionSliderStop[] = [];
  for (const ev of events) {
    if (seen.has(ev.event_id)) continue;
    seen.add(ev.event_id);
    stops.push({
      event_id: ev.event_id,
      label: ev.polled_on.slice(0, 4),
      polled_on: ev.polled_on,
      display: ev.display,
    });
  }
  return stops.sort((a, b) => a.polled_on.localeCompare(b.polled_on));
}

/**
 * Index of `eventId` within `stops`, or `-1` when absent. The slider clamps
 * an unknown/extinct event id to the LAST (most recent) stop so a stale
 * permalink still lands on a valid, scrubbable position rather than an
 * empty control.
 */
export function stopIndexForEvent(
  stops: readonly ElectionSliderStop[],
  eventId: string | null,
): number {
  if (!eventId) return stops.length - 1;
  const i = stops.findIndex((s) => s.event_id === eventId);
  return i >= 0 ? i : stops.length - 1;
}
