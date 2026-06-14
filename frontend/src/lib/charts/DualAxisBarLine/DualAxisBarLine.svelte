<script module lang="ts">
  /**
   * DualAxisBarLine - PR-4 of TODO/20260612-party-rendering-and-party-pages-plan.md.
   *
   * Closed-renderer extension to the schema-is-the-design-system set
   * (docs/concepts/schema-is-the-design-system.md "Closed-renderer
   * extension log"). Bars + line + dots on a shared X axis with
   * dual Y axes (left for bars, right for line). Pure d3-scale +
   * Svelte 5; no external chart lib.
   *
   * Use-cases qualifying the >= 2 indicator threshold (per the
   * existing closed-set extension rule):
   *   - per-party Lok Sabha seats won (bar) vs vote-share pct (line)
   *   - per-party Vidhan Sabha seats won (bar) vs vote-share pct (line)
   *   - future: candidate margin (bar) vs polling-day turnout (line)
   *   - future: party strength index (bar) vs alliance share (line)
   *
   * Mobile contract:
   *   - X-label stride thins to `mobile_label_stride` (default 4) at
   *     viewport widths < 640px.
   *   - tap on a bar reveals year + both values via ChartTooltip.
   *
   * Pure helpers extracted for the unit test (`DualAxisBarLine.test.ts`):
   *   - `buildScales(bars, line)` -> x_domain, left_y_max, right_y_max
   *   - `pickLabelStride(width, year_count, mobile_stride)` -> stride
   *
   * The renderer carries no fetching, no I/O, no view-model coupling;
   * the consumer hand-shapes the `bars` + `line` props from whatever
   * upstream loader makes sense.
   */

  /** Pre-computed scale boundaries derived from the bar + line series. */
  export interface DualAxisScales {
    /** Ordinal domain of period_labels in input order (chronological). */
    x_domain: readonly string[];
    /** Left-axis upper bound; floored at 1 so a zero-only series
     *  still renders a visible axis. */
    left_y_max: number;
    /** Right-axis upper bound; floored at 1; clamped to 100 when
     *  the right axis is a percentage (caller sets via prop). */
    right_y_max: number;
  }

  /** Pure: compute axis boundaries from the bar + line series. */
  export function buildScales(
    bars: readonly { period_label: string; value: number }[],
    line: readonly { period_label: string; value: number }[],
  ): DualAxisScales {
    const seen = new Set<string>();
    const x_domain: string[] = [];
    for (const b of bars) {
      if (!seen.has(b.period_label)) {
        seen.add(b.period_label);
        x_domain.push(b.period_label);
      }
    }
    for (const l of line) {
      if (!seen.has(l.period_label)) {
        seen.add(l.period_label);
        x_domain.push(l.period_label);
      }
    }
    let left_y_max = 0;
    for (const b of bars) {
      if (Number.isFinite(b.value) && b.value > left_y_max) left_y_max = b.value;
    }
    let right_y_max = 0;
    for (const l of line) {
      if (Number.isFinite(l.value) && l.value > right_y_max) right_y_max = l.value;
    }
    return {
      x_domain,
      left_y_max: Math.max(1, left_y_max),
      right_y_max: Math.max(1, right_y_max),
    };
  }

  /** Pure: compute the X-label rendering stride. At widths < 640px
   *  the stride is `mobile_stride` (default 4); above 640px every
   *  label renders (stride 1) until the year count exceeds 12, at
   *  which point a half-strip stride (every 2nd) kicks in to keep
   *  labels legible. */
  export function pickLabelStride(
    width: number,
    year_count: number,
    mobile_stride: number,
  ): number {
    if (year_count <= 0) return 1;
    if (width < 640) return Math.max(1, mobile_stride);
    if (year_count > 12) return 2;
    return 1;
  }

  /** Pure: extract the 4-digit polling year from an ECI event id
   *  (e.g. `AcGenApr2021` -> 2021). Returns the input itself when
   *  no year suffix matches - the renderer falls back to the raw
   *  period_label as the X tick label. */
  export function yearFromPeriodLabel(period_label: string): string {
    const m = period_label.match(/(\d{4})$/);
    return m ? m[1]! : period_label;
  }

  /** PR-10: numeric 4-digit polling year, or null when no trailing
   *  year suffix matches. Powers the methodology-break X-axis seam
   *  placement: a break at `at_year=Y` sits BETWEEN the last bar whose
   *  period_label year is <= Y-1 and the first bar whose year is >= Y. */
  export function yearNumberFromPeriodLabel(
    period_label: string,
  ): number | null {
    const m = period_label.match(/(\d{4})$/);
    return m ? Number(m[1]) : null;
  }

  /** PR-10: methodology-break wire shape consumed by the chart. The
   *  view-model loader (`view-models/party-detail.ts`) builds this
   *  list; the chart positions a thin vertical marker between the
   *  last pre-break bar and the first post-break bar. */
  export interface MethodologyBreakRow {
    methodology_version: string;
    at_year: number;
    at_period_seq: number;
    kind: string;
    note: string;
    publisher_url?: string | null;
    supersedes_methodology_version?: string | null;
  }

  /** PR-10: positioning metadata for one methodology-break marker. */
  export interface MethodologyBreakMarker {
    /** Index into `x_domain` of the LAST bar BEFORE the break (the
     *  bar whose year is < at_year). -1 when the break sits to the
     *  LEFT of the chart's first bar. */
    idx_before: number;
    /** Index into `x_domain` of the FIRST bar AT OR AFTER the break
     *  (the bar whose year is >= at_year). `x_domain.length` when
     *  the break sits to the RIGHT of the chart's last bar. */
    idx_after: number;
    /** 1-based footnote reference number ('1)', '2)', ...). Reflects
     *  the row's position in the input list (chronological order). */
    reference_number: number;
    /** The original wire row (carried through for tooltip rendering). */
    row: MethodologyBreakRow;
  }

  /** PR-2 of TODO/20260614-party-page-reimagination-plan.md - per
   *  Jony J7 the tooltip dispatches a kind-specific verb so the
   *  citizen reads "Boundaries changed in 1967", not the operator
   *  string "1) 1967 methodology break". The closed set mirrors the
   *  five `kind` values declared in
   *  `datasets/schemas/methodology-break.schema.json` v1.0;
   *  anything else falls through to the generic "Methodology
   *  changed in <year>" so a future schema bump that adds a new
   *  kind still renders a readable headline. */
  const KIND_VERB: Record<string, string> = {
    frame_change: "Boundaries changed in",
    definition_change: "Definition changed in",
    coverage_change: "Coverage changed in",
    reclassification: "Reclassified in",
    rebase: "Rebased in",
  };

  /** PR-2: build the citizen-facing tooltip payload for one
   *  methodology-break marker. Pure helper extracted to the script
   *  module so vitest can pin the contract without mounting Svelte.
   *  The tooltip drops the operator `methodology_version` subtitle
   *  (Jony J7), uses a kind-dispatched verb in the title, renders
   *  the (already-cleaned) `note` as the single body line, and -
   *  when `publisher_url` is a parseable URL - hangs the publisher
   *  hostname under a "Source:" hint footer. */
  export function buildMethodologyTooltip(
    marker: MethodologyBreakMarker,
    x: number,
    y: number,
  ): MethodologyTooltipPayload {
    const verb = KIND_VERB[marker.row.kind] ?? "Methodology changed in";
    const title = `${verb} ${marker.row.at_year}`;
    const lines = [{ label: "", value: marker.row.note }];
    let hint: string | undefined;
    if (marker.row.publisher_url) {
      try {
        hint = `Source: ${new URL(marker.row.publisher_url).hostname}`;
      } catch {
        hint = undefined;
      }
    }
    return { x, y, color: "#64748b", title, lines, hint };
  }

  /** PR-2: shape returned by `buildMethodologyTooltip`. Mirrors the
   *  `TooltipState` interface in `ChartTooltip.svelte` (re-declared
   *  here so the module block stays standalone-importable from
   *  vitest without dragging the Svelte runtime in). */
  export interface MethodologyTooltipPayload {
    x: number;
    y: number;
    color: string;
    title: string;
    lines: { label: string; value: string }[];
    hint?: string;
  }

  /** PR-10 of TODO/20260614-party-page-reimagination-plan.md: per-bar
   *  geometry for the composite-mode renderer. The composite mode
   *  collapses the bar + line series into a single bar whose HEIGHT
   *  encodes vote-share % (single Y axis) and whose FILL splits into
   *  two stacked rects - a darker bottom band sized
   *  `bar_height * (seats_won / seats_contested)` (the seat
   *  conversion ratio) and a 40%-opacity upper band that completes
   *  the full bar height. Both rects sit on the same X band; the
   *  consumer plots them via the returned (y, h) pairs.
   *
   *  Defensive: `seats_contested <= 0` collapses the conversion
   *  ratio to 0 (no darker band rendered); negative inputs are
   *  clamped to 0 to keep the SVG geometry positive. */
  export interface CompositeBarSegments {
    /** Y of the contested-fill (full bar) rect - the bar's top. */
    contested_y: number;
    /** Height of the contested-fill rect - the full bar height. */
    contested_h: number;
    /** Y of the seats-fill (darker bottom band) rect. Sits between
     *  `inner_h - seats_h` and `inner_h`. */
    seats_y: number;
    /** Height of the seats-fill rect -
     *  `contested_h * (seats_won / seats_contested)`. */
    seats_h: number;
    /** Conversion ratio 0..1; 0 when `seats_contested <= 0`. */
    seat_conversion_ratio: number;
  }

  export function composeCompositeBarSegments(
    bar_y: number,
    inner_h: number,
    seats_won: number,
    seats_contested: number,
  ): CompositeBarSegments {
    const contested_y = bar_y;
    const contested_h = Math.max(0, inner_h - bar_y);
    const denom = Number.isFinite(seats_contested)
      ? Math.max(0, seats_contested)
      : 0;
    const num = Number.isFinite(seats_won) ? Math.max(0, seats_won) : 0;
    const ratio = denom <= 0 ? 0 : Math.min(1, num / denom);
    const seats_h = contested_h * ratio;
    const seats_y = inner_h - seats_h;
    return {
      contested_y,
      contested_h,
      seats_y,
      seats_h,
      seat_conversion_ratio: ratio,
    };
  }

  /** PR-10: composite-mode tooltip payload. The citizen reads:
   *    "<year>"                           (title)
   *    "<period_label>"                   (subtitle, ECI event id)
   *    Vote share        36.5%
   *    Seats             211 of 543 contested
   *    Seat conversion   38.9%
   *  When `seats_contested <= 0` the seat-conversion line is
   *  omitted (no honest ratio to surface). */
  export function buildCompositeTooltip(
    period_label: string,
    vote_share_pct: number,
    seats_won: number,
    seats_contested: number,
    bar_format: (n: number) => string,
    bar_color: string,
    x: number,
    y: number,
  ): CompositeTooltipPayload {
    const lines: { label: string; value: string }[] = [
      { label: "Vote share", value: bar_format(vote_share_pct) },
    ];
    if (seats_contested > 0) {
      lines.push({
        label: "Seats",
        value: `${seats_won.toLocaleString()} of ${seats_contested.toLocaleString()} contested`,
      });
      const conversion_pct = (seats_won / seats_contested) * 100;
      lines.push({
        label: "Seat conversion",
        value: `${conversion_pct.toFixed(1)}%`,
      });
    } else {
      lines.push({
        label: "Seats",
        value: `${seats_won.toLocaleString()} won (did not contest)`,
      });
    }
    return {
      x,
      y,
      color: bar_color,
      title: yearFromPeriodLabel(period_label),
      subtitle: period_label,
      lines,
    };
  }

  /** PR-10: shape returned by `buildCompositeTooltip`. Mirrors the
   *  `TooltipState` interface in `ChartTooltip.svelte` (re-declared
   *  here so the module block stays standalone-importable from
   *  vitest without dragging the Svelte runtime in). */
  export interface CompositeTooltipPayload {
    x: number;
    y: number;
    color: string;
    title: string;
    subtitle: string;
    lines: { label: string; value: string }[];
  }

  /** Pure: compute the marker positions for each methodology-break
   *  row given the chart's chronological X domain. Markers whose
   *  `at_year` falls entirely OUTSIDE the visible domain - i.e.
   *  at-or-before the first visible year, or strictly after the last
   *  visible year - are filtered out so the chart only renders
   *  markers the citizen can actually see between visible bars. */
  export function computeMethodologyBreakMarkers(
    x_domain: readonly string[],
    breaks: readonly MethodologyBreakRow[],
  ): MethodologyBreakMarker[] {
    if (x_domain.length === 0 || breaks.length === 0) return [];
    const years = x_domain.map((p) => yearNumberFromPeriodLabel(p));
    const first = years.find((y) => y !== null) ?? null;
    const last = [...years].reverse().find((y) => y !== null) ?? null;
    if (first === null || last === null) return [];
    const out: MethodologyBreakMarker[] = [];
    breaks.forEach((row, i) => {
      if (row.at_year <= first || row.at_year > last) return;
      let idx_before = -1;
      for (let j = 0; j < years.length; j += 1) {
        const y = years[j];
        if (y !== null && y < row.at_year) idx_before = j;
      }
      let idx_after = years.length;
      for (let j = 0; j < years.length; j += 1) {
        const y = years[j];
        if (y !== null && y >= row.at_year) {
          idx_after = j;
          break;
        }
      }
      out.push({
        idx_before,
        idx_after,
        reference_number: i + 1,
        row,
      });
    });
    return out;
  }
