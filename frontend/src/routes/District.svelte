<script lang="ts">
  // Per-state per-district landing (/s/:state/d/:district).
  //
  // U2a (sub-plan TODO/20260605-u2-breadcrumb-drawer-district-subplan.md):
  // minimal placeholder route that adds the URL grammar's district node so
  // the U2b breadcrumb spine (renamed to Breadcrumb in PR-W1d) has
  // somewhere to ascend TO. Scope is intentionally
  // small - resolve the LGD district by slug + parent state code, render
  // the place heading, surface a one-paragraph placeholder body referencing
  // the future chart surface. The breadcrumb spine and the chart canvas
  // both lift in later sub-rows; THIS file ships ONLY the URL node + the
  // placeholder so a citizen who follows the new builder lands somewhere
  // reasonable instead of NotFound.
  //
  // Resolution path:
  //   params.state         -> state ECI code via states.codeFromSlug
  //   params.district_slug -> LGD district via loadAllDistrictEntities,
  //                           matching slugify(display_name) + parent state
  //
  // 404 behaviour (never blank, never crash):
  //   * states.json not yet loaded         -> "Loading..."
  //   * unknown state slug                 -> "State not found" panel
  //   * districts loaded + slug unknown    -> "District not found" panel
  //   * districts loader threw             -> "Could not load districts"
  //
  // Per parent plan section 23.5: geo lives in the PATH, never a querystring.
  // The reserved `/sd/:subdistrict` shape is NOT registered here (a future
  // chunk lifts subdistrict-grain data); see main.ts route registration.

  import { loadAllDistrictEntities, type DistrictEntity } from "../lib/view-models/districts";
  import { slugify } from "../lib/slug";
  import { states } from "../lib/states.svelte";
  import { link } from "../lib/links";
  import Breadcrumb from "../lib/Breadcrumb.svelte";
  import { route } from "../lib/router.svelte";

  interface Props {
    params: { state: string; district_slug: string };
  }
  let { params }: Props = $props();

  // Resolve the slug -> ECI state code via the reactive states store.
  // Null while states.json hasn't loaded OR when the slug is unknown.
  const state_code = $derived(states.codeFromSlug(params.state));
  const state_name = $derived(state_code ? states.name(state_code) : "");

  // Districts loader is national-scope; cached per page-load inside
  // loadAllDistrictEntities. Match the citizen-supplied slug against
  // slugify(display_name) AND verify parent state to disambiguate the
  // (rare) cross-state slug collision.
  let districts = $state<DistrictEntity[] | null>(null);
  let load_error = $state<string | null>(null);
  loadAllDistrictEntities()
    .then(d => (districts = d))
    .catch(e => (load_error = String(e)));

  const district = $derived<DistrictEntity | null>(
    districts && state_code
      ? districts.find(
          d =>
            slugify(d.display_name) === params.district_slug &&
            d.parent_entity_id === `IN-${state_code}`,
        ) ?? null
      : null,
  );

  const states_loading = $derived(!states.isLoaded);
  const districts_loading = $derived(districts === null && load_error === null);

  // PR-W1d: per-route crumb chain. Reactive on route navigation AND
  // on async catalogue load (the builder reads states.svelte inside).
  const crumbs = $derived(route.crumbs ? route.crumbs(route.params) : []);
</script>

<Breadcrumb {crumbs} />

<main class="max-w-3xl mx-auto p-4 sm:p-6 space-y-6">
  {#if load_error}
    <div class="rounded border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
      Could not load districts: <code>{load_error}</code>
    </div>
  {:else if states_loading || districts_loading}
    <p class="text-sm text-slate-500">Loading...</p>
  {:else if !state_code}
    <div class="space-y-2">
      <p class="text-sm">
        <a href={link.home()} class="text-sky-700 hover:underline">&larr; Home</a>
      </p>
      <h1 class="text-2xl font-semibold">State not found</h1>
      <p class="text-sm text-slate-600">
        No state with slug <code class="rounded bg-slate-100 px-1">{params.state}</code>.
        Pick a state from the <a href={link.home()} class="text-sky-700 hover:underline">home page</a>.
      </p>
    </div>
  {:else if !district}
    <div class="space-y-2">
      <p class="text-sm">
        <a href={link.state(state_code)} class="text-sky-700 hover:underline"
          >&larr; {state_name}</a
        >
      </p>
      <h1 class="text-2xl font-semibold">District not found</h1>
      <p class="text-sm text-slate-600">
        No district with slug <code class="rounded bg-slate-100 px-1">{params.district_slug}</code>
        in {state_name}.
      </p>
    </div>
  {:else}
    <header class="space-y-2">
      <h1 class="text-2xl font-semibold">{district.display_name}</h1>
      <p class="text-sm text-slate-500">{state_name} &middot; LGD code {district.lgd_code}</p>
    </header>

    <section class="rounded border border-slate-200 bg-white p-4 text-sm text-slate-700 space-y-2">
      <p>
        District-grain data surface is coming. This page exists today as the
        place-first landing for {district.display_name} so deep links to the
        district resolve to something citizen-readable.
      </p>
      <p class="text-xs text-slate-500">
        Future chunks will surface district-grain indicators (literacy, fiscal,
        health) and the district map alongside the state context.
      </p>
    </section>
  {/if}
</main>
