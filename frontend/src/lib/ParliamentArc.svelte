<script lang="ts">
  // ParliamentArc — seat-dot semicircle (per overview.md viz catalog).
  //
  // One dot per seat, arranged on concentric arcs. Parties are sorted by
  // seats_won desc and laid out left→right around the arc. A vertical
  // midline marks the majority threshold (ceil(total/2)).
  //
  // The geometry is parameter-free: we pick row count automatically so that
  // dots are well-spaced regardless of total seat count (TN=234, etc.).

  import type { PartyResult } from "./psephlab/types";
  import { colors } from "./colors/store.svelte";

  interface Props {
    parties: PartyResult[];           // pre-allocated; seats_won >= 0
    total_seats: number;
  }
  let { parties, total_seats }: Props = $props();

  const W = 600;
  const H = 320;
  const cx = W / 2;
  const cy = H - 20;          // baseline of the semicircle
  const r_outer = 280;
  const r_inner = 110;

  // Pick a row count so every row holds at least 6 dots and dots stay legible.
  // Heuristic: rows = clamp(round(sqrt(total/6)), 4, 12).
  const rows = $derived(Math.min(12, Math.max(4, Math.round(Math.sqrt(total_seats / 6)))));

  // Distribute dots across rows proportional to row arc length.
  // Outer rows are longer arcs → carry more dots. Each row is fully-packed
  // such that dot spacing along the arc is approximately equal.
  const layout = $derived.by(() => {
    if (total_seats <= 0) return [] as { x: number; y: number; party_eci_code: string; party_short: string }[];

    const radii: number[] = [];
    for (let i = 0; i < rows; i++) {
      const t = rows === 1 ? 0 : i / (rows - 1);
      radii.push(r_inner + (r_outer - r_inner) * t);
    }
    const arc_lengths = radii.map(r => Math.PI * r);
    const total_arc = arc_lengths.reduce((s, x) => s + x, 0);
    const per_row: number[] = arc_lengths.map(L => Math.max(1, Math.round((L / total_arc) * total_seats)));

    // Reconcile rounding so sum exactly equals total_seats.
    let drift = total_seats - per_row.reduce((s, x) => s + x, 0);
    let ridx = per_row.length - 1;
    while (drift !== 0) {
      per_row[ridx] += drift > 0 ? 1 : -1;
      drift += drift > 0 ? -1 : 1;
      ridx = (ridx - 1 + per_row.length) % per_row.length;
    }

    // Flat list of (row, position-in-row) sorted by angle (left → right).
    // Sort key: angle from π (left) to 0 (right) across all rows.
    const slots: { angle: number; r: number; row: number; col: number }[] = [];
    for (let r = 0; r < per_row.length; r++) {
      const n = per_row[r];
      for (let c = 0; c < n; c++) {
        // Angle from π (left) to 0 (right).
        const angle = n === 1 ? Math.PI / 2 : Math.PI - (c / (n - 1)) * Math.PI;
        slots.push({ angle, r: radii[r], row: r, col: c });
      }
    }
    slots.sort((a, b) => b.angle - a.angle);

    // Sort parties left→right: bigger seat counts first, ties broken by name.
    // Convention: largest party left of centre, in chamber-left tradition.
    const ordered = [...parties]
      .filter(p => p.seats_won > 0)
      .sort((a, b) => b.seats_won - a.seats_won || a.party_short.localeCompare(b.party_short));

    // Walk slots in order, painting dots party-by-party.
    const out: { x: number; y: number; party_eci_code: string; party_short: string }[] = [];
    let s = 0;
    for (const p of ordered) {
      for (let k = 0; k < p.seats_won && s < slots.length; k++, s++) {
        const sl = slots[s];
        out.push({
          x: cx + sl.r * Math.cos(sl.angle),
          y: cy - sl.r * Math.sin(sl.angle),
          party_eci_code: p.party_eci_code,
          party_short: p.party_short,
        });
      }
    }
    return out;
  });

  const dot_radius = $derived(Math.max(3, Math.min(8, 60 / Math.sqrt(total_seats))));
  const majority = $derived(Math.ceil(total_seats / 2));

  // Hover tooltip.
  let hover = $state<{ x: number; y: number; label: string } | null>(null);

  // Per-party legend (already sorted desc).
  const legend = $derived(
    [...parties]
      .filter(p => p.seats_won > 0)
      .sort((a, b) => b.seats_won - a.seats_won),
  );
</script>

<div class="relative">
  <svg viewBox="0 0 {W} {H}" class="w-full h-auto" role="img" aria-label="Seat distribution arc">
    <!-- Majority midline -->
    <line
      x1={cx} y1={cy - r_outer - 8} x2={cx} y2={cy - r_inner + 8}
      stroke="#94a3b8" stroke-width="1" stroke-dasharray="4 3"
    />
    <text x={cx} y={cy - r_outer - 12} text-anchor="middle" font-size="10" fill="#64748b">
      majority {majority}
    </text>

    <!-- Seat dots -->
    {#each layout as d, i (i)}
      <circle
        cx={d.x} cy={d.y} r={dot_radius}
        fill={colors.fill(d.party_eci_code, d.party_short)}
        stroke="#fff" stroke-width="0.8"
        role="img" aria-label={d.party_short}
        onmouseenter={() => (hover = { x: d.x, y: d.y, label: d.party_short })}
        onmouseleave={() => (hover = null)}
      />
    {/each}
  </svg>

  {#if hover}
    <div
      class="absolute pointer-events-none px-2 py-0.5 text-xs bg-slate-900 text-white rounded shadow"
      style:left="{(hover.x / W) * 100}%"
      style:top="{(hover.y / H) * 100}%"
      style:transform="translate(-50%, -130%)"
    >{hover.label}</div>
  {/if}

  <!-- Compact legend -->
  <ul class="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs">
    {#each legend as p (p.party_eci_code)}
      <li class="flex items-center gap-1.5">
        <span class="inline-block w-2.5 h-2.5 rounded-sm" style:background-color={colors.fill(p.party_eci_code, p.party_short)}></span>
        <span class="font-medium">{p.party_short}</span>
        <span class="text-slate-500 tabular-nums">{p.seats_won}</span>
      </li>
    {/each}
  </ul>
</div>
