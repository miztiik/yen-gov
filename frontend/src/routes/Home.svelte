<script lang="ts">
  import { fetchStates, type StateEntry } from "../lib/data";
  import { fetchTopicCatalogue, type TopicCatalogue } from "../lib/catalogue";
  import IndiaMap from "../lib/maplibre/IndiaMap.svelte";
  import { STATE_NAME_TO_ECI } from "../lib/maplibre/sources";
  import { url } from "../lib/url";

  // The IndiaMap colours each state by its leading party in that state's
  // *own* default election event (resolved from
  // datasets/reference/in/election-events.json), so states from different
  // cohorts (May-2026, Nov-2024, Nov-2023, ...) all show up together.
  // No global "current election" — per ADR-0023 / ADR-0022.

  let states = $state<StateEntry[] | null>(null);
  let catalogue = $state<TopicCatalogue | null>(null);
  let error = $state<string | null>(null);

  fetchStates()
    .then(s => (states = s.states))
    .catch(e => (error = String(e)));

  fetchTopicCatalogue()
    .then(c => (catalogue = c))
    .catch(e => (error = String(e)));

  // Availability is decoupled from election-data presence (ADR-0022, P2.3 of
  // IA reset). When the catalogue has any national-scope indicator artifact,
  // every state in states.json has data — indicator artifacts cover all 35+
  // entities. The election-only proxy (STATE_NAME_TO_ECI) remains a fallback
  // for the bootstrap case where the catalogue hasn't loaded yet.
  const has_national_indicator = $derived(
    (catalogue?.topics ?? []).some(t =>
      t.artifacts.some(a => a.kind === "indicator" && (a.scope ?? "national") === "national"),
    ),
  );
  const fallback_codes = new Set(Object.values(STATE_NAME_TO_ECI));
  const available = $derived(
    has_national_indicator
      ? (states ?? [])
      : (states ?? []).filter(s => fallback_codes.has(s.eci_code)),
  );
  const stub = $derived(
    has_national_indicator
      ? []
      : (states ?? []).filter(s => !fallback_codes.has(s.eci_code)),
  );
</script>

<main class="max-w-screen-2xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <h1 class="text-2xl font-bold">yen-gov</h1>
    <p class="text-sm text-slate-500">
      Indian civic data — fiscal capacity, energy, elections, and more,
      compared across states. Click a state to drill in.
      <a href={url.about()} class="text-sky-700 hover:underline">What is this?</a>
    </p>
  </header>

  <section class="bg-white rounded-lg shadow-sm p-4">
    <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">India — leading party by state</h2>
    <IndiaMap />
  </section>

  {#if error}
    <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900">
      Failed to load states: <code>{error}</code>
    </div>
  {:else if !states}
    <div class="text-slate-500">Loading…</div>
  {:else}
    <section class="bg-white rounded-lg shadow-sm p-5 space-y-3">
      <h2 class="text-sm font-semibold uppercase text-slate-500">Available</h2>
      <ul class="divide-y">
        {#each available as st}
          <li>
            <a class="flex justify-between items-center px-2 py-3 hover:bg-slate-50 rounded"
               href={url.state(st.eci_code)}>
              <span class="font-medium">{st.name}</span>
              <span class="text-xs font-mono text-slate-500">{st.eci_code} · {st.iso_3166_2}</span>
            </a>
          </li>
        {/each}
      </ul>
    </section>

    {#if stub.length}
      <section class="bg-white rounded-lg shadow-sm p-5 space-y-3 opacity-70">
        <h2 class="text-sm font-semibold uppercase text-slate-500">Other states (no data yet)</h2>
        <ul class="grid sm:grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1 text-sm">
          {#each stub as st}
            <li class="flex justify-between">
              <span>{st.name}</span>
              <span class="text-xs font-mono text-slate-400">{st.eci_code}</span>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}
</main>
