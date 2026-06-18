/**
 * year-compare-picker-model: pure option projection for the compare-page
 * year-chip strips (originally PR1 of
 * TODO/20260617-election-compare-ux-overhaul-plan.md; the dropdown
 * `<YearComparePicker>` it fed was retired 2026-06-18 in favour of inline
 * tap-to-compare on the rail + inline From/To chip strips on the compare
 * page - a dropdown was the 1990 pattern the citizen rejected).
 *
 * Still the single place that decides option ordering + the disabled
 * (other-axis) flag for the compare page's From / To selectors (options =
 * every same-body event, with the year pinned on the OTHER axis disabled).
 * The rail now resolves its earlier-event targets directly from the rail
 * model's `compare_options`.
 *
 * The consumer renders whatever option list it is handed; this module
 * is the only place that decides ordering + the disabled flag, so vitest
 * pins the contract without mounting Svelte. Same inputs -> same output.
 */

/** Minimal source shape this model reads. The rail's `SiblingEventChip`
 *  and the compare page's synthesised list both satisfy it structurally,
 *  so neither caller needs an adapter. */
export interface YearPickerSourceEvent {
  event_id: string;
  /** Citizen-facing year label, e.g. "2024" (or "2005 FEB" for the
   *  v1.4 collision grammar). Pre-derived by the caller. */
  year_label: string;
  /** Winner party colour hex for the 2px option underline; null falls
   *  back to the slate baseline in the component. */
  winner_color_hex: string | null;
  /** ISO YYYY-MM-DD poll date - the time anchor the forward-time
   *  builder (`buildTimeOrderedYearOptions`) compares on. Optional so
   *  the older `buildYearPickerOptions` callers (which never read it)
   *  need not supply it. */
  polled_on?: string;
}

/** One selectable year in the picker popover. */
export interface YearPickerOption {
  event_id: string;
  year_label: string;
  winner_color_hex: string | null;
  /** True for the year already pinned on the other axis (the current
   *  event, or the From year when building the To picker). Rendered
   *  non-interactive so the citizen cannot compare an event with
   *  itself. */
  is_disabled: boolean;
}

/**
 * Project a (pre-sorted) source event list into picker options.
 *
 * Ordering is preserved verbatim - the caller sorts (the rail + compare
 * page both pass oldest-to-newest). The single `excludeEventId` is
 * flagged `is_disabled` rather than dropped, so the citizen still sees
 * the year they are anchored on (greyed) rather than a gap in the list.
 */
export function buildYearPickerOptions(
  events: readonly YearPickerSourceEvent[],
  opts: { excludeEventId?: string } = {},
): YearPickerOption[] {
  return events.map((e) => ({
    event_id: e.event_id,
    year_label: e.year_label,
    winner_color_hex: e.winner_color_hex,
    is_disabled:
      opts.excludeEventId !== undefined && e.event_id === opts.excludeEventId,
  }));
}

/**
 * Project options for ONE of the two compare-page year selectors with a
 * FORWARD-TIME constraint (Jony + Citizen 2026-06-18): a comparison
 * always reads oldest -> newest, never in reverse.
 *
 * For the `earlier` selector every event at/after the `later` selection
 * is disabled; for the `later` selector every event at/before the
 * `earlier` selection is disabled. This single rule bans BOTH a
 * reverse-in-time pair AND the same year on both sides, while still
 * allowing any GAP (adjacent years or N-5 vs N). Disabled options are
 * greyed in place (never removed) so the list does not reflow under the
 * thumb. Ordering is preserved (caller sorts oldest-first).
 *
 * `otherPolledOn` is the poll date of the year selected on the OTHER
 * selector; null/undefined disables nothing (e.g. before both resolve).
 */
export function buildTimeOrderedYearOptions(
  events: readonly YearPickerSourceEvent[],
  opts: { role: "earlier" | "later"; otherPolledOn: string | null },
): YearPickerOption[] {
  const other = opts.otherPolledOn;
  return events.map((e) => {
    let is_disabled = false;
    if (other && e.polled_on) {
      is_disabled =
        opts.role === "earlier" ? e.polled_on >= other : e.polled_on <= other;
    }
    return {
      event_id: e.event_id,
      year_label: e.year_label,
      winner_color_hex: e.winner_color_hex,
      is_disabled,
    };
  });
}
