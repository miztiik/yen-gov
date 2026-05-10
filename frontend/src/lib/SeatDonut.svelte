<script lang="ts">
  import * as d3 from "d3";
  import { onMount } from "svelte";
  import { tweened } from "svelte/motion";
  import { cubicOut } from "svelte/easing";
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

  // Larger canvas + thicker ring than the original 240/0.55 — the donut now
  // reads as the page's "hero" chart on the State Overview rather than just
  // a small accompanying graphic.
  const size = 280;
  const radius = size / 2;
  const inner = radius * 0.62;
  const outer = radius - 8;

  function key_for(p: PartyTotals): string {
    return p.party_eci_code ?? p.party_short;
  }

  // Sweep-in entrance. `progress` goes 0 → 1 on mount; arc end-angles and
  // the centre tally are both gated on it so the chart "draws itself".
  const progress = tweened(0, { duration: 950, easing: cubicOut });
  onMount(() => { progress.set(1); });

  // Hover pop-out. Tracking the hovered slice key lets the SVG path swap to
  // a slightly larger arc generator (outerRadius +8) for the lift effect,
  // with a CSS transition giving the motion.
  let hover_key = $state<string | null>(null);

  const ranked = $derived.by(() =>
    parties
      .filter(p => p.seats_won > 0)
      .sort((a, b) => b.seats_won - a.seats_won)
      .map(p => ({
        ...p,
        color: colors.fill(p.party_eci_code, p.party_short),
        key: key_for(p),
      })),
  );

  // Build arcs by hand (instead of d3.pie) so we can scale the cumulative
  // sweep against `progress`. padAngle + cornerRadius give the modern
  // segmented-ring look; padAngle stays small so 1-seat slivers survive.
  const arcs = $derived.by(() => {
    const data = ranked;
    const total = data.reduce((s, p) => s + p.seats_won, 0) || 1;
    const sweep = 2 * Math.PI * $progress;
    const arcGen = d3.arc<{ startAngle: number; endAngle: number }>()
      .innerRadius(inner)
      .outerRadius(outer)
      .padAngle(0.012)
      .cornerRadius(4);
    const popGen = d3.arc<{ startAngle: number; endAngle: number }>()
      .innerRadius(inner)
      .outerRadius(outer + 8)
      .padAngle(0.012)
      .cornerRadius(4);
    let cum = 0;
    return data.map(p => {
      const start = (cum / total) * 2 * Math.PI;
      cum += p.seats_won;
      const end = (cum / total) * 2 * Math.PI;
      const cappedStart = Math.min(start, sweep);
      const cappedEnd = Math.min(end, sweep);
      const arcDatum = { startAngle: cappedStart, endAngle: cappedEnd };
      const mid = (cappedStart + cappedEnd) / 2;
      return {
        d: arcGen(arcDatum) ?? "",
        d_pop: popGen(arcDatum) ?? "",
        color: p.color,
        color_dark: d3.color(p.color)?.darker(0.45)?.formatHex() ?? p.color,
        color_light: d3.color(p.color)?.brighter(0.55)?.formatHex() ?? p.color,
        label: p.party_short,
        seats: p.seats_won,
        key: p.key,
        mid_angle: mid,
      };
    });
  });

  const hidden_seats = $derived.by(() => {
    if (!hidden_parties || hidden_parties.size === 0) return 0;
    let n = 0;
    for (const a of arcs) if (hidden_parties.has(a.key)) n += a.seats;
    return n;
  });
  const visible_seats = $derived(total_seats - hidden_seats);

  // Headline pill: the leading party + a "majority" flag when they cross
  // half the chamber. Adds the chart's "story" beat without the user
  // needing to scan a legend.
  const leader = $derived(ranked[0] ?? null);
  const leader_has_majority = $derived(
    leader != null && leader.seats_won * 2 > total_seats,
  );

  // Animated centre tally. We tween the integer to the *currently visible*
  // total so muting a party also animates the centre down/up smoothly.
  const tally = tweened(0, { duration: 600, easing: cubicOut });
  $effect(() => {
    void $progress;
    tally.set(hidden_seats > 0 ? visible_seats : total_seats);
  });
</script>

