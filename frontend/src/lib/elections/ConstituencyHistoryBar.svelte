<script lang="ts">
  // ConstituencyHistoryBar - PR-W4a one-row-per-event lineage strip.
  //
  // Election experience overhaul plan: a citizen reaching the
  // constituency drill page wants the full electoral lineage of the
  // seat at-a-glance. One row per event the constituency was contested
  // in: bar width = winner vote share %, right-side party-pill (party
  // colour from the canonical resolver) + margin %, left-side year.
  //
  // The component is template-only; all derivation lives in
  // `constituency-history-model.ts`. The parent (Constituency.svelte)
  // composes the per-event loader output into the rows[] prop and the
  // template renders one bar per row in the order the parent gave.

  import { getPartyColor } from "../colors/resolver";
  import type { HistoryRow } from "./constituency-history-model";

  interface Props {
    rows: readonly HistoryRow[];
  }

  let { rows }: Props = $props();

  function rowFill(party_id: string): string {
    return getPartyColor(party_id).hex;
  }
</script>

{#if rows.length === 0}
  <p
    class="text-xs text-slate-500"
    data-testid="constituency-history-empty"
  >
    No prior election data on file for this constituency yet.
  </p>
{:else}
  <div
    class="space-y-2"
    data-testid="constituency-history-bar"
  >
    {#each rows as r (r.event_id)}
      <div
        class="flex items-center gap-3"
        data-testid={`history-row-${r.event_id}`}
      >
        <span class="w-12 text-sm font-medium tabular-nums">{r.year}</span>
        <div class="flex-1 bg-slate-100 rounded h-6 overflow-hidden">
          <div
            class="h-full"
            style:width={`${Math.max(0, Math.min(100, r.winner_vote_share_pct))}%`}
            style:background-color={rowFill(r.winner_party_id)}
            title={`${r.winner_party_short} ${r.winner_vote_share_pct.toFixed(2)}%`}
          ></div>
        </div>
        <span
          class="text-xs text-slate-700 w-32 truncate"
          data-testid={`history-row-${r.event_id}-party`}
        >
          {r.winner_party_short}
        </span>
        <span
          class="text-xs text-slate-500 w-14 text-right tabular-nums"
          data-testid={`history-row-${r.event_id}-margin`}
        >
          {r.margin_pct.toFixed(1)}%
        </span>
      </div>
    {/each}
  </div>
{/if}
