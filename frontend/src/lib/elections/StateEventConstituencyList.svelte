<!--
  StateEventConstituencyList - extracted from StateElection.svelte during
  R3 (Beck two-hat: pure structural extraction, no behaviour change) of
  TODO/20260615-state-election-event-page-redesign-plan.md (2026-06-15).

  Renders the flat constituency table + the Compare CTA nav that
  previously lived inline on the state-event route. R4 will refactor
  this surface (fold + search; delete the flat 288-row table; integrate
  Compare CTA as the last row of the fold-collapsed list). R3 preserves
  the DOM shape verbatim; the testids land on identical elements.

  The parent computes `seat_rows`, `previous_same_body`, `compare_href`
  and threads them through props - this keeps the helpers (partyIdFor,
  fillForParty, palette_bundle) on the route. R4 may revisit that
  boundary once the Hero / Party / Map subcomponents are also extracted
  and the shared helper surface stabilises.

  Preserves data-testids: state-event-constituency-table /
  state-event-constituency-table-loading / state-event-constituency-row /
  state-event-constituency-link / state-event-compare-cta.
-->
<script lang="ts">
  import type { ElectionEventRow } from "../election-events";

  export interface SeatRow {
    entity_id: string;
    entity_name: string;
    winner_party_short: string;
    winner_party_id: string;
    winner_color: string;
    winner_share_pct: number | null;
    margin_pct: number | null;
    href: string;
  }

  interface Props {
    loading: boolean;
    seat_rows: readonly SeatRow[];
    previous_same_body: ElectionEventRow | null;
    compare_href: string | null;
    fmtInt: (n: number | null) => string;
    fmtPct: (n: number | null) => string;
  }

  let {
    loading,
    seat_rows,
    previous_same_body,
    compare_href,
    fmtInt,
    fmtPct,
  }: Props = $props();
</script>

<!-- Constituency table -->
<section
  class="space-y-2"
  data-testid="state-event-constituency-table"
>
  <h2 class="text-sm font-medium text-slate-700">
    Constituencies ({loading ? "-" : fmtInt(seat_rows.length)})
  </h2>
  {#if loading}
    <p
      class="text-xs text-slate-500"
      data-testid="state-event-constituency-table-loading"
    >Loading constituency results...</p>
  {:else if seat_rows.length === 0}
    <p class="text-xs text-slate-500">No constituency rows yet.</p>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="text-left text-xs uppercase text-slate-500">
          <tr>
            <th class="py-2">Constituency</th>
            <th class="py-2">Winner</th>
            <th class="py-2 text-right">Share</th>
            <th class="py-2 text-right">Margin</th>
          </tr>
        </thead>
        <tbody class="divide-y">
          {#each seat_rows as r (r.entity_id)}
            <tr
              class="hover:bg-slate-50"
              data-testid="state-event-constituency-row"
            >
              <td class="py-2">
                <a
                  class="text-sky-700 hover:underline"
                  href={r.href}
                  data-testid="state-event-constituency-link"
                >{r.entity_name}</a>
              </td>
              <td class="py-2">
                <span
                  class="inline-block rounded px-1.5 py-0.5 text-xs font-medium text-white"
                  style={`background-color:${r.winner_color};`}
                >{r.winner_party_short}</span>
              </td>
              <td class="py-2 text-right tabular-nums">
                {fmtPct(r.winner_share_pct)}
              </td>
              <td class="py-2 text-right tabular-nums">
                {fmtPct(r.margin_pct)}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>

<!-- Compare CTA (W4b target) -->
{#if compare_href && previous_same_body}
  <nav
    class="flex flex-wrap gap-2 text-sm"
    aria-label="Compare elections"
  >
    <a
      class="rounded border border-sky-200 bg-sky-50 px-3 py-2 text-sky-800 hover:bg-sky-100"
      href={compare_href}
      data-testid="state-event-compare-cta"
    >Compare with {previous_same_body.display} &rarr;</a>
  </nav>
{/if}
