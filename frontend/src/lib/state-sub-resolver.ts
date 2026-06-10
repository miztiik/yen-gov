// Depth-2 state-sub dispatcher for the place-first URL grammar (ADR-0037).
//
// Resolves `/<state>/<position2>` to one of four kinds: a district landing,
// an AC drill-down, a chrome surface (reserved token like `explore`,
// `party`, `ac`, `t`), or notfound. Pure dispatch - no fetch, no DuckDB,
// no async, no DOM. Registries are passed in by the caller (the
// `routes/StateSubRouter.svelte` mount-time loader) so this module is
// 100% unit-testable in isolation.
//
// Deferral 1 of TODO/20260609-url-prefix-drop-phase0-plan.md (Jony's
// verdict): the live route was `/<state>/d/<district>`; the `/d/` literal
// marker is scaffolding noise ("citizen forwarding
// yen-gov.in/tamil-nadu/d/chennai over WhatsApp is sharing a system
// internal"), so this dispatcher drops it and resolves the second
// positional segment against three registries. The fourth registry
// (indicator slugs) is named-but-empty for now; Deferral 2 ships it.
//
// ## Resolution order (LOAD-BEARING, Jony rule #4)
//
//   1. reserved   - chrome surfaces always win over data slugs.
//   2. districts  - first-registered slug wins on collision.
//   3. acs        - second-registered loses on collision; the AC is
//                   still reachable via the canonical event-nested URL
//                   (see Option A note below).
//   4. notfound   - falls through to the NotFound surface.
//
// NEVER alphabetical, NEVER type-priority-by-namespace. The order is
// the contract the build-time tests pin.
//
// ## Option A (ratified 2026-06-10) — resolver-as-gate doctrine
//
// District / AC name collisions are a DESIGN BASELINE on the Indian
// electoral corpus, not a bug to be renamed away. Verified 2026-06-10:
// **401 (state, slug) pairs across 25 states** have a district name
// equal to an AC name in the same state. The corpus is honest about
// the underlying geography (many ACs are named after their district
// HQ - `Coimbatore` AC inside Coimbatore district is the rule, not
// the exception); the URL surface honours that by resolving
// district-first per the order above.
//
// What this means for the colliding AC: it is still reachable via the
// canonical event-nested URL
//
//   /<state>/elections/<event>/ac/<ac>
//
// per ADR-0052. The bare positional URL `/<state>/<slug>` was always a
// convenience entry for the AC, never a canonical resource; Option A
// formalises that. See `docs/architecture/frontend/routing.md` §
// "Depth-2 dispatcher resolution rule" for the citizen-facing
// implication and the link to the optional Hans+Max-signed-off corpus
// rename (deferred; NOT BLOCKING) in
// `TODO/20260609-url-prefix-drop-phase0-plan.md` § "Follow-up
// deferrals".
//
// The build-time gate at
// `frontend/src/contracts/url-namespace-disjointness.test.ts` does
// NOT strict-assert per-state district vs AC disjointness (the
// describe block "Deferral 1 per-state resolver gate (districts vs
// ACs; Option A)" carries the positive presence-of-collisions check
// instead). The other six pairwise disjointness contracts there
// (state⊥topic, state⊥reserved, topic⊥reserved, ac⊥state, ac⊥topic,
// ac⊥reserved) STAY strict - those collision classes are real bugs
// and Option A does not relax any of them.
//
// ## Why "registries-as-arg" (Fowler's verdict)
//
// Keeps the dispatch pure; the caller is responsible for loading the
// right rowset (per-state districts + per-state ACs) and for slug
// normalisation (the resolver does NOT lowercase its inputs - bad
// slug hygiene at the URL parser belongs there, not here). A reserved
// token registry separate from the data registries lets
// `links.ts:RESERVED_PATH_TOKENS` stay the single source of truth and
// lets the resolver enforce Jony rule #3 (reserved tokens stay
// reserved as future escape hatches even when the corresponding ROUTE
// entry is gone).

