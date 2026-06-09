// Vitest — pure helpers for IndicatorCard.svelte's G31 national-
// reference overlay.
//
// Component-render tests are not possible in node-env without
// `@testing-library/svelte` (Skeleton + IndicatorJump precedent +
// /memories/lessons.md note). The four module-scope exports
// (`nationalReferenceMap`, `mergedYMax`, `referenceSparklinePath`,
// `referenceGlyphVerdict`) are the testable surface; the SVG template
// wiring + the four fence-rule guards are exercised by CLAUDE.md §13
// in-browser smoke on /s/<state> for an indicator that opts in via
// `has_national_reference: true` (today: outstanding-liabilities-pct-
// gsdp only).
//
// Mocking carve-out: none. The helpers operate on plain inputs; the
// `indicatorArtifactNationalReference` accessor is exercised in
// `canonical/indicator-from-canonical.test.ts` against a vi.mock'd
// DuckDB module per the CLAUDE.md canonical-store loader carve-out.

import { describe, expect, it } from "vitest";

import {
  mergedYMax,
  nationalReferenceMap,
  referenceGlyphVerdict,
  referenceSparklinePath,
  type SparklineGeom,
  type StatePoint,
} from "./IndicatorCard.svelte";
import type { NationalReferenceRow } from "./canonical/indicator-from-canonical";

// Mirrors the IndicatorCard.svelte instance-script constants. Kept
// here (not imported) so the test owns the geometry it asserts
// against and a future tweak to the card's W/H/PAD must be re-
// asserted explicitly.
const GEOM: SparklineGeom = { W: 240, H: 56, PAD_X: 2, PAD_Y: 3 };

// Pop-weighted national reference for outstanding-liabilities-%-GSDP
// (3-row excerpt from
// datasets/data/datapoints/geo/outstanding-liabilities-pct-gsdp-national.csv).
// `time` is the canonical BIGINT shape — the helper must stringify.
const REF_ROWS: NationalReferenceRow[] = [
  { entity_id: "IN-pop-weighted", time: 2021, value: 30.97, source_id: "src-3efef1095d49" },
  { entity_id: "IN-pop-weighted", time: 2022, value: 30.04, source_id: "src-3efef1095d49" },
  { entity_id: "IN-pop-weighted", time: 2023, value: 30.04, source_id: "src-3efef1095d49" },
];

// State series shape after `seriesForEntity()` — `time` is the string
// form of the fiscal-year integer per the canonical adapter's
// `time: r.period_label` mapping.
const STATE_SERIES: StatePoint[] = [
  { time: "2021", value: 28.5 },
  { time: "2022", value: 29.1 },
  { time: "2023", value: 33.7 },
];

describe("nationalReferenceMap", () => {
  it("returns an empty map for undefined (descriptor opted out)", () => {
    const m = nationalReferenceMap(undefined);
    expect(m.size).toBe(0);
  });

  it("returns an empty map for an empty array", () => {
    expect(nationalReferenceMap([]).size).toBe(0);
  });

  it("keys on String(time) so the BIGINT ref joins the string state series", () => {
    const m = nationalReferenceMap(REF_ROWS);
    expect(m.size).toBe(3);
    expect(m.get("2021")).toBe(30.97);
    expect(m.get("2022")).toBe(30.04);
    expect(m.get("2023")).toBe(30.04);
    // The accessor MUST NOT be reachable via the numeric form — the
    // state series only carries string times.
    // @ts-expect-error - intentional: number key would be a contract bug
    expect(m.get(2021)).toBeUndefined();
  });

  it("skips rows whose value is null (publisher gap at that period)", () => {
    const rows: NationalReferenceRow[] = [
      { entity_id: "IN-pop-weighted", time: 2020, value: null, source_id: "src-x" },
      { entity_id: "IN-pop-weighted", time: 2021, value: 30.97, source_id: "src-x" },
    ];
    const m = nationalReferenceMap(rows);
    expect(m.size).toBe(1);
    expect(m.has("2020")).toBe(false);
    expect(m.get("2021")).toBe(30.97);
  });

  it("skips NaN values defensively", () => {
    const rows: NationalReferenceRow[] = [
      { entity_id: "IN-pop-weighted", time: 2021, value: Number.NaN, source_id: "src-x" },
      { entity_id: "IN-pop-weighted", time: 2022, value: 30.04, source_id: "src-x" },
    ];
    const m = nationalReferenceMap(rows);
    expect(m.size).toBe(1);
    expect(m.has("2021")).toBe(false);
  });
});

