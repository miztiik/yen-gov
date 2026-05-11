<script lang="ts">
  // Scope picker pinned at the top of the left rail. Three selects:
  // Country (India only today), State (loaded from datasets/reference/),
  // Election (AcGenMay2026 only today).
  //
  // Changing State navigates the router to the new state's overview;
  // selecting "All India" clears state and lands at #/. Changing
  // Election persists to localStorage; future routes that include the
  // event in their path will need to navigate too — Phase 2 concern.

  import { fetchStates, type StateEntry } from "../lib/data";
  import { fetchTopicCatalogue, type TopicCatalogue } from "../lib/catalogue";
  import { scope, COUNTRIES, ELECTIONS } from "./scope.svelte";
  import { STATE_NAME_TO_ECI } from "./maplibre/sources";
  import { navigate, url } from "./url";

  // P2.3 of IA reset (ADR-0022): state availability is decoupled from
  // election-data presence. When the catalogue exposes any national-scope
  // indicator artifact, every state has data and the picker shows a single
  // sorted list. The STATE_NAME_TO_ECI proxy stays as a bootstrap fallback.
  const fallback_codes = new Set(Object.values(STATE_NAME_TO_ECI));

  let states_list = $state<StateEntry[] | null>(null);
  let catalogue = $state<TopicCatalogue | null>(null);

  fetchStates()
    .then(s => (states_list = s.states))
    .catch(() => (states_list = []));
  fetchTopicCatalogue()
    .then(c => (catalogue = c))
    .catch(() => (catalogue = null));

  const has_national_indicator = $derived(
    (catalogue?.topics ?? []).some(t =>
      t.artifacts.some(a => a.kind === "indicator" && (a.scope ?? "national") === "national"),
    ),
  );

  const sorted_states = $derived.by(() => {
    const a: StateEntry[] = [];
    const b: StateEntry[] = [];
    for (const s of states_list ?? []) {
      const has = has_national_indicator || fallback_codes.has(s.eci_code);
      (has ? a : b).push(s);
    }
    a.sort((x, y) => x.name.localeCompare(y.name));
    b.sort((x, y) => x.name.localeCompare(y.name));
    return { with_data: a, without_data: b };
  });

  function on_state_change(e: Event): void {
    const v = (e.target as HTMLSelectElement).value;
    navigate(v === "" ? url.home() : url.state(v));
  }

  function on_election_change(e: Event): void {
    scope.setElection((e.target as HTMLSelectElement).value);
  }
</script>

<div class="space-y-2 p-3 border-b border-slate-200 bg-slate-50">
  <label class="block">
    <span class="text-[10px] uppercase tracking-wide text-slate-500">Country</span>
    <select
      class="mt-0.5 w-full text-sm rounded border-slate-300 bg-white py-1 px-2 disabled:opacity-60"
      disabled
      value={scope.country}
    >
      {#each COUNTRIES as c}
        <option value={c.code}>{c.name}</option>
      {/each}
    </select>
  </label>

  <label class="block">
    <span class="text-[10px] uppercase tracking-wide text-slate-500">State</span>
    <select
      class="mt-0.5 w-full text-sm rounded border-slate-300 bg-white py-1 px-2"
      value={scope.state ?? ""}
      onchange={on_state_change}
    >
      <option value="">All India</option>
      <optgroup label="With data">
        {#each sorted_states.with_data as s}
          <option value={s.eci_code}>{s.name}</option>
        {/each}
      </optgroup>
      {#if sorted_states.without_data.length}
        <optgroup label="Other states">
          {#each sorted_states.without_data as s}
            <option value={s.eci_code}>{s.name}</option>
          {/each}
        </optgroup>
      {/if}
    </select>
  </label>

  <label class="block">
    <span class="text-[10px] uppercase tracking-wide text-slate-500">Election</span>
    <select
      class="mt-0.5 w-full text-sm rounded border-slate-300 bg-white py-1 px-2 disabled:opacity-60"
      value={scope.election}
      onchange={on_election_change}
      disabled={ELECTIONS.length === 1}
    >
      {#each ELECTIONS as e}
        <option value={e.code}>{e.name}</option>
      {/each}
    </select>
  </label>
</div>
