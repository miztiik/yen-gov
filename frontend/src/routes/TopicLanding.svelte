<script lang="ts">
  // Topic landing page (/t/:topic).
  //
  // National-scope view of one topic: every indicator artifact under it
  // rendered with the same closed renderer set used on /s/<state>
  // (IndicatorChoropleth + IndicatorRanked + IndicatorSmallMultiples), no
  // bespoke chrome per topic. Mandatory constitutional context per
  // ADR-0022:
  //   - ListBadge next to the topic title (state / union / concurrent / na)
  //   - UnionListBanner above the artifacts when topic.list === "union"
  //
  // Per-artifact peer-set defaults flow through resolvePeerSetDefault()
  // exactly as on the state hub. The landing has no "home state" pin — it's
  // a national view — so home_state is intentionally undefined.

  import {
    fetchTopicCatalogue,
    indicatorPathForArtifact,
    displayForArtifact,
    resolvePeerSetDefault,
    type TopicCatalogue,
    type CatalogueTopic,
    type CatalogueArtifact,
    type PeerSet,
  } from "../lib/catalogue";
  import IndicatorChoropleth from "../lib/IndicatorChoropleth.svelte";
  import IndicatorRanked from "../lib/IndicatorRanked.svelte";
  import IndicatorSmallMultiples from "../lib/IndicatorSmallMultiples.svelte";
  import StackedTrendArtifact from "../lib/StackedTrendArtifact.svelte";
  import ListBadge from "../lib/ListBadge.svelte";
  import UnionListBanner from "../lib/UnionListBanner.svelte";
  import PeerSetFilter from "../lib/PeerSetFilter.svelte";
  import {
    fetchStateTiers,
    resolvePeerSet,
    type StateTiersFile,
  } from "../lib/state-tiers";
  import { url } from "../lib/url";
  import { parseTopicQuery, serializeTopicQuery } from "../lib/topic-query";

  interface Props {
    params: { topic: string };
  }
  let { params }: Props = $props();

  let catalogue = $state<TopicCatalogue | null>(null);
  let load_error = $state<string | null>(null);
  fetchTopicCatalogue()
    .then(c => (catalogue = c))
    .catch(e => (load_error = String(e)));

  let state_tiers = $state<StateTiersFile | null>(null);
  fetchStateTiers()
    .then(t => (state_tiers = t))
    .catch(() => (state_tiers = null));

  // Lookup against the loaded catalogue. Null = catalogue not yet loaded
  // (loading state) OR the slug is not a known topic id (404 state). The
  // latter is rendered with a clear message rather than a blank page.
  const topic = $derived<CatalogueTopic | null>(
    catalogue?.topics.find(t => t.id === params.topic) ?? null,
  );

  const indicator_artifacts = $derived<CatalogueArtifact[]>(
    topic ? topic.artifacts.filter(a => a.kind === "indicator") : [],
  );

  // Per-artifact peer-set state, identical pattern to StateOverview.
  // Initial values come from `?peer=<id>` (P3.3d) when present — it
  // overrides the catalogue's per-artifact default for EVERY artifact on
  // the page so a shared URL produces the same view for the recipient.
  // User-driven changes write back to `?peer=` via `history.replaceState`
  // (no new history entry — the back button still navigates to /t).
  let peer_set_overrides = $state<Record<string, PeerSet>>({});

  function read_query_peer(): PeerSet | null {
    if (typeof window === "undefined") return null;
    return parseTopicQuery(window.location.search).peer;
  }

  function apply_query_peer(): void {
    const p = read_query_peer();
    // Replace overrides wholesale: an absent `?peer=` clears any
    // user-set overrides on back/forward navigation.
    peer_set_overrides = p ? { __global: p } : {};
  }

  // Initial read on mount + re-read on back/forward navigation. The
  // router fires `popstate` for every internal navigation, so this also
  // covers the case where the user clicks a topic link that shares this
  // route component but with a different `?peer=`.
  if (typeof window !== "undefined") {
    apply_query_peer();
    window.addEventListener("popstate", apply_query_peer);
  }

  function peer_set_for(t: CatalogueTopic, a: CatalogueArtifact): PeerSet {
    // Order: per-artifact override > global ?peer= > catalogue default.
    return (
      peer_set_overrides[a.id]
      ?? peer_set_overrides.__global
      ?? resolvePeerSetDefault(t, a)
    );
  }
  function set_peer_set(_t: CatalogueTopic, a: CatalogueArtifact, next: PeerSet) {
    peer_set_overrides = { ...peer_set_overrides, [a.id]: next };
    // Mirror the most-recently-set value to `?peer=` so the URL stays
    // shareable. v0 limitation documented in lib/topic-query.ts: a
    // single `?peer` slot means the URL captures the last-set value, not
    // per-artifact fidelity. `replaceState` so the back button still
    // takes the user to /t, not to a stack of intermediate filter steps.
    if (typeof window !== "undefined") {
      const search = serializeTopicQuery({ peer: next });
      const target = window.location.pathname + search + window.location.hash;
      history.replaceState(null, "", target);
    }
  }
