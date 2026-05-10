<script lang="ts">
  import { fetchStates, type StateEntry } from "../lib/data";
  import IndiaMap from "../lib/maplibre/IndiaMap.svelte";
  import { STATE_NAME_TO_ECI } from "../lib/maplibre/sources";

  const EVENT = "AcGenMay2026";
  // States we have data for (drives the "Available" bucket below).
  const HAS_DATA = new Set(Object.values(STATE_NAME_TO_ECI));

  let states = $state<StateEntry[] | null>(null);
  let error = $state<string | null>(null);

  fetchStates()
    .then(s => (states = s.states))
    .catch(e => (error = String(e)));

  const available = $derived((states ?? []).filter(s => HAS_DATA.has(s.eci_code)));
  const stub = $derived((states ?? []).filter(s => !HAS_DATA.has(s.eci_code)));
</script>

<main class="max-w-screen-2xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <h1 class="text-2xl font-bold">yen-gov</h1>
    <p class="text-sm text-slate-500">
      Indian election data — event <code class="font-mono">{EVENT}</code>.
      Click a state to drill in.
    </p>
  </header>

  <section class="bg-white rounded-lg shadow-sm p-4">
    <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">India — leading party by state</h2>
    <IndiaMap event={EVENT} />
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
               href={`#/s/${st.eci_code}`}>
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
