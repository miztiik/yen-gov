<script lang="ts">
  import * as d3 from "d3";
  import type { PartyTotals } from "./data";
  import { colors } from "./colors/store.svelte";

  let { parties, total_seats }: { parties: PartyTotals[]; total_seats: number } = $props();

  const size = 240;
  const radius = size / 2;

  const arcs = $derived.by(() => {
    const data = parties
      .filter(p => p.seats_won > 0)
      .sort((a, b) => b.seats_won - a.seats_won)
      .map(p => ({ ...p, color: colors.fill(p.party_eci_code, p.party_short) }));
    const pie = d3.pie<typeof data[number]>().value(d => d.seats_won).sort(null);
    const arc = d3.arc<d3.PieArcDatum<typeof data[number]>>()
      .innerRadius(radius * 0.55)
      .outerRadius(radius - 4);
    return pie(data).map(d => ({
      d: arc(d) ?? "",
      color: d.data.color,
      label: d.data.party_short,
      seats: d.data.seats_won,
    }));
  });
</script>

<div class="flex flex-col items-center gap-3">
  <svg width={size} height={size} viewBox="-{radius} -{radius} {size} {size}">
    {#each arcs as a (a.label)}
      <path d={a.d} fill={a.color}>
        <title>{a.label}: {a.seats} seats</title>
      </path>
    {/each}
    <text text-anchor="middle" dominant-baseline="central" class="fill-slate-700">
      <tspan x="0" dy="-0.4em" class="text-3xl font-bold">{total_seats}</tspan>
      <tspan x="0" dy="1.6em" class="text-xs uppercase tracking-wide">seats</tspan>
    </text>
  </svg>
</div>