<div class="flex flex-col items-center gap-3">
  <svg
    width={size}
    height={size}
    viewBox="-{radius} -{radius} {size} {size}"
    class="overflow-visible"
    role="img"
    aria-label="Seat share donut chart"
  >
    <defs>
      <!-- Soft drop shadow used by every slice. Kept very subtle (≤ 4px)
           so the chart still reads cleanly on white backgrounds. -->
      <filter id="seat-donut-shadow" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur in="SourceAlpha" stdDeviation="1.6" />
        <feOffset dx="0" dy="1.5" result="offsetblur" />
        <feComponentTransfer>
          <feFuncA type="linear" slope="0.28" />
        </feComponentTransfer>
        <feMerge>
          <feMergeNode />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
      <!-- Per-slice gradient: brighter "highlight" at the outward face of
           the wedge → base color in the middle → slightly darker at the
           inner edge. Rotating the gradient by the slice's mid-angle keeps
           the highlight on the outward face for every wedge so the ring
           reads as lit from outside. -->
      {#each arcs as a (a.key)}
        {@const deg = (a.mid_angle * 180) / Math.PI - 90}
        <linearGradient
          id="slice-grad-{a.key}"
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1={-outer}
          x2="0"
          y2={outer}
          gradientTransform="rotate({deg})"
        >
          <stop offset="0%" stop-color={a.color_light} />
          <stop offset="55%" stop-color={a.color} />
          <stop offset="100%" stop-color={a.color_dark} />
        </linearGradient>
      {/each}
    </defs>

    <!-- Background ring track: very faint, sits under the slices so the
         chart doesn't "disappear" while the sweep-in is mid-flight. -->
    <circle r={(inner + outer) / 2} fill="none" stroke="#f1f5f9" stroke-width={outer - inner} />

    <!-- Majority halo: a thin gold dashed ring on the outer edge, only
         when the leading party crosses the majority mark. Telegraphs the
         headline at a glance — no extra text needed. -->
    {#if leader_has_majority}
      <circle
        r={outer + 4}
        fill="none"
        stroke="#fbbf24"
        stroke-width="1.5"
        stroke-dasharray="2 4"
        opacity="0.75"
      />
    {/if}

    {#each arcs as a (a.key)}
      {@const muted = !!hidden_parties?.has(a.key)}
      {@const popped = hover_key === a.key}
      {@const clickable = !!onToggleHidden}
      <path
        d={popped ? a.d_pop : a.d}
        fill="url(#slice-grad-{a.key})"
        opacity={muted ? 0.18 : 1}
        filter="url(#seat-donut-shadow)"
        stroke="white"
        stroke-width="1"
        class:cursor-pointer={clickable}
        style="transition: d 180ms ease-out;"
        onclick={() => onToggleHidden?.(a.key)}
        onmouseenter={() => (hover_key = a.key)}
        onmouseleave={() => (hover_key = null)}
        onfocus={() => (hover_key = a.key)}
        onblur={() => (hover_key = null)}
        role={clickable ? "button" : undefined}
        tabindex={clickable ? 0 : undefined}
        aria-label="{a.label}: {a.seats} seats{muted ? ' (muted)' : ''}"
      >
        <title>{a.label}: {a.seats} seats{muted ? " (muted)" : ""}</title>
      </path>
    {/each}

    <!-- Centre tally. Two-line layout: big animated number + small label;
         the optional "of N" line appears only when something is muted.
         text-anchor + x=0 are explicitly repeated on every tspan so SVG
         doesn't drift the cursor between lines (we saw a left-shift on
         Chrome when the second tspan inherited only the parent anchor). -->
    <text text-anchor="middle" dominant-baseline="central" class="fill-slate-800">
      {#if hidden_seats > 0}
        <tspan x="0" y="-6" text-anchor="middle" style="font-size:30px;font-weight:700;font-variant-numeric:tabular-nums;">{Math.round($tally)}</tspan>
        <tspan x="0" y="22" text-anchor="middle" style="font-size:10px;letter-spacing:0.12em;text-transform:uppercase;" class="fill-slate-500">of {total_seats} seats</tspan>
      {:else}
        <tspan x="0" y="-4" text-anchor="middle" style="font-size:38px;font-weight:700;font-variant-numeric:tabular-nums;">{Math.round($tally)}</tspan>
        <tspan x="0" y="24" text-anchor="middle" style="font-size:10px;letter-spacing:0.18em;text-transform:uppercase;" class="fill-slate-500">seats</tspan>
      {/if}
    </text>
  </svg>

  <!-- Leader pill: anchors the story under the donut. Color dot uses the
       same fill as the leader's slice so the eye links them instantly. -->
  {#if leader}
    <div class="flex items-center gap-2 text-xs">
      <span
        class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium"
        style:background-color="{leader.color}1a"
      >
        <span class="inline-block w-2 h-2 rounded-full" style:background-color={leader.color}></span>
        <span class="text-slate-700">{leader.party_short}</span>
        <span class="text-slate-400">·</span>
        <span class="text-slate-700 tabular-nums">{leader.seats_won} seats</span>
        {#if leader_has_majority}
          <span class="text-amber-600 font-semibold">· Majority</span>
        {/if}
      </span>
    </div>
  {/if}
</div>
