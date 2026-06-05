<script module lang="ts">
  /**
   * F2b.6 CirclePack - clustered-magnitude renderer per parent plan
   * §15.1 row 8. Two modes:
   *   - `pack`   d3-hierarchy.pack(); padding=2; hierarchical
   *              (parent_id grouping respected); precise-compare vibe.
   *   - `bubble` d3-hierarchy.pack(); padding=8; flat children only
   *              (parent_id ignored); clustered-magnitude vibe.
   *
   * Discriminator vs Treemap per parent §15.1:
   *   - Treemap = precise compare (rectangles tile to fill).
   *   - CirclePack = clustered magnitude vibe (circles cluster).
   *
   * Doctrine ties:
   *   - One card per measure. The mode picker is INSIDE the card.
   *   - Labels render only when r >= 24px; smaller circles are
   *     swatch-only with the label exposed via tooltip on hover.
   *   - Sqrt area scale HONESTY per parent §15.1; d3-hierarchy.pack()
   *     applies this directly when the hierarchy is summed via
   *     `.sum(d => d.value)`.
   *   - CLAUDE.md §0: no aria/role on circles.
   */
  export {
    packLayout,
    shouldRenderCircleLabel,
  } from "./circle-pack-helpers";
</script>

<script lang="ts">
  import MapTooltip from "./MapTooltip.svelte";
  import SourceLine from "./SourceLine.svelte";
  import {
    packLayout,
    shouldRenderCircleLabel,
    type CirclePackCircle,
    type CirclePackMode,
    type CirclePackRow,
  } from "./circle-pack-helpers";

  interface Props {
    /** Observation rows; one per leaf. */
    rows: readonly CirclePackRow[];
    /** Mode discriminator (pack vs bubble). */
    mode?: CirclePackMode;
    /** Circle fill resolver (category palette or shared-scale binned). */
    color_for_circle?: (circle: CirclePackCircle) => string;
    /** Citizen-readable value formatter. */
    format_value?: (v: number) => string;
    /** Chart title. */
    title: string;
    /** Source publisher (mandatory for C5). */
    source_owner: string;
    /** Source vintage label. */
    source_vintage: string;
    /** Optional source URL. */
    source_url?: string | null;
    /** Total svg width in px. */
    width?: number;
    /** Total svg height in px. */
    height?: number;
    /** Minimum radius for the in-circle label to render. */
    label_min_radius_px?: number;
  }

  const DEFAULT_FILL = "#94a3b8";

  const {
    rows,
    mode = "pack",
    color_for_circle,
    format_value,
    title,
    source_owner,
    source_vintage,
    source_url = null,
    width = 640,
    height = 480,
    label_min_radius_px = 24,
  }: Props = $props();

  let hover_id = $state<string | null>(null);
  let hover_x = $state<number>(0);
  let hover_y = $state<number>(0);

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

  const circles = $derived(packLayout(rows, { width, height, mode }));

  function fillForCircle(c: CirclePackCircle): string {
    return color_for_circle ? color_for_circle(c) : DEFAULT_FILL;
  }

  function onCircleEnter(c: CirclePackCircle, e: MouseEvent): void {
    hover_id = c.id;
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
  }
  function onCircleMove(e: MouseEvent): void {
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
  }
  function onCircleLeave(): void {
    hover_id = null;
  }

  const hover_payload = $derived.by(() => {
    if (hover_id == null) return null;
    const c = circles.find(x => x.id === hover_id);
    if (!c) return null;
    return {
      region_label: c.label,
      parent_label: c.parent_id,
      formatted_value: fmt(c.value),
      swatch_color: fillForCircle(c),
    };
  });
</script>

<div
  class="circle-pack"
  data-component="circle-pack"
  data-mode={mode}
  style="width: {width}px;"
>
  <div class="circle-pack__title">{title}</div>

  <div
    class="circle-pack__canvas"
    style="position: relative; width: {width}px; height: {height}px;"
  >
    <svg
      class="circle-pack__svg"
      width={width}
      height={height}
      viewBox="0 0 {width} {height}"
    >
      {#each circles as c (c.id)}
        {@const label_visible = shouldRenderCircleLabel(c, label_min_radius_px)}
        <g class="circle-pack__circle-group">
          <circle
            cx={c.cx}
            cy={c.cy}
            r={c.r}
            fill={fillForCircle(c)}
            stroke="var(--surface)"
            stroke-width="1"
            class="circle-pack__circle"
            data-circle-id={c.id}
            onmouseenter={(e) => onCircleEnter(c, e)}
            onmousemove={onCircleMove}
            onmouseleave={onCircleLeave}
          />
          {#if label_visible}
            <text
              x={c.cx}
              y={c.cy - 4}
              text-anchor="middle"
              font-size="11"
              font-weight="600"
              fill="var(--surface)"
              class="circle-pack__label"
              pointer-events="none"
            >
              {c.label}
            </text>
            <text
              x={c.cx}
              y={c.cy + 10}
              text-anchor="middle"
              font-size="10"
              fill="var(--surface)"
              class="circle-pack__value"
              pointer-events="none"
            >
              {fmt(c.value)}
            </text>
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

  <div class="circle-pack__source">
    <SourceLine
      owner={source_owner}
      vintage={source_vintage}
      url={source_url}
    />
  </div>
</div>

<style>
  .circle-pack {
    font-family: var(--font-sans);
    color: var(--ink);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .circle-pack__title {
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
  }
  .circle-pack__canvas {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--r-md);
    overflow: hidden;
  }
  .circle-pack__svg {
    display: block;
  }
  .circle-pack__circle {
    cursor: pointer;
    transition: stroke-width 120ms ease-out;
  }
  .circle-pack__circle:hover {
    stroke: var(--ink);
    stroke-width: 2;
  }
</style>
