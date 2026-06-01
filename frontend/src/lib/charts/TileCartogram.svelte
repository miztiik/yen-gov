<script lang="ts">
  // TileCartogram — equal-area hex cartogram (UK-style elections plan, PR-B2).
  //
  // A pure SVG hex grid: one hexagon per constituency tile, positioned by the
  // persisted axial coords (q,r) from `election_tile_layouts.json`. NOT
  // maplibre — every seat is the same size so no large rural constituency
  // visually dominates a dense urban cluster (the whole point of a cartogram).
  //
  // Grain-agnostic: it renders whatever `TileRow[]` it is handed (AC or PC).
  // Colour / opacity / tooltip are resolved upstream by
  // `view-models/election-tile-layout.ts` (party colour + margin->opacity),
  // so this component stays purely presentational.
  //
  // CLAUDE.md §0: no aria/role; visible affordances only. Hexes are real
  // <polygon> with pointer + keyboard-free click handlers.

  import type { TileRow } from "../view-models/election-tile-layout";

  interface LegendEntry {
    label: string;
    color: string;
  }

  interface Props {
    tiles: TileRow[];
    /** CSS height of the SVG container. */
    height?: string;
    /** unit_id to emphasise; every other tile dims so it reads first. */
    highlight_key?: string | null;
    legend?: LegendEntry[];
    onSelect?: (unit_id: string) => void;
    onHover?: (unit_id: string | null) => void;
  }

  let {
    tiles,
    height = "520px",
    highlight_key = null,
    legend = [],
    onSelect,
    onHover,
  }: Props = $props();

  // Hex geometry (pointy-top, odd-r offset). `S` = centre-to-corner radius.
  const S = 10;
  const HEX_W = Math.sqrt(3) * S; // flat width
  const ROW_H = 1.5 * S; // vertical centre spacing
  const PAD = S;

  const bounds = $derived.by(() => {
    if (tiles.length === 0) return { minQ: 0, maxQ: 0, minR: 0, maxR: 0 };
    let minQ = Infinity,
      maxQ = -Infinity,
      minR = Infinity,
      maxR = -Infinity;
    for (const t of tiles) {
      if (t.q < minQ) minQ = t.q;
      if (t.q > maxQ) maxQ = t.q;
      if (t.r < minR) minR = t.r;
      if (t.r > maxR) maxR = t.r;
    }
    return { minQ, maxQ, minR, maxR };
  });

  function center(q: number, r: number): { cx: number; cy: number } {
    const col = q - bounds.minQ;
    const row = r - bounds.minR;
    const offset = (row & 1) === 1 ? HEX_W / 2 : 0;
    const cx = PAD + col * HEX_W + offset + HEX_W / 2;
    const cy = PAD + row * ROW_H + S;
    return { cx, cy };
  }

  // Pointy-top hexagon vertices (vertex at top).
  function hexPoints(cx: number, cy: number): string {
    const pts: string[] = [];
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 180) * (60 * i - 90);
      pts.push(`${(cx + S * Math.cos(a)).toFixed(2)},${(cy + S * Math.sin(a)).toFixed(2)}`);
    }
    return pts.join(" ");
  }

  const viewBox = $derived.by(() => {
    const cols = bounds.maxQ - bounds.minQ + 1;
    const rows = bounds.maxR - bounds.minR + 1;
    const w = PAD * 2 + cols * HEX_W + HEX_W / 2;
    const h = PAD * 2 + (rows - 1) * ROW_H + 2 * S;
    return `0 0 ${w.toFixed(1)} ${h.toFixed(1)}`;
  });

  const rendered = $derived(
    tiles.map((t) => {
      const { cx, cy } = center(t.q, t.r);
      const dim =
        highlight_key != null && t.unit_id !== highlight_key ? 0.22 : 1;
      const opacity = t.unit_id === highlight_key ? 1 : t.opacity * dim;
      return { tile: t, points: hexPoints(cx, cy), opacity };
    }),
  );

  let hovered = $state<string | null>(null);
  let tip = $state<{ x: number; y: number; html: string } | null>(null);

  function onEnter(e: MouseEvent, t: TileRow): void {
    hovered = t.unit_id;
    tip = { x: e.offsetX, y: e.offsetY, html: t.tooltip_html };
    onHover?.(t.unit_id);
  }
  function onMove(e: MouseEvent): void {
    if (tip) tip = { ...tip, x: e.offsetX, y: e.offsetY };
  }
  function onLeave(): void {
    hovered = null;
    tip = null;
    onHover?.(null);
  }
</script>

<div class="tile-cartogram relative" style:height>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <svg
    viewBox={viewBox}
    class="h-full w-full"
    preserveAspectRatio="xMidYMid meet"
    onmousemove={onMove}
    onmouseleave={onLeave}
  >
    {#each rendered as r (r.tile.unit_id)}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <polygon
        points={r.points}
        fill={r.tile.fill}
        fill-opacity={r.opacity}
        stroke={r.tile.selected ? "#0f172a" : hovered === r.tile.unit_id ? "#334155" : "#ffffff"}
        stroke-width={r.tile.selected ? 2 : hovered === r.tile.unit_id ? 1.5 : 0.6}
        class="cursor-pointer transition-[stroke-width] duration-75"
        data-unit-id={r.tile.unit_id}
        data-pending={r.tile.pending}
        onclick={() => onSelect?.(r.tile.unit_id)}
        onmouseenter={(e) => onEnter(e, r.tile)}
      ></polygon>
    {/each}
  </svg>

  {#if tip}
    <div
      class="pointer-events-none absolute z-10 rounded bg-white px-2 py-1 text-xs shadow-lg ring-1 ring-slate-200"
      style:left={`${tip.x + 12}px`}
      style:top={`${tip.y + 12}px`}
    >
      {@html tip.html}
    </div>
  {/if}

  {#if legend.length > 0}
    <div class="mt-2 flex flex-wrap gap-3 text-xs text-slate-600">
      {#each legend as l (l.label)}
        <span class="inline-flex items-center gap-1">
          <span class="inline-block h-3 w-3 rounded-sm" style:background-color={l.color}></span>
          {l.label}
        </span>
      {/each}
    </div>
  {/if}
</div>
