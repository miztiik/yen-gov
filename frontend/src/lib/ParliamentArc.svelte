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
    /**
     * Visually mute the seats of these parties without removing them. Same
     * semantics as PartyBar / SeatDonut. Hidden seats stay in their slots
     * (so the chamber doesn't reflow on every click); they just drop to
     * low opacity. Click the legend chip to toggle.
     */
    hidden_parties?: Set<string>;
    onToggleHidden?: (party_eci_code: string) => void;
  }
  let { parties, total_seats, hidden_parties, onToggleHidden }: Props = $props();

  // Canvas grown vs v1 (was 600×320) so dots have room to breathe at
  // TN scale (234 seats). Aspect ratio still ~16:9; SVG scales to width.
  const W = 720;
  const H = 380;
  const cx = W / 2;
  const cy = H - 24;          // baseline of the semicircle
  const r_outer = 340;
  const r_inner = 140;

  // Pick a row count so every row holds at least ~6 dots and dots stay legible.
  // Heuristic: rows = clamp(round(sqrt(total/6)), 4, 12).
  const rows = $derived(Math.min(12, Math.max(4, Math.round(Math.sqrt(total_seats / 6)))));

  // Geometry derivation. Returns dot positions AND the dot radius computed
  // from the actual achieved spacing — so the radius scales with the real
  // layout (rows + per-row counts) rather than a hand-tuned √total fudge.
  const geometry = $derived.by(() => {
    type Dot = { x: number; y: number; party_eci_code: string; party_short: string };
    if (total_seats <= 0) return { dots: [] as Dot[], dot_radius: 4 };

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

    // Real spacing: along each row's arc and between rows radially.
    // Dot radius is taken as ~42 % of the tighter of the two so adjacent
    // dots never visually touch; clamped to a sane visual range.
    const radial_gap = rows > 1 ? (r_outer - r_inner) / (rows - 1) : (r_outer - r_inner);
    const min_arc_spacing = Math.min(
      ...radii.map((r, i) => (Math.PI * r) / Math.max(1, per_row[i] - 1)),
    );
    const min_spacing = Math.min(min_arc_spacing, radial_gap);
    const dot_radius = Math.max(4, Math.min(14, 0.42 * min_spacing));

    // Flat list of (row, position-in-row) sorted by angle (left → right).
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
    const dots: Dot[] = [];
    let s = 0;
    for (const p of ordered) {
      for (let k = 0; k < p.seats_won && s < slots.length; k++, s++) {
        const sl = slots[s];
        dots.push({
          x: cx + sl.r * Math.cos(sl.angle),
          y: cy - sl.r * Math.sin(sl.angle),
          party_eci_code: p.party_eci_code,
          party_short: p.party_short,
        });
      }
    }
    return { dots, dot_radius };
  });

  const layout = $derived(geometry.dots);
  const dot_radius = $derived(geometry.dot_radius);
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

<div class="relative pt-4">
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
      {@const muted = !!hidden_parties?.has(d.party_eci_code)}
      <circle
        cx={d.x} cy={d.y} r={dot_radius}
        fill={colors.fill(d.party_eci_code, d.party_short)}
        opacity={muted ? 0.18 : 1}
        stroke="#fff" stroke-width="0.8"
        role="img" aria-label={d.party_short}
        onmouseenter={() => (hover = { x: d.x, y: d.y, label: d.party_short })}
        onmouseleave={() => (hover = null)}
      />
    {/each}
  </svg>

  {#if hover}
    <!-- Tooltip rides above the dot. The wrapping `pt-4` plus a -180% Y
         translate keeps the bubble inside the rounded card even for the
         topmost row of dots (where -130% used to bleed above the card edge). -->
    <div
      class="absolute pointer-events-none px-2 py-0.5 text-xs bg-slate-900 text-white rounded shadow whitespace-nowrap"
      style:left="{(hover.x / W) * 100}%"
      style:top="{(hover.y / H) * 100}%"
      style:transform="translate(-50%, -180%)"
    >{hover.label}</div>
  {/if}

  <!-- Compact legend -->
  <ul class="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs">
    {#each legend as p (p.party_eci_code)}
      {@const muted = !!hidden_parties?.has(p.party_eci_code)}
      {@const clickable = !!onToggleHidden}
      <li
        class="flex items-center gap-1.5 transition-opacity"
        class:opacity-40={muted}
        class:cursor-pointer={clickable}
        role={clickable ? "button" : undefined}
        tabindex={clickable ? 0 : undefined}
        title={clickable ? (muted ? `Click to show ${p.party_short}` : `Click to mute ${p.party_short}`) : undefined}
        onclick={() => onToggleHidden?.(p.party_eci_code)}
        onkeydown={(e) => { if (clickable && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onToggleHidden?.(p.party_eci_code); } }}
      >
        <span class="inline-block w-2.5 h-2.5 rounded-sm" style:background-color={colors.fill(p.party_eci_code, p.party_short)}></span>
        <span class="font-medium">{p.party_short}</span>
        <span class="text-slate-500 tabular-nums">{p.seats_won}</span>
      </li>
    {/each}
  </ul>
</div>