describe("mergedYMax", () => {
  it("falls back to state-only max when the ref map is empty", () => {
    const m = mergedYMax(STATE_SERIES, new Map());
    // max(|28.5|, |29.1|, |33.7|) = 33.7
    expect(m).toBe(33.7);
  });

  it("returns 1 (the clamp) when the state series is empty and ref is empty", () => {
    expect(mergedYMax([], new Map())).toBe(1);
  });

  it("folds reference values at overlapping periods INTO the y_max", () => {
    // Reference at 2021 = 30.97 — below state max 33.7, so y_max stays 33.7
    const ref_map_lower = nationalReferenceMap(REF_ROWS);
    expect(mergedYMax(STATE_SERIES, ref_map_lower)).toBe(33.7);

    // Bump the reference values above the state max to prove the merge
    // actually consults the reference side. The renderer needs both
    // polylines to share a Y-scale; if mergedYMax ignored the ref, the
    // ref polyline would plot off-canvas when ref > state max.
    const ref_map_higher = new Map<string, number>([
      ["2021", 99.5],
      ["2022", 99.6],
      ["2023", 99.7],
    ]);
    expect(mergedYMax(STATE_SERIES, ref_map_higher)).toBe(99.7);
  });

  it("ignores reference values OUTSIDE the state series range", () => {
    // A reference value at year 1900 that exceeds the state max must
    // NOT stretch the y_max — it would not be plotted (state has no
    // period at 1900), so it would be a misleading scale.
    const ref_map = new Map<string, number>([["1900", 9999]]);
    expect(mergedYMax(STATE_SERIES, ref_map)).toBe(33.7);
  });
});

describe("referenceSparklinePath", () => {
  it("returns '' when the state series has fewer than 2 points", () => {
    const ref_map = nationalReferenceMap(REF_ROWS);
    expect(referenceSparklinePath([], ref_map, 50, GEOM)).toBe("");
    expect(
      referenceSparklinePath([{ time: "2023", value: 30 }], ref_map, 50, GEOM),
    ).toBe("");
  });

  it("returns '' when the ref map is empty (no reference attached)", () => {
    expect(referenceSparklinePath(STATE_SERIES, new Map(), 50, GEOM)).toBe("");
  });

  it("returns '' when fewer than 2 state periods have matching ref values", () => {
    // Only the last state period has a ref entry → 1 plotted point,
    // which collapses to an invisible zero-length path. Suppress.
    const ref_map = new Map<string, number>([["2023", 30.04]]);
    expect(referenceSparklinePath(STATE_SERIES, ref_map, 50, GEOM)).toBe("");
  });

  it("emits a single segment when every state period has a ref value", () => {
    const ref_map = nationalReferenceMap(REF_ROWS);
    const path = referenceSparklinePath(STATE_SERIES, ref_map, 35, GEOM);
    // 3 state periods => 1 M + 2 L commands, no second M.
    expect((path.match(/M/g) ?? []).length).toBe(1);
    expect((path.match(/L/g) ?? []).length).toBe(2);
  });

  it("splits into multiple segments on gaps so no connector spans a missing period", () => {
    // Gap in the middle: ref present at 2021 + 2023, absent at 2022.
    const state: StatePoint[] = [
      { time: "2021", value: 28.5 },
      { time: "2022", value: 29.1 },
      { time: "2023", value: 33.7 },
    ];
    const ref_map = new Map<string, number>([
      ["2021", 30.97],
      ["2023", 30.04],
    ]);
    // 2 plotted points across a gap => 2 segments => 2 M commands,
    // each followed by zero L (single-point segments). The plotted
    // count >= 2 condition is met (sum of plotted points across
    // segments), so the path is non-empty.
    const path = referenceSparklinePath(state, ref_map, 35, GEOM);
    expect(path).not.toBe("");
    expect((path.match(/M/g) ?? []).length).toBe(2);
  });

  it("projects to the same INDEX-driven x as the state path (no period-axis offset)", () => {
    // With W=240, PAD_X=2, span=2, inner_w=236 — the LAST x is
    // PAD_X + (2/2)*inner_w = 238. The reference path's last L must
    // share that x so the two polylines stay visually aligned at the
    // citizen's "latest period" end of the chart.
    const ref_map = nationalReferenceMap(REF_ROWS);
    const path = referenceSparklinePath(STATE_SERIES, ref_map, 35, GEOM);
    // The path string ends with the last point — pull it via a regex.
    const last_pt = path.match(/L([\d.]+),([\d.]+)$/);
    expect(last_pt).not.toBeNull();
    expect(parseFloat(last_pt![1])).toBeCloseTo(238, 2);
  });
});

