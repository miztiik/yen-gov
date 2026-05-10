<script lang="ts">
  import * as d3 from "d3";
  import { onMount } from "svelte";
  import { tweened } from "svelte/motion";
  import { cubicOut } from "svelte/easing";
  import type { PartyTotals } from "./data";
  import { colors } from "./colors/store.svelte";
  import { hasMajority } from "./electoral";
  import ChartTooltip, { type TooltipState } from "./ChartTooltip.svelte";

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

  // Visual minimum-angle for tiny slices.
  // The honest geometry: 1 seat out of 234 = 1.54° = 0.027 rad. Below ~2°
  // a slice is essentially invisible to the human eye even before any
  // gradient/shadow blurring eats more pixels off the edges. We give every
  // visible slice a *visual* minimum of 1.4° (0.024 rad), then redistribute
  // the donated angle from the largest slice. The numeric tally + tooltip
  // both still report the true seat counts, so the chart stays honest while
  // becoming readable for fringe parties (TVK in 2021, BJP/DMDK in 2026).
  const MIN_VISUAL_ANGLE = 0.024;

  function key_for(p: PartyTotals): string {
    return p.party_eci_code ?? p.party_short;
  }

  // Sweep-in entrance. `progress` goes 0 → 1 on mount; arc end-angles and
  // the centre tally are both gated on it so the chart "draws itself".
  const progress = tweened(0, { duration: 950, easing: cubicOut });
  onMount(() => { progress.set(1); });

  // Hover pop-out. Tracking the hovered slice key lets the SVG path swap to
  // a slightly larger arc generator (outerRadius +6) for the lift effect,
  // with a CSS transition giving the motion.
  let hover_key = $state<string | null>(null);
  let tooltip = $state<TooltipState | null>(null);

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

  // Visual angles per slice — see MIN_VISUAL_ANGLE comment. We compute the
  // honest fractions, lift any below the floor up to it, and then subtract
  // the borrowed budget from the largest slice (which can spare it without
  // becoming visually wrong — donating 6° from a 130° wedge is invisible).
  const visual_angles = $derived.by<{ key: string; angle: number }[]>(() => {
    const data = ranked;
    const total = data.reduce((s, p) => s + p.seats_won, 0) || 1;
    const TWO_PI = 2 * Math.PI;
    const honest = data.map(p => ({ key: p.key, angle: (p.seats_won / total) * TWO_PI }));
    let borrowed = 0;
    const adjusted = honest.map(a => {
      if (a.angle < MIN_VISUAL_ANGLE) {
        borrowed += MIN_VISUAL_ANGLE - a.angle;
        return { ...a, angle: MIN_VISUAL_ANGLE };
      }
      return a;
    });
    if (borrowed > 0) {
      // Subtract from the largest slice — by construction it's at least
      // ~30° in any plausible election, so a few degrees off won't read.
      let maxIdx = 0;
      for (let i = 1; i < adjusted.length; i++) if (adjusted[i].angle > adjusted[maxIdx].angle) maxIdx = i;
      adjusted[maxIdx] = { ...adjusted[maxIdx], angle: Math.max(0, adjusted[maxIdx].angle - borrowed) };
    }
    return adjusted;
  });

  // Build arcs by hand (instead of d3.pie) so we can scale the cumulative
  // sweep against `progress`. padAngle gives the modern segmented-ring look;
  // cornerRadius rounds the slice ends. We removed the white inter-slice
  // stroke that the previous iteration used — combined with padAngle it was
  // double-spacing every wedge and erasing the 1-seat slivers entirely.
  const arcs = $derived.by(() => {
    const data = ranked;
    const sweep = 2 * Math.PI * $progress;
    const arcGen = d3.arc<{ startAngle: number; endAngle: number }>()
      .innerRadius(inner)
      .outerRadius(outer)
      .padAngle(0.018)
      .cornerRadius(4);
    const popGen = d3.arc<{ startAngle: number; endAngle: number }>()
      .innerRadius(inner)
      .outerRadius(outer + 6)
      .padAngle(0.018)
      .cornerRadius(4);
    let cum = 0;
    const angleByKey = new Map(visual_angles.map(v => [v.key, v.angle]));
    return data.map(p => {
      const a = angleByKey.get(p.key) ?? 0;
      const start = cum;
      const end = cum + a;
      cum = end;
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
        full_name: p.party_full ?? p.party_short,
        seats: p.seats_won,
        vote_share: p.vote_share_pct,
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

  // The donut still uses the *leader has majority* signal to draw a gold
  // halo, but the textual leader pill below the donut is gone — per UX
  // review, the bar chart + tooltip already carry that information and the
  // pill was a static repeat.
  const leader = $derived(arcs[0] ?? null);
  const leader_has_majority = $derived(
    leader != null && hasMajority(leader.seats, total_seats),
  );

  // Animated centre tally. We tween the integer to the *currently visible*
  // total so muting a party also animates the centre down/up smoothly.
  const tally = tweened(0, { duration: 600, easing: cubicOut });
  $effect(() => {
    void $progress;
    tally.set(hidden_seats > 0 ? visible_seats : total_seats);
  });

  function showTip(e: MouseEvent, a: typeof arcs[number]): void {
    const muted = !!hidden_parties?.has(a.key);
    tooltip = {
      x: e.clientX,
      y: e.clientY,
      color: a.color,
      title: a.label,
      subtitle: a.full_name !== a.label ? a.full_name : undefined,
      lines: [
        { label: "Seats", value: String(a.seats), suffix: `of ${total_seats}` },
        { label: "Vote share", value: `${a.vote_share.toFixed(1)}%` },
      ],
      hint: onToggleHidden ? (muted ? "Click to show this party" : "Click to mute this party") : undefined,
    };
  }
  function moveTip(e: MouseEvent): void {
    if (tooltip) tooltip = { ...tooltip, x: e.clientX, y: e.clientY };
  }
  function hideTip(): void { tooltip = null; }
</script>

<div class="flex flex-col items-center">
  <svg
    width={size}
    height={size}
    viewBox="-{radius} -{radius} {size} {size}"
    class="overflow-visible"
    role="img"
    aria-label="House composition donut chart"
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
        class:cursor-pointer={clickable}
        style="transition: d 180ms ease-out;"
        onclick={() => onToggleHidden?.(a.key)}
        onmouseenter={(e) => { hover_key = a.key; showTip(e, a); }}
        onmousemove={moveTip}
        onmouseleave={() => { hover_key = null; hideTip(); }}
        onfocus={(e) => { hover_key = a.key; showTip(e as unknown as MouseEvent, a); }}
        onblur={() => { hover_key = null; hideTip(); }}
        role={clickable ? "button" : undefined}
        tabindex={clickable ? 0 : undefined}
        aria-label="{a.label}: {a.seats} seats{muted ? ' (muted)' : ''}"
      ></path>
    {/each}

    <!-- Centre tally. Two-line layout: big animated number + small label;
         the optional "of N" line appears only when something is muted. -->
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
</div>

<ChartTooltip tip={tooltip} />
