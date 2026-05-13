<script lang="ts">
  // Generic indicator Compare (P4, ADR-0022).
  //
  // Route: `/compare?i=<indicator-id>&states=<slugs-csv>&peer=<peer-set-id>`
  //
  // This is the disciplined "tool route" for cross-state indicator
  // comparison — distinct from `/compare/:state/:event` (election Compare,
  // which keeps its own component). All three URL slots are optional:
  //
  //   i missing      → render a catalogue-driven indicator chooser. NOT
  //                    a 404. The route is reachable from the rail
  //                    without any prior state.
  //   i + no states  → render the full peer-restricted IndicatorRanked
  //                    plus a state-chip toggle row to pin states.
  //   i + states     → render IndicatorRanked with `pinned_states` set,
  //                    plus the toggle row pre-filled.
  //   peer present   → restricts the candidate pool. Pinned states are
  //                    always admitted regardless (citizen never loses
  //                    a state they explicitly asked for; rule mirrors
  //                    home_state honouring on /s/<state> hubs).
  //
  // The URL is the source of truth for every interaction here. User edits
  // (toggling a state chip, swapping the indicator, changing peer set)
  // write back via `history.replaceState` so the page is shareable but
  // doesn't bloat the back stack with intermediate tweaks.

  import { onMount } from "svelte";
  import { url } from "../lib/url";
  import {
    fetchTopicCatalogue,
    type TopicCatalogue,
    type CatalogueArtifact,
    type CatalogueTopic,
  } from "../lib/catalogue";
  import {
    fetchStateTiers,
    resolvePeerSet,
    type StateTiersFile,
  } from "../lib/state-tiers";
  import { states } from "../lib/states.svelte";
  import { STATE_NAME_TO_ECI } from "../lib/maplibre/sources";
  import IndicatorRanked from "../lib/IndicatorRanked.svelte";
  import {
    parseCompareQuery,
    serializeCompareQuery,
    type CompareQuery,
  } from "../lib/compare-query";

  // Reactive query mirror. Re-read on popstate so back/forward navigation
  // (and external `history.pushState` from the app router) stay in sync.
  let query = $state<CompareQuery>({ indicator: null, states: [], peer: null });

  function read_query(): void {
    if (typeof window === "undefined") return;
    query = parseCompareQuery(window.location.search);
  }

  function write_query(next: CompareQuery): void {
    if (typeof window === "undefined") return;
    const target =
      window.location.pathname + serializeCompareQuery(next) + window.location.hash;
    history.replaceState(null, "", target);
    query = next;
  }

  onMount(() => {
    read_query();
    window.addEventListener("popstate", read_query);
    return () => window.removeEventListener("popstate", read_query);
  });

  // Catalogue + tiers (best-effort; tiers may be absent in dev fixtures).
  let catalogue = $state<TopicCatalogue | null>(null);
  let catalogue_error = $state<string | null>(null);
  fetchTopicCatalogue()
    .then(c => (catalogue = c))
    .catch(e => (catalogue_error = String(e)));

  let state_tiers = $state<StateTiersFile | null>(null);
  fetchStateTiers()
    .then(t => (state_tiers = t))
    .catch(() => (state_tiers = null));

  // Build a flat (topic, indicator-artifact) list for the chooser. We
  // include only `kind: "indicator"` artifacts; election artifacts have
  // their own Compare route at `/compare/:state/:event`.
  type IndicatorOption = {
    topic: CatalogueTopic;
    artifact: CatalogueArtifact;
    indicator_id: string;
    label: string;
  };
  const indicator_options = $derived<IndicatorOption[]>(
    (catalogue?.topics ?? []).flatMap(t =>
      t.artifacts
        .filter(a => a.kind === "indicator")
        .map(a => ({
          topic: t,
          artifact: a,
          indicator_id: a.id,
          label: a.display ?? a.id,
        })),
    ),
  );

  // Look the chosen indicator up in the catalogue so we can show its
  // human title + topic context. Null when query.indicator is null OR
  // the id is not in the catalogue (shows a friendly "unknown indicator"
  // panel rather than 500-ing).
  const selected = $derived<IndicatorOption | null>(
    query.indicator
      ? indicator_options.find(o => o.indicator_id === query.indicator) ?? null
      : null,
  );

  const indicator_path = $derived<string | null>(
    selected ? `/indicators/in/${selected.indicator_id}.json` : null,
  );

  // Resolve peer set members. Null = no filter.
  const peer_members = $derived<string[] | null>(
    query.peer && state_tiers ? resolvePeerSet(state_tiers, query.peer) : null,
  );

  // Resolve URL state slugs to ECI codes. Unknown slugs are dropped
  // silently (the parser already shape-validates; this layer drops slugs
  // that don't resolve to a real state). The resolver may not be loaded
  // on first render, in which case we get nulls back; effect retries
  // once `states.isLoaded` flips.
  const pinned_codes = $derived<string[]>(
    query.states
      .map(slug => states.codeFromSlug(slug))
      .filter((c): c is string => c !== null),
  );

  // All states for the chip toggle row, alphabetised.
  const all_state_chips = $derived(
    Object.entries(STATE_NAME_TO_ECI)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([name, code]) => ({ name, code })),
  );

  function chip_pinned(code: string): boolean {
    return pinned_codes.includes(code);
  }

  function toggle_state_chip(code: string): void {
    const slug = states.slug(code);
    if (!slug) return;
    const next_states = query.states.includes(slug)
      ? query.states.filter(s => s !== slug)
      : [...query.states, slug];
    write_query({ ...query, states: next_states });
  }

  function clear_pins(): void {
    write_query({ ...query, states: [] });
  }

  function on_indicator_change(e: Event): void {
    const v = (e.target as HTMLSelectElement).value;
    write_query({ ...query, indicator: v || null });
  }

  function on_peer_change(e: Event): void {
    const v = (e.target as HTMLSelectElement).value;
    // The empty option's value is "" → null peer (no filter).
    write_query({ ...query, peer: v ? (v as CompareQuery["peer"]) : null });
  }

  // Peer-set chooser options come from state-tiers (only non-empty tiers
  // are offered; the catalogue's PEER_SET_VALUES is the schema, but the
  // dataset's actual coverage decides what's clickable). Falls back to a
  // single "All states" option until tiers load.
  const peer_options = $derived.by<{ value: string; label: string }[]>(() => {
    if (!state_tiers) return [{ value: "", label: "All states" }];
    return [
      { value: "", label: "All states" },
      ...state_tiers.tiers.map(t => ({ value: t.id, label: t.label })),
    ];
  });
