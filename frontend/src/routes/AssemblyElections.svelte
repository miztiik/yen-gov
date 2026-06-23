<!--
  AssemblyElections - the redesigned `/t/elections/assemblies` route
  mounted by PR-E4 of TODO/20260615-elections-redesign-plan.md.

  Place-first card grid; latest election only per state. Per Section
  0.1 Jony verdict + Section 2 E5:
   - Tab strip above the H1 (ElectionsRouteTabs)
   - H1 "Assembly elections"
   - Grid: 1 col mobile / 2 cols md / 3 cols lg
   - Card: state name + 'N elections on record' + 'Latest YYYY' +
     party pill + seats + turnout + per-event drill-down link
   - 5 honest no-legislature cards (Chandigarh / Lakshadweep / Ladakh /
     Dadra+Daman / Andaman & Nicobar) per ADR-0022 constitutional
     honesty - no party pill, no year, no event link

  Data: loadAssemblyElections() from view-models/assembly-elections-model
  (PR-E3) reads event_summary.csv + parties.csv + state catalogue.
-->
<script lang="ts">
  import ElectionsRouteTabs from "../lib/elections/ElectionsRouteTabs.svelte";
  import PageContainer from "../lib/layout/PageContainer.svelte";
  import TableSkeleton from "../lib/TableSkeleton.svelte";
  import {
    loadAssemblyElections,
    type AssemblyCardViewModel,
  } from "../lib/view-models/assembly-elections-model";

  let cards = $state<AssemblyCardViewModel[] | null>(null);
  let err = $state<string | null>(null);

  loadAssemblyElections()
    .then((c) => {
      cards = c;
    })
    .catch((e: unknown) => {
      err = e instanceof Error ? e.message : String(e);
    });

  function fmtPct(n: number | null): string {
    return n == null ? "-" : `${n.toFixed(1)}%`;
  }
</script>

<PageContainer width="wide">
  <ElectionsRouteTabs current="assembly" />

  <header class="space-y-1">
    <h1 class="text-2xl font-semibold text-slate-900">Assembly elections</h1>
    <p class="text-sm text-slate-600">
      Latest state assembly election for every Indian state and Union
      Territory. UTs without a legislative assembly are flagged
      honestly.
    </p>
  </header>

  {#if err}
    <div
      class="rounded border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
      data-testid="assembly-elections-error"
    >
      Couldn't load: {err}
    </div>
  {:else if cards == null}
    <div data-testid="assembly-elections-loading">
      <!-- Known shape (a grid of election cards) -> table skeleton
           instead of a frozen "Loading..." (perf plan Row 7). -->
      <TableSkeleton rows={6} />
    </div>
  {:else}
    <ul
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 list-none p-0 m-0"
      data-testid="assembly-elections-grid"
    >
      {#each cards as c (c.state_slug)}
        {#if c.has_legislature}
          {@const ev = c.latest_event}
          <li
            class="rounded border border-slate-200 bg-white p-4 hover:border-sky-200 hover:bg-sky-50 transition-colors"
            data-testid={`assembly-elections-card-${c.state_slug}`}
          >
            <div class="flex items-start justify-between gap-3">
              <a
                href={c.state_hub_href}
                class="text-base font-semibold text-slate-900 hover:text-sky-700 hover:underline"
                data-testid={`assembly-elections-state-link-${c.state_slug}`}
              >
                {c.state_name}
              </a>
              {#if c.total_events_on_record > 0}
                <span class="text-[10px] uppercase tracking-wide text-slate-500">
                  {c.total_events_on_record} on record
                </span>
              {/if}
            </div>

            {#if ev}
              <div class="mt-2 space-y-1.5">
                <div class="text-xs text-slate-500">Latest:
                  <a
                    href={ev.detail_href}
                    class="font-mono font-semibold text-sky-700 hover:text-sky-900 hover:underline"
                    data-testid={`assembly-elections-year-link-${c.state_slug}`}
                  >
                    {ev.year}
                  </a>
                </div>
                <div class="flex items-center gap-2 flex-wrap">
                  {#if ev.leading_party_id && ev.leading_party_href}
                    <a
                      href={ev.leading_party_href}
                      class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium text-white hover:opacity-90"
                      style:background-color={ev.leading_color}
                      data-testid={`assembly-elections-party-pill-${c.state_slug}`}
                    >
                      {ev.leading_short}
                    </a>
                  {:else if ev.leading_party_id}
                    <span
                      class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium text-white"
                      style:background-color={ev.leading_color}
                    >
                      {ev.leading_short}
                    </span>
                  {/if}
                  <span class="font-mono text-xs text-slate-600">
                    {ev.seats_won} of {ev.seats_contested}
                  </span>
                  <span class="font-mono text-xs text-slate-500">
                    {fmtPct(ev.turnout_pct)} turnout
                  </span>
                </div>
              </div>
            {:else}
              <p class="mt-2 text-xs text-slate-500 italic">
                No election in the catalogue yet.
              </p>
            {/if}
          </li>
        {:else}
          <li
            class="rounded border border-slate-200 bg-slate-50 p-4"
            data-testid={`assembly-elections-card-${c.state_slug}`}
            data-no-legislature="true"
          >
            <div class="text-base font-semibold text-slate-900">
              {c.state_name}
            </div>
            <p class="mt-2 text-xs italic text-slate-500">
              No state legislature.
            </p>
            <a
              href={c.state_hub_href}
              class="mt-2 inline-block text-xs text-sky-700 hover:text-sky-900 hover:underline"
            >
              View {c.state_name} page ->
            </a>
          </li>
        {/if}
      {/each}
    </ul>
  {/if}
</PageContainer>
