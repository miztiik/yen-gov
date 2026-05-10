<script lang="ts">
  import * as d3 from "d3";
  import type { PartyTotals } from "./data";
  import { colors } from "./colors/store.svelte";
  import { majorityFor } from "./electoral";
  import ChartTooltip, { type TooltipState } from "./ChartTooltip.svelte";

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
  // when one party is muted. We also include `majority` (with a small 5 %
  // headroom) in the scale so the dashed majority marker is always visible
  // *inside* the chart, even when the leading party hasn't crossed it
  // (the visible *gap* between the top bar and the marker IS the story
  // in fragmented results).
  //
  // `majorityFor` is the shared helper: floor(N/2)+1, the FPTP "strictly
  // more than half" threshold. Same value Psephlab + ParliamentArc use.
  const majority = $derived(majorityFor(total_seats));
  const max_seats = $derived(
    Math.max(1, Math.ceil(majority * 1.05), ...ranked.map(p => p.seats_won)),
  );
  const majority_pct = $derived((majority / max_seats) * 100);

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
  // Lighter shade per party for the bar gradient. Cheap, but isolating
  // here keeps the markup tidy.
  function lighten(hex: string): string {
    return d3.color(hex)?.brighter(0.7)?.formatHex() ?? hex;
  }

  // Leader = first row (post-sort). Used to add a soft ambient glow on the
  // top bar so the headline party is unmissable at a glance.
  const leader_key = $derived(ranked[0] ? key_for(ranked[0]) : null);

  // Custom tooltip (replaces native browser <title>). Driven by row-level
  // mouse events. We thread x/y from the event so the card follows the
  // cursor; ChartTooltip handles edge-flipping.
  const clickable_global = $derived(!!onToggleHidden);
  let tooltip = $state<TooltipState | null>(null);
  function showTip(e: MouseEvent, p: PartyTotals): void {
    const k = key_for(p);
    const muted = !!hidden_parties?.has(k);
    tooltip = {
      x: e.clientX,
      y: e.clientY,
      color: colors.fill(p.party_eci_code, p.party_short),
      title: p.party_short,
      subtitle: p.party_full && p.party_full !== p.party_short ? p.party_full : undefined,
      lines: [
        { label: "Seats", value: String(p.seats_won), suffix: `of ${total_seats}` },
        { label: "Vote share", value: `${p.vote_share_pct.toFixed(1)}%` },
      ],
      hint: clickable_global ? (muted ? "Click to show this party" : "Click to mute this party") : undefined,
    };
  }
  function moveTip(e: MouseEvent): void {
    if (tooltip) tooltip = { ...tooltip, x: e.clientX, y: e.clientY };
  }
  function hideTip(): void { tooltip = null; }
</script>

<!-- Outer wrapper hosts the absolutely-positioned majority marker overlay
     so it can span the full bar stack without affecting bar layout.
     pt-5 leaves room for the marker label to sit ABOVE the first bar
     without being clipped by ancestor screenshot tooling that sometimes
     mis-paints absolute children placed at negative offsets. -->
