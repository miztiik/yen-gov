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
  import PartySymbolGlyph, { glyphUrlFor } from "./PartySymbolGlyph.svelte";
  import { majorityFor } from "./electoral";
  import { orderArcParties } from "./parliament-arc-order";
  import {
    computeArcGeometry,
    ARC_W,
    ARC_H,
    ARC_CX,
    ARC_CY,
    ARC_R_INNER,
    ARC_R_OUTER,
  } from "./parliament-arc-geometry";

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


  // Geometry lives in a pure, unit-tested helper (parliament-arc-geometry.ts)
  // so the 234-seat reconciliation + small-chamber compactness invariants can
  // be proven without mounting this component. The helper scales BOTH radii
  // with seat count (clamped to 1 at >= 140 seats) so small chambers render
  // compact; large chambers (TN 234) stay byte-identical to the prior layout.
  const geometry = $derived(computeArcGeometry({ parties, total_seats, alliance_of }));
  const layout = $derived(geometry.dots);
  const dot_radius = $derived(geometry.dot_radius);

  // Effective radii for the majority midline + label so they track the
  // compact arc. max_radius is the scaled outer radius; the inner is the same
  // scale applied to ARC_R_INNER (max_radius * ARC_R_INNER / ARC_R_OUTER).
  const max_radius = $derived(geometry.max_radius);
  const inner_radius = $derived(max_radius * (ARC_R_INNER / ARC_R_OUTER));
  const majority = $derived(majorityFor(total_seats));

  // Focused party - the seat bloc the citizen is pointing at (a seat dot or
  // a legend chip). Drives BOTH the centre read-out and the dimming of every
  // other party's dots. Null = nothing hovered; the centre then shows the
  // chamber total ("N seats") so the empty middle is never blank.
  let focused_pid = $state<string | null>(null);

  // Per-party legend, in the same (alliance-grouped or seats) order as the dots.
  const legend = $derived(orderActiveParties(parties));

  // Party rendered in the chamber centre while hovered. Null = nothing
  // focused, in which case the centre falls back to the chamber total. Its
  // brand colour + curated symbol feed the seats / name / glyph read-out.
  const focused_party = $derived(
    focused_pid != null
      ? parties.find((p) => p.party_eci_code === focused_pid) ?? null
      : null,
  );
  const focused_colour = $derived(
    focused_party ? partyColourHex(focused_party) : "#0f172a",
  );
  const focused_logo = $derived(
    focused_party ? glyphUrlFor(focused_party.election_symbol_asset_path) : null,
  );
</script>

<div class="relative pt-4">
  <!--
    viewBox top is `-20`, not `0`. At full size (scale 1, >= 140 seats) the
    majority label sits at y = cy - max_radius - 12 = (380 - 24) - 340 - 12 = 4,
    which clipped the text ascenders above a `0` top edge. 20px of headroom
    keeps the label fully visible. The viewBox WIDTH stays ARC_W so a compact
    (scaled) arc shows centred with left/right whitespace instead of being
    scaled back up to full width by `w-full`. cx/cy + the 234-dot
    reconciliation math the E5 invariant gate depends on are unchanged.
  -->
  <svg viewBox="0 -20 {ARC_W} {ARC_H + 20}" class="w-full h-auto" role="img" aria-label="Seat distribution arc">
    <!-- Majority midline - tracks the compact arc via max_radius / inner_radius -->
    <line
      x1={ARC_CX} y1={ARC_CY - max_radius - 8} x2={ARC_CX} y2={ARC_CY - inner_radius + 8}
      stroke="#94a3b8" stroke-width="1" stroke-dasharray="4 3"
    />
    <text x={ARC_CX} y={ARC_CY - max_radius - 12} text-anchor="middle" font-size="10" fill="#64748b">
      majority {majority}
    </text>

    <!-- Seat dots -->
    {#each layout as d, i (i)}
      {@const muted = !!hidden_parties?.has(d.party_eci_code)}
      {@const dimmed = focused_pid != null && d.party_eci_code !== focused_pid}
      <circle
        cx={d.x} cy={d.y} r={dot_radius}
        fill={d.fill}
        opacity={muted ? 0.18 : dimmed ? 0.28 : 1}
        stroke="#fff" stroke-width="0.8"
        role="img" aria-label={d.party_short}
        onmouseenter={() => (focused_pid = d.party_eci_code)}
        onmouseleave={() => (focused_pid = null)}
      />
    {/each}

    <!--
      Centre read-out - painted in the empty middle of the chamber (the
      "balance of power" idiom). SVG-native (not an HTML overlay) so it scales
      with the responsive viewBox AND keeps the legend <ul> a direct
      following-sibling of this <svg>, which the e2e seat-invariant specs rely
      on (`following-sibling::ul[1]`). Carries no <circle>, so the dot-count
      invariant is untouched. `pointer-events-none` so the text never steals
      hover from the dots it sits over. Shows the hovered party (symbol +
      seats + short name, in the party's colour) when focused, else the
      chamber total ("N seats").
    -->
    {#if total_seats > 0}
      <g data-testid="parliament-arc-focus" class="pointer-events-none">
        {#if focused_party}
          {#if focused_logo}
            <image
              href={focused_logo}
              x={ARC_CX - 18} y={266}
              width="36" height="36"
              preserveAspectRatio="xMidYMid meet"
              onerror={(e) => { (e.currentTarget as SVGImageElement).style.display = "none"; }}
            />
          {/if}
          <text
            x={ARC_CX} y={focused_logo ? 336 : 330}
            text-anchor="middle" font-size="28" font-weight="800"
            fill={focused_colour} class="tabular-nums"
          >{focused_party.seats_won}</text>
          <text
            x={ARC_CX} y={focused_logo ? 354 : 348}
            text-anchor="middle" font-size="13" font-weight="600"
            fill={focused_colour}
          >{focused_party.party_short}</text>
        {:else}
          <!-- Default (nothing hovered): the chamber total. -->
          <text
            x={ARC_CX} y={334}
            text-anchor="middle" font-size="32" font-weight="800"
            fill="#0f172a" class="tabular-nums"
          >{total_seats}</text>
          <text
            x={ARC_CX} y={353}
            text-anchor="middle" font-size="12" font-weight="600"
            fill="#64748b"
          >seats</text>
        {/if}
      </g>
    {/if}
  </svg>

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
        onmouseenter={() => (focused_pid = p.party_eci_code)}
        onmouseleave={() => (focused_pid = null)}
        onfocus={() => (focused_pid = p.party_eci_code)}
        onblur={() => (focused_pid = null)}
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
