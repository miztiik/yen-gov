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
    computeYMax,
    maxMarginVotes,
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
    /** Override for the SVG width (px). When omitted, the chart binds to
     *  the wrapper's clientWidth and scales responsively. Tests pass an
     *  explicit width to pin the SVG dimensions; production usage leaves
     *  it undefined so the SVG fills the parent (TODO/20260612 Row A.4). */
    width?: number;
    /** Override for the SVG height (px). Defaults to 480. */
    height?: number;
    /** Optional honesty caption override. Defaults to the Max Q8 verdict
     *  text; pass a shorter string for low-context surfaces. */
    honesty_caption?: string;
    /** When true, the Body filter chip block does NOT render. Use on
     *  surfaces where the body is already fixed by the route (state-event
     *  + national-event views) - the chip would only let citizens toggle
     *  to an inactive body that empties the chart. The scatter still
     *  honours the `filters.body` value passed in by the consumer.
     *  TODO/20260612 Row A.5. */
    lock_body?: boolean;
    /** When true, surface the small `(i)` info-icon next to the chart
     *  title that reveals the cross-event honesty caption (Max Q8). The
     *  caveat is only relevant when the displayed data crosses the 2009
     *  delimitation boundary; on a single-event surface (state-event,
     *  national-event) the icon does NOT render. Defaults to false.
     *  TODO/20260612 Row A.6. */
    show_delim_caveat?: boolean;
    /** Party ids muted via the PartyBar (click-to-mute). Dots whose winning
     *  party is in this set recede to a neutral grey at low opacity - kept
     *  for context, NOT dropped (mirrors the per-PC map mute recede).
     *  Default: nothing muted. */
    muted_pids?: ReadonlySet<string>;
  }

  let {
    data,
    filters = {},
    onFiltersChange,
    onDotClick,
    width,
    height = 480,
    honesty_caption,
    lock_body = false,
    show_delim_caveat = false,
    muted_pids = new Set<string>(),
  }: Props = $props();

  // ---- Responsive width (TODO/20260612 Row A.4) ----------------------
  // The wrapper <div> reports its clientWidth; the SVG inherits that
  // dimension via `width`. Tests can still pin a fixed width via the
  // `width` prop, in which case `wrapper_width` is ignored.
  let wrapper_width = $state(720);
  const effective_width = $derived(width ?? Math.max(280, wrapper_width));

  // ---- Layout constants -----------------------------------------------
  const MARGIN_TOP = 24;
  const MARGIN_RIGHT = 24;
  const MARGIN_BOTTOM = 48;
  const MARGIN_LEFT = 56;
  const MIN_R = 2; // pixel floor so a 0-margin AC is still visible
  // TODO/20260612 Row A.1: shrunk from 22 -> 10 so dense urban states
  // don't render as one blob. Combined with the radius-encoding swap
  // (Row B: electors -> margin_votes), individual dots stay legible at
  // 540+ per chart.
  const MAX_R = 10;
  // Neutral recede fill for a muted-party dot (slate-300; matches the per-PC
  // map mute recede). Paired with a low fill-opacity so muted dots stay as
  // faint context without competing with the live parties.
  const MUTED_FILL = "#cbd5e1";

  const inner_w = $derived(Math.max(0, effective_width - MARGIN_LEFT - MARGIN_RIGHT));
  const inner_h = $derived(Math.max(0, height - MARGIN_TOP - MARGIN_BOTTOM));

  // ---- Derived data ---------------------------------------------------
  const filtered = $derived(applyFilters(data, filters));
  // TODO/20260612 Row B: radius encoding now reads margin_votes (the
  // absolute winner-runnerup vote gap) instead of electors. A 3k-vote
  // squeaker looks tiny next to a 4 lakh-vote walkover, even when both
  // have the same % margin - Citizen + Max verdict.
  const max_margin_votes = $derived(Math.max(1, maxMarginVotes(data)));

  // TODO/20260612 Row A.3: Y-axis adapts to the filtered data range.
  // Formula: max(40, ceil(1.1 * max_margin_pct / 10) * 10), capped at
  // 100. X stays fixed 0..100 (turnout is a universal participation
  // rate; price of cross-event comparability).
  const y_max = $derived(computeYMax(filtered));

  // d3-scale instances are reactive on inner_w / inner_h / y_max.
  const x_scale = $derived(scaleLinear().domain([0, 100]).range([0, inner_w]));
  const y_scale = $derived(scaleLinear().domain([0, y_max]).range([inner_h, 0]));
  const r_scale = $derived(
    scaleSqrt().domain([0, max_margin_votes]).range([0, MAX_R]),
  );

  // X ticks stay every 20%; Y tick step adapts to the dynamic upper
  // bound: every 10% when the chart caps at <=50% (the dominant case for
  // single state-event surfaces), every 20% otherwise.
  const X_TICKS = [0, 20, 40, 60, 80, 100];
  const Y_TICKS = $derived.by(() => {
    const step = y_max <= 50 ? 10 : 20;
    const out: number[] = [];
    for (let t = 0; t <= y_max; t += step) out.push(t);
    return out;
  });

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

  // TODO/20260612 Row A.6: the cross-event delim caveat lives behind an
  // info-icon. State-event + national-event surfaces show a single event
  // and never cross the 2009 boundary, so the icon stays hidden there
  // (`show_delim_caveat=false`). Multi-event scopes (firehose, analyst
  // lab) flip the prop true so the citizen can hover/focus to read why
  // the dot positions are not 1:1 comparable across delim eras.
  let caveat_open = $state(false);
