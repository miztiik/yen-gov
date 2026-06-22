<!--
  GeneralElections - the redesigned `/t/elections` route.

  Render contract (2026-06-22 redesign, user-approved, Jony consult):
   - Tab strip above the H1 (ElectionsRouteTabs)
   - H1 "General elections"
   - GeneralSeatsWindow: a windowed seat-composition chart (1-3 cycles
     visible) with a draggable range slider, mounted above the table.
   - Table columns: Year (link) | Leading party (pill + "N of M" seats +
     mandate tag) | Turnout (plain %) | Seat swing (leading-slot seat
     change vs the prior cycle, green-up / red-down glyph) | Lead (over
     the runner-up, hidden < 640px) | Runners-up (hidden < 768px)
   - The majority story lives in the mandate tag (text) and the chart's
     per-cycle majority line; the table no longer repeats it as a bar.
   - One SourceList provenance footer (Holy Law #9) covers both the
     chart and the table - every national row cites the same source_id.
   - The standalone "Seats" column was removed: it duplicated the
     "N of M" already shown under the leading-party pill.

  Data: loadGeneralElections() reads datasets/data/marts/elections/
  event_summary.csv (scope='national') and joins parties.csv for colour +
  short name; loadGeneralElectionsSources() resolves the cited source_ids
  into publisher pills from datasets/data/entities/source.csv.
-->
<script lang="ts">
  import ElectionsRouteTabs from "../lib/elections/ElectionsRouteTabs.svelte";
  import GeneralSeatsWindow from "../lib/elections/GeneralSeatsWindow.svelte";
  import PageContainer from "../lib/layout/PageContainer.svelte";
  import { SourceList } from "../lib/sources";
  import type { PublisherPill } from "../lib/sources";
  import {
    loadGeneralElections,
    loadGeneralElectionsSources,
    type GeneralElectionRowViewModel,
  } from "../lib/view-models/general-elections-model";

  let rows = $state<GeneralElectionRowViewModel[] | null>(null);
  let sourcePills = $state<PublisherPill[]>([]);
  let err = $state<string | null>(null);

  loadGeneralElections()
    .then(async (r) => {
      const pills = await loadGeneralElectionsSources(
        r.map((x) => x.source_id),
      );
      rows = r;
      sourcePills = pills;
    })
    .catch((e: unknown) => {
      err = e instanceof Error ? e.message : String(e);
    });

  function fmtPct(n: number | null): string {
    return n == null ? "-" : `${n.toFixed(1)}%`;
  }

  function fmtSwing(n: number | null): {
    text: string;
    color: string;
    glyph: string;
  } {
    if (n == null) return { text: "-", color: "text-slate-300", glyph: "" };
    if (n === 0) return { text: "0", color: "text-slate-500", glyph: "" };
    if (n > 0)
      return { text: `+${n}`, color: "text-emerald-600", glyph: "\u25B2" };
    return { text: `${n}`, color: "text-rose-600", glyph: "\u25BC" };
  }
</script>

<PageContainer width="wide">
  <ElectionsRouteTabs current="general" />

  <header class="space-y-1">
    <h1 class="text-2xl font-semibold text-slate-900">General elections</h1>
    <p class="text-sm text-slate-600">
      Every Indian General (Parliament) election on record. Each row is
      one all-India cycle.
    </p>
  </header>

  {#if err}
    <div
      class="rounded border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
      data-testid="general-elections-error"
    >
      Couldn't load: {err}
    </div>
  {:else if rows == null}
    <div class="text-sm text-slate-400" data-testid="general-elections-loading">
      Loading...
    </div>
  {:else}
    <!-- Windowed seat-composition chart: 1-3 cycles visible with a
         draggable range slider. Defaults to the latest 3 cycles. -->
    <GeneralSeatsWindow rows={rows} />

    <div class="overflow-x-auto rounded border border-slate-200 bg-white">
      <table
        class="w-full text-left text-sm"
        data-testid="general-elections-table"
      >
        <thead
          class="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"
        >
          <tr>
            <th class="px-3 py-2">Year</th>
            <th class="px-3 py-2">Leading party</th>
            <th class="px-3 py-2">Turnout</th>
            <th class="px-3 py-2">Seat swing</th>
            <th class="px-3 py-2 hidden sm:table-cell">Lead</th>
            <th class="px-3 py-2 hidden md:table-cell">Runners-up</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as r (r.event_id)}
            {@const swing = fmtSwing(r.seat_swing)}
            <tr
              class="border-t border-slate-100 odd:bg-white even:bg-slate-50 hover:bg-sky-50"
              data-testid={`general-elections-row-${r.event_id}`}
            >
              <td class="px-3 py-2 align-top font-mono text-xs">
                <a
                  href={r.detail_href}
                  class="font-semibold text-sky-700 hover:text-sky-900 hover:underline"
                  data-testid={`general-elections-year-link-${r.event_id}`}
                >
                  {r.year}
                </a>
              </td>
              <td class="px-3 py-2 align-top">
                <div class="flex flex-col gap-1">
                  {#if r.leading.party_id && r.leading.detail_href}
                    <a
                      href={r.leading.detail_href}
                      class="inline-flex items-center self-start rounded-full px-2 py-0.5 text-xs font-medium text-white hover:opacity-90"
                      style:background-color={r.leading.color}
                      data-testid={`general-elections-leading-pill-${r.event_id}`}
                    >
                      {r.leading.short}
                    </a>
                  {:else if r.leading.party_id}
                    <span
                      class="inline-flex items-center self-start rounded-full px-2 py-0.5 text-xs font-medium text-white"
                      style:background-color={r.leading.color}
                    >
                      {r.leading.short}
                    </span>
                  {:else}
                    <span class="text-xs text-slate-400">-</span>
                  {/if}
                  <span
                    class="font-mono text-xs text-slate-600"
                    data-testid={`general-elections-seats-${r.event_id}`}
                  >
                    {r.seats_won} of {r.seats_contested}
                  </span>
                  <span
                    class="text-[10px] font-medium {r.mandate.majority
                      ? 'text-emerald-700'
                      : 'text-slate-500'}"
                    data-testid={`general-elections-mandate-${r.event_id}`}
                  >
                    {r.mandate.label}
                  </span>
                </div>
              </td>
              <td class="px-3 py-2 align-top text-slate-700">
                <span class="font-mono text-xs">{fmtPct(r.turnout_pct)}</span>
              </td>
              <td class="px-3 py-2 align-top {swing.color}">
                <span
                  class="font-mono text-xs"
                  data-testid={`general-elections-swing-${r.event_id}`}
                >
                  {swing.glyph}
                  {swing.text}
                </span>
              </td>
              <td
                class="px-3 py-2 align-top text-slate-700 hidden sm:table-cell"
              >
                <span
                  class="font-mono text-xs"
                  data-testid={`general-elections-margin-${r.event_id}`}
                >
                  +{r.margin}
                </span>
              </td>
              <td class="px-3 py-2 align-top hidden md:table-cell">
                {#if r.runner_up}
                  <span class="flex flex-wrap gap-1">
                    {#if r.runner_up.detail_href}
                      <a
                        href={r.runner_up.detail_href}
                        class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium text-white hover:opacity-90"
                        style:background-color={r.runner_up.color}
                      >
                        {r.runner_up.short} {r.runner_up.seats}
                      </a>
                    {:else}
                      <span
                        class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium text-white"
                        style:background-color={r.runner_up.color}
                      >
                        {r.runner_up.short} {r.runner_up.seats}
                      </span>
                    {/if}
                  </span>
                {:else}
                  <span class="text-xs text-slate-300">-</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if sourcePills.length > 0}
      <SourceList pills={sourcePills} />
    {/if}
  {/if}
</PageContainer>
