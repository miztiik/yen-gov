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
  //
  // Parent plan section 25.4 (E3): optional faint state silhouette layer
  // drawn BEHIND the hex grid for single-state cartograms (ElectionMap),
  // so the citizen instantly recognises which state the tile board
  // represents. Source = the SAME canonical `boundaries/in/states/all.topojson`
  // the choropleth surface loads via `loadStateSilhouette` - one shared
  // boundary corpus, no new fetch. The national cartogram
  // (NationalElectionsAtlas) does not pass a silhouette feature; the
  // layer is skipped.

  import { geoMercator, geoPath, type GeoPermissibleObjects } from "d3-geo";
  import type { Feature, Geometry, GeoJsonProperties } from "geojson";

  import type { TileRow } from "../view-models/election-tile-layout";
  import {
    DEFAULT_HIGHLIGHT_STATE,
    NEUTRAL_HEX_FALLBACK,
    cellTreatment,
    type HighlightMode,
    type MinMargin,
  } from "./map-highlight-utils";
  import HoverCardShell from "./HoverCardShell.svelte";

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
    /**
     * Parent plan section 25.4 (E3): optional state silhouette feature.
     * When supplied (single-state cartograms only), the renderer
     * projects this feature via `d3-geo geoMercator().fitSize` onto
     * the SAME viewBox the hex grid uses, then renders a slate-200
     * `<path>` at 0.25 opacity UNDER the hexes so the citizen reads
     * the rough state shape as a containing envelope. National
     * cartograms (e.g. `NationalElectionsAtlas`) leave this null and
     * the layer is skipped (back-compat).
     */
    state_silhouette_feature?: Feature<Geometry, GeoJsonProperties> | null;
    /**
     * E4 (parent plan section 25.5): the shared map-highlight axis.
     * Both StateAcMap and TileCartogram read the same `MapHighlightLegend`
     * component up-stream; the legend's `{ mode, selected_party_id,
     * min_margin }` state is threaded here as 3 props. When the props
     * stay at their defaults (`margin` mode), each tile is painted
     * with its precomputed `fill` + `opacity` from the upstream
     * builder (back-compat); the existing margin-ramp formula in the
     * builder matches `marginOpacity` exactly. When `highlight_mode`
     * is `"party_won"`, each tile's fill / opacity is recomputed via
     * the shared `cellTreatment` helper so the visual contract is
     * identical to StateAcMap. Recede uses `--party-neutral` (E2 #800
     * token) at low opacity.
     */
    highlight_mode?: HighlightMode;
    selected_party_id?: string | null;
    min_margin?: MinMargin;
  }

  let {
    tiles,
    height = "520px",
    highlight_key = null,
    legend = [],
    onSelect,
    onHover,
    state_silhouette_feature = null,
    highlight_mode = DEFAULT_HIGHLIGHT_STATE.mode,
    selected_party_id = DEFAULT_HIGHLIGHT_STATE.selected_party_id,
    min_margin = DEFAULT_HIGHLIGHT_STATE.min_margin,
  }: Props = $props();

  // Hex geometry (pointy-top, odd-r offset). `S` = centre-to-corner radius.
  const S = 10;
  const HEX_W = Math.sqrt(3) * S; // flat width
  const ROW_H = 1.5 * S; // vertical centre spacing
  const PAD = S;
  // In-hex 2-letter state label (US-style tilegram). Sized to fit two
  // upper-case glyphs inside the flat hex width (HEX_W ~= 1.73*S); only
  // drawn when the tile carries a `code` (multi-state cartograms only).
  const CODE_FONT = S * 0.78;

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

  // Parent plan section 25.4 (E3): the silhouette path. Projected via
  // `geoMercator().fitSize` so the feature fills the same SVG viewBox
  // the hex grid uses; the hexes float on top of the rough state
  // envelope. Cartograms are by definition area-preserving, so this
  // is "decor" - the silhouette is not pixel-aligned to any hex.
  const silhouette_path = $derived.by(() => {
    if (!state_silhouette_feature) return null;
    const cols = bounds.maxQ - bounds.minQ + 1;
    const rows = bounds.maxR - bounds.minR + 1;
    const w = PAD * 2 + cols * HEX_W + HEX_W / 2;
    const h = PAD * 2 + (rows - 1) * ROW_H + 2 * S;
    try {
      const projection = geoMercator().fitSize(
        [w, h],
        state_silhouette_feature as GeoPermissibleObjects,
      );
      const path = geoPath(projection);
      return path(state_silhouette_feature) ?? null;
    } catch {
      return null;
    }
  });

  const rendered = $derived(
    tiles.map((t) => {
      const { cx, cy } = center(t.q, t.r);
      // E4 (parent plan section 25.5): when the shared highlight
      // legend is in `party_won` mode, recompute fill / opacity / stroke
      // via `cellTreatment` so the visual contract matches StateAcMap
      // exactly. In `margin` mode the precomputed `t.fill` + `t.opacity`
      // from `buildTileRows` already encode the winner-colour +
      // marginOpacity ramp (the builder uses the same formula), so we
      // skip the recompute and keep zero behaviour change for non-E4
      // consumers (e.g. the national PC atlas).
      let fill = t.fill;
      let base_opacity = t.opacity;
      let recede_stroke: string | null = null;
      if (highlight_mode === "party_won") {
        const treat = cellTreatment({
          mode: highlight_mode,
          selected_party_id,
          min_margin,
          winner_party_id: t.winner_party_id ?? null,
          margin_pct: t.margin_pct ?? null,
          winner_party_hex: t.fill,
          neutral_hex,
        });
        fill = treat.fill;
        base_opacity = treat.opacity;
        recede_stroke = treat.stroke;
      }
      const dim =
        highlight_key != null && t.unit_id !== highlight_key ? 0.22 : 1;
      const opacity = t.unit_id === highlight_key ? 1 : base_opacity * dim;
      return {
        tile: t,
        points: hexPoints(cx, cy),
        cx,
        cy,
        code: t.code ?? null,
        fill,
        opacity,
        recede_stroke,
      };
    }),
  );

  let hovered = $state<string | null>(null);
  let tip = $state<{ x: number; y: number; html: string } | null>(null);

  // E4 (parent plan section 25.5): live `--party-neutral` token value
  // for the recede fill in party_won mode. Resolved on the
  // `.tile-cartogram` host so a future theme override picks up here
  // the same way it does on the host of MapHighlightLegend / PartyPill.
  // Falls back to the literal `NEUTRAL_HEX_FALLBACK` (slate-300) when
  // the DOM is not available (SSR / test stub).
  let host: HTMLDivElement | null = null;
  let neutral_hex = $state<string>(NEUTRAL_HEX_FALLBACK);
  $effect(() => {
    if (host == null) return;
    if (typeof getComputedStyle === "undefined") return;
    try {
      const v = getComputedStyle(host).getPropertyValue("--party-neutral").trim();
      neutral_hex = v || NEUTRAL_HEX_FALLBACK;
    } catch {
      neutral_hex = NEUTRAL_HEX_FALLBACK;
    }
  });

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

