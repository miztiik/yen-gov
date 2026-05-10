<script lang="ts">
  import type { PartyTotals } from "./data";
  import { colors } from "./colors/store.svelte";

  interface Props {
    parties: PartyTotals[];
    total_seats: number;
    /**
     * Optional set of party identifiers (party_eci_code OR party_short when
     * the code is null) the caller wants visually muted. Hidden parties
     * still render so users can click to un-hide; they DON'T trigger any
     * recomputation of seats / vote share — by design (StateOverview spec:
     * "do not recompute, just show actuals").
     */
    hidden_parties?: Set<string>;
    /** Click callback toggles a party in/out of the hidden set. */
    onToggleHidden?: (party_key: string) => void;
  }
  let { parties, total_seats, hidden_parties, onToggleHidden }: Props = $props();

  function key_for(p: PartyTotals): string {
    return p.party_eci_code ?? p.party_short;
  }

  // Sort by seats descending; ties broken by vote share so that 0-seat
  // parties surface in a meaningful order. Caller may pre-sort but we
  // re-sort defensively (cheap).
  const ranked = $derived(
    [...parties].sort(
      (a, b) =>
        b.seats_won - a.seats_won ||
        b.vote_share_pct - a.vote_share_pct ||
        a.party_short.localeCompare(b.party_short),
    ),
  );
  // Max for bar scaling uses ALL parties (incl. hidden) so widths stay
  // stable when toggling — prevents the disorienting "everything resizes"
  // when one party is muted.
  const max_seats = $derived(Math.max(1, ...ranked.map(p => p.seats_won)));
  const majority = $derived(Math.ceil(total_seats / 2));

  // Bar fill widths in [0..1]. A label is "inside" the colored fill iff
  // there's enough room (≥ ~28% of track) for both the seat count and the
  // vote-share suffix to read without crowding. Otherwise the label sits
  // outside, in the gray track, so 0-seat parties stay legible.
  function widthFrac(seats: number): number {
    return seats / max_seats;
  }
  function labelInside(seats: number): boolean {
    return widthFrac(seats) >= 0.28;
  }
</script>

<div class="space-y-2">
  {#each ranked as p (p.party_short)}
    {@const w = widthFrac(p.seats_won)}
    {@const inside = labelInside(p.seats_won)}
    {@const k = key_for(p)}
    {@const hidden = !!hidden_parties?.has(k)}
    {@const clickable = !!onToggleHidden}
    <div
      class="flex items-center gap-3 transition-opacity"
      class:opacity-40={hidden}
      class:line-through={hidden}
      class:cursor-pointer={clickable}
      role={clickable ? "button" : undefined}
      tabindex={clickable ? 0 : undefined}
      title={clickable ? (hidden ? `Click to show ${p.party_short}` : `Click to mute ${p.party_short}`) : undefined}
      onclick={() => onToggleHidden?.(k)}
      onkeydown={(e) => { if (clickable && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onToggleHidden?.(k); } }}
    >
      <div class="w-20 text-right text-sm font-medium text-slate-700 truncate" title={p.party_full ?? p.party_short}>
        {p.party_short}
      </div>
      <div class="relative flex-1 h-7 bg-slate-100 rounded">
        <div
          class="absolute inset-y-0 left-0 rounded transition-[width] duration-500 ease-out"
          style:width="{w * 100}%"
          style:background-color={colors.fill(p.party_eci_code, p.party_short)}
        ></div>
        <!-- Two-position label: inside the fill when the bar is wide enough,
             outside (in the track) otherwise. Avoids the previous mix-blend
             trick which washed out 0-width bars. -->
        {#if inside}
          <div class="absolute inset-y-0 left-0 flex items-center px-2 text-xs font-semibold text-white drop-shadow-[0_1px_1px_rgba(0,0,0,0.35)]">
            {p.seats_won}<span class="ml-2 font-normal opacity-90">({p.vote_share_pct.toFixed(2)}%)</span>
          </div>
        {:else}
          <div
            class="absolute inset-y-0 flex items-center text-xs font-semibold text-slate-700"
            style:left="calc({w * 100}% + 0.5rem)"
          >
            {p.seats_won}<span class="ml-2 font-normal text-slate-500">({p.vote_share_pct.toFixed(2)}%)</span>
          </div>
        {/if}
      </div>
    </div>
  {/each}
  <div class="text-xs text-slate-500 pt-2">
    Majority mark: {majority} of {total_seats} seats
    {#if hidden_parties && hidden_parties.size > 0}
      · <span class="text-slate-400">{hidden_parties.size} party muted</span>
    {/if}
  </div>
</div>