</script>

<section class="p-4 sm:p-6 space-y-6 max-w-6xl">
  {#if load_error}
    <div class="rounded border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
      Failed to load topic catalogue: <code>{load_error}</code>
    </div>
  {:else if !catalogue}
    <p class="text-sm text-slate-500">Loading topic catalogue…</p>
  {:else if !topic}
    <div class="space-y-2">
      <p class="text-sm">
        <a href={url.topics()} class="text-sky-700 hover:underline">← All topics</a>
      </p>
      <h1 class="text-2xl font-semibold">Topic not found</h1>
      <p class="text-sm text-slate-600">
        No topic with id <code class="rounded bg-slate-100 px-1">{params.topic}</code> in the catalogue.
        See the <a href={url.topics()} class="text-sky-700 hover:underline">topic index</a> for the
        full list.
      </p>
    </div>
  {:else}
    <header class="space-y-2">
      <nav aria-label="Breadcrumb" class="text-xs text-slate-500">
        <ol class="flex items-center gap-1 list-none p-0 m-0">
          <li><a href={url.topics()} class="hover:text-sky-700 hover:underline">Topics</a></li>
          <li aria-hidden="true" class="text-slate-400">›</li>
          <li class="text-slate-700" aria-current="page">{topic.title}</li>
        </ol>
      </nav>
      <div class="flex items-baseline gap-3 flex-wrap">
        <h1 class="text-2xl font-semibold">{topic.title}</h1>
        <ListBadge list={topic.list} />
      </div>
      <p class="text-sm text-slate-600 max-w-3xl">{topic.summary}</p>
      {#if topic.notes}
        <p class="text-xs text-slate-500 max-w-3xl">{topic.notes}</p>
      {/if}
    </header>

    {#if topic.list === "union"}
      <UnionListBanner topic_title={topic.title} />
    {/if}

    {#if indicator_artifacts.length === 0}
      <p class="text-sm text-slate-500">
        No indicator artifacts catalogued for this topic yet.
      </p>
    {:else}
      <div class="space-y-8">
        {#each indicator_artifacts as artifact (artifact.id)}
          {@const path = indicatorPathForArtifact(artifact)}
          {#if path}
            {@const current_peer_set = peer_set_for(topic, artifact)}
            {@const peer_members = resolvePeerSet(state_tiers, current_peer_set)}
            <section class="space-y-3">
              <div class="flex items-center gap-2 flex-wrap">
                <h2 class="text-base font-semibold">{displayForArtifact(artifact)}</h2>
                <span class="ml-auto">
                  <PeerSetFilter
                    value={current_peer_set}
                    tiers={state_tiers}
                    onChange={(next) => set_peer_set(topic, artifact, next)}
                    id_prefix={`peerset-${topic.id}-${artifact.id}`}
                  />
                </span>
              </div>
              {#if artifact.chart_type === "stacked-trend"}
                <StackedTrendArtifact
                  indicator_path={path}
                  mode="spatial"
                  dimension={artifact.dimension ?? "generic"}
                  category_labels={{
                    coal: "Coal",
                    gas: "Gas",
                    hydro: "Hydro",
                    nuclear: "Nuclear",
                    renewable: "Renewable",
                    other_thermal: "Other thermal",
                  }}
                />
              {:else}
                <IndicatorChoropleth
                  indicator_path={path}
                  peer_set_members={peer_members}
                />
                <IndicatorRanked
                  indicator_path={path}
                  peer_set_members={peer_members}
                />
                <IndicatorSmallMultiples indicator_path={path} />
              {/if}
            </section>
          {/if}
        {/each}
      </div>
    {/if}
  {/if}
</section>
