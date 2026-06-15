<!--
  GeneralElections - the redesigned `/t/elections` route mounted by
  PR-E4 of TODO/20260615-elections-redesign-plan.md. Replaces the
  315-row lazy-hydration firehose with a 6-11 row Parliament-cycle
  table per the user-mandated rip-and-replace doctrine (Section 0.2).

  Render contract per Section 0.1 Jony verdict + Section 2 E4:
   - Tab strip above the H1 (ElectionsRouteTabs)
   - H1 "General elections"
   - Table columns: Year (link) | Leading party pill | Vote-share bar |
     Turnout | Delta (green-up / red-down arrow) | Runners-up
   - Year text IS the click affordance (no separate chevron column)
   - Inline vote-share bar = plain Tailwind div (closed-set faithful)
   - Mobile contract: 4 columns at < 640px (Year | Leading party + seats |
     Turnout + delta | Runners-up hidden); vote-share bar hidden

  Data: loadGeneralElections() from view-models/general-elections-model
  (PR-E3) reads datasets/data/marts/elections/event_summary.csv shipped
  by PR-E2 and joins parties.csv for color + short name.

  Per Hans: leading_party_id is the canonical party_id with most seats
  (alliance attribution may land later writer-side; renderer unchanged).
-->
<script lang="ts">
  import ElectionsRouteTabs from "../lib/elections/ElectionsRouteTabs.svelte";
  import PageContainer from "../lib/layout/PageContainer.svelte";
  import {
    loadGeneralElections,
    type GeneralElectionRowViewModel,
  } from "../lib/view-models/general-elections-model";

  let rows = $state<GeneralElectionRowViewModel[] | null>(null);
  let err = $state<string | null>(null);

  loadGeneralElections()
    .then((r) => {
      rows = r;
    })
    .catch((e: unknown) => {
      err = e instanceof Error ? e.message : String(e);
    });

  function fmtPct(n: number | null): string {
    return n == null ? "-" : `${n.toFixed(1)}%`;
  }

  function fmtDelta(n: number | null): {
    text: string;
    color: string;
    glyph: string;
  } {
    if (n == null) return { text: "-", color: "text-slate-300", glyph: "" };
    if (n === 0) return { text: "0pp", color: "text-slate-500", glyph: "" };
    if (n > 0)
      return {
        text: `+${n.toFixed(1)}pp`,
        color: "text-emerald-600",
        glyph: "\u25B2",
      };
    return {
      text: `${n.toFixed(1)}pp`,
      color: "text-rose-600",
      glyph: "\u25BC",
    };
  }

  function voteShareWidth(seats_won: number, seats_contested: number): string {
    if (seats_contested <= 0) return "0%";
    const pct = Math.min(100, Math.max(0, (seats_won / seats_contested) * 100));
    return `${pct.toFixed(1)}%`;
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
            <th class="px-3 py-2 hidden sm:table-cell">Seats</th>
            <th class="px-3 py-2">Turnout</th>
            <th class="px-3 py-2">Delta</th>
            <th class="px-3 py-2 hidden md:table-cell">Runners-up</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as r (r.event_id)}
            {@const delta = fmtDelta(r.turnout_delta_pp)}
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
                  <!-- Inline vote-share bar (PR-E4 spec): plain Tailwind
                       div, closed-set faithful per docs/concepts/
                       schema-is-the-design-system.md. Width encodes
                       the leading-party seat share. Hidden < 640px. -->
                  <span class="hidden sm:block w-32 h-1.5 rounded bg-slate-200">
                    <span
                      class="block h-full rounded"
                      style:background-color={r.leading.color}
                      style:width={voteShareWidth(
                        r.seats_won,
                        r.seats_contested,
                      )}
                    ></span>
                  </span>
                </div>
              </td>
              <td class="px-3 py-2 align-top text-slate-700 hidden sm:table-cell">
                <span class="font-mono text-xs">
                  {r.seats_won}/{r.seats_contested}
                </span>
              </td>
              <td class="px-3 py-2 align-top text-slate-700">
                <span class="font-mono text-xs"
                  >{fmtPct(r.turnout_pct)}</span
                >
              </td>
              <td class="px-3 py-2 align-top {delta.color}">
                <span class="font-mono text-xs"
                  data-testid={`general-elections-delta-${r.event_id}`}>
                  <span aria-hidden="true">{delta.glyph}</span>
                  {delta.text}
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
  {/if}
</PageContainer>
