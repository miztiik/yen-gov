/**
 * Phase 1 renderer primitives — TODO/VIZ-LAYER-GAPS-PLAN.md.
 *
 * Five small pure functions that fix the three honesty defects Fowler
 * flagged in the 2026-05-15 audit:
 *
 *   1. `formatTimeLabel(time, grain)` — one place that turns a raw
 *      schema time string + the indicator's `time_grain` into the
 *      string a citizen reads on an axis. Stops the "same chart shows
 *      `2024`, `2024-04`, `2025-03` mixed together" bug.
 *
 *   2. `splitOnBreaks(rows, breaks, getTime)` — chops a series into
 *      contiguous segments at every `series_breaks[]` boundary so a
 *      polyline renderer draws N lines instead of one continuous one
 *      across a base-year change. Returns the segments in order.
 *
 *   3. `growthSafeAcross(prev, curr, breaks)` — per-period growth that
 *      returns `null` when the two points straddle a series break.
 *      Stops headlines like "+3,400% YoY" at a vintage splice.
 *
 *   4. `vintageTooltipLine(meta, atTime)` — composes the one extra line
 *      tooltips append: "Methodology vintage: …" plus, when `atTime`
 *      coincides with or sits adjacent to a break, the break note.
 *
 *   5. `indexAxisHint(meta)` — returns the axis-label suffix and the
 *      "= 100 in {base}" annotation for `value_kind: "index"` series so
 *      they get their own treatment instead of being plotted on the
 *      same axis as ₹-Crore series.
 *
 * These are pure (no DOM, no Svelte, no fetch) and exhaustively unit-
 * tested in the sibling `indicator-render.test.ts`. Phase 2 components
 * consume them; nothing in this file knows about Svelte.
 *
 * Why a sibling module rather than appending to `indicators.ts`: that
 * file already mixes types, fetcher, rollups, and colour helpers. A
 * separate module keeps the renderer-honesty surface searchable, and
 * the test file co-locates with it under a single feature heading.
 */

import type { IndicatorMeta, IndicatorRow, TimeGrain } from "./indicators";

// ---- 1. formatTimeLabel ----------------------------------------------------

/** Map an indicator row's raw `time` string + the indicator's `time_grain`
 *  to the string a citizen reads on a chart axis or in a tooltip.
 *
 *  Inputs honour the schema's `time` pattern: `YYYY`, `YYYY-MM`, or
 *  `YYYY-MM-DD`. Output rules:
 *
 *    grain=year         "2024"             → "2024"
 *    grain=fiscal_year  "2024-04"          → "FY 2024-25"
 *                       "2024"             → "FY 2024-25" (treated as start year)
 *    grain=quarter      "2024-04"          → "2024 Q1"   (Apr-Jun)
 *                       "2024-07"          → "2024 Q2"   (Jul-Sep)
 *                       "2024-10"          → "2024 Q3"
 *                       "2025-01"          → "2024 Q4"
 *    grain=month        "2024-04"          → "Apr 2024"
 *    grain=date         "2024-04-15"       → "15 Apr 2024"
 *
 *  The fiscal-year quarter mapping follows the Government of India fiscal
 *  calendar (FY runs Apr–Mar). Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec,
 *  Q4=Jan-Mar; a Jan-Mar quarter belongs to the FY that started the
 *  preceding April. */
export function formatTimeLabel(time: string, grain: TimeGrain): string {
  if (!time || typeof time !== "string") return "";

  const [yearStr, monthStr, dayStr] = time.split("-");
  const year = Number(yearStr);
  const month = monthStr ? Number(monthStr) : null;
  const day = dayStr ? Number(dayStr) : null;
  if (!Number.isFinite(year)) return time;

  const monthNames = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];

  switch (grain) {
    case "year":
      return String(year);

    case "fiscal_year": {
      // FY starts in April. A "2024-04" stamp belongs to FY 2024-25;
      // a "2025-01" stamp also belongs to FY 2024-25 (Q4). A bare year
      // is read as the start year.
      const start = month != null && month >= 1 && month <= 3 ? year - 1 : year;
      const endShort = String((start + 1) % 100).padStart(2, "0");
      return `FY ${start}-${endShort}`;
    }

    case "quarter": {
      if (month == null) return String(year);
      // Map Apr-Jun=Q1, Jul-Sep=Q2, Oct-Dec=Q3, Jan-Mar=Q4 (prev FY).
      let q: number;
      let displayYear = year;
      if (month >= 4 && month <= 6) { q = 1; }
      else if (month >= 7 && month <= 9) { q = 2; }
      else if (month >= 10 && month <= 12) { q = 3; }
      else { q = 4; displayYear = year - 1; }
      return `${displayYear} Q${q}`;
    }

    case "month": {
      if (month == null || month < 1 || month > 12) return String(year);
      return `${monthNames[month - 1]} ${year}`;
    }

    case "date": {
      if (month == null || day == null || month < 1 || month > 12) {
        return String(year);
      }
      return `${day} ${monthNames[month - 1]} ${year}`;
    }
  }
}

