<script lang="ts">
  // Per-state elections hub (PR-W3a, 2026-06-10).
  //
  // Mounted inside StateTopic.svelte's `topic.id === "elections"` branch
  // so the route URL `/<state>/t/elections` is unchanged; only the body
  // is rebuilt. Replaces the pre-rip "horrible page" — a "List: N/A"
  // chrome badge + "How <state> compares" subtitle + a single
  // default-event card with a collapsed "Other elections" disclosure —
  // with a chronological event timeline + body-kind filter chip.
  //
  // Per Jony's Q3 (TODO/20260609-election-experience-overhaul-plan.md
  // PR-W3a row):
  //   - Header: <state-name> + "Election history" (NOT the topic title;
  //     "Elections" was a redundant chrome label for a route already
  //     scoped to elections).
  //   - Body filter: [All] [Parliament] [Assembly] chips, single-select.
  //     By-elections are bucketed under Assembly because they are AC-house
  //     events from the citizen mental model; the timeline chip pins the
  //     distinction visually.
  //   - Chronological timeline, newest first. One row per event, click-
  //     through to the canonical per-event view at
  //     `/<state>/elections/<event_id>`.
  //
  // This component owns its own catalogue fetch and state-slug lookup so
  // it is self-contained — the parent StateTopic.svelte only forwards
  // params.state. The catalogue is small (~3 KB gzipped) and
  // fetchElectionEvents() dedupes via a Promise singleton so concurrent
  // mounts (StateTopic + this hub) share the network.

  import {
    fetchElectionEvents,
    listEventsForState,
    type ElectionEventsCatalogue,
    type ElectionEventRow,
  } from "../lib/election-events";
  import { states } from "../lib/states.svelte";
  import StateEventTimeline from "../lib/elections/StateEventTimeline.svelte";

  interface Props {
    /** State slug from the route (`params.state`). The hub resolves the
     * ECI code + display name from the states store. */
    state_slug: string;
  }

  let { state_slug }: Props = $props();

  // Three-state filter. "all" is the default so a citizen who lands on
  // the hub sees the full chronology before narrowing.
  type BodyFilter = "all" | "parliament" | "assembly";
  let body_filter = $state<BodyFilter>("all");

  let catalogue = $state<ElectionEventsCatalogue | null>(null);
  let load_failed = $state(false);
  fetchElectionEvents()
    .then(c => (catalogue = c))
    .catch(() => (load_failed = true));

  const state_code = $derived(states.codeFromSlug(state_slug));
  const state_name = $derived(state_code ? states.name(state_code) : state_slug);

  // listEventsForState() returns newest-first by polled_on (sorts a copy
  // of the cached array, never mutates). The timeline component re-sorts
  // defensively but the order coming out of here is already correct.
  const all_events = $derived<ElectionEventRow[]>(
    listEventsForState(catalogue, state_code),
  );

  // Body-kind filter. Parliament bucket includes the future general_bye
  // kind (PR-W2a doctrine; today the catalogue has zero general_bye rows
  // but the type union allows them). Assembly bucket includes
  // assembly_bye + the legacy by_election catch-all so AC by-elections
  // never fall out of the citizen-visible timeline.
  const filtered = $derived<ElectionEventRow[]>(
    body_filter === "all"
      ? all_events
      : body_filter === "parliament"
        ? all_events.filter(
            e => e.kind === "parliament" || e.kind === "general_bye",
          )
        : all_events.filter(
            e =>
              e.kind === "assembly" ||
              e.kind === "assembly_bye" ||
              e.kind === "by_election",
          ),
  );

  const loading = $derived(catalogue === null && !load_failed);

  const FILTER_CHIPS: ReadonlyArray<{ value: BodyFilter; label: string }> = [
    { value: "all", label: "All" },
    { value: "parliament", label: "Parliament" },
    { value: "assembly", label: "Assembly" },
  ];
</script>

<section class="space-y-4" data-testid="state-elections-hub">
  <header class="space-y-1">
    <h1 class="text-2xl font-semibold text-slate-900">{state_name}</h1>
    <p class="text-sm text-slate-600">Election history</p>
  </header>

  <div
    class="flex flex-wrap gap-2"
    role="group"
    aria-label="Filter by body"
    data-testid="state-elections-body-filter"
  >
    {#each FILTER_CHIPS as chip (chip.value)}
      <button
        type="button"
        aria-pressed={body_filter === chip.value}
        data-testid="body-filter-{chip.value}"
        class="rounded border px-3 py-1 text-sm transition-colors {body_filter ===
        chip.value
          ? 'border-slate-900 bg-slate-900 text-white'
          : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'}"
        onclick={() => (body_filter = chip.value)}
      >
        {chip.label}
      </button>
    {/each}
  </div>

  {#if load_failed}
    <p
      class="rounded border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"
      data-testid="state-elections-hub-error"
    >
      Failed to load the election events catalogue.
    </p>
  {:else if loading}
    <p class="text-sm text-slate-500">Loading election history...</p>
  {:else if all_events.length === 0}
    <p
      class="rounded border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600"
      data-testid="state-elections-hub-empty"
    >
      No elections on file for {state_name} yet.
    </p>
  {:else}
    <StateEventTimeline events={filtered} {state_slug} />
  {/if}
</section>