<div class="tile-cartogram relative" style:height bind:this={host}>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <svg
    viewBox={viewBox}
    class="h-full w-full"
    preserveAspectRatio="xMidYMid meet"
    onmousemove={onMove}
    onmouseleave={onLeave}
    data-highlight-mode={highlight_mode}
    data-selected-party-id={selected_party_id ?? ""}
    data-min-margin={min_margin}
  >
    {#if silhouette_path}
      <!--
        Parent plan section 25.4 (E3) state silhouette: slate-200 fill
        at ~0.25 opacity, no stroke, non-interactive. Rendered BEFORE
        the hex grid so the grid paints on top.
      -->
      <path
        d={silhouette_path}
        fill="#e2e8f0"
        fill-opacity="0.25"
        stroke="none"
        pointer-events="none"
        data-layer="state-silhouette"
      ></path>
    {/if}
    {#each rendered as r (r.tile.unit_id)}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <polygon
        points={r.points}
        fill={r.fill}
        fill-opacity={r.opacity}
        stroke={r.tile.selected
          ? "#0f172a"
          : hovered === r.tile.unit_id
          ? "#334155"
          : r.recede_stroke ?? "#ffffff"}
        stroke-width={r.tile.selected ? 2 : hovered === r.tile.unit_id ? 1.5 : 0.6}
        class="cursor-pointer transition-[stroke-width] duration-75"
        data-unit-id={r.tile.unit_id}
        data-pending={r.tile.pending}
        data-recede={r.recede_stroke != null}
        onclick={() => onSelect?.(r.tile.unit_id)}
        onmouseenter={(e) => onEnter(e, r.tile)}
      ></polygon>
      {#if r.code}
        <!--
          In-hex 2-letter state label (US-style tilegram). White glyph
          with a dark halo (paint-order:stroke) so it reads on any party
          fill AND on the light "pending" grey. Non-interactive so the
          hover / click still lands on the hex underneath.
        -->
        <text
          x={r.cx}
          y={r.cy}
          text-anchor="middle"
          dominant-baseline="central"
          font-size={CODE_FONT}
          font-weight="700"
          fill="#ffffff"
          stroke="#0f172a"
          stroke-width={CODE_FONT * 0.16}
          stroke-opacity="0.55"
          paint-order="stroke"
          stroke-linejoin="round"
          pointer-events="none"
          class="select-none"
          data-tile-code={r.code}
        >{r.code}</text>
      {/if}
    {/each}
  </svg>

  {#if tip}
    <HoverCardShell
      x={tip.x}
      y={tip.y}
      html={tip.html}
      containerW={host?.clientWidth ?? 0}
      containerH={host?.clientHeight ?? 0}
    />
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
