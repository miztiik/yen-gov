// Breadcrumb data contract shared by the rendering component
// (Breadcrumb.svelte) and the per-route crumb builders (route-crumbs.ts).
//
// PR-W1d (election experience overhaul, 2026-06-10): a single Crumb[]
// shape feeds ONE rendering component across both the election cascades
// (state -> state-elections -> event -> AC) AND the socio-econ
// cascades (state -> topic -> indicator). The previous place-first
// derivation lived inside GeoBreadcrumb.svelte's `computeCrumbs`; PR-W1d
// lifts it out to per-route builders so each route owns its own chain.

/** One crumb in the breadcrumb trail. */
export interface Crumb {
  /** Citizen-visible label (e.g. "Tamil Nadu", "Mylapore"). */
  label: string;
  /** Ascend URL. Omit on the leaf (the current page is not clickable). */
  href?: string;
  /** True for the rightmost crumb (terminal; rendered as a `<span>` with
   * `aria-current="page"`, never as a link). */
  isLeaf?: boolean;
}
