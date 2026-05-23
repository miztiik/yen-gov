<script lang="ts">
  // StackedTrendV2 — component with wired geometry, segmented mode
  // control, and pinned readout panel (Phases 2.1c + 2.2 + 2.3).
  //
  // Per TODO/20260518-frontend-charting-modernisation-plan.md Phases
  // 2.1 + 2.2 + 2.3.
  //
  // Behaviour delivered so far:
  //
  //  - Phase 2.1c: bar/segment <rect> geometry driven by the pure
  //    helpers shipped in PR #110, plus baseline axis, period-label
  //    row, and a legend strip listing only `visibleCategoryIds`.
  //  - Phase 2.2: live segmented mode toggle. The citizen flips
  //    between "Share" (percent of bar) and "Total" (absolute height
  //    vs. max bar) without losing scroll or focus. R-12: button
  //    group, NOT select.
  //  - Phase 2.3 (this PR): pinned readout panel on bar tap. R-12: no
  //    hover-as-state, the readout is committed by a click. Each bar
  //    gets a full-slot transparent click target so the citizen does
  //    not have to land on a specific segment to pin the bar. The
  //    pinned bar gets a thin outline ring; the readout panel renders
  //    below the chart, listing every segment (including missing /
  //    not_applicable rows) with share% + colour chip + value. Initial
  //    pin is the LAST bar so the panel is populated immediately.
  //
  // What's STILL out of scope (each ships in its own PR):
  //
  //  - Inline + leader labels (Phase 2.4).
  //  - Missing / not_applicable hatch (Phase 2.5).
  //  - Motion / 200ms tween (Phase 2.6).
  //  - Export control (Phase 2.7).
  //
  // Per R-08 Branch by Abstraction: v2 ships ALONGSIDE
  // `frontend/src/lib/charts/StackedTrend.svelte` (v1). v1 is NOT
  // modified. Caller migration runs in Track-D D10..D12; v1 deletion
  // in D13. ZERO callers consume v2 today.
  //
  // SVG layout choices:
  //
  //  - One outer `<svg viewBox="0 0 100 100" preserveAspectRatio="none">`
  //    so the chart scales fluidly to any container width without locking
  //    to a pixel-grid. The height is constrained by the wrapping div
  //    (`h-72` = 18rem ≈ 288 px on desktop) so the citizen never sees a
  //    1px-tall chart on narrow viewports.
  //  - Bars are positioned at `x = i * pitch` with width `barWidth`
  //    so the bar count stays self-evident even when bars are short.
  //  - Segments stack from the bottom (`y = 100 - cumulativeHeight`)
  //    using `segmentVisualHeightPct` from the helpers (which mirrors v1
  //    geometry — toggling modes does not bounce the visual).
  //  - Colours come from the existing `categoryFill` helper plus the v2
  //    `OTHER_CATEGORY_FILL_V2` constant — same palette discipline as
  //    v1, so cross-chart consistency is preserved during migration.
  //  - Per-bar hit targets are full-slot transparent `<rect>`s with
  //    `pointer-events="none"` on the segment fills so the click always
  //    lands on the hit target (no z-ordering surprises). The pinned
  //    bar gets an outlined `<rect>` overlay so the citizen sees what
  //    drives the readout panel below.
  //
  // CLAUDE.md S0 (a11y descoped): no aria-label, no role attribute.
  // The mode buttons + bar hit targets + close button carry `data-*`
  // attributes for Playwright; they are real `<button>` / `<rect>`
  // elements (keyboard- and pointer-navigable for free for buttons)
  // but no aria-pressed / aria-expanded is set.

  import { categoryFill } from "../colors/category-colour";
  import {
    MODE_LABELS,
    barTotal,
    maxBarTotal,
    readoutRows,
    resolveInitialMode,
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
     * Optional caller override of `model.default_mode`. Sets the
     * INITIAL mode at mount; the citizen can still toggle via the
     * segmented control after mount. Use this when a specific route
     * needs to land on "Total" (or "Share") regardless of the model's
     * own default — never as a permanent lock.
     */
    mode_override?: "percent" | "absolute";
  } = $props();

  // Live mode state (Phase 2.2 / R-12). Initial value resolved via the
  // pure `resolveInitialMode` helper (unit-tested in
  // `stacked-trend-v2/helpers.test.ts`); subsequent changes flow from
  // the segmented control's <button> clicks below.
  //
  // svelte-ignore state_referenced_locally — initial-only-at-mount is
  // INTENTIONAL: the citizen's click is the source of truth after mount,
  // a prop change must not silently overwrite the citizen's choice.
  let currentMode = $state<"percent" | "absolute">(
    resolveInitialMode(mode_override, model.default_mode),
  );

  // Pinned readout state (Phase 2.3 / R-12 — no-hover-as-state). The
  // initial pin is the last (most recent) bar so the citizen sees a
  // populated panel immediately rather than an empty placeholder.
  // Click a bar to switch the pin; click the same bar (or the panel's
  // close button) to clear it.
  //
  // svelte-ignore state_referenced_locally — same rationale as
  // currentMode: prop changes must not silently overwrite the citizen's
  // selection.
  const initialPinnedPeriod =
    model.bars[model.bars.length - 1]?.period_id ?? null;
  let pinnedPeriod = $state<string | null>(initialPinnedPeriod);

  const pinnedBar = $derived(
    pinnedPeriod != null
      ? (model.bars.find((b) => b.period_id === pinnedPeriod) ?? null)
      : null,
  );

  const pinnedRows = $derived(
    pinnedBar != null ? readoutRows(pinnedBar, model.categories) : null,
  );

  const pinnedBarTotal = $derived(
    pinnedBar != null ? barTotal(pinnedBar) : 0,
  );

  function togglePin(period_id: string): void {
    pinnedPeriod = pinnedPeriod === period_id ? null : period_id;
  }

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
        currentMode,
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
  data-mode={currentMode}
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
    <span class="text-slate-500">Show as</span>
    <div
      class="stacked-trend-v2__mode-control inline-flex rounded border border-slate-300 overflow-hidden"
      data-control="mode-toggle"
    >
      {#each ["percent", "absolute"] as const as m (m)}
        <button
          type="button"
          class="px-2.5 py-1 text-xs font-medium transition-colors"
          class:bg-slate-800={currentMode === m}
          class:text-white={currentMode === m}
          class:bg-white={currentMode !== m}
          class:text-slate-700={currentMode !== m}
          class:hover:bg-slate-100={currentMode !== m}
          data-mode-value={m}
          data-active={currentMode === m}
          onclick={() => (currentMode = m)}
        >
          {MODE_LABELS[m]}
        </button>
      {/each}
    </div>
    <span class="ml-auto text-slate-500">{model.x_axis_label}</span>
  </div>

  <div class="stacked-trend-v2__viewport relative h-72 w-full">
    <svg
      class="stacked-trend-v2__canvas block w-full h-full"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
    >
      <g class="stacked-trend-v2__bars" data-phase="2.3-readout">
        {#each model.bars as bar, i (bar.period_id)}
          {@const total = barTotal(bar)}
          {@const rects = rectsForBar(bar.segments, total)}
          {@const isPinned = pinnedPeriod === bar.period_id}
          <g class="stacked-trend-v2__bar" transform="translate({barX(i)} 0)">
            {#each rects as r (r.category_id)}
              <rect
                x="0"
                y={r.y}
                width={barWidth}
                height={r.height}
                fill={r.fill}
                class="stacked-trend-v2__segment"
                pointer-events="none"
              >
                <title>{labelFor(r.category_id)}: {fmtValue(r.value)}</title>
              </rect>
            {/each}
            <!-- Full-slot transparent hit target. Sized to the entire
                 100-unit-tall slot so the citizen does not have to land
                 on a specific segment to pin the bar; clicking the gap
                 above the bar also works. -->
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <rect
              x="0"
              y="0"
              width={barWidth}
              height="100"
              fill="transparent"
              class="stacked-trend-v2__hit cursor-pointer"
              data-period-id={bar.period_id}
              data-pinned={isPinned}
              onclick={() => togglePin(bar.period_id)}
            >
              <title>{bar.period_label}</title>
            </rect>
            {#if isPinned}
              <!-- Visual ring around the pinned bar so the citizen sees
                   which bar drives the readout panel below. Outline
                   only — fill stays transparent so the segments below
                   remain visible. `vector-effect=non-scaling-stroke`
                   keeps the ring 1px regardless of the canvas's CSS
                   scale. -->
              <rect
                x="0"
                y="0"
                width={barWidth}
                height="100"
                fill="none"
                stroke="#1e293b"
                stroke-width="0.6"
                vector-effect="non-scaling-stroke"
                class="stacked-trend-v2__pin-ring pointer-events-none"
              />
            {/if}
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

  {#if pinnedBar && pinnedRows && pinnedRows.length > 0}
    <div
      class="stacked-trend-v2__readout rounded border border-slate-300 bg-white p-3 text-xs"
      data-readout="pinned"
      data-period-id={pinnedBar.period_id}
    >
      <div class="flex items-baseline gap-2 mb-2">
        <div class="font-semibold text-slate-900 text-sm">{pinnedBar.period_label}</div>
        {#if pinnedBarTotal > 0}
          <div class="text-slate-500">Total · {fmtValue(pinnedBarTotal)}</div>
        {/if}
        <button
          type="button"
          class="ml-auto text-slate-400 hover:text-slate-700 px-1.5 py-0.5 rounded"
          data-readout-action="clear"
          onclick={() => (pinnedPeriod = null)}
          title="Clear selection"
        >
          ×
        </button>
      </div>
      <ul class="space-y-1">
        {#each pinnedRows as row (row.category_id)}
          <li
            class="flex items-center gap-2"
            data-category-id={row.category_id}
            data-availability={row.availability}
          >
            <span
              class="inline-block w-2.5 h-2.5 rounded-sm flex-shrink-0"
              style:background-color={fillFor(row.category_id)}
              class:opacity-30={row.availability !== "present"}
            ></span>
            <span class="font-medium text-slate-800 truncate">{row.label}</span>
            {#if row.availability === "present" && row.value != null}
              <span class="text-slate-600 tabular-nums ml-auto">{fmtValue(row.value)}</span>
              <span class="text-slate-400 tabular-nums w-12 text-right">{row.share_pct.toFixed(1)}%</span>
            {:else}
              <span class="text-slate-400 italic ml-auto">{row.availability_label ?? (row.availability === "missing" ? "Not reported" : "Not applicable")}</span>
            {/if}
          </li>
        {/each}
      </ul>
    </div>
  {/if}

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
