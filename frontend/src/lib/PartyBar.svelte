<script lang="ts">
  import type { PartyTotals } from "./data";
  import { colors } from "./colors/store.svelte";

  let { parties, total_seats }: { parties: PartyTotals[]; total_seats: number } = $props();

  // Sort by seats descending; pre-trimmed by caller.
  const ranked = $derived([...parties].sort((a, b) => b.seats_won - a.seats_won));
  const max_seats = $derived(Math.max(1, ...ranked.map(p => p.seats_won)));
  const majority = $derived(Math.ceil(total_seats / 2));
</script>

<div class="space-y-2">
  {#each ranked as p (p.party_short)}
    <div class="flex items-center gap-3">
      <div class="w-20 text-right text-sm font-medium text-slate-700 truncate" title={p.party_full ?? p.party_short}>
        {p.party_short}
      </div>
      <div class="relative flex-1 h-7 bg-slate-100 rounded overflow-hidden">
        <div
          class="absolute inset-y-0 left-0 rounded transition-[width] duration-500 ease-out"
          style:width="{(p.seats_won / max_seats) * 100}%"
          style:background-color={colors.fill(p.party_eci_code, p.party_short)}
        ></div>
        <div class="absolute inset-y-0 flex items-center px-2 text-xs font-semibold text-slate-900 mix-blend-luminosity">
          {p.seats_won} <span class="ml-2 text-slate-700 font-normal">({p.vote_share_pct.toFixed(2)}%)</span>
        </div>
      </div>
    </div>
  {/each}
  <div class="text-xs text-slate-500 pt-2">
    Majority mark: {majority} of {total_seats} seats
  </div>
</div>
