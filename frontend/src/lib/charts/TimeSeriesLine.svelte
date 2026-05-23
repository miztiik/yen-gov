<script lang="ts" generics="T">
  // TimeSeriesLine — Phase 3.5 generic renderer.
  //
  // Consumes a `TimeSeriesLineViewModel<T>` built by Phase 1.6's
  // `buildTimeSeriesLineViewModel`. Renders one polyline per series
  // across the shared `period_axis`, with direct end-of-line labels
  // for the series flagged `show_direct_end_label === true`.
  //
  // Doctrine:
  //   - Pure renderer. Zero data fetching. SVG output.
  //   - Series order = builder's order (which respects pinned-first,
  //     value-desc, etc.). Points inside each series are always
  //     chronological.
  //   - Series colour from `series_colour` when provided, otherwise
  //     cycles through a small palette.
  //   - Missing points are skipped. `is_break_start` introduces a
  //     gap in the polyline (renderer breaks the path at that index
  //     when `suppress_breaks` is true) OR draws a dashed bridge
  //     when `suppress_breaks` is false.
  //   - Direct end labels only for series flagged
  //     `show_direct_end_label === true`.
  //   - Optional ChartShell wrap via `wrap_in_shell` + `chart_title`.
  //   - CLAUDE.md §0: no aria/role.

  import type { Snippet } from "svelte";
  import type {
    SourceV2Row,
    ChartShellHonestyBanner,
  } from "./chart-shell/types";
  import type {
    TimeSeriesLineViewModel,
    TimeSeriesSeriesVM,
    TimeSeriesPointVM,
  } from "./time-view-models";
  import ChartShell from "./ChartShell.svelte";

  interface Props {
    view_model: TimeSeriesLineViewModel<T>;
    chart_title?: string;
    chart_subtitle?: string | null;
    honesty_banners?: readonly ChartShellHonestyBanner[];
    sources?: readonly SourceV2Row[];
    schema_version?: string | null;
    wrap_in_shell?: boolean;
    format_value?: (v: number) => string;
    height_px?: number;
    /** Padding inside the SVG viewBox (px). */
    padding?: { top: number; right: number; bottom: number; left: number };
    /** Optional palette; cycles when a series has no `series_colour`. */
    palette?: readonly string[];
    toolbar?: Snippet;
  }

  let {
    view_model,
    chart_title,
    chart_subtitle = null,
    honesty_banners = [],
    sources,
    schema_version = null,
    wrap_in_shell = true,
    format_value = (v: number) => Number(v).toLocaleString(),
    height_px = 220,
    padding = { top: 12, right: 96, bottom: 28, left: 40 },
    palette = [
      "rgb(37 99 235)",   // blue-600
      "rgb(220 38 38)",   // red-600
      "rgb(22 163 74)",   // green-600
      "rgb(217 119 6)",   // amber-600
      "rgb(124 58 237)",  // violet-600
      "rgb(15 118 110)",  // teal-700
    ],
    toolbar,
  }: Props = $props();

  const VIEW_BOX_WIDTH = 1000;
  const inner_w = $derived(VIEW_BOX_WIDTH - padding.left - padding.right);
  const inner_h = $derived(height_px - padding.top - padding.bottom);

  const period_count = $derived(view_model.period_axis.length);

  function xFor(period_index: number): number {
    if (period_count <= 1) return padding.left + inner_w / 2;
    const f = period_index / (period_count - 1);
    return padding.left + f * inner_w;
  }

  function yFor(value: number): number {
    if (view_model.max_abs_value <= 0) return padding.top + inner_h;
    const f = Math.min(1, Math.max(0, Math.abs(value) / view_model.max_abs_value));
    return padding.top + (1 - f) * inner_h;
  }

  function colourFor(series_index: number, series_colour?: string): string {
    if (series_colour && series_colour.length > 0) return series_colour;
    if (palette.length === 0) return "rgb(71 85 105)";
    return palette[series_index % palette.length];
  }

  /**
   * Build a polyline-segment list per series. Each segment is a
   * contiguous run of non-missing points. When `suppress_breaks`
   * is true, segments are returned as-is. When false, the renderer
   * bridges across breaks with a dashed line connecting the last
   * point of one segment to the first of the next.
   */
  function segmentsFor(
    series: TimeSeriesSeriesVM<T>,
  ): { kind: "solid" | "dashed"; path: string }[] {
    const axis_index_of: Record<string, number> = {};
    view_model.period_axis.forEach((p, i) => {
      axis_index_of[p.period_id] = i;
    });

    const out: { kind: "solid" | "dashed"; path: string }[] = [];
    let current: { x: number; y: number }[] = [];
    const segments: { points: { x: number; y: number }[] }[] = [];

    for (const pt of series.points) {
      if (pt.is_missing || pt.value === null) {
        if (current.length > 0) {
          segments.push({ points: current });
          current = [];
        }
        continue;
      }
      const ix = axis_index_of[pt.period_id];
      if (ix === undefined) continue;
      current.push({ x: xFor(ix), y: yFor(pt.value) });
    }
    if (current.length > 0) segments.push({ points: current });

    for (let i = 0; i < segments.length; i++) {
      const seg = segments[i];
      const path = seg.points
        .map((p, j) => (j === 0 ? `M ${p.x.toFixed(2)} ${p.y.toFixed(2)}` : `L ${p.x.toFixed(2)} ${p.y.toFixed(2)}`))
        .join(" ");
      out.push({ kind: "solid", path });

      if (!view_model.suppress_breaks && i < segments.length - 1) {
        const a = seg.points[seg.points.length - 1];
        const b = segments[i + 1].points[0];
        out.push({
          kind: "dashed",
          path: `M ${a.x.toFixed(2)} ${a.y.toFixed(2)} L ${b.x.toFixed(2)} ${b.y.toFixed(2)}`,
        });
      }
    }
    return out;
  }

  function lastVisiblePoint(series: TimeSeriesSeriesVM<T>): TimeSeriesPointVM | null {
    for (let i = series.points.length - 1; i >= 0; i--) {
      const p = series.points[i];
      if (!p.is_missing && p.value !== null) return p;
    }
    return null;
  }

  function axisIndex(period_id: string): number {
    return view_model.period_axis.findIndex(p => p.period_id === period_id);
  }
