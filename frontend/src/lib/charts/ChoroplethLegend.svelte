<script module lang="ts">
  // C2 ChoroplethLegend (parent plan section 14.3) - horizontal binned
  // intensity bar with title + numeric tick labels + an optional
  // value-tick marker (caret + hairline) for the hovered / selected
  // entity. Shared with <Matrix> per parent plan section 14.5
  // doctrine #5 (ColorScale + Legend serves both Choropleth + Matrix).
  //
  // Doctrine ties:
  //   - Rectangular always (per parent 14.3 + Jony bank-branch
  //     observation). Never circular, never angular.
  //   - Numeric labels always (never colour alone) per parent 14.5 #5.
  //   - Value-tick only when `shouldRenderValueTick(domain, value)`
  //     returns true (predicate exported by color-scale.ts for unit
  //     coverage; rendering branch is a pure boolean here).
  //   - CLAUDE.md section 0: no aria/role. Visible affordances only.

  import type { BinnedSequentialScale } from "./color-scale";

  // Re-export the predicate so consumers can type-check renderer
  // wiring (e.g. GeoChoropleth + Matrix call this BEFORE setting the
  // legend's value_tick prop to short-circuit a meaningless render).
  export { shouldRenderValueTick } from "./color-scale";
</script>

<script lang="ts">
  import { shouldRenderValueTick } from "./color-scale";

  interface Props {
    /** The binned scale built via `binnedSequential(...)`. Provides
     *  the swatches + tick labels + position math. */
    scale: BinnedSequentialScale;
    /** Domain the scale was built over. Passed in separately so the
     *  predicate + position math do not have to round-trip through
     *  the scale's bin edges. */
    domain: { min: number; max: number };
    /** Legend title (typically the indicator name + unit). */
    title: string;
    /** Optional value-tick: render the caret + hairline marker on the
     *  legend bar when this value is in-domain (Jony's bank-branch
     *  chart observation). Null/undefined hides the marker. */
    value_tick?: number | null;
    /** Optional label for the value-tick (typically the entity name
     *  + formatted value, e.g. "Karnataka: 24.1 GW"). Hidden when
     *  the value-tick itself is hidden. */
    value_tick_label?: string | null;
    /** Bar height in px. Default 12 (per parent 14.3 "rectangular
     *  binned intensity bar" - the bar is the chrome, not the data). */
    bar_height?: number;
    /** Width of the bar in px. Caller controls layout. */
    width?: number;
  }

  const {
    scale,
    domain,
    title,
    value_tick = null,
    value_tick_label = null,
    bar_height = 12,
    width = 320,
  }: Props = $props();

  // Position math derived from the scale. Returns null when the value
  // is out-of-domain so the tick disappears cleanly.
  const tick_position = $derived(
    shouldRenderValueTick(domain, value_tick)
      ? scale.positionForValue(value_tick ?? null)
      : null,
  );
  const tick_x_px = $derived(
    tick_position == null ? null : tick_position * width,
  );

  // Even-spaced tick label positions across the bar. We render every
  // bin edge (length = bins + 1). At 5 bins that is 6 labels.
  const tick_xs = $derived.by(() => {
    const n = scale.bin_edges.length;
    if (n <= 1) return [];
    return scale.bin_edges.map((_, i) => (i / (n - 1)) * width);
  });
</script>

<div class="choropleth-legend" data-component="choropleth-legend">
  <div class="choropleth-legend__title">{title}</div>

  <svg
    class="choropleth-legend__bar"
    width={width}
    height={bar_height + 22}
    viewBox="0 0 {width} {bar_height + 22}"
  >
    <!-- Bin swatches, side by side -->
    {#each scale.swatches as swatch, i}
      <rect
        x={(i / scale.swatches.length) * width}
        y={0}
        width={width / scale.swatches.length}
        height={bar_height}
        fill={swatch}
      />
    {/each}

    <!-- Numeric tick labels at every bin edge -->
    {#each scale.tick_labels as label, i}
      <text
        x={tick_xs[i]}
        y={bar_height + 14}
        text-anchor={i === 0 ? "start" : i === scale.tick_labels.length - 1 ? "end" : "middle"}
        font-size="10"
        fill="var(--ink-muted)"
      >
        {label}
      </text>
    {/each}

    <!-- Value-tick marker (caret + hairline) when an entity is hovered/selected -->
    {#if tick_x_px != null}
      <g class="choropleth-legend__value-tick" data-slot="value-tick">
        <!-- Vertical hairline through the bar -->
        <line
          x1={tick_x_px}
          y1={-2}
          x2={tick_x_px}
          y2={bar_height + 2}
          stroke="var(--ink)"
          stroke-width="1.5"
        />
        <!-- Caret above the bar (downward-pointing triangle) -->
        <polygon
          points="{tick_x_px - 4},-4 {tick_x_px + 4},-4 {tick_x_px},2"
          fill="var(--ink)"
        />
      </g>
    {/if}
  </svg>

  {#if value_tick_label && tick_x_px != null}
    <div class="choropleth-legend__tick-label" data-slot="value-tick-label">
      {value_tick_label}
    </div>
  {/if}
</div>

<style>
  .choropleth-legend {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-family: var(--font-sans);
    color: var(--ink);
  }
  .choropleth-legend__title {
    font-size: 12px;
    font-weight: 600;
    color: var(--ink);
  }
  .choropleth-legend__bar {
    display: block;
    overflow: visible; /* let the caret render above the bar */
  }
  .choropleth-legend__tick-label {
    font-size: 11px;
    color: var(--ink);
    font-variant-numeric: tabular-nums;
  }
</style>
