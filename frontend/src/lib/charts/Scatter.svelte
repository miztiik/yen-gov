<script lang="ts">
  // Scatter — PR-W4c MUST-FEATURE chart primitive (Election experience
  // overhaul, 2026-06-10).
  //
  // Plotting: one constituency-election per dot. Encodings (Max verdict
  // baked into the PR-W4c brief):
  //   X    : voter turnout %                  (0..100, linear)
  //   Y    : winning margin %                 (0..100, linear)
  //   r    : sqrt(electors)                   (OWID Rosling: visual area
  //                                            scales with the value)
  //   fill : winning party                    (via getPartyColor, with
  //                                            the 3-tier anchor/brand/
  //                                            algorithmic fallover)
  //
  // 6 filters (sticky pills, no URL persistence per binding constraint #8):
  //   event, state, highlight_party, reservation, body, margin_band
  //
  // Click any dot -> consumer-supplied onDotClick (typically
  // `/<state>/elections/<event>/<constituency>` per ADR-0052).
  //
  // Per the PR-W4c escalation rule, this is a STANDALONE chart — NO
  // ChartShell wrapper. The honesty caption (Max Q8 verdict) renders as
  // an inline `<p>` below the SVG so the anti-leakage rule against
  // touching socio-econ chart files holds.
  //
  // All derivation lives in `scatter-model.ts`; vitest exercises the
  // model directly, and the Playwright spec at
  // `frontend/e2e/elections-scatter.spec.ts` covers the DOM click +
  // narrowing semantics end-to-end.

  import { scaleLinear, scaleSqrt } from "d3-scale";
  import { getPartyColor } from "../colors/resolver";
  import {
    applyFilters,
    maxElectors,
    type MarginBand,
    type ScatterDatum,
    type ScatterFilters,
  } from "./scatter-model";

  interface Props {
    /** Pre-loaded rows from the caller; this component never fetches. */
    data: readonly ScatterDatum[];
    /** Current filter state. Pass `{}` for "all events, all states, ...". */
    filters?: ScatterFilters;
    /** Fires when the citizen toggles a filter chip; consumer holds the
     *  authoritative filter state (typically `$state` on the route). */
    onFiltersChange?: (next: ScatterFilters) => void;
    /** Fires on dot click; consumer typically navigates to the
     *  constituency leaf. */
    onDotClick?: (datum: ScatterDatum) => void;
    /** Override for the SVG width (px). Defaults to 720; component is
     *  responsive via CSS, this is the intrinsic viewBox width. */
    width?: number;
    /** Override for the SVG height (px). Defaults to 480. */
    height?: number;
    /** Optional honesty caption override. Defaults to the Max Q8 verdict
     *  text; pass a shorter string for low-context surfaces. */
    honesty_caption?: string;
  }

  let {
    data,
    filters = {},
    onFiltersChange,
    onDotClick,
    width = 720,
    height = 480,
    honesty_caption,
  }: Props = $props();

  // ---- Layout constants -----------------------------------------------
  const MARGIN_TOP = 24;
  const MARGIN_RIGHT = 24;
  const MARGIN_BOTTOM = 48;
  const MARGIN_LEFT = 56;
  const MIN_R = 2; // pixel floor so a low-electors AC is still visible
  const MAX_R = 22;

  const inner_w = $derived(Math.max(0, width - MARGIN_LEFT - MARGIN_RIGHT));
  const inner_h = $derived(Math.max(0, height - MARGIN_TOP - MARGIN_BOTTOM));

  // ---- Derived data ---------------------------------------------------
  const filtered = $derived(applyFilters(data, filters));
  const max_electors = $derived(Math.max(1, maxElectors(data)));

  // d3-scale instances are reactive on inner_w / inner_h.
  const x_scale = $derived(scaleLinear().domain([0, 100]).range([0, inner_w]));
  const y_scale = $derived(scaleLinear().domain([0, 100]).range([inner_h, 0]));
  const r_scale = $derived(
    scaleSqrt().domain([0, max_electors]).range([0, MAX_R]),
  );

  // Static axis ticks (every 20% on both axes).
  const X_TICKS = [0, 20, 40, 60, 80, 100];
  const Y_TICKS = [0, 20, 40, 60, 80, 100];

  // ---- Tooltip state --------------------------------------------------
  let hover: ScatterDatum | null = $state(null);
  let hover_x = $state(0);
  let hover_y = $state(0);

  function onDotEnter(e: MouseEvent, d: ScatterDatum): void {
    hover = d;
    const r = (e.currentTarget as Element).getBoundingClientRect();
    hover_x = r.left + r.width / 2;
    hover_y = r.top;
  }
  function onDotLeave(): void {
    hover = null;
  }

  // ---- Filter chip helpers (pure dispatch to onFiltersChange) ---------
  function setReservation(v: "all" | "GEN" | "SC" | "ST"): void {
    onFiltersChange?.({ ...filters, reservation: v });
  }
  function setBody(v: "all" | "parliament" | "assembly"): void {
    onFiltersChange?.({ ...filters, body: v });
  }
  function setMarginBand(v: "all" | MarginBand): void {
    onFiltersChange?.({ ...filters, margin_band: v });
  }

  function chipClass(active: boolean): string {
    return active
      ? "px-2 py-0.5 rounded text-xs font-medium bg-slate-900 text-white"
      : "px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700 hover:bg-slate-200";
  }

  const PCT_FMT = new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  const COMPACT_FMT = new Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: 2,
  });

  function fmtPct(n: number): string {
    return `${PCT_FMT.format(n)}%`;
  }
  function fmtCompact(n: number): string {
    return COMPACT_FMT.format(n);
  }

  // ---- Honesty caption (Max Q8 verdict default) -----------------------
  const default_caption = $derived(
    `Plotting ${filtered.length} constituency-election${filtered.length === 1 ? "" : "s"}. ` +
      "2008 delimitation + AP/Telangana 2014 + Assam/J&K post-2022 redelim " +
      "mean pre-2009 PC seats are not 1:1 comparable.",
  );
  const caption = $derived(honesty_caption ?? default_caption);

  // ---- Reservation chip note (degraded UX placeholder) ----------------
  // Today the W2b loader projects `reservation` from
  // `datasets/data/entities/electoral.csv` where the column is empty for
  // every row; every projected datum lands on the `GEN` default. The
  // SC / ST chips therefore narrow to zero rows. The note below makes
  // the limitation explicit so a citizen does not read "0 ST seats" as
  // a publisher claim. A future PR backfilling the column lets this note
  // retire silently.
  const reservation_note =
    "Reservation data not yet populated; the SC / ST chips currently filter to zero.";
