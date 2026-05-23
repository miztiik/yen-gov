<script lang="ts">
  // StackedTrendV2 — component with wired geometry, segmented mode
  // control, pinned readout panel, inline labels, missing /
  // not_applicable hatch, and subtle 200ms motion (Phases 2.1c + 2.2
  // + 2.3 + 2.4 + 2.5 + 2.6).
  //
  // Per TODO/20260518-frontend-charting-modernisation-plan.md Phases
  // 2.1..2.6.
  //
  // Behaviour delivered so far:
  //
  //  - Phase 2.1c: bar/segment <rect> geometry driven by the pure
  //    helpers shipped in PR #110, plus baseline axis, period-label
  //    row, and a legend strip listing only `visibleCategoryIds`.
  //  - Phase 2.2: live segmented mode toggle. R-12: button, not select.
  //  - Phase 2.3: pinned readout panel on bar tap. R-12: no
  //    hover-as-state. Initial pin = LAST bar.
  //  - Phase 2.4: inline labels overlay (HTML on top of SVG) with
  //    YIQ-based `inkForFill` per segment.
  //  - Phase 2.5: missing / not_applicable hatch — slim hatched
  //    stripes (diagonal for missing, dotted for not_applicable)
  //    stacked above the present rects so absence is visible at a
  //    glance.
  //  - Phase 2.6 (this PR): subtle 200ms motion on mode + data
  //    changes. CSS-only — `transition: y/height/left/top
  //    var(--stv2-tween-duration) ease` on segments, stripes, and
  //    HTML labels. Wrapped in `@media (prefers-reduced-motion:
  //    no-preference)` so reduced-motion users see no animation. No
  //    entrance animation: CSS transitions only fire on property
  //    changes, so initial paint renders fully present. The single
  //    source of truth for the duration is the pure constant
  //    `STV2_TWEEN_DURATION_MS = 200` from `./stacked-trend-v2/helpers.ts`
  //    (unit-pinned in `helpers.test.ts`) — the component projects
  //    it onto the root as a CSS custom property so the CSS rule
  //    cannot drift from the constant.
  //
  // What's STILL out of scope (each ships in its own PR):
  //
  //  - (none — Phase 2 polish list complete)
  //
  // Phase 2.7 (this PR): standalone SVG export. A single explicit
  // download button sits in the toolbar row next to the segmented mode
  // toggle (R-12: one icon/button near the chart title, no multi-icon
  // modebar). Clicking serialises the current model + mode through the
  // pure helper `buildExportSvg` from
  // `./stacked-trend-v2/export.ts` (unit-tested) and triggers a
  // browser download via Blob + `<a download>`. The exported SVG
  // includes title, mode label, period window, all bars, legend, and
  // a provenance footer line citing the highest-confidence source —
  // Holy Law #9 (no anonymous data ships) extends to the downloaded
  // artifact.
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
    buildExportFilename,
    buildExportSvg,
  } from "./stacked-trend-v2/export";
  import {
    DEFAULT_LABEL_THRESHOLD_PCT,
    MODE_LABELS,
    STV2_TWEEN_DURATION_MS,
    UNKNOWN_STRIPE_HEIGHT_PCT,
    barTotal,
    inkForFill,
    isLabelEligible,
    maxBarTotal,
    readoutRows,
    resolveInitialMode,
    segmentVisualHeightPct,
    unknownStripesForBar,
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
  import TemporalViewportBrush from "./temporal-viewport/TemporalViewportBrush.svelte";
  import {
    buildDomain,
    filterItemsToWindow,
    fullWindow,
  } from "./temporal-viewport/helpers";
  import type {
    TemporalDomainKind,
    TemporalWindow,
  } from "./temporal-viewport/types";

  let {
    model,
    mode_override,
    enable_temporal_brush = false,
    temporal_domain_kind = "year",
    temporal_recent_count = 5,
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
    /**
     * Phase 1.5 — first renderer adopter for the temporal viewport
     * brush. Default `false` keeps every existing caller bit-identical;
     * routes opt in by passing `enable_temporal_brush={true}`. Window
     * state stays LOCAL to the component (R-07 — URL grammar is
     * route-owned, not renderer-owned).
     */
    enable_temporal_brush?: boolean;
    /**
     * Domain kind used when building the brush's temporal domain. The
     * renderer can't sniff this from `model.bars[].period_id` alone
     * (a four-digit prefix could be a calendar year, fiscal year, or
     * the start of an election cycle), so the caller declares the
     * dimension. Defaults to `"year"` because StackedTrendV2 today is
     * mostly mounted on yearly economy/energy series.
     */
    temporal_domain_kind?: TemporalDomainKind;
    /**
     * Window size for the brush's `recent` preset. Default 5.
     */
    temporal_recent_count?: number;
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

  // Phase 1.5 — temporal viewport brush wiring (first renderer adopter).
  //
  // Domain is derived from the current model's bars; window state is
  // LOCAL to this component (R-07 — URL grammar is route-owned).
  // Initialised to `null` and lazy-seeded in $effect so a model swap
  // (e.g. route change between two energy series) reseeds to the full
  // window of the NEW domain rather than holding the previous one.
  //
  // When `enable_temporal_brush={false}` (the default), the window
  // collapses to `fullWindow(domain)` and `visibleBars === model.bars`
  // — zero behaviour change for existing callers.
  const temporal_domain = $derived(
    buildDomain(
      model.bars.map((b) => b.period_id),
      temporal_domain_kind,
    ),
  );

  let temporal_window: TemporalWindow | null = $state(null);

  $effect(() => {
    // Re-seed when the brush window references a period_id that no
    // longer exists in the current domain (model swap). Helpers will
    // clamp defensively, but the visible state should mirror the
    // intent (full window after a swap).
    if (temporal_window === null) {
      temporal_window = fullWindow(temporal_domain);
      return;
    }
    const ids = new Set(temporal_domain.ordered_period_ids);
    if (
      !ids.has(temporal_window.from_period_id) ||
      !ids.has(temporal_window.to_period_id)
    ) {
      temporal_window = fullWindow(temporal_domain);
    }
  });

  const effective_window = $derived(
    temporal_window ?? fullWindow(temporal_domain),
  );

  const visibleBars = $derived(
    enable_temporal_brush
      ? filterItemsToWindow(
          model.bars,
          (b) => b.period_id,
          effective_window,
          temporal_domain,
        )
      : model.bars,
  );

  // Period label map for the brush strip cells. Keyed by period_id,
  // value is the human-facing `period_label` already used in the
  // chart's axis row — keeps both views consistent.
  const temporal_period_labels = $derived.by(() => {
    const out: Record<string, string> = {};
    for (const bar of model.bars) {
      out[bar.period_id] = bar.period_label;
    }
    return out;
  });

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
      ? (visibleBars.find((b) => b.period_id === pinnedPeriod) ?? null)
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

  /**
   * Phase 2.7 — trigger a citizen-initiated SVG download of the chart
   * as it currently appears (current mode; pin state intentionally
   * NOT serialised — the export captures data, not interactive UI
   * overlays). Uses `URL.createObjectURL` + an in-DOM `<a download>`
   * click rather than a `data:` URI so the SVG payload (~3 KB to
   * many-KB) doesn't bloat the URL bar; revokes the object URL after
   * the click to release the in-memory blob.
   *
   * Guarded against the SSR / test-runner environment by an existence
   * check on `document` — the function is a no-op in node so the
   * component still mounts in vitest without an `instanceof Window`
   * stub. Browser smoke is the gate (R-12, CLAUDE.md §13).
   */
  function downloadSvg(): void {
    if (typeof document === "undefined") return;
    const svg = buildExportSvg(model, { mode: currentMode });
    const filename = buildExportFilename(model, currentMode);
    const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  const visibleIds = $derived(visibleCategoryIds(model));
  const maxTotal = $derived(maxBarTotal(visibleBars));

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
  const pitch = $derived(100 / Math.max(1, visibleBars.length));
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
    eligibleForLabel: boolean;
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
        eligibleForLabel: isLabelEligible(
          height,
          DEFAULT_LABEL_THRESHOLD_PCT,
        ),
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
  style:--stv2-tween-duration={`${STV2_TWEEN_DURATION_MS}ms`}
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
    <button
      type="button"
      class="stacked-trend-v2__download-svg ml-2 inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
      data-action="download-svg"
      title="Download this chart as an SVG image"
      onclick={downloadSvg}
    >
      <!-- Inline download glyph: 12x12 viewBox, stroke-only so it
           inherits the button's `currentColor`. No icon-registry hookup
           in v2.7 — single use-site; the iconography pass (Phase 1.3b-f)
           wires the registry across the broader UI. -->
      <svg
        viewBox="0 0 12 12"
        width="12"
        height="12"
        fill="none"
        stroke="currentColor"
        stroke-width="1.4"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M6 1.5v7" />
        <path d="M3 5.75 6 8.75l3-3" />
        <path d="M2 10.5h8" />
      </svg>
      <span>SVG</span>
    </button>
    <span class="ml-auto text-slate-500">{model.x_axis_label}</span>
  </div>

  <div class="stacked-trend-v2__viewport relative h-72 w-full">
    <svg
      class="stacked-trend-v2__canvas block w-full h-full"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
    >
      <!--
        Phase 2.5 hatch patterns. Both patterns use a fixed userSpace
        size (2x2 viewBox units) so the hatch density stays stable
        regardless of bar width — wider bars get more stripes / dots,
        not bigger ones. Light slate background so the hatch reads as
        "incomplete data" without competing with category colours.

          - `stv2-hatch-missing`: diagonal lines → "we expected a
            number, none was reported".
          - `stv2-hatch-na`: dots → "this category doesn't apply to
            this period" (a different absence than missing).

        The pinned-readout panel from Phase 2.3 carries the plain-
        language explanation; the hatch is the visual entry point.
      -->
      <defs>
        <pattern
          id="stv2-hatch-missing"
          patternUnits="userSpaceOnUse"
          width="2"
          height="2"
          patternTransform="rotate(45)"
        >
          <rect width="2" height="2" fill="#f1f5f9" />
          <line x1="0" y1="0" x2="0" y2="2" stroke="#94a3b8" stroke-width="0.5" />
        </pattern>
        <pattern
          id="stv2-hatch-na"
          patternUnits="userSpaceOnUse"
          width="2"
          height="2"
        >
          <rect width="2" height="2" fill="#f8fafc" />
          <circle cx="1" cy="1" r="0.35" fill="#94a3b8" />
        </pattern>
      </defs>
      <g class="stacked-trend-v2__bars" data-phase="2.6-motion">
        {#each visibleBars as bar, i (bar.period_id)}
          {@const total = barTotal(bar)}
          {@const rects = rectsForBar(bar.segments, total)}
          {@const stripes = unknownStripesForBar(bar)}
          {@const presentTopY = rects.length > 0 ? rects[rects.length - 1].y : 100}
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
            <!--
              Phase 2.5 hatched stripes for missing / not_applicable
              segments. Stacked ABOVE the present rects (smaller y) so
              the present geometry is unaffected by toggling modes —
              the citizen sees the cap and understands the bar has
              incomplete data; the readout panel breaks down which
              categories are missing vs not-applicable.
            -->
            {#each stripes as s, sIdx (s.category_id)}
              {@const stripeY = presentTopY - (sIdx + 1) * s.height}
              <rect
                x="0"
                y={stripeY}
                width={barWidth}
                height={s.height}
                fill={s.availability === "missing"
                  ? "url(#stv2-hatch-missing)"
                  : "url(#stv2-hatch-na)"}
                stroke="#cbd5e1"
                stroke-width="0.2"
                vector-effect="non-scaling-stroke"
                class="stacked-trend-v2__stripe"
                data-availability={s.availability}
                data-category-id={s.category_id}
                pointer-events="none"
              >
                <title
                  >{labelFor(s.category_id)}: {s.availability_label ??
                    (s.availability === "missing"
                      ? "Not reported"
                      : "Not applicable")}</title
                >
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

    <!--
      Phase 2.4 — inline labels. HTML overlay positioned over the chart
      viewport using percent coords (which align with the SVG's 0..100
      viewBox because `preserveAspectRatio=none` makes 1 viewBox unit =
      1% of width / height). SVG `<text>` would be stretched by the
      preserveAspectRatio rule and become illegible; HTML labels stay
      crisp at any container size.

      Citizen-readable rules (R-12 3-tier label):
        - Tier 1 (inline): segment height >= DEFAULT_LABEL_THRESHOLD_PCT
          (8% of canvas) → render `<short-label>` + `<value-with-unit>`
          stacked.
        - Tier 2 (legend fallback): everything else lives in the legend
          strip below the chart + the readout panel when pinned.

      Ink colour comes from `inkForFill(rect.fill)` so the label stays
      legible on both light and dark category colours.

      Labels are non-interactive (`pointer-events-none`) so clicks pass
      through to the bar hit target underneath.
    -->
    <div
      class="stacked-trend-v2__labels absolute inset-0 pointer-events-none"
      data-overlay="inline-labels"
    >
      {#each visibleBars as bar, i (bar.period_id)}
        {@const total = barTotal(bar)}
        {@const rects = rectsForBar(bar.segments, total)}
        {#each rects as r (r.category_id)}
          {#if r.eligibleForLabel}
            <div
              class="stacked-trend-v2__label absolute flex flex-col items-center justify-center text-center leading-tight"
              style:left={`${barX(i) + barWidth / 2}%`}
              style:top={`${r.y + r.height / 2}%`}
              style:width={`${barWidth}%`}
              style:transform="translate(-50%, -50%)"
              style:color={inkForFill(r.fill)}
              data-category-id={r.category_id}
              data-period-id={bar.period_id}
            >
              <span class="text-[10px] font-medium truncate w-full px-0.5">{labelFor(r.category_id)}</span>
              <span class="text-[9px] opacity-90 tabular-nums truncate w-full px-0.5">{fmtValue(r.value)}</span>
            </div>
          {/if}
        {/each}
      {/each}
    </div>
  </div>

  <div class="flex w-full text-[10px] text-slate-500">
    {#each visibleBars as bar (bar.period_id)}
      <div
        class="flex-1 min-w-0 text-center truncate"
        title={bar.period_label}
      >
        {bar.period_label}
      </div>
    {/each}
  </div>

  {#if enable_temporal_brush}
    <!--
      Phase 1.5 first renderer adopter — temporal viewport brush.
      Sits below the period-label row so the citizen can see which
      bars they're selecting / dropping. Uncontrolled mode: the
      component owns its window state; we surface the same state via
      `effective_window` so the chart's geometry stays in sync.

      Strip cells receive `period_labels` keyed by `period_id` so the
      brush displays the same human-facing period label used in the
      chart axis above (no duplicate formatting).
    -->
    <TemporalViewportBrush
      domain={temporal_domain}
      window={effective_window}
      recent_count={temporal_recent_count}
      period_labels={temporal_period_labels}
      on_window_change={(next) => (temporal_window = next)}
    />
  {/if}

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

<style>
  /*
   * Phase 2.6 — subtle motion on mode + data changes.
   *
   * The transition fires whenever a segment's `y` / `height` (SVG) or
   * a label's `left` / `top` (HTML overlay) change — i.e. on mode
   * toggles and on data updates — so the redistribution is legible
   * rather than a snap. Initial paint does NOT animate because CSS
   * transitions only fire on property changes (not the first render).
   *
   * Wrapped in `prefers-reduced-motion: no-preference` so reduced-
   * motion users get the snap behaviour with zero JS — the browser
   * honours their OS-level preference natively.
   *
   * Duration sourced from `STV2_TWEEN_DURATION_MS` via the
   * `--stv2-tween-duration` custom property projected onto the chart
   * root, so the constant in `./stacked-trend-v2/helpers.ts` is the
   * single source of truth (unit-pinned in `helpers.test.ts`).
   */
  @media (prefers-reduced-motion: no-preference) {
    :global(.stacked-trend-v2__segment),
    :global(.stacked-trend-v2__stripe) {
      transition:
        y var(--stv2-tween-duration, 200ms) ease,
        height var(--stv2-tween-duration, 200ms) ease;
    }
    :global(.stacked-trend-v2__label) {
      transition:
        left var(--stv2-tween-duration, 200ms) ease,
        top var(--stv2-tween-duration, 200ms) ease;
    }
  }
</style>