</script>

<div class="space-y-3" data-testid="scatter">
  <!-- Info-icon affordance for the cross-event delim caveat
       (TODO/20260612 Row A.6). Only renders when the host explicitly
       declares the chart spans the 2009 delimitation boundary; single-
       event surfaces (state-event, national-event) keep it hidden. -->
  {#if show_delim_caveat}
    <div class="flex items-start gap-2 text-xs">
      <button
        type="button"
        class="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-300 bg-white text-[10px] font-semibold text-slate-600 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-300"
        aria-label="About cross-event comparability"
        data-testid="scatter-caveat-icon"
        onclick={() => (caveat_open = !caveat_open)}
      >i</button>
      {#if caveat_open}
        <small class="text-slate-500" data-testid="scatter-caveat-text">
          {caption}
        </small>
      {/if}
    </div>
  {/if}

  <!-- Filter chips (TODO/20260612 Row A.7: chip rail wraps cleanly on
       narrow viewports via flex-col / sm:flex-row + sm:flex-wrap). -->
  <div
    class="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-6 sm:gap-y-2 text-xs"
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
    {#if !lock_body}
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
    {/if}
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
    <!-- Responsive width wrapper (TODO/20260612 Row A.4). The SVG's
         intrinsic width tracks the parent's clientWidth so the chart
         scales to the page's max-w-6xl on wide viewports and shrinks
         cleanly on narrow ones. Tests pin the width via the `width`
         prop, in which case the bind is ignored. -->
    <div bind:clientWidth={wrapper_width} data-testid="scatter-wrapper">
      <svg
        width={effective_width}
        {height}
        viewBox={`0 0 ${effective_width} ${height}`}
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

        <!-- Dots (TODO/20260612 Row A.2: no resting stroke; on hover the
             stroke + opacity lift via the `scatter-dot--hover` class
             which the enter/leave handlers toggle. Row B: radius scales
             with margin_votes, not electors). -->
        {#each filtered as d (`${d.entity_id}-${d.event_id}`)}
          {@const cx = x_scale(Math.max(0, Math.min(100, d.turnout_pct)))}
          {@const cy_raw = y_scale(Math.max(0, Math.min(y_max, d.margin_pct)))}
          {@const cy = Number.isFinite(cy_raw) ? cy_raw : 0}
          {@const mv = Math.max(0, d.margin_votes ?? 0)}
          {@const r = Math.max(MIN_R, r_scale(mv))}
          {@const muted = muted_pids.has(d.winner_party_id)}
          {@const fill = muted ? MUTED_FILL : getPartyColor(d.winner_party_id).hex}
          {@const is_hover = hover != null && hover.entity_id === d.entity_id && hover.event_id === d.event_id}
          <circle
            {cx}
            {cy}
            {r}
            {fill}
            fill-opacity={muted ? 0.15 : is_hover ? 1 : 0.55}
            stroke={is_hover ? "#0f172a" : "none"}
            stroke-width={is_hover ? 1.5 : 0}
            class="cursor-pointer"
            data-testid={`scatter-dot-${d.entity_id}-${d.event_id}`}
            onclick={() => onDotClick?.(d)}
            onmouseenter={(e) => onDotEnter(e, d)}
            onmouseleave={onDotLeave}
          />
        {/each}
      </g>
      </svg>
    </div>
  {/if}

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
        margin {fmtPct(hover.margin_pct)} &middot; {hover.margin_votes == null ? "-" : `${fmtCompact(hover.margin_votes)} votes`}
      </div>
    </div>
  {/if}
</div>
