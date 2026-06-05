// ChartShell state helpers (U5 sub-plan U5a, parent plan section 23.5).
//
// Parent plan section 23.5: "Error/empty states fold into the existing
// ChartShell (U5), no new component: loading -> Skeleton, fetch-fail ->
// 'Data unavailable' + source line, zero-rows -> the no-data hatch
// swatch."
//
// This module is the pure surface: a state enum + the resolver that
// normalises `null` / `undefined` to the default "data" state + the
// two default-copy constants. The renderer (ChartShell.svelte) imports
// these to decide which body slot to mount; vitest covers the resolver
// in node-env (no DOM mount needed, mirrors the existing
// `chart-shell/actions.ts` + `actions.test.ts` shape).

/**
 * Closed enum of ChartShell body states. The renderer mounts a
 * different body slot per branch:
 *
 *   - "loading" -> `<Skeleton />` (default) or the caller's
 *                  `loading_slot` snippet.
 *   - "error"   -> "Data unavailable" + an optional source line
 *                  (caller-supplied) so the citizen knows WHICH
 *                  publisher failed.
 *   - "empty"   -> a small inline diagonal-stripe hatch swatch +
 *                  "No data for this selection." (default) so a true
 *                  zero-rows result is visually distinct from a
 *                  loading or failed state.
 *   - "data"    -> the caller's `children` snippet (the chart).
 *
 * The header (title / subtitle / toolbar / honesty banners) and footer
 * (sources / actions) ride UNCHANGED in every state - the chrome stays
 * consistent so the citizen does not lose context when a chart fails
 * or returns nothing. This is the central UX point of the rational
 * chart-viz doctrine in parent plan section 21.9.
 */
export type ChartShellState = "loading" | "error" | "empty" | "data";

/**
 * Citizen-readable default for the error state. Surfaced as the leading
 * paragraph when the caller does not pass an `error_message` prop. Kept
 * deliberately short so it pairs cleanly with the optional source-line
 * snippet ("Source: RBI, fetched 2026-05-11" or similar).
 */
export const DEFAULT_ERROR_MESSAGE = "Data unavailable";

/**
 * Citizen-readable default for the empty state. Renders below the
 * inline hatch swatch when the caller does not pass an `empty_message`
 * prop. The hatch + the message together signal "we ran the query,
 * the publisher had no rows for this selection" (distinct from a
 * loading or failed state).
 */
export const DEFAULT_EMPTY_MESSAGE = "No data for this selection.";

/**
 * Normalise the caller's state prop to a valid `ChartShellState`.
 * Treats `null` / `undefined` as "data" (the default rendering branch)
 * so a renderer that does not opt into the new states keeps its
 * pre-U5a behaviour byte-for-byte. Returns the input unchanged when it
 * is already a valid state.
 *
 * Pure: no side effects. Defensive against any non-typed JS call site;
 * the TS signature already covers the typed branch.
 */
export function resolveChartShellState(
  state: ChartShellState | null | undefined,
): ChartShellState {
  if (state === "loading" || state === "error" || state === "empty") {
    return state;
  }
  return "data";
}
