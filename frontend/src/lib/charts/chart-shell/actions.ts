// ChartShell — pure footer-action helpers. No Svelte, no DOM, no state.
//
// These helpers are the **gate** between caller-supplied action specs
// and what the renderer is allowed to draw. Closing the action
// vocabulary here (not in the renderer) means the Phase 1.4 test
// "action footer does not render unapproved controls" is one vitest
// case, not a Playwright crawl across every chart route.

import type {
  ChartShellAction,
  ChartShellActionSpec,
} from "./types";

/**
 * The closed enum of footer actions ChartShell may render. Frozen so
 * downstream code cannot mutate the policy at runtime. Order here is
 * the **canonical display order** consumed by `sortActionsForFooter`.
 *
 * Adding an action requires editing three places in lockstep:
 *
 *   1. `ChartShellAction` union in `./types.ts`.
 *   2. This array (and its `as const` literal types stay in sync via
 *      TypeScript's `satisfies` clause below).
 *   3. The Phase 1.4 plan task list in
 *      `TODO/20260518-frontend-charting-modernisation-plan.md`.
 */
export const ALLOWED_ACTIONS = Object.freeze([
  "view_data",
  "download",
  "copy_link",
  "share",
  "reset_view",
  "full_range",
] as const) satisfies readonly ChartShellAction[];

/**
 * Drop any spec whose `id` is not in `ALLOWED_ACTIONS`. Preserves input
 * order (stable). Returns the same reference type as input so callers
 * can compose with `sortActionsForFooter` downstream.
 *
 * This is the **policy seam**: the renderer never inspects ids, it
 * trusts that the array it receives has already been filtered.
 */
export function filterAllowedActions(
  actions: readonly ChartShellActionSpec[],
): readonly ChartShellActionSpec[] {
  const allowed = new Set<ChartShellAction>(ALLOWED_ACTIONS);
  return actions.filter(a => allowed.has(a.id));
}

/**
 * Sort actions for footer display using the canonical order in
 * `ALLOWED_ACTIONS`. Unknown ids (if any survive `filterAllowedActions`
 * — they shouldn't, but defence-in-depth) sort to the end in stable
 * insertion order.
 *
 * Stable: equal ranks keep their input order, so the view-model can
 * tie-break locally if it wants (e.g. "download" twice for SVG+CSV).
 */
export function sortActionsForFooter(
  actions: readonly ChartShellActionSpec[],
): readonly ChartShellActionSpec[] {
  const rank = new Map<ChartShellAction, number>(
    ALLOWED_ACTIONS.map((id, idx) => [id, idx]),
  );
  // decorate-sort-undecorate to keep the sort stable in browsers that
  // historically did not guarantee Array.prototype.sort stability.
  return actions
    .map((spec, idx) => ({
      spec,
      rank: rank.get(spec.id) ?? Number.MAX_SAFE_INTEGER,
      idx,
    }))
    .sort((a, b) => a.rank - b.rank || a.idx - b.idx)
    .map(({ spec }) => spec);
}
