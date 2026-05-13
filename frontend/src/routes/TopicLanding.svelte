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
  import ListBadge from "../lib/ListBadge.svelte";
  import UnionListBanner from "../lib/UnionListBanner.svelte";
  import PeerSetFilter from "../lib/PeerSetFilter.svelte";
  import {
    fetchStateTiers,
    resolvePeerSet,
    type StateTiersFile,
  } from "../lib/state-tiers";
  import { url } from "../lib/url";

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
  let peer_set_overrides = $state<Record<string, PeerSet>>({});
  function peer_set_for(t: CatalogueTopic, a: CatalogueArtifact): PeerSet {
    return peer_set_overrides[a.id] ?? resolvePeerSetDefault(t, a);
  }
  function set_peer_set(_t: CatalogueTopic, a: CatalogueArtifact, next: PeerSet) {
    peer_set_overrides = { ...peer_set_overrides, [a.id]: next };
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
      <p class="text-sm">
        <a href={url.topics()} class="text-sky-700 hover:underline">← All topics</a>
      </p>
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
              <IndicatorChoropleth
                indicator_path={path}
                peer_set_members={peer_members}
              />
              <IndicatorRanked
                indicator_path={path}
                peer_set_members={peer_members}
              />
              <IndicatorSmallMultiples indicator_path={path} />
            </section>
          {/if}
        {/each}
      </div>
    {/if}
  {/if}
</section>