// ---- 2. splitOnBreaks ------------------------------------------------------

export interface SeriesBreak {
  at_time: string;
  kind: "rebase" | "definition_change" | "frame_change" | "coverage_change";
  note: string;
}

/** Split an ordered series into contiguous segments at every break point.
 *  Convention: a break "at_time = T" means the value AT T belongs to the
 *  NEW (post-break) segment. The pre-break segment ends at the latest
 *  point strictly before T. Equivalent to: start a new segment whenever
 *  the next point's time >= some break.at_time AND a previous point
 *  existed before that break.
 *
 *  Returns at least one segment (possibly empty). Never reorders rows;
 *  callers are responsible for sorting before calling. Idempotent on
 *  empty `breaks` (returns `[rows]`).
 *
 *  Rationale: the audit found that line-charts of vintage-spliced NSDP
 *  drew a single polyline across the 2011-12 base-year change. With
 *  this helper, the chart iterates the returned segments and draws
 *  one polyline per segment, leaving a visible gap that
 *  `<SeriesBreakAnnotation>` (Phase 2) labels.
 */
export function splitOnBreaks<T>(
  rows: readonly T[],
  breaks: readonly SeriesBreak[],
  getTime: (row: T) => string,
): T[][] {
  if (rows.length === 0) return [[]];
  if (breaks.length === 0) return [[...rows]];

  // Sort break times ascending and dedupe.
  const breakTimes = [...new Set(breaks.map(b => b.at_time))].sort();
  const segments: T[][] = [];
  let current: T[] = [];
  let breakCursor = 0;

  for (const row of rows) {
    const t = getTime(row);
    // Advance break cursor past every break <= this row's time and,
    // for each, close the current segment (if non-empty) before adding.
    while (breakCursor < breakTimes.length && breakTimes[breakCursor] <= t) {
      if (current.length > 0) {
        segments.push(current);
        current = [];
      }
      breakCursor++;
    }
    current.push(row);
  }
  if (current.length > 0) segments.push(current);
  return segments.length > 0 ? segments : [[]];
}

// ---- 3. growthSafeAcross ---------------------------------------------------

/** Period-over-period growth, returning `null` when the two endpoints
 *  straddle a series break (so the renderer omits the headline rather
 *  than printing `+3,400%` at a base-year splice).
 *
 *    Returns (curr - prev) / prev when both values are finite, prev != 0,
 *    AND no break.at_time falls in the half-open interval (prevTime, currTime].
 *
 *  Returns `null` for: null/non-finite inputs, prev == 0 (avoid div-by-0),
 *  or a straddled break. Equivalent to splitting on breaks and computing
 *  growth only within a segment.
 */
export function growthSafeAcross(
  prev: number | null,
  curr: number | null,
  prevTime: string,
  currTime: string,
  breaks: readonly SeriesBreak[],
): number | null {
  if (prev == null || curr == null) return null;
  if (!Number.isFinite(prev) || !Number.isFinite(curr)) return null;
  if (prev === 0) return null;
  for (const b of breaks) {
    if (b.at_time > prevTime && b.at_time <= currTime) return null;
  }
  return (curr - prev) / prev;
}

// ---- 4. vintageTooltipLine -------------------------------------------------

export interface VintageTooltip {
  /** Single-line vintage statement, e.g. "RBI Handbook 2024-25 edition".
   *  Empty string when the indicator declares no methodology_vintage. */
  vintageLine: string;
  /** Optional extra line when `atTime` coincides with a series break,
   *  e.g. "Series rebased at FY 2011-12 (RBI splice)." */
  breakLine: string;
}

/** Compose the trailing line(s) a tooltip appends so the citizen sees
 *  vintage and break context in the same place every time. Never throws;
 *  returns empty strings when nothing applies.
 *
 *  When `atTime` is provided AND a break.at_time matches it (or the
 *  first break that is `>= atTime`), the break.note is surfaced. The
 *  caller decides whether to render `breakLine`; this module just
 *  composes the strings.
 */
export function vintageTooltipLine(
  meta: Pick<IndicatorMeta, "methodology_vintage" | "series_breaks">,
  atTime?: string,
): VintageTooltip {
  const vintageLine = meta.methodology_vintage
    ? `Methodology vintage: ${meta.methodology_vintage}`
    : "";

  let breakLine = "";
  if (atTime && meta.series_breaks && meta.series_breaks.length > 0) {
    // Match an exact break first; otherwise the most recent break <= atTime.
    const exact = meta.series_breaks.find(b => b.at_time === atTime);
    if (exact) {
      breakLine = `Series ${exact.kind.replaceAll("_", " ")} at ${exact.at_time}: ${exact.note}`;
    }
  }
  return { vintageLine, breakLine };
}

