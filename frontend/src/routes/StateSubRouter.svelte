<script lang="ts">
  // Depth-2 state-sub dispatcher (route pattern `/:state/:position2`).
  //
  // Deferral 1 of TODO/20260609-url-prefix-drop-phase0-plan.md: this is
  // the route component that drops the `/d/` literal marker and resolves
  // the second positional segment against three registries (reserved
  // chrome / district / AC). Resolution + design rationale: see the
  // header docstring on `frontend/src/lib/state-sub-resolver.ts`.
  //
  // What this component does:
  //
  //   1. Resolves params.state (slug or ECI code) -> ECI code via the
  //      reactive `states` store. While the states catalogue is async-
  //      loading, the dispatcher renders a small "Loading..." chrome
  //      panel rather than guessing.
  //
  //   2. Loads three async registries in parallel:
  //        a) districts:    loadAllDistrictEntities() (entities.json),
  //                         filtered to this state by parent_entity_id.
  //        b) acs:          fetchConstituencies(eci_code) (per-state
  //                         constituencies.json), name + eci_no rows.
  //        c) events:       fetchElectionEvents() (taxonomy/
  //                         election_events.json) for the default
  //                         event resolution (AC dispatch needs an
  //                         event to short-circuit Constituency's
  //                         bare-AC redirect; see ADR-0052).
  //
  //   3. Builds the registries (reserved-tokens + district slug map +
  //      AC slug map) and calls the pure dispatcher.
  //
  //   4. Mutates the reactive `route.params` + `route.crumbs` so the
  //      mounted child's Breadcrumb sees the right shape (the child
  //      uses `route.crumbs(route.params)`, not the parent's
  //      params). Without this mutation, the child Breadcrumb would
  //      see `{state, position2}` instead of `{state, district_slug}`
  //      / `{state, ac_slug, eci_no, event}` and the chain would mis-
  //      label.
  //
  //   5. Conditionally renders <District /> | <Constituency /> |
  //      <NotFound /> based on the dispatch kind. Chrome-token dispatch
  //      shouldn't happen at runtime (the route table already mounts
  //      chrome literals on their own routes before this depth-2 catch-
  //      all); when it does (defensive), this dispatcher renders
  //      NotFound rather than silently falling through.
  //
  // Why the dispatcher pre-resolves the AC's default event (vs leaving
  // Constituency's bare-AC effect to run): Constituency.svelte's
  // bare-AC effect navigates to the canonical 5-segment URL, which on
  // a name-only slug like `mylapore` would then resolve to eci_no=-1
  // (parseAcSlug returns null for name slugs - it expects a numeric
  // prefix). Passing the event AND eci_no in directly keeps the
  // citizen on the positional URL and skips the redirect entirely.
  // The redirect path stays alive for the legacy `/<state>/ac/<n>`
  // entry where the slug carries a numeric prefix.
  //
  // Pre-existing /s/ leftover in Constituency.svelte: PR-P4 deleted the
  // `/s/*` route but missed the redirect string in Constituency. That
  // bug is bundled into this PR (1-line scoped fix) because Deferral 1's
  // AC smoke test requires the redirect to land on a live Grammar A
  // URL, not a dead `/s/...` 404.

  import { onMount } from "svelte";
  import {
    resolveStateSub,
    type AcRow,
    type DistrictRow,
    type StateSubRegistries,
    type StateSubResult,
  } from "../lib/state-sub-resolver";
  import { RESERVED_PATH_TOKENS } from "../lib/links";
  import { loadAllDistrictEntities, type DistrictEntity } from "../lib/view-models/districts";
  import { fetchConstituencies, type ConstituencyEntry } from "../lib/data";
  import {
    fetchElectionEvents,
    defaultEventForState,
    type ElectionEventsCatalogue,
  } from "../lib/election-events";
  import { slugify } from "../lib/slug";
  import { states } from "../lib/states.svelte";
  import { route } from "../lib/router.svelte";
  import {
    districtCrumbs,
    constituencyBareCrumbs,
    notFoundCrumbs,
  } from "../lib/route-crumbs";
  import District from "./District.svelte";
  import Constituency from "./Constituency.svelte";
  import NotFound from "./NotFound.svelte";
  import PageContainer from "../lib/layout/PageContainer.svelte";

  interface Props {
    params: { state: string; position2: string };
  }
  let { params }: Props = $props();

  // Frozen reserved-token set, shared across calls. The cast lifts the
  // tuple's readonly element type to plain string for the Set generic.
  const RESERVED_SET = new Set<string>(
    RESERVED_PATH_TOKENS as readonly string[],
  );

  // Async resolution state. The four kinds the dispatcher commits to
  // are mutually exclusive; `null` means "still loading registries,
  // render the loading chrome panel".
  let resolved = $state<StateSubResult | null>(null);
  let load_error = $state<string | null>(null);
  // AC dispatch needs the default event resolved up-front to short-
  // circuit Constituency.svelte's bare-AC redirect. `null` while
  // loading; the empty-event string is a no-op for non-AC dispatch.
  let default_event = $state<string | null>(null);

  const state_code = $derived(states.codeFromSlug(params.state));

  onMount(() => {
    void resolveAll();
  });

  async function resolveAll(): Promise<void> {
    try {
      // Wait for the states catalogue so codeFromSlug resolves. The
      // module-level void-promise in states.svelte fires this at
      // module load; we just spin until it lands.
      let attempts = 0;
      while (!states.isLoaded && attempts < 100) {
        await new Promise((r) => setTimeout(r, 25));
        attempts += 1;
      }
      const sc = states.codeFromSlug(params.state);
      if (!sc) {
        resolved = { kind: "notfound", payload: null };
        applyRouteShape({ kind: "notfound", payload: null });
        return;
      }

      // Load all three registries in parallel. fetchConstituencies can
      // 404 for states without a constituencies.json (test states /
      // pre-bootstrap states); on 404 fall back to an empty AC set
      // so dispatch can still resolve to district / notfound.
      const [districtsAll, constituencies, catalogue] = await Promise.all([
        loadAllDistrictEntities(),
        fetchConstituencies(sc).catch(() => null),
        fetchElectionEvents().catch(() => null),
      ]);

      const districtMap = buildDistrictMap(districtsAll, sc);
      const acMap = buildAcMap(constituencies);

      const registries: StateSubRegistries = {
        reserved: RESERVED_SET,
        districts: districtMap,
        acs: acMap,
      };
      const r = resolveStateSub(params.state, params.position2, registries);

      // Resolve the default event AC-only - districts + chrome don't
      // need it. defaultEventForState returns null when the state has
      // no catalogue rows; that's fine, Constituency will render its
      // own "no event" panel.
      if (r.kind === "ac") {
        default_event = pickDefaultEvent(catalogue, sc);
      }

      applyRouteShape(r);
      resolved = r;
    } catch (e) {
      load_error = String(e);
      // Failure-mode is NotFound (loud), not a blank render. Mirrors
      // District.svelte's loader-error UI pattern.
      resolved = { kind: "notfound", payload: null };
      applyRouteShape({ kind: "notfound", payload: null });
    }
  }

  function buildDistrictMap(
    rows: DistrictEntity[],
    sc: string,
  ): Map<string, DistrictRow> {
    const parent_eid = `IN-${sc}`;
    const m = new Map<string, DistrictRow>();
    for (const r of rows) {
      if (r.parent_entity_id !== parent_eid) continue;
      const slug = slugify(r.display_name);
      if (!slug) continue;
      // First-registered wins (matches the resolver's resolution
      // order rule); subsequent dupes are ignored at the registry
      // layer, not the resolver layer.
      if (!m.has(slug)) m.set(slug, { entity_id: r.entity_id, display_name: r.display_name });
    }
    return m;
  }

  function buildAcMap(
    constituencies: { constituencies: ConstituencyEntry[] } | null,
  ): Map<string, AcRow> {
    const m = new Map<string, AcRow>();
    if (!constituencies?.constituencies) return m;
    for (const c of constituencies.constituencies) {
      const slug = slugify(c.name);
      if (!slug) continue;
      if (!m.has(slug)) {
        m.set(slug, {
          // Synthesised entity_id: the constituencies.json shape does
          // not carry one. The resolver doesn't read it; only the
          // Constituency route consumes eci_no.
          entity_id: `${slug}-${c.eci_no}`,
          name: c.name,
          eci_no: c.eci_no,
        });
      }
    }
    return m;
  }

  function pickDefaultEvent(
    catalogue: ElectionEventsCatalogue | null,
    sc: string,
  ): string | null {
    return defaultEventForState(catalogue, sc)?.event_id ?? null;
  }

  // Mutate the reactive `route` store so the mounted child's
  // Breadcrumb (which reads route.crumbs + route.params) sees the
  // right shape. Without this the child's chain mis-labels (it would
  // see `{state, position2}` from the dispatcher route pattern).
  function applyRouteShape(r: StateSubResult): void {
    if (r.kind === "district") {
      route.params = { state: params.state, district_slug: params.position2 };
      route.crumbs = districtCrumbs;
    } else if (r.kind === "ac") {
      route.params = {
        state: params.state,
        ac_slug: params.position2,
        eci_no: r.payload.eci_no,
      };
      route.crumbs = constituencyBareCrumbs;
    } else {
      // chrome (defensive) + notfound both fall through to the 404
      // page. Chrome dispatch shouldn't reach here at runtime - the
      // route table mounts chrome literals on their own routes
      // before this depth-2 catch-all.
      route.params = { path: window.location.pathname };
      route.crumbs = notFoundCrumbs;
    }
  }
</script>

{#if load_error}
  <PageContainer width="narrow">
    <div
      class="rounded border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"
    >
      Could not resolve <code>/{params.state}/{params.position2}</code>:
      <code>{load_error}</code>
    </div>
  </PageContainer>
{:else if resolved === null}
  <PageContainer width="narrow">
    <p class="text-sm text-slate-500">Loading...</p>
  </PageContainer>
{:else if resolved.kind === "district"}
  <District params={{ state: params.state, district_slug: params.position2 }} />
{:else if resolved.kind === "ac"}
  <Constituency
    params={{
      state: params.state,
      eci_no: resolved.payload.eci_no,
      ac_slug: params.position2,
      ...(default_event ? { event: default_event } : {}),
    }}
  />
{:else}
  <NotFound params={{ path: typeof window === "undefined" ? "" : window.location.pathname }} />
{/if}