</script>

<section class="p-4 sm:p-6 space-y-6 max-w-6xl">
  <header class="space-y-2">
    <nav aria-label="Breadcrumb" class="text-xs text-slate-500">
      <ol class="flex items-center gap-1 list-none p-0 m-0">
        <li><a href={url.topics()} class="hover:text-sky-700 hover:underline">Topics</a></li>
        <li aria-hidden="true" class="text-slate-400">›</li>
        <li class="text-slate-700" aria-current="page">Compare states</li>
      </ol>
    </nav>
    <div class="flex items-baseline justify-between gap-3 flex-wrap">
      <h1 class="text-2xl font-bold">Compare states</h1>
    </div>
    <p class="text-sm text-slate-600 max-w-prose">
      Pick an indicator and pin the states you want to compare side by side. The URL
      captures every choice — paste it to share the exact view you're looking at.
    </p>
  </header>

  {#if catalogue_error}
    <div class="text-sm bg-rose-50 border border-rose-200 text-rose-900 px-3 py-2 rounded">
      Couldn't load the topic catalogue: <code>{catalogue_error}</code>
    </div>
  {/if}

  <!-- Controls row: indicator chooser + peer-set filter. Always visible
       so the citizen can swap indicator without going back to the front
       door. -->
  <div class="bg-white border border-slate-200 rounded-lg p-3 sm:p-4 space-y-3">
    <div class="flex flex-wrap items-end gap-4">
      <div class="flex flex-col gap-1 grow min-w-[16rem]">
        <label class="text-xs text-slate-500" for="compare-indicator-select">
          Indicator
        </label>
        <select
          id="compare-indicator-select"
          class="text-sm border border-slate-200 rounded px-2 py-1.5"
          value={query.indicator ?? ""}
          onchange={on_indicator_change}
        >
          <option value="">— pick an indicator —</option>
          {#each indicator_options as o (o.indicator_id)}
            <option value={o.indicator_id}>
              {o.topic.title} · {o.label}
            </option>
          {/each}
        </select>
      </div>
      <div class="flex flex-col gap-1">
        <label class="text-xs text-slate-500" for="compare-peer-select">
          Compare across
        </label>
        <select
          id="compare-peer-select"
          class="text-sm border border-slate-200 rounded px-2 py-1.5"
          value={query.peer ?? ""}
          onchange={on_peer_change}
        >
          {#each peer_options as o}
            <option value={o.value}>{o.label}</option>
          {/each}
        </select>
      </div>
    </div>

    {#if query.indicator}
      <div class="space-y-2 pt-2 border-t border-slate-100">
        <div class="flex items-baseline justify-between gap-3 flex-wrap">
          <p class="text-xs text-slate-500">
            Pin states ({pinned_codes.length} pinned)
          </p>
          {#if pinned_codes.length > 0}
            <button
              type="button"
              class="text-xs text-sky-700 hover:underline"
              onclick={clear_pins}
            >
              Clear pins
            </button>
          {/if}
        </div>
        <div class="flex flex-wrap gap-1.5">
          {#each all_state_chips as { name, code } (code)}
            {@const on = chip_pinned(code)}
            <button
              type="button"
              class="text-xs px-2 py-1 rounded-full border transition-colors"
              class:bg-emerald-100={on}
              class:border-emerald-300={on}
              class:text-emerald-900={on}
              class:bg-white={!on}
              class:border-slate-200={!on}
              class:text-slate-700={!on}
              class:hover:bg-slate-50={!on}
              onclick={() => toggle_state_chip(code)}
            >
              {name}
            </button>
          {/each}
        </div>
      </div>
    {/if}
  </div>

  {#if !query.indicator}
    <!-- Empty state: friendly chooser hint. The select above is the
         primary CTA; this just adds context so the route doesn't render
         as a one-line page. -->
    <div class="text-sm text-slate-600 bg-slate-50 border border-slate-200 rounded p-4 max-w-prose">
      Choose an indicator from the dropdown to start a comparison. You can also
      land here pre-filtered: any topic page's
      <a href={url.topics()} class="text-sky-700 hover:underline">indicator panels</a>
      will eventually link in with their state and peer-set context preserved.
    </div>
  {:else if query.indicator && !selected}
    <div class="text-sm bg-amber-50 border border-amber-200 text-amber-900 px-3 py-2 rounded">
      Indicator <code>{query.indicator}</code> isn't in the topic catalogue. It may have
      been renamed or removed. Pick another from the dropdown.
    </div>
  {:else if indicator_path}
    <IndicatorRanked
      {indicator_path}
      peer_set_members={peer_members}
      pinned_states={pinned_codes.length > 0 ? pinned_codes : null}
      initial_rows={pinned_codes.length > 0 ? Math.max(10, pinned_codes.length) : 10}
    />
  {/if}
</section>