// ---- 5. indexAxisHint ------------------------------------------------------

export interface IndexAxisHint {
  /** Suffix to append to the y-axis label, e.g. "(index, 2012=100)". */
  axisSuffix: string;
  /** Caption shown next to the legend, e.g. "= 100 in 2012". */
  baseCaption: string;
  /** Whether the indicator should be plotted on its own axis (true for
   *  `value_kind: "index"`; false for everything else). Drives the
   *  decision in chart code to NOT co-plot index series with ₹-Crore. */
  ownAxis: boolean;
}

/** Detect whether an indicator is an index (`value_kind === "index"`) and
 *  if so extract the base year from its `unit` string so renderers can
 *  surface "= 100 in {base}" without per-indicator code.
 *
 *  Recognises units in any of these shapes (case-insensitive):
 *    "index (Base 2012=100)"
 *    "Index, 2011-12 = 100"
 *    "index (2004-05=100)"
 *    "index"  (no base detected)
 *
 *  The base substring captured may be a year (2012) or a fiscal-year
 *  pair (2011-12). Returned verbatim — the caller decides how to render.
 */
export function indexAxisHint(
  meta: Pick<IndicatorMeta, "value_kind" | "unit">,
): IndexAxisHint {
  if (meta.value_kind !== "index") {
    return { axisSuffix: "", baseCaption: "", ownAxis: false };
  }
  const unit = meta.unit ?? "";
  // Capture "<digits>(-<digits>)? = 100" with optional whitespace.
  const m = unit.match(/(\d{4}(?:-\d{2,4})?)\s*=\s*100/i);
  const base = m ? m[1] : "";
  return {
    axisSuffix: base ? `(index, ${base}=100)` : "(index)",
    baseCaption: base ? `= 100 in ${base}` : "",
    ownAxis: true,
  };
}

// ---- Convenience re-exports ------------------------------------------------

/** Convenience: extract an ordered, deduped break list from an indicator
 *  meta block. Keeps callers from having to remember to sort. */
export function breaksFromMeta(
  meta: Pick<IndicatorMeta, "series_breaks">,
): SeriesBreak[] {
  if (!meta.series_breaks || meta.series_breaks.length === 0) return [];
  return [...meta.series_breaks].sort((a, b) => a.at_time.localeCompare(b.at_time));
}

/** Convenience: split rows for a single entity using the indicator's own
 *  declared breaks. Sorts rows ascending by time first. */
export function splitRowsForEntity(
  rows: readonly IndicatorRow[],
  meta: Pick<IndicatorMeta, "series_breaks">,
): IndicatorRow[][] {
  const sorted = [...rows].sort((a, b) => a.time.localeCompare(b.time));
  return splitOnBreaks(sorted, breaksFromMeta(meta), r => r.time);
}

// ---- 6. axisUnitLabel + legendCaption (PR-T row 1.10 / T-4) ---------------

/** Compact unit string for a chart's Y-axis / legend swatch row.
 *
 *  Prefers `indicator.short_unit` (compact glyph form authored for
 *  legend space, e.g. `"₹cr"` for `unit="INR crore"`, `"kWh/cap"` for
 *  `unit="kWh per person per year"`). Falls back to `indicator.unit`
 *  when no short form is authored, then to empty string when the
 *  indicator declares no unit at all (rare — only counts/indices that
 *  publishers ship unitless).
 *
 *  Accepts a Partial so the helper can be probed defensively from
 *  test fixtures or chart code that hasn't fully populated meta yet;
 *  callers in production pass the real `IndicatorMeta` where `unit`
 *  is required.
 *
 *  One generic helper so every chart wrapper picks up the new
 *  `short_unit` field via a single import. See PR-T / row 1.10. */
export function axisUnitLabel(
  meta: Partial<Pick<IndicatorMeta, "unit" | "short_unit">>,
): string {
  return meta.short_unit ?? meta.unit ?? "";
}

/** One-line citizen-readable caption for a chart legend / sub-title.
 *
 *  Prefers `indicator.description_short` (Plain-Facts register, ≤280
 *  chars, hand-authored on top-30 citizen-facing indicators per PR-T).
 *  Falls back to the publisher-style `indicator.description` for the
 *  tail of indicators not yet backfilled — preserves the existing
 *  citizen surface during the per-family migration window. Last-resort
 *  fallback is `indicator.title` so the caption never disappears
 *  entirely and never "lies" (CLAUDE.md §10).
 *
 *  Per Hans + Max 2026-05-19 Q3 verdict the tail backfills `description_short`
 *  per-family at next natural touch, NOT via auto-stub. Once the tail
 *  is fully backfilled the middle fallback becomes dead code and can
 *  be removed in a later PR. */
export function legendCaption(
  meta: Partial<Pick<IndicatorMeta, "title" | "description" | "description_short">>,
): string {
  return meta.description_short ?? meta.description ?? meta.title ?? "";
}
