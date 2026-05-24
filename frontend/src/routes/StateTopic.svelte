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
  // Renderer is polymorphic on the artifact's `kind` (catalogue v1.0):
  //   * `kind: "indicator"`   → IndicatorCard grid (the original case)
  //   * `kind: "election"`    → per-state election summary card; the
  //                             default event is resolved at render time
  //                             via defaultEventForState(state_code) so
  //                             the surface is state-agnostic (HP shows
  //                             HP's 2022 result, TN shows TN's 2026
  //                             result — same code, different data).
  //                             Pre-2026-05-24 the catalogue carried a
  //                             TN-specific `id: "AcGenMay2026"` literal
  //                             that silently emptied this surface for
  //                             every non-TN state; see ADR-0023 §latest.
  //   * other kinds           → silently skipped (no v1 consumers).
  //
  // The legacy `topic.notes` field was previously rendered verbatim into
  // a `<p>` below the H1, which leaked engineer-facing ADR doctrine
  // paragraphs into the citizen UI (e.g. the energy topic's 5-paragraph
  // ingestion-history footnote, or the elections topic's ADR-0022 quote).
  // Per Jony's read-aloud review, `notes` is now engineer/agent commentary
  // only — the catalogue still carries it, but no route renders it to
  // citizens. If a topic genuinely needs caveats on the citizen surface,
  // promote them into `summary` (the one-sentence plain-language field)
  // or build a dedicated component for the caveat type.
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
    type CatalogueArtifact,
  } from "../lib/catalogue";
  import IndicatorCard from "../lib/IndicatorCard.svelte";
  import ListBadge from "../lib/ListBadge.svelte";
  import TopicIcon from "../lib/TopicIcon.svelte";
  import UnionListBanner from "../lib/UnionListBanner.svelte";
  import { states } from "../lib/states.svelte";
  import { url } from "../lib/url";
  import {
    fetchElectionEvents,
    defaultEventForState,
    listEventsForState,
    type ElectionEventsCatalogue,
    type ElectionEventRow,
  } from "../lib/election-events";

  interface Props {
    params: { state: string; topic: string };
  }
  let { params }: Props = $props();

  let catalogue = $state<TopicCatalogue | null>(null);
  let load_error = $state<string | null>(null);
  fetchTopicCatalogue()
    .then(c => (catalogue = c))
    .catch(e => (load_error = String(e)));

  // Lazy-loaded once any election artifact is in scope on this topic.
  // The catalogue is small (~3 KB gzipped) and shared across all routes
  // that touch elections; concurrent fetches dedupe in election-events.ts.
  let election_catalogue = $state<ElectionEventsCatalogue | null>(null);
  fetchElectionEvents()
    .then(c => (election_catalogue = c))
    .catch(() => (election_catalogue = null));

  // params.state is a slug; resolve via the states store. Null while
  // states.json hasn't loaded OR when the slug is unknown — we
  // disambiguate using `states.isLoaded` so we don't 404 before the
  // resolver has had a chance to answer.
  const state_code = $derived(states.codeFromSlug(params.state));
  const state_name = $derived(state_code ? states.name(state_code) : "");

  const topic = $derived<CatalogueTopic | null>(
    catalogue?.topics.find(t => t.id === params.topic) ?? null,
  );

  // Renderer dispatch (catalogue polymorphism). Indicator artifacts feed
  // the existing IndicatorCard grid; election artifacts feed the per-
  // state election summary block. Other kinds are unmount-safe noops.
  const indicator_artifacts = $derived<CatalogueArtifact[]>(
    topic ? topic.artifacts.filter(a => a.kind === "indicator") : [],
  );
  const election_artifacts = $derived<CatalogueArtifact[]>(
    topic ? topic.artifacts.filter(a => a.kind === "election") : [],
  );

  // For election artifacts, the per-state default event is resolved at
  // render time. When the artifact carries an explicit `id` (e.g. a
  // historical pin to a specific cohort), we honour that; when it does
  // not (the v1.4 catalogue default for `/s/:state/t/elections`), we
  // fall back to the catalogue helper. Returns null for states with no
  // election rows on file — the renderer surfaces "no election data" copy.
  const election_default_row = $derived<ElectionEventRow | null>(
    defaultEventForState(election_catalogue, state_code),
  );
  const election_other_rows = $derived<ElectionEventRow[]>(
    listEventsForState(election_catalogue, state_code).filter(
      r => r.event_id !== election_default_row?.event_id,
    ),
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
        <h1 class="text-2xl font-semibold flex items-center gap-2">
          <TopicIcon name={topic.icon} cls="w-6 h-6 text-slate-500 shrink-0" />
          <span>{topic.title}</span>
        </h1>
        <ListBadge list={topic.list} />
      </div>
      <p class="text-sm text-slate-600 max-w-3xl">
        How {state_name} compares.
      </p>
    </header>

    {#if topic.list === "union"}
      <UnionListBanner topic_title={topic.title} />
    {/if}

    {#if election_artifacts.length > 0}
      <section class="space-y-3" data-testid="election-topic-section">
        {#if election_catalogue === null}
          <p class="text-sm text-slate-500">Loading election data…</p>
        {:else if election_default_row === null}
          <div class="rounded border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
            No election data ingested for {state_name} yet.
          </div>
        {:else}
          {@const ev = election_default_row}
          <article
            class="rounded border border-slate-200 bg-white p-4 space-y-2"
            data-testid="election-topic-card"
          >
            <header class="flex items-baseline justify-between gap-3 flex-wrap">
              <h2 class="text-base font-semibold">
                <a
                  href={url.stateElection(state_code, ev.event_id)}
                  class="text-sky-700 hover:underline"
                  data-testid="election-topic-default-link"
                >
                  {ev.display}
                </a>
              </h2>
              <span class="text-xs text-slate-500">Polled {ev.polled_on}</span>
            </header>
            <p class="text-xs text-slate-600">
              {ev.kind === "assembly"
                ? "State Assembly election"
                : ev.kind === "lok_sabha"
                  ? "Lok Sabha (national) election slice for this state"
                  : "By-election"}{ev.data_status === "pending_upstream"
                ? " — awaiting publication by ECI."
                : ev.data_status === "partial"
                  ? " — partial data on disk."
                  : ""}
            </p>
            <p class="text-xs text-slate-500">
              <a
                href={url.stateElection(state_code, ev.event_id)}
                class="text-sky-700 hover:underline"
              >
                View constituency-level results →
              </a>
            </p>
          </article>

          {#if election_other_rows.length > 0}
            <details class="text-sm" data-testid="election-topic-others">
              <summary class="cursor-pointer text-slate-700">
                Other {state_name} elections on file
                <span class="text-slate-400">({election_other_rows.length})</span>
              </summary>
              <ul class="mt-2 space-y-1 list-none p-0">
                {#each election_other_rows as row (row.event_id)}
                  <li>
                    <a
                      href={url.stateElection(state_code, row.event_id)}
                      class="text-sky-700 hover:underline"
                    >
                      {row.display}
                    </a>
                    <span class="text-xs text-slate-400">· {row.polled_on}</span>
                  </li>
                {/each}
              </ul>
            </details>
          {/if}
        {/if}
      </section>
    {/if}

    {#if indicator_artifacts.length === 0 && election_artifacts.length === 0}
      <p class="text-sm text-slate-500">
        No indicator artifacts catalogued for this topic yet.
      </p>
    {:else if indicator_artifacts.length > 0}
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
