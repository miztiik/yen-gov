<script module lang="ts">
  /**
   * F2b.4 Matrix - entity x time heatmap. Renders rows pivoted into
   * a 2D grid coloured by `binnedSequential()` from color-scale.ts;
   * shares the ColorScale + Legend primitive with GeoChoropleth per
   * parent plan section 14.5 doctrine #5.
   *
   * Doctrine ties:
   *   - Pure presentation; helpers are exported from
   *     `matrix-helpers.ts` (sibling module) so vitest covers the
   *     pivot/order/domain without a DOM.
   *   - One card per measure (CLAUDE.md anti-pattern); a Matrix is
   *     ONE measure across (entity, time). Faceting lives in the
   *     wrapping IndicatorCard's tabs, not in Matrix props.
   *   - Hover any cell -> the C2 ChoroplethLegend's value-tick lights
   *     up (Jony's bank-branch chart observation; parent 14.3 C2).
   *   - CLAUDE.md section 0: no aria/role. Visible affordances only.
   *
   * Re-exports the pure helpers from `<script module>` so the .svelte
   * file is the public surface (same pattern as GeoChoropleth).
   */
  export {
    rowsByEntityByTime,
    entityOrder,
    timeOrder,
    deriveDomain,
  } from "./matrix-helpers";
</script>

<script lang="ts">
  import { type Direction } from "../indicators";
  import {
    binnedSequential,
    type BinnedSequentialScale,
  } from "./color-scale";
  import ChoroplethLegend from "./ChoroplethLegend.svelte";
  import MapTooltip from "./MapTooltip.svelte";
  import SourceLine from "./SourceLine.svelte";
  import {
    deriveDomain,
    entityOrder,
    rowsByEntityByTime,
    timeOrder,
    type MatrixRow,
  } from "./matrix-helpers";

  interface Props {
    /** Observation rows; one per (entity, time) pair. */
    rows: readonly MatrixRow[];
    /** Optional pre-sorted entity order. Defaults to entityOrder(rows). */
    entity_order?: readonly string[];
    /** Optional pre-sorted time order. Defaults to timeOrder(rows). */
    time_order?: readonly string[];
    /** Citizen-readable entity label (e.g. id -> "Karnataka"). */
    entity_label?: (entity_id: string) => string;
    /** Citizen-readable time label (e.g. "2024" -> "FY 2024-25"). */
    time_label?: (time: string) => string;
    /** Optional explicit domain override; defaults to deriveDomain(rows). */
    domain?: { min: number; max: number };
    /** Indicator direction; drives the OkLCh ramp hue. */
    direction?: Direction;
    /** Bins for the legend ColorScale. Defaults to 5. */
    bins?: number;
    /** d3-format tick label string. */
    format_tick?: string;
    /** Citizen-readable value formatter for the tooltip. */
    format_value?: (v: number) => string;
    /** Chart title. */
    title: string;
    /** Source attribution: publisher (mandatory for C5). */
    source_owner: string;
    /** Source vintage label. */
    source_vintage: string;
    /** Optional source URL. */
    source_url?: string | null;
    /** Pixel height for each cell row. */
    cell_height?: number;
    /** Minimum pixel width per cell column. Caller-driven layout. */
    cell_min_width?: number;
    /** Pixel width reserved for the left axis labels. */
    label_width?: number;
    /** Total svg width in px. Caller controls layout. */
    width?: number;
  }

  const {
    rows,
    entity_order: entity_order_prop,
    time_order: time_order_prop,
    entity_label,
    time_label,
    domain: domain_override,
    direction = "neutral",
    bins = 5,
    format_tick = ".2s",
    format_value,
    title,
    source_owner,
    source_vintage,
    source_url = null,
    cell_height = 22,
    cell_min_width = 30,
    label_width = 120,
    width = 640,
  }: Props = $props();

  // Hover state - drives the tooltip + the legend value-tick.
  let hover_entity = $state<string | null>(null);
  let hover_time = $state<string | null>(null);
  let hover_x = $state<number>(0);
  let hover_y = $state<number>(0);

  // Default tooltip formatter.
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

  // Pivot the rows once.
  const value_by_entity_by_time = $derived(rowsByEntityByTime(rows));

  // Axis orders (caller may override).
  const resolved_entities = $derived(
    entity_order_prop ?? entityOrder(rows),
  );
  const resolved_times = $derived(
    time_order_prop ?? timeOrder(rows),
  );

  // Domain from values (caller may override).
  const resolved_domain = $derived(
    domain_override ?? deriveDomain(rows),
  );

  // Build the binned color scale.
  const scale: BinnedSequentialScale = $derived(
    binnedSequential({
      domain: resolved_domain,
      bins,
      direction,
      format_tick,
    }),
  );

  // Layout: total grid width and column width.
  const grid_width = $derived(width - label_width);
  const column_width = $derived(
    Math.max(cell_min_width, grid_width / Math.max(1, resolved_times.length)),
  );
  const svg_height = $derived(
    cell_height * resolved_entities.length + 32,
  );

  // Resolve cell fill: lookup the value, then colorForValue. Missing
  // cells get the hatch fill so the grid is always rectangular.
  const HATCH_FILL = "url(#matrix-hatch)";
  function fillForCell(entity_id: string, time: string): string {
    const value = value_by_entity_by_time.get(entity_id)?.get(time);
    if (value == null) return HATCH_FILL;
    return scale.colorForValue(value);
  }

  function valueForCell(entity_id: string, time: string): number | null {
    return value_by_entity_by_time.get(entity_id)?.get(time) ?? null;
  }

  // Tooltip payload for the hovered cell.
  const hover_payload = $derived.by(() => {
    if (hover_entity == null || hover_time == null) return null;
    const value = valueForCell(hover_entity, hover_time);
    const label = entity_label ? entity_label(hover_entity) : hover_entity;
    const parent = time_label ? time_label(hover_time) : hover_time;
    return {
      region_label: label,
      parent_label: parent,
      value,
      formatted_value: value == null ? "No data" : fmt(value),
      swatch_color: value == null ? "#e2e8f0" : scale.colorForValue(value),
    };
  });

  function onCellEnter(entity_id: string, time: string, e: MouseEvent): void {
    hover_entity = entity_id;
    hover_time = time;
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
  }
  function onCellMove(e: MouseEvent): void {
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
  }
  function onCellLeave(): void {
    hover_entity = null;
    hover_time = null;
  }
