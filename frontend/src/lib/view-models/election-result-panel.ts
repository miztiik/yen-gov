// Pure helper for the StateElection / NationalElection event-view
// panel-state machine.
//
// Bug (PR fix/state-parl-seats-0-loader, 2026-06-12): the state Parliament
// event pages were showing "Seats 0 / No constituency rows yet" for the
// ~5-second window between DOM-ready and DuckDB-WASM finishing the JOIN
// against parliament/election=<yr>/summary.csv + data/entities/electoral.csv.
// The data was on disk (verified end-to-end via DuckDB: 48 MH PCs for both
// 2024 and 2019), the JOIN ran clean (zero unmatched entity_ids), all 17
// CSV requests succeeded, no console errors. The visual symptom came from
// the template not differentiating between LOADER-IN-FLIGHT and
// EMPTY-AFTER-OK:
//
//   * `winners = []` when LoaderResult is `loading` (the derived only
//     accepted `ok` or `partial`).
//   * `kpis.total_seats = 0` because winners is empty.
//   * `seat_rows.length === 0` so the table rendered "No constituency rows yet."
//   * `top_parties.length === 0` so the bar rendered "No party totals yet."
//   * The `pending` derived only fired on `partial` / `ok-with-zero` -
//     NOT on `loading` - so the calm "Results for this election are
//     not published yet" callout did not show either.
//
// Citizens saw "Seats 0" for several seconds and reasonably assumed the
// data was missing. Structural fix per CLAUDE.md §5: introduce a typed
// panel-state enum that distinguishes the four citizen-visible UI states,
// and let the template branch on it. Pure helper extracted here so the
// no-`@testing-library/svelte` test regime can pin the contract without
// mounting the Svelte component (see Skeleton.test.ts precedent + the
// /memories/lessons.md note on the project's no-jsdom-mounts policy).

import type { LoaderResult } from "../loader-result";

/** What the event-view page's data-bearing sections should render. */
export type EventPanelState =
  /** Loader still in flight. Sections render a loading affordance
   *  (skeleton / "—" placeholders) - never "0 seats" or "no rows yet". */
  | "loading"
  /** Loader returned with no rows because the publisher has not
   *  released data yet (status: "partial"). Sections render the calm
   *  pending callout. */
  | "pending"
  /** Loader returned 0 rows with status "ok" - i.e. the data file
   *  exists and parsed cleanly but contains no rows for this scope.
   *  Sections render the empty-state copy. */
  | "empty"
  /** Loader returned >= 1 row. Sections render real data. */
  | "data"
  /** Loader threw (status: "failed"). The error banner is rendered
   *  elsewhere; data-bearing sections should suppress themselves. */
  | "error";

/** Map (loader status, post-filter row count) -> panel state.
 *
 *  `filteredCount` is the number of rows AFTER any client-side filter
 *  the consumer applies (e.g. StateElection's `row.state_slug ===
 *  params.state` filter on top of a NATIONAL-PC fetch). The
 *  distinction matters only for the `data` vs `empty` arm; loading /
 *  pending / error short-circuit before any filter consideration. */
export function pickEventPanelState<T>(
  result: LoaderResult<T[]>,
  filteredCount: number,
): EventPanelState {
  if (result.status === "loading") return "loading";
  if (result.status === "failed") return "error";
  if (result.status === "partial") return "pending";
  // status === "ok"
  return filteredCount === 0 ? "empty" : "data";
}