describe("referenceGlyphVerdict", () => {
  const ref_map = nationalReferenceMap(REF_ROWS);

  // === Test case (a) — reference absent / flag off ==========================
  it("returns 'missing' when the ref map is empty (no reference attached)", () => {
    expect(
      referenceGlyphVerdict(
        { time: "2023", value: 33.7 },
        new Map(),
        "lower_is_better",
      ),
    ).toBe("missing");
  });

  it("returns 'missing' when home_latest is null (state has no data)", () => {
    expect(referenceGlyphVerdict(null, ref_map, "lower_is_better")).toBe(
      "missing",
    );
  });

  it("returns 'missing' when the home period has no matching ref entry", () => {
    expect(
      referenceGlyphVerdict(
        { time: "1999", value: 50 },
        ref_map,
        "lower_is_better",
      ),
    ).toBe("missing");
  });

  // === Test case (b) — lower_is_better, state ABOVE ref ====================
  it("returns 'worse' when lower_is_better and state ABOVE ref at home period", () => {
    // outstanding-liabilities pilot: state 33.7% vs national 30.04% in 2023,
    // direction=lower_is_better → state is in the BAD zone → 'worse' verdict
    // (which the StatusGlyph renders as a red triangle pointing DOWN).
    expect(
      referenceGlyphVerdict(
        { time: "2023", value: 33.7 },
        ref_map,
        "lower_is_better",
      ),
    ).toBe("worse");
  });

  // === Test case (c) — lower_is_better, state BELOW ref ====================
  it("returns 'better' when lower_is_better and state BELOW ref at home period", () => {
    // Same pilot inverted: state 25.0% vs national 30.04% in 2023,
    // direction=lower_is_better → state is in the GOOD zone → 'better'
    // verdict (renders as a green triangle pointing UP).
    expect(
      referenceGlyphVerdict(
        { time: "2023", value: 25.0 },
        ref_map,
        "lower_is_better",
      ),
    ).toBe("better");
  });

  // === Symmetry case — higher_is_better, the same scenarios ================
  it("returns 'better' when higher_is_better and state ABOVE ref (symmetric to lower_is_better/worse)", () => {
    expect(
      referenceGlyphVerdict(
        { time: "2023", value: 33.7 },
        ref_map,
        "higher_is_better",
      ),
    ).toBe("better");
  });

  it("returns 'worse' when higher_is_better and state BELOW ref", () => {
    expect(
      referenceGlyphVerdict(
        { time: "2023", value: 25.0 },
        ref_map,
        "higher_is_better",
      ),
    ).toBe("worse");
  });

  // === Neutral-direction gate (fence rule 2 at the verdict level) =========
  it("returns 'neutral' (no colour) when direction is 'neutral'", () => {
    // The template's `should_render_reference` guard also short-circuits
    // on direction=neutral so the polyline ALSO doesn't render. Here
    // we just verify the verdict half: a neutral indicator gets the
    // neutral hollow-circle glyph, never a triangle.
    expect(
      referenceGlyphVerdict(
        { time: "2023", value: 33.7 },
        ref_map,
        "neutral",
      ),
    ).toBe("neutral");
  });

  it("returns 'equal' when state value === ref value at the home period", () => {
    expect(
      referenceGlyphVerdict(
        { time: "2023", value: 30.04 },
        ref_map,
        "lower_is_better",
      ),
    ).toBe("equal");
  });
});