</script>

<script lang="ts">
  import { scaleBand, scaleLinear } from "d3-scale";
  import ChartTooltip, { type TooltipState } from "../../ChartTooltip.svelte";

  interface BarDatum {
    period_label: string;
    value: number;
    /** PR-10 composite-mode only: seats won this cycle. Ignored in
     *  the default `dual-axis` mode. Required when `mode="composite"`
     *  - the renderer treats missing as 0 (defensive). */
    seats_won?: number;
    /** PR-10 composite-mode only: seats this party CONTESTED this
     *  cycle (denominator of the seat-conversion ratio). Ignored in
     *  the default `dual-axis` mode. When 0 or missing, the
     *  conversion ratio collapses to 0 and the darker bottom band
     *  does not render. */
    seats_contested?: number;
  }
  interface LineDatum {
    period_label: string;
    value: number;
  }

  interface Props {
    bars: readonly BarDatum[];
    line: readonly LineDatum[];
    bar_color: string;
    line_color?: string;
    bar_y_label?: string;
    line_y_label?: string;
    bar_format?: (n: number) => string;
    line_format?: (n: number) => string;
    height?: number;
    mobile_label_stride?: number;
    /** PR-10: methodology-break rows to render as thin grey vertical
     *  markers between bars. Default empty preserves the pre-PR-10
     *  signature for any caller that doesn't surface breaks. */
    methodology_breaks?: readonly MethodologyBreakRow[];
    /** PR-10 of TODO/20260614-party-page-reimagination-plan.md: the
     *  renderer's encoding mode.
     *
     *  - `"dual-axis"` (default; preserves the pre-PR-10 contract):
     *    bars on the left axis, line on the right axis. Used by any
     *    caller that hasn't opted in.
     *  - `"composite"`: single Y axis (left, labelled with
     *    `bar_y_label` - caller usually passes "Vote share %"). Each
     *    bar renders TWO stacked rects on the same X band - an outer
     *    `contested-fill` rect at 40% opacity covering the full bar
     *    height, and an inner `seats-fill` rect at 100% opacity
     *    covering `bar_height * (seats_won / seats_contested)` from
     *    the bottom. The line series + right Y axis are hidden. The
     *    bar tooltip surfaces the composite payload (vote-share +
     *    seats-of-contested + seat-conversion %).
     *
     *  The composite mode consumes the optional `seats_won` +
     *  `seats_contested` fields on each `BarDatum`. Bars missing
     *  those fields render as a single full-opacity rect (defensive
     *  fallback identical to the dual-axis mode's bar). */
    mode?: "composite" | "dual-axis";
  }

  let {
    bars,
    line,
    bar_color,
    line_color = "#334155",
    bar_y_label = "Value",
    line_y_label = "Line",
    bar_format = (n: number) => Number(n).toLocaleString(),
    line_format = (n: number) => `${Number(n).toFixed(1)}%`,
    height = 360,
    mobile_label_stride = 4,
    methodology_breaks = [],
    mode = "dual-axis",
  }: Props = $props();

  // Layout constants. Symmetric left/right margins for the dual axes.
  const MARGIN_TOP = 24;
  const MARGIN_RIGHT = 48;
  const MARGIN_BOTTOM = 56;
  const MARGIN_LEFT = 48;

  // Responsive width via the wrapper's clientWidth.
  let wrapper_width = $state(640);
  const effective_width = $derived(Math.max(280, wrapper_width));
  const inner_w = $derived(
    Math.max(0, effective_width - MARGIN_LEFT - MARGIN_RIGHT),
  );
  const inner_h = $derived(Math.max(0, height - MARGIN_TOP - MARGIN_BOTTOM));

  const scales = $derived(buildScales(bars, line));

  // Detect "percentage" axis: when line_format produces a `%`-suffixed
  // string for 1.0, clamp the right axis to 100. Otherwise scale from
  // the right_y_max directly. Sample-once via $derived so the test
  // doesn't have to mock window.
  const right_y_cap = $derived.by(() => {
    const sample = line_format(1.0);
    if (sample.includes("%")) return Math.max(100, scales.right_y_max);
    return scales.right_y_max;
  });

  // PR-10: same percentage-clamp for the LEFT axis when composite
  // mode's bar_format produces a `%`-suffixed string for 1.0. In
  // dual-axis mode the left axis carries an absolute count and the
  // clamp is a no-op (Math.max(0, left_y_max) === left_y_max).
  const left_y_cap = $derived.by(() => {
    const sample = bar_format(1.0);
    if (sample.includes("%")) return Math.max(100, scales.left_y_max);
    return scales.left_y_max;
  });

  const x_scale = $derived(
    scaleBand<string>()
      .domain([...scales.x_domain])
      .range([0, inner_w])
      .padding(0.18),
  );
  const left_y_scale = $derived(
    scaleLinear().domain([0, left_y_cap]).range([inner_h, 0]).nice(),
  );
  const right_y_scale = $derived(
    scaleLinear().domain([0, right_y_cap]).range([inner_h, 0]).nice(),
  );

  // Y-tick ladders. Left axis ticks every fifth of the rounded-up
  // domain; right axis the same.
  function ticks(max: number, count: number): number[] {
    if (!Number.isFinite(max) || max <= 0) return [0];
    const step = max / count;
    const out: number[] = [];
    for (let i = 0; i <= count; i += 1) out.push(step * i);
    return out;
  }
  const LEFT_TICKS = $derived(ticks(left_y_cap, 5));
  const RIGHT_TICKS = $derived(ticks(right_y_cap, 5));

  const stride = $derived(
    pickLabelStride(effective_width, scales.x_domain.length, mobile_label_stride),
  );

  // Build the line `path d` from the line series. Points skip when
  // their period_label is absent from the X domain (defensive).
  const line_path = $derived.by(() => {
    if (line.length === 0) return "";
    const segs: string[] = [];
    let idx = 0;
    for (const pt of line) {
      const x = x_scale(pt.period_label);
      if (x === undefined) continue;
      const cx = x + x_scale.bandwidth() / 2;
      const cy = right_y_scale(pt.value);
      segs.push(`${idx === 0 ? "M" : "L"} ${cx.toFixed(2)} ${cy.toFixed(2)}`);
      idx += 1;
    }
    return segs.join(" ");
  });

  // Tooltip state. ChartTooltip imperatively reads `tip`; we set/clear
  // it via the bar/dot mouse handlers.
  let tip = $state<TooltipState | null>(null);
  function onBarEnter(e: MouseEvent, datum: BarDatum): void {
    if (mode === "composite") {
      tip = buildCompositeTooltip(
        datum.period_label,
        datum.value,
        datum.seats_won ?? 0,
        datum.seats_contested ?? 0,
        bar_format,
        bar_color,
        e.clientX,
        e.clientY,
      );
      return;
    }
    const lineValue = line.find((l) => l.period_label === datum.period_label)?.value;
    const yearStr = yearFromPeriodLabel(datum.period_label);
    tip = {
      x: e.clientX,
      y: e.clientY,
      color: bar_color,
      title: yearStr,
      subtitle: datum.period_label,
      lines: [
        { label: bar_y_label, value: bar_format(datum.value) },
        ...(lineValue == null
          ? []
          : [{ label: line_y_label, value: line_format(lineValue) }]),
      ],
    };
  }
  function onBarLeave(): void {
    tip = null;
  }

  // PR-10 methodology-break markers. Visible positions are computed
  // from the chart's chronological X domain; tooltip carries the
  // citizen-readable note + reference number. The midpoint between
  // the two bracketing bars is in band-space - convert via x_scale
  // when rendering inside the chart group.
  const markers = $derived(
    computeMethodologyBreakMarkers(scales.x_domain, methodology_breaks),
  );
  function markerX(m: MethodologyBreakMarker): number {
    const bw = x_scale.bandwidth();
    const last_idx = scales.x_domain.length - 1;
    if (m.idx_before < 0) {
      const pl = scales.x_domain[m.idx_after] ?? scales.x_domain[0];
      return pl !== undefined ? (x_scale(pl) ?? 0) : 0;
    }
    if (m.idx_after > last_idx) {
      const pl = scales.x_domain[m.idx_before] ?? scales.x_domain[last_idx];
      return pl !== undefined ? (x_scale(pl) ?? 0) + bw : 0;
    }
    const pl_before = scales.x_domain[m.idx_before];
    const pl_after = scales.x_domain[m.idx_after];
    if (pl_before === undefined || pl_after === undefined) return 0;
    const right_before = (x_scale(pl_before) ?? 0) + bw;
    const left_after = x_scale(pl_after) ?? 0;
    return (right_before + left_after) / 2;
  }
  function onMarkerEnter(e: MouseEvent, m: MethodologyBreakMarker): void {
    tip = buildMethodologyTooltip(m, e.clientX, e.clientY);
  }
  function onMarkerLeave(): void {
    tip = null;
  }
