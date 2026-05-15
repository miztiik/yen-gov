<script lang="ts">
  /**
   * SeriesBreakAnnotation — vertical marker that names a series break
   * inside a chart's plotting area (Phase 2 of the viz-layer plan).
   *
   * Renders a thin dashed vertical line at `xPx` plus a small label
   * pinned to the top of the plot. The label says e.g. "rebase 2011-04".
   *
   * The component does NOT compute the x-pixel position — the parent
   * chart, which owns the x-scale, passes it in. That keeps this
   * component pure-presentational and reusable across line / bar /
   * stacked-area renderers (all of which already produce pixel
   * coordinates from their own scales).
   *
   * Why we need it: the audit (docs/reference/data-coverage-report.md
   * §6) found that vintage-spliced NSDP rendered as one continuous
   * polyline across the 2011-12 base-year change. With Phase 1's
   * `splitOnBreaks` chopping the polyline into segments AND this
   * component naming the boundary, the citizen sees both the gap and
   * the reason for it.
   *
   * Direction-of-fit: this is a chart-internal label, not a banner.
   * For chart-level disclosure use `RebaseBanner.svelte`.
   */
  import type { SeriesBreak } from "../indicator-render";

  interface Props {
    /** The break being annotated. */
    break_: SeriesBreak;
    /** X-pixel position inside the plot area. Caller computes from
     *  its own x-scale: e.g. `xScale(break_.at_time)`. */
    xPx: number;
    /** Plot height in pixels. The line spans `0 .. plotHeight`. */
    plotHeight: number;
    /** Optional label override; defaults to "<kind> <at_time>". */
    label?: string;
  }

  const { break_, xPx, plotHeight, label }: Props = $props();

  const text = $derived(
    label ?? `${break_.kind.replaceAll("_", " ")} ${break_.at_time}`,
  );
</script>

<g class="series-break" transform={`translate(${xPx}, 0)`}>
  <line
    x1="0"
    y1="0"
    x2="0"
    y2={plotHeight}
    stroke="#94a3b8"
    stroke-width="1"
    stroke-dasharray="3 3"
  />
  <text
    x="4"
    y="10"
    font-size="10"
    fill="#475569"
    class="select-none"
  >
    {text}
  </text>
  <title>{break_.note}</title>
</g>
