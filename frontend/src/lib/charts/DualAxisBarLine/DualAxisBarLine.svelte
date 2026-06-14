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

  const x_scale = $derived(
    scaleBand<string>()
      .domain([...scales.x_domain])
      .range([0, inner_w])
      .padding(0.18),
  );
  const left_y_scale = $derived(
    scaleLinear().domain([0, scales.left_y_max]).range([inner_h, 0]).nice(),
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
  const LEFT_TICKS = $derived(ticks(scales.left_y_max, 5));
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
    tip = {
      x: e.clientX,
      y: e.clientY,
      color: "#64748b",
      title: `${m.reference_number}) ${m.row.at_year} methodology break`,
      subtitle: m.row.methodology_version,
      lines: [{ label: "why", value: m.row.note }],
    };
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

        <!-- Right Y ticks (labels only; reuse the left grid). -->
        {#each RIGHT_TICKS as t (`ry-${t}`)}
          <text
            x={inner_w + 8}
            y={right_y_scale(t)}
            text-anchor="start"
            dominant-baseline="middle"
            class="fill-slate-500 text-[10px]"
          >{line_format(t)}</text>
        {/each}

        <!-- Axis labels -->
        <text
          x={-inner_h / 2}
          y={-36}
          text-anchor="middle"
          transform="rotate(-90)"
          class="fill-slate-700 text-xs font-medium"
        >{bar_y_label}</text>
        <text
          x={inner_h / 2}
          y={inner_w + 36}
          text-anchor="middle"
          transform="rotate(90)"
          class="fill-slate-700 text-xs font-medium"
        >{line_y_label}</text>

        <!-- Bars -->
        {#each bars as b, i (`bar-${b.period_label}-${i}`)}
          {@const bx = x_scale(b.period_label) ?? 0}
          {@const by = left_y_scale(b.value)}
          {@const bw = x_scale.bandwidth()}
          {@const bh = Math.max(0, inner_h - by)}
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

        <!-- Line + dots -->
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

    <!-- Legend below the chart. -->
    <div
      class="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-600"
      data-testid="dual-axis-bar-line-legend"
    >
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
    </div>
  </div>

  <ChartTooltip {tip} />
{/if}