</script>

{#if scales.x_domain.length === 0}
  <div
    class="rounded border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500"
    data-testid="dual-axis-bar-line-empty"
  >
    No data to display.
  </div>
{:else}
  <div
    bind:clientWidth={wrapper_width}
    data-testid="dual-axis-bar-line"
    data-component="dual-axis-bar-line"
    class="w-full"
  >
    <svg
      width={effective_width}
      {height}
      viewBox={`0 0 ${effective_width} ${height}`}
      class="max-w-full"
      data-testid="dual-axis-bar-line-svg"
    >
      <g transform={`translate(${MARGIN_LEFT}, ${MARGIN_TOP})`}>
        <!-- Left Y grid + ticks -->
        {#each LEFT_TICKS as t (`ly-${t}`)}
          <line
            x1={0}
            x2={inner_w}
            y1={left_y_scale(t)}
            y2={left_y_scale(t)}
            stroke="#e2e8f0"
            stroke-dasharray={t === 0 ? "0" : "2 2"}
          />
          <text
            x={-8}
            y={left_y_scale(t)}
            text-anchor="end"
            dominant-baseline="middle"
            class="fill-slate-500 text-[10px]"
          >{bar_format(t)}</text>
        {/each}

        <!-- Right Y ticks (labels only; reuse the left grid). Hidden
             in composite mode - there is no right axis to label. -->
        {#if mode === "dual-axis"}
          {#each RIGHT_TICKS as t (`ry-${t}`)}
            <text
              x={inner_w + 8}
              y={right_y_scale(t)}
              text-anchor="start"
              dominant-baseline="middle"
              class="fill-slate-500 text-[10px]"
            >{line_format(t)}</text>
          {/each}
        {/if}

        <!-- Axis labels -->
        <text
          x={-inner_h / 2}
          y={-36}
          text-anchor="middle"
          transform="rotate(-90)"
          class="fill-slate-700 text-xs font-medium"
        >{bar_y_label}</text>
        {#if mode === "dual-axis"}
          <text
            x={inner_h / 2}
            y={inner_w + 36}
            text-anchor="middle"
            transform="rotate(90)"
            class="fill-slate-700 text-xs font-medium"
          >{line_y_label}</text>
        {/if}

        <!-- Bars. Dual-axis mode: single rect per bar (existing
             behaviour). Composite mode: two stacked rects per bar -
             an outer `contested-fill` at 40% opacity spanning the
             full bar height, and an inner `seats-fill` at full
             opacity spanning the seat-conversion ratio from the
             bottom. The hover halo is delivered by an invisible
             hit rect spanning the full bar so the citizen can
             aim at any pixel of the cycle (Jony 1d). -->
        {#each bars as b, i (`bar-${b.period_label}-${i}`)}
          {@const bx = x_scale(b.period_label) ?? 0}
          {@const by = left_y_scale(b.value)}
          {@const bw = x_scale.bandwidth()}
          {@const bh = Math.max(0, inner_h - by)}
          {#if mode === "composite"}
            {@const seg = composeCompositeBarSegments(
              by,
              inner_h,
              b.seats_won ?? 0,
              b.seats_contested ?? 0,
            )}
            <rect
              x={bx}
              y={seg.contested_y}
              width={bw}
              height={seg.contested_h}
              fill={bar_color}
              fill-opacity={0.4}
              stroke={tip && tip.subtitle === b.period_label ? "#0f172a" : "none"}
              stroke-width={tip && tip.subtitle === b.period_label ? 1 : 0}
              data-mode="composite"
              data-overlay="contested-fill"
              data-testid={`bar-${b.period_label}-contested`}
              pointer-events="none"
            />
            {#if seg.seats_h > 0}
              <rect
                x={bx}
                y={seg.seats_y}
                width={bw}
                height={seg.seats_h}
                fill={bar_color}
                fill-opacity={1}
                data-mode="composite"
                data-overlay="seats-fill"
                data-testid={`bar-${b.period_label}-seats`}
                pointer-events="none"
              />
            {/if}
            <!-- Hit rect: transparent, covers the full bar so a tap
                 anywhere on the cycle column wakes the tooltip. -->
            <rect
              x={bx}
              y={seg.contested_y}
              width={bw}
              height={seg.contested_h}
              fill="transparent"
              class="cursor-pointer"
              data-mode="composite"
              data-overlay="hit"
              data-testid={`bar-${b.period_label}`}
              onmouseenter={(e) => onBarEnter(e, b)}
              onmouseleave={onBarLeave}
            />
          {:else}
            <rect
              x={bx}
              y={by}
              width={bw}
              height={bh}
              fill={bar_color}
              fill-opacity={tip && tip.subtitle === b.period_label ? 1 : 0.85}
              stroke={tip && tip.subtitle === b.period_label ? "#0f172a" : "none"}
              stroke-width={tip && tip.subtitle === b.period_label ? 1 : 0}
              class="cursor-pointer"
              data-testid={`bar-${b.period_label}`}
              onmouseenter={(e) => onBarEnter(e, b)}
              onmouseleave={onBarLeave}
            />
          {/if}
        {/each}

        <!-- PR-10 methodology-break markers. Rendered AFTER bars
             so the dashed vertical line + footnote number sit on
             top of the bars rather than being clipped under them.
             The transparent hit rect widens the tap target to ~16px
             so the marker is touch-reachable on mobile (Jony 1d). -->
        {#each markers as marker (`mbm-${marker.row.methodology_version}`)}
          {@const mx = markerX(marker)}
          <g
            class="cursor-pointer"
            data-testid="methodology-break-marker"
            data-methodology-version={marker.row.methodology_version}
            data-reference-number={marker.reference_number}
          >
            <rect
              x={mx - 8}
              y={0}
              width={16}
              height={inner_h}
              fill="transparent"
              onmouseenter={(e) => onMarkerEnter(e, marker)}
              onmouseleave={onMarkerLeave}
              onclick={(e) => onMarkerEnter(e, marker)}
            />
            <line
              x1={mx}
              x2={mx}
              y1={0}
              y2={inner_h}
              stroke="rgba(100, 116, 139, 0.4)"
              stroke-width={1}
              stroke-dasharray="3 2"
              pointer-events="none"
            />
            <text
              x={mx}
              y={-6}
              text-anchor="middle"
              class="fill-slate-500 text-[10px]"
              pointer-events="none"
            >{marker.reference_number})</text>
          </g>
        {/each}

        <!-- Line + dots. Hidden entirely in composite mode - the
             vote-share % is carried by the bar height itself, not a
             separate series. -->
        {#if mode === "dual-axis"}
          {#if line_path}
            <path
              d={line_path}
              fill="none"
              stroke={line_color}
              stroke-width={2}
              stroke-linejoin="round"
              data-testid="line-path"
            />
          {/if}
          {#each line as l, i (`dot-${l.period_label}-${i}`)}
            {@const lx = x_scale(l.period_label)}
            {#if lx !== undefined}
              {@const cx = lx + x_scale.bandwidth() / 2}
              {@const cy = right_y_scale(l.value)}
              <circle
                {cx}
                {cy}
                r={4}
                fill={line_color}
                stroke="#ffffff"
                stroke-width={1.5}
                data-testid={`dot-${l.period_label}`}
              />
            {/if}
          {/each}
        {/if}

        <!-- X-axis tick labels (with stride thinning) -->
        {#each scales.x_domain as period, i (`xt-${period}-${i}`)}
          {#if i % stride === 0}
            {@const tx = (x_scale(period) ?? 0) + x_scale.bandwidth() / 2}
            <text
              x={tx}
              y={inner_h + 16}
              text-anchor="middle"
              class="fill-slate-500 text-[10px]"
            >{yearFromPeriodLabel(period)}</text>
          {/if}
        {/each}
      </g>
    </svg>

    <!-- Legend below the chart. Composite mode swaps the dual
         bar/line legend for a single two-tone bar key (full = seats
         contested, darker bottom = seats won). -->
    <div
      class="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-600"
      data-testid="dual-axis-bar-line-legend"
    >
      {#if mode === "composite"}
        <span class="inline-flex items-center gap-1.5">
          <span
            class="inline-block h-3 w-3 rounded-sm"
            style:background-color={bar_color}
            style:opacity={0.4}
          ></span>
          Seats contested
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span
            class="inline-block h-3 w-3 rounded-sm"
            style:background-color={bar_color}
          ></span>
          Seats won
        </span>
        <span class="text-slate-500">Bar height = vote share %</span>
      {:else}
        <span class="inline-flex items-center gap-1.5">
          <span
            class="inline-block h-3 w-3 rounded-sm"
            style:background-color={bar_color}
          ></span>
          {bar_y_label}
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span
            class="inline-block h-0.5 w-4"
            style:background-color={line_color}
          ></span>
          <span
            class="inline-block h-2 w-2 rounded-full"
            style:background-color={line_color}
          ></span>
          {line_y_label}
        </span>
      {/if}
    </div>
  </div>

  <ChartTooltip {tip} />
{/if}