</script>

<div class="space-y-3" data-testid="scatter">
  <!-- Filter chips -->
  <div
    class="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs"
    data-testid="scatter-filters"
  >
    <div class="flex flex-wrap items-center gap-1">
      <span class="text-slate-500">Reservation</span>
      {#each ["all", "GEN", "SC", "ST"] as v (v)}
        <button
          type="button"
          class={chipClass(
            (filters.reservation ?? "all") === v,
          )}
          onclick={() => setReservation(v as "all" | "GEN" | "SC" | "ST")}
          data-testid={`scatter-filter-reservation-${v}`}
        >
          {v === "all" ? "All" : v}
        </button>
      {/each}
    </div>
    <div class="flex flex-wrap items-center gap-1">
      <span class="text-slate-500">Body</span>
      {#each ["all", "parliament", "assembly"] as v (v)}
        <button
          type="button"
          class={chipClass(
            (filters.body ?? "all") === v,
          )}
          onclick={() => setBody(v as "all" | "parliament" | "assembly")}
          data-testid={`scatter-filter-body-${v}`}
        >
          {v === "all"
            ? "All"
            : v === "parliament"
              ? "Parliament"
              : "Assembly"}
        </button>
      {/each}
    </div>
    <div class="flex flex-wrap items-center gap-1">
      <span class="text-slate-500">Margin</span>
      {#each ["all", "lt2", "2to5", "5to10", "gt10"] as v (v)}
        <button
          type="button"
          class={chipClass(
            (filters.margin_band ?? "all") === v,
          )}
          onclick={() => setMarginBand(v as "all" | MarginBand)}
          data-testid={`scatter-filter-margin-band-${v}`}
        >
          {v === "all"
            ? "All"
            : v === "lt2"
              ? "<2%"
              : v === "2to5"
                ? "2-5%"
                : v === "5to10"
                  ? "5-10%"
                  : ">10%"}
        </button>
      {/each}
    </div>
  </div>

  {#if filtered.length === 0}
    <div
      class="rounded border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500"
      data-testid="scatter-empty"
    >
      No constituencies match the current filters.
    </div>
  {:else}
    <!-- SVG chart -->
    <svg
      {width}
      {height}
      viewBox={`0 0 ${width} ${height}`}
      class="max-w-full"
      data-testid="scatter-chart"
    >
      <!-- Grid + axes -->
      <g transform={`translate(${MARGIN_LEFT}, ${MARGIN_TOP})`}>
        <!-- Y grid + ticks -->
        {#each Y_TICKS as t (`y-${t}`)}
          <line
            x1={0}
            x2={inner_w}
            y1={y_scale(t)}
            y2={y_scale(t)}
            stroke="#e2e8f0"
            stroke-dasharray={t === 0 ? "0" : "2 2"}
          />
          <text
            x={-8}
            y={y_scale(t)}
            text-anchor="end"
            dominant-baseline="middle"
            class="fill-slate-500 text-[10px]"
          >{t}%</text>
        {/each}
        <!-- X grid + ticks -->
        {#each X_TICKS as t (`x-${t}`)}
          <line
            x1={x_scale(t)}
            x2={x_scale(t)}
            y1={0}
            y2={inner_h}
            stroke="#e2e8f0"
            stroke-dasharray={t === 0 ? "0" : "2 2"}
          />
          <text
            x={x_scale(t)}
            y={inner_h + 16}
            text-anchor="middle"
            class="fill-slate-500 text-[10px]"
          >{t}%</text>
        {/each}
        <!-- Axis labels -->
        <text
          x={inner_w / 2}
          y={inner_h + 36}
          text-anchor="middle"
          class="fill-slate-700 text-xs font-medium"
        >Voter turnout %</text>
        <text
          x={-inner_h / 2}
          y={-44}
          text-anchor="middle"
          transform="rotate(-90)"
          class="fill-slate-700 text-xs font-medium"
        >Winning margin %</text>

        <!-- Dots -->
        {#each filtered as d (`${d.entity_id}-${d.event_id}`)}
          {@const cx = x_scale(Math.max(0, Math.min(100, d.turnout_pct)))}
          {@const cy = y_scale(Math.max(0, Math.min(100, d.margin_pct)))}
          {@const r = Math.max(MIN_R, r_scale(Math.max(0, d.electors)))}
          {@const fill = getPartyColor(d.winner_party_id).hex}
          <circle
            {cx}
            {cy}
            {r}
            {fill}
            fill-opacity="0.7"
            stroke="white"
            stroke-width="1"
            class="cursor-pointer transition-opacity hover:fill-opacity-100"
            data-testid={`scatter-dot-${d.entity_id}-${d.event_id}`}
            onclick={() => onDotClick?.(d)}
            onmouseenter={(e) => onDotEnter(e, d)}
            onmouseleave={onDotLeave}
          />
        {/each}
      </g>
    </svg>
  {/if}

  <!-- Honesty caption (Max Q8) -->
  <p class="text-xs text-slate-500" data-testid="scatter-caption">
    {caption}
  </p>
  <p class="text-[11px] text-slate-400" data-testid="scatter-reservation-note">
    {reservation_note}
  </p>

  <!-- Tooltip (positioned with fixed-position overlay so it escapes the
       SVG bbox; only renders when a dot is hovered) -->
  {#if hover}
    <div
      class="pointer-events-none fixed z-50 rounded border border-slate-300 bg-white px-2 py-1 text-xs shadow-md"
      style:left="{hover_x + 12}px"
      style:top="{hover_y - 8}px"
      data-testid="scatter-tooltip"
    >
      <div class="font-semibold text-slate-900">{hover.constituency_name}</div>
      <div class="text-slate-600">
        {hover.winner_party_short} &middot; turnout {fmtPct(hover.turnout_pct)}
      </div>
      <div class="text-slate-600">
        margin {fmtPct(hover.margin_pct)} &middot; electors {fmtCompact(hover.electors)}
      </div>
    </div>
  {/if}
</div>
