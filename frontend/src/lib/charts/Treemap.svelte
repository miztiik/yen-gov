<script module lang="ts">
  /**
   * F2b.5 Treemap - tiled part-to-whole renderer per parent plan
   * section 15.1 row 7. Uses d3-hierarchy's treemap() to produce
   * aspect-ratio-balanced rectangles whose AREA is proportional to
   * `value` (sqrt HONESTY per parent plan §15.1: a 4x value reads
   * as 4x area, not 16x).
   *
   * Doctrine ties:
   *   - One card per measure (CLAUDE.md anti-pattern). A treemap is
   *     ONE breakdown view of ONE measure; faceting lives in
   *     IndicatorCard tabs, not Treemap props.
   *   - Labels render only on tiles wide AND tall enough; smaller
   *     tiles are swatch-only with the label exposed via tooltip
   *     (parent §15.1 "labels survive at 360px").
   *   - Color comes from a caller-supplied `color_for_tile` function
   *     so the same Treemap can paint by category (e.g. region)
   *     or by value-magnitude via binnedSequential() from F2b.2.
   *   - CLAUDE.md §0: no aria/role on tile rects. Visible
   *     affordances only (tooltip, swatch, label).
   *
   * Re-exports the pure helpers from `<script module>`.
   */
  export {
    treemapLayout,
    shouldRenderTileLabel,
    totalValue,
  } from "./treemap-helpers";
</script>

<script lang="ts">
  import MapTooltip from "./MapTooltip.svelte";
  import SourceLine from "./SourceLine.svelte";
  import {
    shouldRenderTileLabel,
    totalValue,
    treemapLayout,
    type TreemapRow,
    type TreemapTile,
  } from "./treemap-helpers";

  interface Props {
    /** Observation rows; one per leaf. */
    rows: readonly TreemapRow[];
    /** Tile fill resolver: callers pass either a category->colour
     *  map or a value-magnitude binned scale. Default returns a
     *  neutral slate so the renderer works without colour wiring. */
    color_for_tile?: (tile: TreemapTile) => string;
    /** Citizen-readable value formatter for tooltip + tile labels. */
    format_value?: (v: number) => string;
    /** Chart title. */
    title: string;
    /** Source publisher (mandatory for C5). */
    source_owner: string;
    /** Source vintage label. */
    source_vintage: string;
    /** Optional source URL. */
    source_url?: string | null;
    /** Total svg width in px. Caller controls layout. */
    width?: number;
    /** Total svg height in px. */
    height?: number;
    /** Minimum tile width (px) for the in-tile label to render. */
    label_min_width_px?: number;
    /** Minimum tile height (px) for the in-tile label to render. */
    label_min_height_px?: number;
  }

  const DEFAULT_FILL = "#94a3b8"; // slate-400, neutral

  const {
    rows,
    color_for_tile,
    format_value,
    title,
    source_owner,
    source_vintage,
    source_url = null,
    width = 640,
    height = 480,
    label_min_width_px = 40,
    label_min_height_px = 18,
  }: Props = $props();

  // Hover state for the C3 tooltip.
  let hover_tile_id = $state<string | null>(null);
  let hover_x = $state<number>(0);
  let hover_y = $state<number>(0);

  // Default value formatter (citizen-readable SI fallback).
  const fmt = $derived.by(() => {
    if (format_value) return format_value;
    return (v: number): string => {
      if (!Number.isFinite(v)) return "-";
      if (Math.abs(v) >= 1000) {
        return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
      }
      return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    };
  });

  // Compute the treemap layout once per (rows, width, height).
  const tiles = $derived(treemapLayout(rows, { width, height }));
  const total = $derived(totalValue(rows));

  function fillForTile(tile: TreemapTile): string {
    return color_for_tile ? color_for_tile(tile) : DEFAULT_FILL;
  }

  function onTileEnter(tile: TreemapTile, e: MouseEvent): void {
    hover_tile_id = tile.id;
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
  }
  function onTileMove(e: MouseEvent): void {
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
  }
  function onTileLeave(): void {
    hover_tile_id = null;
  }

  // Hover payload for the C3 tooltip.
  const hover_payload = $derived.by(() => {
    if (hover_tile_id == null) return null;
    const tile = tiles.find(t => t.id === hover_tile_id);
    if (!tile) return null;
    const pct = total > 0 ? (tile.value / total) * 100 : 0;
    return {
      region_label: tile.label,
      parent_label: tile.parent_id,
      formatted_value: `${fmt(tile.value)} (${pct.toFixed(1)}%)`,
      swatch_color: fillForTile(tile),
    };
  });
</script>

<div
  class="treemap"
  data-component="treemap"
  style="width: {width}px;"
>
  <div class="treemap__title">{title}</div>

  <div
    class="treemap__canvas"
    style="position: relative; width: {width}px; height: {height}px;"
  >
    <svg
      class="treemap__svg"
      width={width}
      height={height}
      viewBox="0 0 {width} {height}"
    >
      {#each tiles as tile (tile.id)}
        {@const label_visible = shouldRenderTileLabel(tile, label_min_width_px, label_min_height_px)}
        <g class="treemap__tile-group">
          <rect
            x={tile.x0}
            y={tile.y0}
            width={tile.width}
            height={tile.height}
            fill={fillForTile(tile)}
            stroke="var(--surface)"
            stroke-width="1"
            class="treemap__tile"
            data-tile-id={tile.id}
            onmouseenter={(e) => onTileEnter(tile, e)}
            onmousemove={onTileMove}
            onmouseleave={onTileLeave}
          />
          {#if label_visible}
            <text
              x={tile.x0 + 6}
              y={tile.y0 + 14}
              font-size="11"
              font-weight="600"
              fill="var(--surface)"
              class="treemap__label"
              pointer-events="none"
            >
              {tile.label}
            </text>
            {#if tile.height >= label_min_height_px + 12}
              <text
                x={tile.x0 + 6}
                y={tile.y0 + 28}
                font-size="10"
                fill="var(--surface)"
                class="treemap__value"
                pointer-events="none"
              >
                {fmt(tile.value)}
              </text>
            {/if}
          {/if}
        </g>
      {/each}
    </svg>

    {#if hover_payload}
      <MapTooltip
        x={hover_x}
        y={hover_y}
        region_label={hover_payload.region_label}
        parent_label={hover_payload.parent_label}
        formatted_value={hover_payload.formatted_value}
        swatch_color={hover_payload.swatch_color}
      />
    {/if}
  </div>

  <div class="treemap__total">
    Total: <span class="treemap__total-value">{fmt(total)}</span>
  </div>

  <div class="treemap__source">
    <SourceLine
      owner={source_owner}
      vintage={source_vintage}
      url={source_url}
    />
  </div>
</div>

<style>
  .treemap {
    font-family: var(--font-sans);
    color: var(--ink);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .treemap__title {
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
  }
  .treemap__canvas {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--r-md);
    overflow: hidden;
  }
  .treemap__svg {
    display: block;
  }
  .treemap__tile {
    cursor: pointer;
    transition: stroke-width 120ms ease-out, opacity 120ms ease-out;
  }
  .treemap__tile:hover {
    stroke: var(--ink);
    stroke-width: 2;
  }
  .treemap__total {
    font-size: 12px;
    color: var(--ink-muted);
  }
  .treemap__total-value {
    color: var(--ink);
    font-weight: 600;
  }
</style>