/** District registry row. Just enough to render a district landing. */
export interface DistrictRow {
  /** Canonical district entity_id (e.g. "IN-S22-D569"). */
  entity_id: string;
  /** Citizen-readable district name from entities.json (e.g. "Coimbatore"). */
  display_name: string;
}

/** AC registry row. Carries the eci_no the Constituency route needs. */
export interface AcRow {
  /** Canonical AC entity_id (e.g. "IN-AC-2008-tamil-nadu-3881"). */
  entity_id: string;
  /** Citizen-readable AC name (e.g. "Mylapore"). */
  name: string;
  /** ECI assembly-constituency number (e.g. 25). */
  eci_no: number;
}

/**
 * The three registries the resolver dispatches against. The 4th registry
 * (indicator slugs) is named-but-empty for now; Deferral 2 of the URL
 * prefix drop plan adds it. Each Map is keyed on the URL slug
 * (lowercase, dash-separated) that appears at position 2 of the URL.
 */
export interface StateSubRegistries {
  /** Reserved chrome tokens from `links.ts:RESERVED_PATH_TOKENS`. */
  reserved: ReadonlySet<string>;
  /** Map of district slug -> {entity_id, display_name} for this state. */
  districts: ReadonlyMap<string, DistrictRow>;
  /** Map of AC slug -> {entity_id, name, eci_no} for this state. */
  acs: ReadonlyMap<string, AcRow>;
}

/**
 * Discriminated union over the four dispatch outcomes. Exhaustiveness
 * checking on `kind` is enforced by the test file - any new kind must
 * land with a matching switch arm.
 */
export type StateSubResult =
  | { kind: "district"; payload: DistrictRow }
  | { kind: "ac"; payload: AcRow }
  | { kind: "chrome"; payload: { token: string } }
  | { kind: "notfound"; payload: null };

/**
 * Resolve `/<state>/<position2>` to one of the four kinds.
 *
 * Pure synchronous dispatch. The caller MUST pass slug-normalised
 * registries (lowercase, dash-separated) and a slug-normalised
 * `position2`; the resolver does not normalise on its behalf so that
 * misnormalised input fails loud at the test boundary, not silently at
 * the dispatch boundary.
 *
 * @param _state    The state slug at position 1 (e.g. "tamil-nadu"). Not
 *                  consulted by the resolver itself - the caller has
 *                  already filtered the district + AC registries to this
 *                  state - but kept in the signature so the parameter list
 *                  documents the URL grammar at the type boundary.
 * @param position2 The second URL segment (e.g. "mylapore", "coimbatore",
 *                  "explore"). Looked up against reserved, then
 *                  districts, then acs.
 * @param r         The three registries (see {@link StateSubRegistries}).
 * @returns         A discriminated union over the four dispatch outcomes.
 *
 * Resolution order (Jony rule #4, LOAD-BEARING):
 *   1. reserved   - chrome surfaces always win over data slugs
 *   2. districts  - first-registered slug wins on collision
 *   3. acs        - second-registered loses; the AC stays reachable
 *                   via the canonical event-nested URL
 *                   `/<state>/elections/<event>/ac/<ac>` (ADR-0052)
 *                   per the Option A doctrine in the module
 *                   docstring above
 *   4. notfound   - falls through to the NotFound surface
 */
export function resolveStateSub(
  _state: string,
  position2: string,
  r: StateSubRegistries,
): StateSubResult {
  if (r.reserved.has(position2)) {
    return { kind: "chrome", payload: { token: position2 } };
  }
  const district = r.districts.get(position2);
  if (district) {
    return { kind: "district", payload: district };
  }
  const ac = r.acs.get(position2);
  if (ac) {
    return { kind: "ac", payload: ac };
  }
  return { kind: "notfound", payload: null };
}
