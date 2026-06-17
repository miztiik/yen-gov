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
  import { partyColourHex } from "./psephlab/colour-bridge";
  import PartySymbolGlyph from "./PartySymbolGlyph.svelte";
  import { majorityFor } from "./electoral";
  import { orderArcParties } from "./parliament-arc-order";

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
    /**
     * Optional alliance resolver. When provided, the chamber is ordered by
     * ALLIANCE bloc rather than by raw party size: blocs are sorted by total
     * seats descending (the winning bloc fills from chamber-left), parties
     * within a bloc by seats descending, and unaligned parties trail last.
     * Returns the alliance label for a party, or null when the party is
     * unaligned for this event. Falls back to seats-only ordering when omitted.
     */
    alliance_of?: (party: PartyResult) => string | null;
  }
  let { parties, total_seats, hidden_parties, onToggleHidden, alliance_of }: Props = $props();

  // Order the seat-bearing parties left -> right. Pure helper (see
  // parliament-arc-order.ts): seats-descending without a resolver, alliance-
  // grouped (blocs by total seats desc, parties within by seats desc,
  // unaligned trailing) when `alliance_of` is supplied.
  const orderActiveParties = (list: PartyResult[]): PartyResult[] =>
    orderArcParties(list, alliance_of);


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
    type Dot = { x: number; y: number; party_eci_code: string; party_short: string; fill: string };
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

    // Order parties left->right: alliance-grouped when a resolver is given,
    // else seats-descending (chamber-left tradition: largest first).
    const ordered = orderActiveParties(parties);

    // Walk slots in order, painting dots party-by-party.
    const dots: Dot[] = [];
    let s = 0;
    for (const p of ordered) {
      const fill = partyColourHex(p);
      for (let k = 0; k < p.seats_won && s < slots.length; k++, s++) {
        const sl = slots[s];
        dots.push({
          x: cx + sl.r * Math.cos(sl.angle),
          y: cy - sl.r * Math.sin(sl.angle),
          party_eci_code: p.party_eci_code,
          party_short: p.party_short,
          fill,
        });
      }
    }
    return { dots, dot_radius };
  });

  const layout = $derived(geometry.dots);
  const dot_radius = $derived(geometry.dot_radius);
  const majority = $derived(majorityFor(total_seats));

  // Hover tooltip.
  let hover = $state<{ x: number; y: number; label: string } | null>(null);

  // Per-party legend, in the same (alliance-grouped or seats) order as the dots.
  const legend = $derived(orderActiveParties(parties));
</script>

<div class="relative pt-4">
  <!--
    viewBox top is `-20`, not `0`. The majority label sits at y =
    cy - r_outer - 12 = (380 - 24) - 340 - 12 = 4, which clipped the
    text ascenders above a `0` top edge. 20px of headroom keeps the
    label fully visible without touching cx/cy/r_outer/r_inner or the
    234-dot reconciliation math the E5 invariant gate depends on.
  -->
  <svg viewBox="0 -20 {W} {H + 20}" class="w-full h-auto" role="img" aria-label="Seat distribution arc">
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
        fill={d.fill}
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

  <!--
    Compact legend - symbol-ring chips (Jony verdict 2026-06-09, user
    ask #2). Each chip is a small open ring stroked at the party's
    brand colour, with the party's election symbol centred inside when
    `election_symbol_asset_path` is curated. Falls back to the first
    letter of `party_short` when no glyph is curated (mirrors the
    no-placeholder doctrine in PartySymbolGlyph). The party name + seat
    count stay beside the ring so the chip still reads when the glyph
    fails. Replaces the bare 10px coloured square the legend used
    before; the swatch is forbidden going forward per CLAUDE.md
    schema-is-the-design-system rule.
  -->
  <ul class="flex flex-wrap gap-x-3 gap-y-2 mt-3 text-xs">
    {#each legend as p (p.party_eci_code)}
      {@const muted = !!hidden_parties?.has(p.party_eci_code)}
      {@const clickable = !!onToggleHidden}
      {@const ring_colour = partyColourHex(p)}
      {@const asset_path = p.election_symbol_asset_path ?? null}
      <li
        class="flex items-center gap-2 transition-opacity"
        class:opacity-40={muted}
        class:cursor-pointer={clickable}
        role={clickable ? "button" : undefined}
        tabindex={clickable ? 0 : undefined}
        title={clickable ? (muted ? `Click to show ${p.party_short}` : `Click to mute ${p.party_short}`) : undefined}
        onclick={() => onToggleHidden?.(p.party_eci_code)}
        onkeydown={(e) => { if (clickable && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onToggleHidden?.(p.party_eci_code); } }}
      >
        <span
          class="inline-flex items-center justify-center w-7 h-7 rounded-full bg-white shrink-0"
          style:border="2px solid {ring_colour}"
          aria-hidden="true"
        >
          {#if asset_path}
            <PartySymbolGlyph assetPath={asset_path} size={16} />
          {:else}
            <span class="text-[10px] font-semibold leading-none" style:color={ring_colour}>{p.party_short.charAt(0)}</span>
          {/if}
        </span>
        <span class="font-medium">{p.party_short}</span>
        <span class="text-slate-500 tabular-nums">{p.seats_won}</span>
      </li>
    {/each}
  </ul>
</div>