</script>

{#snippet body()}
  <div class="tsl" data-component="time-series-line">
    <svg
      class="tsl__svg"
      viewBox="0 0 {VIEW_BOX_WIDTH} {height_px}"
      preserveAspectRatio="none"
      data-period-count={period_count}
    >
      {#each view_model.series as series, series_index (series.series_id)}
        {@const col = colourFor(series_index, series.series_colour)}
        {@const segs = segmentsFor(series)}
        {@const tip = lastVisiblePoint(series)}
        <g
          class="tsl__series"
          class:tsl__series--pinned={series.is_pinned}
          class:tsl__series--missing={series.is_missing}
          data-series-id={series.series_id}
          data-pinned={series.is_pinned}
          data-missing={series.is_missing}
        >
          {#each segs as seg, seg_index (seg_index)}
            <path
              d={seg.path}
              fill="none"
              stroke={col}
              stroke-width={series.is_pinned ? 2.5 : 1.75}
              stroke-dasharray={seg.kind === "dashed" ? "4 4" : undefined}
              stroke-linecap="round"
              stroke-linejoin="round"
            ></path>
          {/each}
          {#if tip && series.show_direct_end_label && tip.value !== null}
            {@const tx = xFor(axisIndex(tip.period_id)) + 4}
            {@const ty = yFor(tip.value)}
            <circle cx={xFor(axisIndex(tip.period_id))} cy={ty} r="3" fill={col}></circle>
            <text
              class="tsl__end-label"
              x={tx}
              y={ty}
              dy="0.32em"
              fill={col}
            >{series.series_label} {format_value(tip.value)}</text>
          {/if}
        </g>
      {/each}

      <!-- x-axis tick labels (period_label) -->
      {#each view_model.period_axis as p, i (p.period_id)}
        <text
          class="tsl__x-label"
          x={xFor(i)}
          y={height_px - 8}
          text-anchor="middle"
        >{p.period_label}</text>
      {/each}
    </svg>
  </div>
{/snippet}

{#if wrap_in_shell && chart_title}
  <ChartShell
    title={chart_title}
    subtitle={chart_subtitle}
    {honesty_banners}
    {sources}
    {schema_version}
    {toolbar}
  >
    {@render body()}
  </ChartShell>
{:else}
  {@render body()}
{/if}

<style>
  .tsl {
    width: 100%;
  }
  .tsl__svg {
    width: 100%;
    height: auto;
    display: block;
  }
  .tsl__series--missing {
    opacity: 0.35;
  }
  .tsl__x-label {
    font-size: 10px;
    fill: rgb(71 85 105); /* slate-600 */
    font-variant-numeric: tabular-nums;
  }
  .tsl__end-label {
    font-size: 10px;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
  }
</style>
