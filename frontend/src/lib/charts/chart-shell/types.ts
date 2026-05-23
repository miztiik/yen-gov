// ChartShell — typed contract for the shared chart shell/footer primitive
// shipped in Phase 1.4 task 1 of
// `docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md`.
//
// This file is the **contract** — types only, no runtime, no Svelte.
// The renderer (`frontend/src/lib/charts/ChartShell.svelte`) imports
// from here; pure helpers (`./actions.ts`) consume the same types.
// Adapter / view-model code emits values typed against this contract.
//
// Doctrine ties:
//
//   - R-08 Branch by Abstraction. Ships ALONGSIDE every existing chart
//     renderer (StackedTrendV2, SeatDonut, MarginHistogram, …). v1 chart
//     headers / footers continue to ship; per-caller migration follows
//     in dedicated PRs once each renderer is ready to consume the shell.
//
//   - R-24 Fetch-telemetry-free chrome. The shell hosts the v2.0
//     `SourceListV2` slot which already refuses url / fetched_at /
//     content_hash. No telemetry leaks here either.
//
//   - R-28 Manifest-registered sources only. The shell receives a
//     `readonly SourceV2Row[]` resolved upstream from `taxonomy.sources`
//     via the manifest-registered `table_id`. No direct parquet path.
//
//   - Action vocabulary is a **closed enum** (see `ALLOWED_ACTIONS`
//     below). The renderer drops unknown ids silently — Phase 1.4
//     contract test "action footer does not render unapproved controls".
//     Any new action requires this file + `actions.ts` + the plan to be
//     edited together.

import type { SourceV2Row } from "../../source-list-v2/types";

/**
 * The closed enum of footer actions the chart shell is allowed to
 * render. Order here is also the **canonical display order** in the
 * footer toolbar (see `sortActionsForFooter` in `./actions.ts`).
 *
 * Per Phase 1.4 plan task 4: "Add footer action slots for `view_data`,
 * `download`, `copy_link/share`, `reset_view`, and `full_range`".
 *
 *   - `view_data`   — open the visible rows in a tabular view
 *                     (currently visible window first, not the whole
 *                     indicator corpus — plan rule).
 *   - `download`    — file-export (SVG/PNG/CSV; renderer decides which).
 *   - `copy_link`   — copy the deep-link URL to clipboard. Distinct
 *                     from `share` so a renderer can offer one or both.
 *   - `share`       — Web Share API invocation. Falls back to copy_link
 *                     when navigator.share is absent.
 *   - `reset_view`  — clear pin / zoom / brush state. View-model decides
 *                     whether it has any state to reset.
 *   - `full_range`  — reset temporal viewport to full domain (Phase 1.5
 *                     brush companion; distinct from `reset_view` which
 *                     covers non-temporal interaction state).
 */
export type ChartShellAction =
  | "view_data"
  | "download"
  | "copy_link"
  | "share"
  | "reset_view"
  | "full_range";

/**
 * A single action button spec passed to ChartShell. The view-model
 * decides whether the action is **useful** for this render (per plan:
 * "actions appear only when the view-model says they are useful") and
 * supplies the click handler.
 *
 *   - `id`         — must be one of `ChartShellAction`. Unknown ids
 *                    are dropped by `filterAllowedActions`.
 *   - `label`      — citizen-readable text shown on the button.
 *   - `on_invoke`  — sync click handler. Renderer wires it to onclick.
 *   - `disabled?`  — optional. Disabled buttons render greyed-out.
 */
export interface ChartShellActionSpec {
  readonly id: ChartShellAction;
  readonly label: string;
  readonly on_invoke: () => void;
  readonly disabled?: boolean;
}

/**
 * Inline honesty disclosure rendered above the chart body. Mirrors the
 * shape of `StackedTrendV2Honesty` but at the **shell** level so every
 * renderer (donut, bar, choropleth, line) can surface the same
 * comparability / series-break / unit-change / vintage / missing-data
 * caveats without re-implementing the chip strip.
 */
export type ChartShellHonestyKind =
  | "comparability"
  | "series_break"
  | "unit_change"
  | "vintage"
  | "missing_data"
  | "note";

export interface ChartShellHonestyBanner {
  readonly kind: ChartShellHonestyKind;
  readonly text: string;
}

/**
 * Re-export the source-row type the footer slot consumes. Keeps the
 * caller free to import everything ChartShell-related from this one
 * module barrel without reaching across the chart-shell / source-list-v2
 * boundary.
 */
export type { SourceV2Row };
