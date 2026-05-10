<script lang="ts">
  import * as d3 from "d3";
  import type { PartyTotals } from "./data";
  import { colors } from "./colors/store.svelte";

  interface Props {
    parties: PartyTotals[];
    total_seats: number;
    /**
     * When set, slices for hidden parties are drawn at low opacity and
     * marked as visually muted. Hidden seats are NOT removed — the donut
     * still represents the actual allocation. Hidden parties remain
     * clickable so the user can un-mute them.
     */
    hidden_parties?: Set<string>;
    onToggleHidden?: (party_key: string) => void;
  }
  let { parties, total_seats, hidden_parties, onToggleHidden }: Props = $props();

  const size = 240;
  const radius = size / 2;

  function key_for(p: PartyTotals): string {
    return p.party_eci_code ?? p.party_short;
  }

  const arcs = $derived.by(() => {
    const data = parties
      .filter(p => p.seats_won > 0)
      .sort((a, b) => b.seats_won - a.seats_won)
      .map(p => ({
        ...p,
        color: colors.fill(p.party_eci_code, p.party_short),
        key: key_for(p),
      }));
    const pie = d3.pie<typeof data[number]>().value(d => d.seats_won).sort(null);
    const arc = d3.arc<d3.PieArcDatum<typeof data[number]>>()
      .innerRadius(radius * 0.55)
      .outerRadius(radius - 4);
    return pie(data).map(d => ({
      d: arc(d) ?? "",
      color: d.data.color,
      label: d.data.party_short,
      seats: d.data.seats_won,
      key: d.data.key,
    }));
  });

  const hidden_seats = $derived.by(() => {
    if (!hidden_parties || hidden_parties.size === 0) return 0;
    let n = 0;
    for (const a of arcs) if (hidden_parties.has(a.key)) n += a.seats;
    return n;
  });
  const visible_seats = $derived(total_seats - hidden_seats);
</script>

<div class="flex flex-col items-center gap-3">
  <svg width={size} height={size} viewBox="-{radius} -{radius} {size} {size}">
    {#each arcs as a (a.label)}
      {@const muted = !!hidden_parties?.has(a.key)}
      {@const clickable = !!onToggleHidden}
      <path
        d={a.d}
        fill={a.color}
        opacity={muted ? 0.18 : 1}
        class:cursor-pointer={clickable}
        onclick={() => onToggleHidden?.(a.key)}
        role={clickable ? "button" : undefined}
        tabindex={clickable ? 0 : undefined}
      >
        <title>{a.label}: {a.seats} seats{muted ? " (muted)" : ""}</title>
      </path>
    {/each}
    <text text-anchor="middle" dominant-baseline="central" class="fill-slate-700">
      {#if hidden_seats > 0}
        <tspan x="0" dy="-0.6em" class="text-2xl font-bold">{visible_seats}</tspan>
        <tspan x="0" dy="1.4em" class="text-[10px] uppercase tracking-wide fill-slate-500">of {total_seats}</tspan>
      {:else}
        <tspan x="0" dy="-0.4em" class="text-3xl font-bold">{total_seats}</tspan>
        <tspan x="0" dy="1.6em" class="text-xs uppercase tracking-wide">seats</tspan>
      {/if}
    </text>
  </svg>
</div>
