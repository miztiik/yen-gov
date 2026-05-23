<script lang="ts">
  // StackedTrendV2 — component shell with wired bar geometry (Phase 2.1c).
  //
  // Per TODO/20260518-frontend-charting-modernisation-plan.md Phase 2.1.
  //
  // What changed from PR #108 (the 2.1b shell):
  //
  //  - The empty `<g class="stacked-trend-v2__bars"/>` placeholder is now
  //    populated with one `<rect>` per present segment per bar, geometry
  //    driven entirely by the pure helpers shipped in PR #110.
  //  - A horizontal axis baseline + period labels render below the bars
  //    so the chart is interpretable without a caller-side legend.
  //  - A flat legend strip renders below the chart, listing only
  //    `visibleCategoryIds(model)` (categories that contribute at least
  //    one non-zero present value somewhere in the series — invisible
  //    categories would only confuse a citizen).
  //
  // What's STILL out of scope (each ships in its own PR):
  //
  //  - Segmented mode toggle (Phase 2.2 / R-12 — a real `<button>` group).
  //  - Pinned readout panel on bar tap (Phase 2.3 / R-12, no hover-as-state).
  //  - Inline + leader labels (Phase 2.4).
  //  - Missing / not_applicable hatch (Phase 2.5).
  //  - Motion / 200ms tween (Phase 2.6).
  //  - Export control (Phase 2.7).
  //
  // Per R-08 Branch by Abstraction: v2 ships ALONGSIDE
  // `frontend/src/lib/charts/StackedTrend.svelte` (v1). v1 is NOT modified,
  // NOT deprecated. Caller migration is one PR per caller; v1 is deleted
  // in a single final PR after the last caller migrates. ZERO callers
  // consume v2 today, so this PR is still inert from the citizen's
  // perspective.
  //
  // SVG layout choices:
  //
  //  - One outer `<svg viewBox="0 0 100 100" preserveAspectRatio="none">`
  //    so the chart scales fluidly to any container width without locking
  //    to a pixel-grid. The height is constrained by the wrapping div
  //    (`h-72` = 18rem ≈ 288 px on desktop) so the citizen never sees a
  //    1px-tall chart on narrow viewports.
  //  - Bars are positioned at `x = i * BAR_PITCH` with width `BAR_WIDTH`
  //    so the bar count stays self-evident even when bars are short.
  //  - Segments stack from the bottom (`y = 100 - cumulativeHeight`)
  //    using `segmentVisualHeightPct` from the helpers (which mirrors v1
  //    geometry — toggling modes doesn't bounce the visual).
  //  - Colours come from the existing `categoryFill` helper plus the v2
  //    `OTHER_CATEGORY_FILL_V2` constant — same palette discipline as v1,
  //    so cross-chart consistency is preserved during migration.
  //
  // CLAUDE.md S0 (a11y descoped): no aria-label, no role attribute. The
  // honesty-banner copy + headline copy + colour discipline carry meaning
  // visually for sighted citizens; the pattern is retained on visual-
  // clarity grounds, not WCAG grounds. The `<title>` tooltip on each
  // `<rect>` is the browser-native hover-text; it costs nothing and helps
  // citizens identify segments before Phase 2.3 ships the pinned readout.

  import { categoryFill } from "../colors/category-colour";
  import {
    barTotal,
    maxBarTotal,
    segmentVisualHeightPct,
    visibleCategoryIds,
  } from "./stacked-trend-v2/helpers";
  import type {
    StackedTrendV2Model,
    StackedTrendV2Segment,
  } from "./stacked-trend-v2/types";
  import {
    OTHER_CATEGORY_FILL_V2,
    OTHER_CATEGORY_ID_V2,
  } from "./stacked-trend-v2/types";

  let {
    model,
    mode_override,
  }: {
    model: StackedTrendV2Model;
    /**
     * Optional caller override of `model.default_mode`. Wired through to
     * the segmented mode control in Phase 2.2 (still TODO). Today the
     * caller's only knob is the model's `default_mode` plus this
     * optional one-way override.
     */
    mode_override?: "percent" | "absolute";
  } = $props();

  const mode = $derived<"percent" | "absolute">(
    mode_override ?? model.default_mode,
  );

  const visibleIds = $derived(visibleCategoryIds(model));
  const maxTotal = $derived(maxBarTotal(model.bars));

  /**
   * Stable lookup for a segment's fill colour. Uses the model's explicit
   * `category.fill` when set, otherwise falls back to `categoryFill`
   * (which is dimension-aware and palette-collision-aware). The
   * `__OTHER__` collapsed bucket gets the v2 fixed grey so the citizen
   * always recognises the residual.
   */
  function fillFor(category_id: string): string {
    if (category_id === OTHER_CATEGORY_ID_V2) return OTHER_CATEGORY_FILL_V2;
    const cat = model.categories.find((c) => c.id === category_id);
    if (cat?.fill) return cat.fill;
    return categoryFill(category_id, visibleIds, model.dimension);
  }

  /**
   * Plain-language number for the `<title>` tooltip + future readout
   * panel. Mirrors v1 `fmtValue` so the citizen-facing units stay
   * stable during caller migration.
   */
  function fmtValue(v: number): string {
    if (model.unit.value_kind === "share") return `${(v * 100).toFixed(1)}%`;
    if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)}k ${model.unit.label}`;
    return `${v.toFixed(0)} ${model.unit.label}`;
  }

  /** Category-id → label, for tooltip + legend chrome. */
  function labelFor(category_id: string): string {
    if (category_id === OTHER_CATEGORY_ID_V2) return "Other";
    return (
      model.categories.find((c) => c.id === category_id)?.label ?? category_id
    );
  }

  // ---- bar geometry constants --------------------------------------------
  //
  // viewBox uses 0..100 in both axes. `pitch` = the per-bar slot width
  // (bar + horizontal gap); `barWidth` = the bar itself (narrower than
  // pitch so adjacent bars don't touch). Derived from bar count so a
  // 3-bar series breathes and a 30-bar series stays dense but legible.

  const BAR_GAP_RATIO = 0.15; // 15% of pitch reserved for inter-bar gap
  const pitch = $derived(100 / Math.max(1, model.bars.length));
  const barWidth = $derived(pitch * (1 - BAR_GAP_RATIO));
  const barX = (i: number): number => i * pitch + (pitch - barWidth) / 2;

  /**
   * Pre-compute a bar's segment rectangles so the template stays flat.
   * Returns rects in stack order (bottom-most first). Hidden segments
   * (missing / not_applicable / null / zero-height) are elided — the
   * renderer will surface them as hatched rects in Phase 2.5.
   */
  interface SegmentRect {
    category_id: string;
    y: number;
    height: number;
    fill: string;
    value: number;
  }

  function rectsForBar(
    segments: readonly StackedTrendV2Segment[],
    totalForBar: number,
  ): SegmentRect[] {
    const result: SegmentRect[] = [];
    let cursorY = 100; // SVG y grows downward; stack from the bottom
    for (const seg of segments) {
      if (seg.availability !== "present") continue;
      if (seg.value == null) continue;
      const height = segmentVisualHeightPct(
        seg,
        totalForBar,
        maxTotal,
        mode,
      );
      if (height <= 0) continue;
      cursorY -= height;
      result.push({
        category_id: seg.category_id,
        y: cursorY,
        height,
        fill: fillFor(seg.category_id),
        value: seg.value,
      });
    }
    return result;
  }
</script>

<!--
  Phase 2.1c — wired bar geometry. Headline + honesty banner + SVG bar
  layer + period-label row + legend. Still NO segmented mode toggle, NO
  pinned readout panel, NO inline labels, NO hatch, NO motion, NO export.
  Citizen-visible content is meaningful for the first time in the v2
  chain; caller migration follows in Track-D D10..D12.
-->
<div
  class="stacked-trend-v2 space-y-3"
  data-chart="stacked-trend-v2"
  data-mode={mode}
>
  {#if model.headline?.text}
    <div class="rounded border border-slate-200 bg-slate-50 p-3 text-sm">
      <div class="font-semibold text-slate-800">{model.headline.text}</div>
      {#if model.headline.so_what}
        <div class="text-slate-600 text-xs mt-0.5">{model.headline.so_what}</div>
      {/if}
    </div>
  {/if}

  {#if model.honesty?.comparability === "not_comparable_across_states"}
    <div class="rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900">
      Read this carefully — ranking by this number is misleading.
    </div>
  {:else if model.honesty?.attribution_geography === "where_allocated"}
    <div class="rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900">
      Values are this state's allocated share of central-sector capacity, not the location of the plant.
    </div>
  {:else if model.honesty?.attribution_geography === "where_produced"}
    <div class="rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900">
      This shows where the asset is sited, not who uses it.
    </div>
  {/if}

  <div class="flex items-center gap-3 text-xs">
    <span class="text-slate-500">Mode</span>
    <span class="font-medium text-slate-800 uppercase tracking-wide">{mode}</span>
    <span class="ml-auto text-slate-500">{model.x_axis_label}</span>
  </div>

  <div class="stacked-trend-v2__viewport relative h-72 w-full">
    <svg
      class="stacked-trend-v2__canvas block w-full h-full"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
    >
      <g class="stacked-trend-v2__bars" data-phase="2.1c-wired">
        {#each model.bars as bar, i (bar.period_id)}
          {@const total = barTotal(bar)}
          {@const rects = rectsForBar(bar.segments, total)}
          <g class="stacked-trend-v2__bar" transform="translate({barX(i)} 0)">
            {#each rects as r (r.category_id)}
              <rect
                x="0"
                y={r.y}
                width={barWidth}
                height={r.height}
                fill={r.fill}
                class="stacked-trend-v2__segment"
              >
                <title>{labelFor(r.category_id)}: {fmtValue(r.value)}</title>
              </rect>
            {/each}
          </g>
        {/each}
      </g>
      <!-- Horizontal baseline so a citizen can see the zero line even on
           a sparse / mostly-missing series. -->
      <line
        x1="0"
        y1="100"
        x2="100"
        y2="100"
        stroke="#cbd5e1"
        stroke-width="0.3"
        vector-effect="non-scaling-stroke"
      />
    </svg>
  </div>

  <div class="flex w-full text-[10px] text-slate-500">
    {#each model.bars as bar (bar.period_id)}
      <div
        class="flex-1 min-w-0 text-center truncate"
        title={bar.period_label}
      >
        {bar.period_label}
      </div>
    {/each}
  </div>

  <ul class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
    {#each visibleIds as id (id)}
      <li class="flex items-center gap-1.5">
        <span
          class="inline-block w-2.5 h-2.5 rounded-sm"
          style:background-color={fillFor(id)}
        ></span>
        <span class="font-medium">{labelFor(id)}</span>
      </li>
    {/each}
  </ul>

  {#if model.honesty?.notes}
    <p class="text-[12px] text-slate-700">{model.honesty.notes}</p>
  {/if}
  {#if model.honesty?.methodology_vintage}
    <p class="text-[11px] text-slate-500">Methodology · {model.honesty.methodology_vintage}</p>
  {/if}
</div>
