<script lang="ts">
  // Per-state topic page (/s/:state/t/:topic).
  //
  // Citizen flow this serves (IA-reset Step #2): pick a state in scope →
  // click a topic in the rail's THIS STATE group → land here, showing the
  // topic's indicator cards filtered to THIS state. Same `IndicatorCard`
  // renderer used on `/s/<state>` (closed renderer set, per
  // docs/concepts/schema-is-the-design-system.md) — this route is
  // composition, not a new visual primitive.
  //
  // 404 paths render a clear panel (never a blank page, never a crash):
  //   - catalogue loaded + topic id unknown → "Topic not found"
  //   - catalogue loaded + state slug unknown → "State not found"
  //
  // See TODO/20260515-state-page-ia-rework-plan.md §9 row 2.

  import {
    fetchTopicCatalogue,
    indicatorPathForArtifact,
    type TopicCatalogue,
    type CatalogueTopic,
  } from "../lib/catalogue";
  import IndicatorCard from "../lib/IndicatorCard.svelte";
  import ListBadge from "../lib/ListBadge.svelte";
  import UnionListBanner from "../lib/UnionListBanner.svelte";
  import { states } from "../lib/states.svelte";
  import { url } from "../lib/url";

  interface Props {
    params: { state: string; topic: string };
  }
  let { params }: Props = $props();

  let catalogue = $state<TopicCatalogue | null>(null);
  let load_error = $state<string | null>(null);
  fetchTopicCatalogue()
    .then(c => (catalogue = c))
    .catch(e => (load_error = String(e)));

  // params.state is a slug; resolve via the states store. Null while
  // states.json hasn't loaded OR when the slug is unknown — we
  // disambiguate using `states.isLoaded` so we don't 404 before the
  // resolver has had a chance to answer.
  const state_code = $derived(states.codeFromSlug(params.state));
  const state_name = $derived(state_code ? states.name(state_code) : "");

  const topic = $derived<CatalogueTopic | null>(
    catalogue?.topics.find(t => t.id === params.topic) ?? null,
  );

  const indicator_artifacts = $derived(
    topic ? topic.artifacts.filter(a => a.kind === "indicator") : [],
  );

  // Loading: either side not yet resolved. We treat "states loaded but
  // slug unknown" as 404, not loading — same pattern as TopicLanding's
  // catalogue handling.
  const states_loading = $derived(!states.isLoaded);
  const catalogue_loading = $derived(catalogue === null && load_error === null);
</script>

<section class="p-4 sm:p-6 space-y-6 max-w-6xl">
  {#if load_error}
    <div class="rounded border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
      Failed to load topic catalogue: <code>{load_error}</code>
    </div>
  {:else if catalogue_loading || states_loading}
    <p class="text-sm text-slate-500">Loading…</p>
  {:else if !state_code}
    <div class="space-y-2">
      <p class="text-sm">
        <a href={url.home()} class="text-sky-700 hover:underline">← Home</a>
      </p>
      <h1 class="text-2xl font-semibold">State not found</h1>
      <p class="text-sm text-slate-600">
        No state with slug <code class="rounded bg-slate-100 px-1">{params.state}</code>.
        Pick a state from the <a href={url.home()} class="text-sky-700 hover:underline">home page</a>.
      </p>
    </div>
  {:else if !topic}
    <div class="space-y-2">
      <p class="text-sm">
        <a href={url.state(state_code)} class="text-sky-700 hover:underline"
          >← {state_name}</a
        >
      </p>
      <h1 class="text-2xl font-semibold">Topic not found</h1>
      <p class="text-sm text-slate-600">
        No topic with id <code class="rounded bg-slate-100 px-1">{params.topic}</code> in the catalogue.
        See the <a href={url.topics()} class="text-sky-700 hover:underline">topic index</a> for the full list.
      </p>
    </div>
  {:else}
    <header class="space-y-2">
      <nav aria-label="Breadcrumb" class="text-xs text-slate-500">
        <ol class="flex items-center gap-1 list-none p-0 m-0">
          <li>
            <a href={url.state(state_code)} class="hover:text-sky-700 hover:underline"
              >{state_name}</a
            >
          </li>
          <li aria-hidden="true" class="text-slate-400">›</li>
          <li class="text-slate-700" aria-current="page">{topic.title}</li>
        </ol>
      </nav>
      <div class="flex items-baseline gap-3 flex-wrap">
        <h1 class="text-2xl font-semibold">{topic.title}</h1>
        <ListBadge list={topic.list} />
      </div>
      <p class="text-sm text-slate-600 max-w-3xl">
        How {state_name} compares.
      </p>
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
      <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {#each indicator_artifacts as artifact (artifact.id)}
          {@const path = indicatorPathForArtifact(artifact)}
          {#if path}
            <IndicatorCard
              {topic}
              {artifact}
              indicator_path={path}
              home_state={state_code}
            />
          {/if}
        {/each}
      </div>
    {/if}
  {/if}
</section>
