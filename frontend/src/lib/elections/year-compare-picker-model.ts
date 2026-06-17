/**
 * year-compare-picker-model: pure option projection for the reusable
 * `<YearComparePicker>` popover (PR1 of
 * TODO/20260617-election-compare-ux-overhaul-plan.md).
 *
 * ONE picker primitive serves two surfaces (section 2b):
 *   - the sibling rail's "Compare" entry (options = the earlier
 *     same-body events the current one can be compared against); and
 *   - the compare page's From / To selectors (options = every same-body
 *     event, with the year already pinned on the OTHER axis disabled).
 *
 * The component renders whatever option list it is handed; this module
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