</script>

<div
  class="matrix"
  data-component="matrix"
  style="width: {width}px;"
>
  <div class="matrix__title">{title}</div>

  <div
    class="matrix__canvas"
    style="position: relative; width: {width}px;"
  >
    <svg
      class="matrix__svg"
      width={width}
      height={svg_height}
      viewBox="0 0 {width} {svg_height}"
    >
      <defs>
        <!-- C4 diagonal-stripe hatch for missing cells; same visual
             language as GeoChoropleth + CategoryBar. -->
        <pattern
          id="matrix-hatch"
          width="6"
          height="6"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)"
        >
          <rect width="6" height="6" fill="#ffffff" />
          <rect width="2" height="6" fill="#d8d8d8" />
        </pattern>
      </defs>

      <!-- Top axis: time labels (rotated 0deg; the cell is wider than
           the typical time label so no rotation is needed). -->
      {#each resolved_times as t, ti}
        <text
          x={label_width + ti * column_width + column_width / 2}
          y={12}
          text-anchor="middle"
          font-size="10"
          fill="var(--ink-muted)"
        >
          {time_label ? time_label(t) : t}
        </text>
      {/each}

      <!-- Left axis: entity labels + cell rows -->
      {#each resolved_entities as entity_id, ei}
        <text
          x={label_width - 6}
          y={20 + ei * cell_height + cell_height / 2 + 4}
          text-anchor="end"
          font-size="11"
          fill="var(--ink)"
        >
          {entity_label ? entity_label(entity_id) : entity_id}
        </text>
        {#each resolved_times as t, ti}
          <rect
            x={label_width + ti * column_width}
            y={20 + ei * cell_height}
            width={column_width - 1}
            height={cell_height - 1}
            fill={fillForCell(entity_id, t)}
            stroke={hover_entity === entity_id && hover_time === t
              ? "var(--ink)"
              : "var(--surface)"}
            stroke-width={hover_entity === entity_id && hover_time === t ? 1.5 : 0.5}
            data-entity-id={entity_id}
            data-time={t}
            class="matrix__cell"
            onmouseenter={(e) => onCellEnter(entity_id, t, e)}
            onmousemove={onCellMove}
            onmouseleave={onCellLeave}
          />
        {/each}
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

  <div class="matrix__legend">
    <ChoroplethLegend
      {scale}
      domain={resolved_domain}
      {title}
      value_tick={hover_payload?.value ?? null}
      value_tick_label={hover_payload
        ? `${hover_payload.region_label} ${hover_payload.parent_label}: ${hover_payload.formatted_value}`
        : null}
      width={Math.min(width, 320)}
    />
  </div>

  <div class="matrix__source">
    <SourceLine
      owner={source_owner}
      vintage={source_vintage}
      url={source_url}
    />
  </div>
</div>

<style>
  .matrix {
    font-family: var(--font-sans);
    color: var(--ink);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .matrix__title {
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
  }
  .matrix__canvas {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--r-md);
    overflow: hidden;
    padding: 8px;
  }
  .matrix__svg {
    display: block;
  }
  .matrix__cell {
    cursor: pointer;
    transition: stroke-width 120ms ease-out;
  }
  .matrix__legend {
    margin-top: 4px;
  }
</style>