<div class="relative pt-5">
  <!-- Track-area overlay: matches the bar layout (label gutter w-20 + gap-3
       + flex-1 track) so the dashed marker lines up with the actual bar
       pixels rather than the card padding. -->
  <div class="pointer-events-none absolute inset-0 flex items-stretch gap-3 z-0" aria-hidden="true">
    <div class="w-20 shrink-0"></div>
    <div class="relative flex-1">
      {#if majority_pct < 100}
        <div
          class="absolute top-5 bottom-10 border-l-2 border-dashed border-amber-400/80"
          style:left="{majority_pct}%"
        ></div>
        <!-- Label flips to right-anchored when the marker sits past 75 %
             of the track, so the text never gets clipped against the card
             edge. Both variants live at top-0 inside the pt-5 padding so
             the label has its own real estate and never overlaps a bar. -->
        {#if majority_pct > 75}
          <div
            class="absolute top-0 text-[10px] font-medium text-amber-600 whitespace-nowrap"
            style:right="calc({100 - majority_pct}% + 4px)"
          >
            Majority · {majority}
          </div>
        {:else}
          <div
            class="absolute top-0 text-[10px] font-medium text-amber-600 -translate-x-1/2 whitespace-nowrap"
            style:left="{majority_pct}%"
          >
            Majority · {majority}
          </div>
        {/if}
      {/if}
    </div>
  </div>

  <div class="space-y-2.5 relative z-10">
    {#each ranked as p, i (p.party_short)}
      {@const w = widthFrac(p.seats_won)}
      {@const inside = labelInside(p.seats_won)}
      {@const k = key_for(p)}
      {@const hidden = !!hidden_parties?.has(k)}
      {@const clickable = !!onToggleHidden}
      {@const fill = colors.fill(p.party_eci_code, p.party_short)}
      {@const fill_light = lighten(fill)}
      {@const is_leader = k === leader_key}
      <div
        class="group flex items-center gap-3 transition-opacity"
        class:opacity-40={hidden}
        class:cursor-pointer={clickable}
        role={clickable ? "button" : undefined}
        tabindex={clickable ? 0 : undefined}
        onclick={() => onToggleHidden?.(k)}
        onkeydown={(e) => { if (clickable && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onToggleHidden?.(k); } }}
        onmouseenter={(e) => showTip(e, p)}
        onmousemove={moveTip}
        onmouseleave={hideTip}
        onfocus={(e) => showTip(e as unknown as MouseEvent, p)}
        onblur={hideTip}
      >
        <div class="w-20 text-right text-sm font-medium text-slate-700 truncate flex items-center justify-end gap-1.5" title={p.party_full ?? p.party_short}>
          {#if is_leader && p.seats_won > 0}
            <!-- Discreet "leading" indicator: a small filled dot in the
                 party color. No emoji crown — keeps the chart serious. -->
            <span
              class="inline-block w-1.5 h-1.5 rounded-full"
              style:background-color={fill}
              title="Leading party"
            ></span>
          {/if}
          <span>{p.party_short}</span>
        </div>
        <div class="relative flex-1 h-8 bg-slate-100 rounded-full overflow-hidden ring-1 ring-slate-200/70">
          <!-- Gradient fill. The horizontal gradient (party color → ~70%
               brighter shade) gives the bar depth without obscuring the
               base hue. The transition animates the sweep-in on mount,
               with a small per-row stagger so the chart "ripples" into
               place rather than slamming all bars at once. The leader bar
               carries an outer glow in its own party color. -->
          <div
            class="absolute inset-y-0 left-0 rounded-full transition-[width,filter] duration-700 ease-out group-hover:brightness-110"
            style:width="{w * 100}%"
            style:background="linear-gradient(90deg, {fill} 0%, {fill_light} 100%)"
            style:transition-delay="{Math.min(i * 35, 350)}ms"
            style:box-shadow={is_leader && p.seats_won > 0
              ? `0 0 0 1px ${fill}40, 0 2px 10px ${fill}55`
              : undefined}
          ></div>
          <!-- Inner highlight stripe: 2-px gloss along the top edge. Very
               subtle, but it's what reads as "modern" vs the old flat fill. -->
          {#if w > 0.02}
            <div
              class="pointer-events-none absolute top-0 left-0 h-[2px] rounded-full opacity-60"
              style:width="{w * 100}%"
              style:background="linear-gradient(90deg, rgba(255,255,255,0.55), rgba(255,255,255,0.05))"
              style:transition="width 700ms ease-out"
              style:transition-delay="{Math.min(i * 35, 350)}ms"
            ></div>
          {/if}
          <!-- Two-position label: inside the fill when the bar is wide enough,
               outside (in the track) otherwise. Avoids the previous mix-blend
               trick which washed out 0-width bars. -->
          {#if inside}
            <div class="absolute inset-y-0 left-0 flex items-center px-3 text-xs font-semibold text-white drop-shadow-[0_1px_1px_rgba(0,0,0,0.45)] tabular-nums">
              {p.seats_won}<span class="ml-2 font-normal opacity-90">({p.vote_share_pct.toFixed(1)}%)</span>
            </div>
          {:else}
            <div
              class="absolute inset-y-0 flex items-center text-xs font-semibold text-slate-700 tabular-nums"
              style:left="calc({w * 100}% + 0.5rem)"
            >
              {p.seats_won}<span class="ml-2 font-normal text-slate-500">({p.vote_share_pct.toFixed(1)}%)</span>
            </div>
          {/if}
        </div>
      </div>
    {/each}
  </div>

  <div class="text-xs text-slate-500 pt-3 flex items-center gap-2 flex-wrap">
    <span class="inline-flex items-center gap-1.5">
      <span class="inline-block w-3 border-t-2 border-dashed border-amber-400/80 align-middle"></span>
      <span>Majority threshold ({majority} of {total_seats})</span>
    </span>
    {#if hidden_parties && hidden_parties.size > 0}
      <span class="text-slate-300">·</span>
      <span class="text-slate-400">{hidden_parties.size} party muted</span>
    {/if}
  </div>
</div>

<ChartTooltip tip={tooltip} />
