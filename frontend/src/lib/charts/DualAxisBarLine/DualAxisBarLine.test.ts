// PR-4 vitest for `DualAxisBarLine.svelte`.
//
// Per project doctrine (`@testing-library/svelte` is NOT installed):
// pure helpers are extracted to the `<script module>` block so vitest
// can pin the contract without mounting Svelte. The Svelte template
// is covered by the e2e spec (`frontend/e2e/party-detail.spec.ts`)
// and the CLAUDE.md section 13 in-browser smoke.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  buildCompositeTooltip,
  buildMethodologyTooltip,
  buildScales,
  composeCompositeBarSegments,
  computeMethodologyBreakMarkers,
  pickLabelStride,
  yearFromPeriodLabel,
  yearNumberFromPeriodLabel,
  type MethodologyBreakMarker,
  type MethodologyBreakRow,
} from "./DualAxisBarLine.svelte";

// --- buildScales ----------------------------------------------------------

describe("buildScales", () => {
  it("returns the bar period_labels in input order in the x_domain", () => {
    const bars = [
      { period_label: "AcGenJan1989", value: 24 },
      { period_label: "AcGenFeb1991", value: 2 },
      { period_label: "AcGenFeb1996", value: 173 },
    ];
    const line = [
      { period_label: "AcGenJan1989", value: 14.4 },
      { period_label: "AcGenFeb1991", value: 22.5 },
      { period_label: "AcGenFeb1996", value: 42.1 },
    ];
    const out = buildScales(bars, line);
    expect(out.x_domain).toEqual([
      "AcGenJan1989",
      "AcGenFeb1991",
      "AcGenFeb1996",
    ]);
  });

  it("merges in line-only period_labels at the end of the x_domain", () => {
    const bars = [{ period_label: "AcGenJan1989", value: 24 }];
    const line = [
      { period_label: "AcGenJan1989", value: 14.4 },
      { period_label: "AcGenFeb1991", value: 22.5 },
    ];
    const out = buildScales(bars, line);
    expect(out.x_domain).toEqual(["AcGenJan1989", "AcGenFeb1991"]);
  });

  it("floors left_y_max + right_y_max at 1 so a zero-only series renders a visible axis", () => {
    const out = buildScales(
      [{ period_label: "AcGenFeb1991", value: 0 }],
      [{ period_label: "AcGenFeb1991", value: 0 }],
    );
    expect(out.left_y_max).toBe(1);
    expect(out.right_y_max).toBe(1);
  });

  it("computes the max across all bar values, ignoring non-finite entries", () => {
    const out = buildScales(
      [
        { period_label: "a", value: 12 },
        { period_label: "b", value: NaN },
        { period_label: "c", value: 99 },
      ],
      [],
    );
    expect(out.left_y_max).toBe(99);
  });

  it("returns an empty x_domain for an empty input pair", () => {
    const out = buildScales([], []);
    expect(out.x_domain).toEqual([]);
    expect(out.left_y_max).toBe(1);
    expect(out.right_y_max).toBe(1);
  });
});

// --- pickLabelStride (PR-10 width-driven) ---------------------------------

describe("pickLabelStride", () => {
  // PR-10 of TODO/20260615-party-page-citizen-fixes-plan.md replaced
  // the prior viewport-cutoff rule with a width-driven formula:
  //   maxTicksThatFit = max(1, floor(chart_width / min_label_spacing_px))
  //   stride = max(1, ceil(year_count / maxTicksThatFit))
  // The default `min_label_spacing_px` is 48 (OWID time-axis spacing
  // for rotated 4-digit year labels at 10px font). The 3rd arg is
  // now the spacing override, not a mobile stride.

  it("returns stride 1 when every tick fits at the minimum 48px spacing", () => {
    // inner_w 1184 (the 1280-viewport bound after MARGIN_LEFT+RIGHT)
    // fits floor(1184/48) = 24 ticks. 18 years <= 24, so no thinning.
    expect(pickLabelStride(1184, 18)).toBe(1);
    expect(pickLabelStride(1184, 24)).toBe(1);
    expect(pickLabelStride(720, 12)).toBe(1);
  });

  it("thins to keep adjacent labels >= 48px apart on mobile", () => {
    // inner_w 224 (the 320-viewport bound after MARGIN_LEFT+RIGHT)
    // fits floor(224/48) = 4 ticks. 18 years -> ceil(18/4) = 5.
    expect(pickLabelStride(224, 18)).toBe(5);
    // 14 years on a 360-viewport drawable region (~264px) fits
    // floor(264/48) = 5 ticks; ceil(14/5) = 3.
    expect(pickLabelStride(264, 14)).toBe(3);
  });

  it("thins on desktop when year_count exceeds maxTicksThatFit", () => {
    // 30 years on a 1184 drawable region: floor(1184/48) = 24,
    // ceil(30/24) = 2; rendered count = ceil(30/2) = 15.
    expect(pickLabelStride(1184, 30)).toBe(2);
    // 100 years on a 1184 drawable region: ceil(100/24) = 5;
    // rendered count = ceil(100/5) = 20.
    expect(pickLabelStride(1184, 100)).toBe(5);
  });

  it("honours the min_label_spacing_px override (3rd arg)", () => {
    // Wider spacing -> fewer slots -> larger stride.
    expect(pickLabelStride(960, 20, 96)).toBe(2); // floor(960/96)=10, ceil(20/10)=2
    expect(pickLabelStride(960, 8, 96)).toBe(1); // 8 <= 10
  });

  it("returns 1 for an empty year list (defensive)", () => {
    expect(pickLabelStride(900, 0)).toBe(1);
    expect(pickLabelStride(0, 0)).toBe(1);
  });

  it("clamps a zero / negative spacing up to 1 so the formula stays defined", () => {
    // spacing clamped to 1 -> maxTicks = chart_width -> stride = 1
    // for any reasonable year_count <= chart_width.
    expect(pickLabelStride(360, 14, 0)).toBe(1);
    expect(pickLabelStride(360, 14, -8)).toBe(1);
  });

  it("guarantees the rendered tick count stays <= the visual ceiling at the spec viewports", () => {
    // Acceptance gate from the PR-10 brief: at chart_width = 320
    // (mobile, before margin trim) the renderer caps at 8 labels;
    // at chart_width = 1280 (desktop) it caps at 24. Test the
    // upper-bound math directly via the rendered-count formula
    // `ceil(year_count / stride)` for a stressed 60-year domain.
    const year_count = 60;
    // Mobile: inner_w 224 (320 - 96 margins). 60 years -> stride
    // ceil(60/4) = 15 -> rendered ceil(60/15) = 4 labels. Well
    // under the 8-label ceiling.
    const stride_mobile = pickLabelStride(224, year_count);
    expect(Math.ceil(year_count / stride_mobile)).toBeLessThanOrEqual(8);
    // Desktop: inner_w 1184. 60 years -> stride ceil(60/24) = 3
    // -> rendered ceil(60/3) = 20 labels. Under the 24 ceiling.
    const stride_desktop = pickLabelStride(1184, year_count);
    expect(Math.ceil(year_count / stride_desktop)).toBeLessThanOrEqual(24);
  });
});

// --- yearFromPeriodLabel --------------------------------------------------

describe("yearFromPeriodLabel", () => {
  it("extracts the 4-digit trailing year from an ECI event id", () => {
    expect(yearFromPeriodLabel("AcGenApr2021")).toBe("2021");
    expect(yearFromPeriodLabel("LsGenMay2024")).toBe("2024");
    expect(yearFromPeriodLabel("AcByeOct1971")).toBe("1971");
  });

  it("falls back to the raw input when no year suffix matches", () => {
    expect(yearFromPeriodLabel("not-an-event-id")).toBe("not-an-event-id");
    expect(yearFromPeriodLabel("")).toBe("");
  });
});

// --- yearNumberFromPeriodLabel + computeMethodologyBreakMarkers (PR-10) ---

describe("yearNumberFromPeriodLabel", () => {
  it("returns the trailing year as a number", () => {
    expect(yearNumberFromPeriodLabel("LsGenMay2024")).toBe(2024);
    expect(yearNumberFromPeriodLabel("LsGenFeb1962")).toBe(1962);
  });

  it("returns null when no trailing year suffix matches", () => {
    expect(yearNumberFromPeriodLabel("bogus")).toBeNull();
    expect(yearNumberFromPeriodLabel("")).toBeNull();
  });
});

describe("computeMethodologyBreakMarkers", () => {
  const lsDomainPrePost: readonly string[] = [
    "LsGenFeb1962",
    "LsGenFeb1967",
    "LsGenMar1971",
    "LsGenMar1977",
    "LsGenJan1980",
    "LsGenDec1984",
    "LsGenNov1989",
    "LsGenMay1991",
    "LsGenMay1996",
    "LsGenMar1998",
    "LsGenSep1999",
    "LsGenMay2004",
    "LsGenMay2009",
    "LsGenMay2014",
    "LsGenMay2019",
    "LsGenJun2024",
  ];
  const delim1967: MethodologyBreakRow = {
    methodology_version: "lspc-delim-1967",
    at_year: 1967,
    at_period_seq: 2,
    kind: "frame_change",
    note: "first break",
  };
  const delim1976: MethodologyBreakRow = {
    methodology_version: "lspc-delim-1976",
    at_year: 1977,
    at_period_seq: 3,
    kind: "frame_change",
    note: "second break",
  };

  it("returns 2 markers when both lspc-delim rows fall inside the LS chart's full domain", () => {
    const out = computeMethodologyBreakMarkers(lsDomainPrePost, [
      delim1967,
      delim1976,
    ]);
    expect(out).toHaveLength(2);
    expect(out[0]!.row.methodology_version).toBe("lspc-delim-1967");
    expect(out[0]!.reference_number).toBe(1);
    expect(out[1]!.row.methodology_version).toBe("lspc-delim-1976");
    expect(out[1]!.reference_number).toBe(2);
  });

  it("positions the 1967 marker between LsGenFeb1962 (idx 0) and LsGenFeb1967 (idx 1)", () => {
    const out = computeMethodologyBreakMarkers(lsDomainPrePost, [delim1967]);
    expect(out[0]!.idx_before).toBe(0);
    expect(out[0]!.idx_after).toBe(1);
  });

  it("positions the 1976 marker between LsGenMar1971 (idx 2) and LsGenMar1977 (idx 3)", () => {
    const out = computeMethodologyBreakMarkers(lsDomainPrePost, [delim1976]);
    expect(out[0]!.idx_before).toBe(2);
    expect(out[0]!.idx_after).toBe(3);
  });

  it("filters out markers whose at_year sits AT or BEFORE the first visible year (no bar to anchor 'before')", () => {
    // Chart starts at 1999; the 1967 + 1976 breaks have no pre-bar.
    const onlyPost1999: readonly string[] = [
      "LsGenSep1999",
      "LsGenMay2004",
      "LsGenMay2009",
      "LsGenMay2024",
    ];
    const out = computeMethodologyBreakMarkers(onlyPost1999, [
      delim1967,
      delim1976,
    ]);
    expect(out).toEqual([]);
  });

  it("filters out markers whose at_year sits AFTER the last visible year", () => {
    // Chart ends 1962-1971; 1977 break has no post-bar.
    const onlyPre1976: readonly string[] = [
      "LsGenFeb1962",
      "LsGenFeb1967",
      "LsGenMar1971",
    ];
    const out = computeMethodologyBreakMarkers(onlyPre1976, [
      delim1967,
      delim1976,
    ]);
    // Only the 1967 break survives (between 1962 and 1967).
    expect(out).toHaveLength(1);
    expect(out[0]!.row.methodology_version).toBe("lspc-delim-1967");
  });

  it("returns empty for an empty x_domain or empty breaks list", () => {
    expect(computeMethodologyBreakMarkers([], [delim1967])).toEqual([]);
    expect(computeMethodologyBreakMarkers(lsDomainPrePost, [])).toEqual([]);
  });

  it("assigns 1-based reference_numbers in input order (used as footnote labels)", () => {
    const out = computeMethodologyBreakMarkers(lsDomainPrePost, [
      delim1967,
      delim1976,
    ]);
    expect(out.map((m) => m.reference_number)).toEqual([1, 2]);
  });
});

// --- buildMethodologyTooltip (PR-2) ---------------------------------------

describe("buildMethodologyTooltip", () => {
  function markerFixture(
    overrides: Partial<MethodologyBreakRow> = {},
  ): MethodologyBreakMarker {
    return {
      idx_before: 0,
      idx_after: 1,
      reference_number: 1,
      row: {
        methodology_version: "lspc-delim-1967",
        at_year: 1967,
        at_period_seq: 2,
        kind: "frame_change",
        note: "Parliament constituency boundaries shifted from the 1951-Order delimitation to the 1962 Delimitation Commission output.",
        publisher_url: "https://eci.gov.in/files/file/14045-delimitation-order-1976/",
        supersedes_methodology_version: null,
        ...overrides,
      },
    };
  }

  it("uses a kind-dispatched verb in the title (frame_change -> 'Boundaries changed in YYYY')", () => {
    const out = buildMethodologyTooltip(markerFixture(), 100, 200);
    expect(out.title).toBe("Boundaries changed in 1967");
  });

  it("uses 'Definition changed in YYYY' for kind=definition_change", () => {
    const out = buildMethodologyTooltip(
      markerFixture({ kind: "definition_change", at_year: 2021 }),
      0,
      0,
    );
    expect(out.title).toBe("Definition changed in 2021");
  });

  it("uses 'Reclassified in YYYY' for kind=reclassification", () => {
    const out = buildMethodologyTooltip(
      markerFixture({ kind: "reclassification", at_year: 2015 }),
      0,
      0,
    );
    expect(out.title).toBe("Reclassified in 2015");
  });

  it("falls back to 'Methodology changed in YYYY' for an unknown kind", () => {
    const out = buildMethodologyTooltip(
      markerFixture({ kind: "unknown_kind" as MethodologyBreakRow["kind"] }),
      0,
      0,
    );
    expect(out.title).toBe("Methodology changed in 1967");
  });

  it("drops the methodology_version subtitle leak entirely", () => {
    const out = buildMethodologyTooltip(markerFixture(), 0, 0);
    expect(out).not.toHaveProperty("subtitle");
    // The lspc-delim-* identifier must not show up anywhere in the tooltip.
    const serialised = JSON.stringify(out);
    expect(serialised).not.toMatch(/lspc-delim/);
    expect(serialised).not.toMatch(/methodology_version/);
  });

  it("renders the note verbatim as the single body line (no 'why' label leak)", () => {
    const out = buildMethodologyTooltip(markerFixture(), 0, 0);
    expect(out.lines).toHaveLength(1);
    expect(out.lines[0]!.label).toBe("");
    expect(out.lines[0]!.value).toContain(
      "Parliament constituency boundaries",
    );
  });

  it("hangs a 'Source: <hostname>' hint when publisher_url parses", () => {
    const out = buildMethodologyTooltip(markerFixture(), 0, 0);
    expect(out.hint).toBe("Source: eci.gov.in");
  });

  it("omits the hint when publisher_url is null", () => {
    const out = buildMethodologyTooltip(
      markerFixture({ publisher_url: null }),
      0,
      0,
    );
    expect(out.hint).toBeUndefined();
  });

  it("omits the hint when publisher_url is unparseable", () => {
    const out = buildMethodologyTooltip(
      markerFixture({ publisher_url: "not-a-url" }),
      0,
      0,
    );
    expect(out.hint).toBeUndefined();
  });

  it("passes through the cursor coordinates verbatim", () => {
    const out = buildMethodologyTooltip(markerFixture(), 123, 456);
    expect(out.x).toBe(123);
    expect(out.y).toBe(456);
  });
});

// --- composeCompositeBarSegments (PR-10) ----------------------------------

describe("composeCompositeBarSegments", () => {
  it("returns the full bar as `contested` and a bottom band sized by the seat-conversion ratio", () => {
    // bar_y=20 + inner_h=100 -> bar_height=80. Half-conversion -> seats
    // band fills the bottom 40 pixels (80 * 0.5), rooted at y = inner_h
    // - 40 = 60.
    const seg = composeCompositeBarSegments(20, 100, 5, 10);
    expect(seg.contested_y).toBe(20);
    expect(seg.contested_h).toBe(80);
    expect(seg.seats_y).toBeCloseTo(60, 5);
    expect(seg.seats_h).toBeCloseTo(40, 5);
    expect(seg.seat_conversion_ratio).toBeCloseTo(0.5, 5);
  });

  it("collapses the seats band to height zero when seats_contested is zero (party did not contest)", () => {
    const seg = composeCompositeBarSegments(50, 200, 0, 0);
    expect(seg.contested_h).toBe(150);
    expect(seg.seats_h).toBe(0);
    expect(seg.seat_conversion_ratio).toBe(0);
  });

  it("clamps the seat-conversion ratio to 1 when seats_won exceeds seats_contested (defensive)", () => {
    // Won > contested is a data error. Defensive: ratio clamps to 1 so
    // the seats band can't escape the contested band.
    const seg = composeCompositeBarSegments(0, 100, 12, 10);
    expect(seg.seat_conversion_ratio).toBe(1);
    expect(seg.seats_h).toBeCloseTo(100, 5);
    expect(seg.seats_y).toBeCloseTo(0, 5);
  });

  it("clamps negative inputs to zero (defensive)", () => {
    const seg = composeCompositeBarSegments(10, 100, -5, 10);
    expect(seg.seat_conversion_ratio).toBe(0);
    expect(seg.seats_h).toBe(0);
  });

  it("collapses both bands to zero height when bar_y matches inner_h (vote-share is zero)", () => {
    const seg = composeCompositeBarSegments(100, 100, 5, 10);
    expect(seg.contested_h).toBe(0);
    expect(seg.seats_h).toBe(0);
  });
});

// --- buildCompositeTooltip (PR-10) ----------------------------------------

describe("buildCompositeTooltip", () => {
  const fmt = (n: number) => `${n.toFixed(1)}%`;

  it("titles with the year derived from period_label and carries the period_label as subtitle", () => {
    const out = buildCompositeTooltip(
      "general-2024",
      37.4,
      240,
      441,
      fmt,
      "#FF9933",
      100,
      200,
    );
    expect(out.title).toBe("2024");
    expect(out.subtitle).toBe("general-2024");
    expect(out.color).toBe("#FF9933");
    expect(out.x).toBe(100);
    expect(out.y).toBe(200);
  });

  it("emits three lines when seats_contested > 0: vote-share, seats-of-contested, seat conversion %", () => {
    const out = buildCompositeTooltip(
      "general-2024",
      37.4,
      240,
      441,
      fmt,
      "#FF9933",
      0,
      0,
    );
    expect(out.lines).toHaveLength(3);
    expect(out.lines[0]).toEqual({ label: "Vote share", value: "37.4%" });
    expect(out.lines[1]).toEqual({ label: "Seats", value: "240 of 441 contested" });
    expect(out.lines[2]?.label).toBe("Seat conversion");
    // 240/441 = 0.544..., -> 54.4% (1dp).
    expect(out.lines[2]?.value).toBe("54.4%");
  });

  it("omits the seat-conversion line and tags `(did not contest)` when seats_contested is zero", () => {
    const out = buildCompositeTooltip(
      "general-1999",
      0,
      0,
      0,
      fmt,
      "#FF9933",
      0,
      0,
    );
    expect(out.lines).toHaveLength(2);
    expect(out.lines[0]).toEqual({ label: "Vote share", value: "0.0%" });
    expect(out.lines[1]).toEqual({ label: "Seats", value: "0 won (did not contest)" });
  });

  it("renders the conversion ratio with one decimal place (5/10 = 50.0%)", () => {
    const out = buildCompositeTooltip(
      "general-2014",
      20.0,
      5,
      10,
      fmt,
      "#138808",
      0,
      0,
    );
    expect(out.lines[2]).toEqual({ label: "Seat conversion", value: "50.0%" });
  });
});

// --- D6 (PR-4): redundant `0.0%` baseline label is suppressed ------------
//
// Plan-doc TODO/20260615-party-page-citizen-fixes-plan.md row PR-4.
// The x-axis IS the zero line; rendering "0.0%" / "0" at the chart
// baseline is redundant chrome that visually collides with the year
// ticks. The structural fix wraps both the LEFT_TICKS and the
// RIGHT_TICKS label `<text>` nodes in a `{#if t > 0}` guard. The
// gridline `<line>` element at `t === 0` MUST still render so the
// chart baseline remains anchored.
//
// Because `@testing-library/svelte` is NOT installed in this repo,
// the in-browser behaviour is verified via the CLAUDE.md section 13
// smoke + the e2e spec; this vitest pin asserts the structural
// invariant directly on the .svelte source so a future refactor that
// drops the guard fails CI.

describe("D6 PR-4: y-axis tick labels suppress the t === 0 baseline label", () => {
  const SVELTE_SRC = readFileSync(
    fileURLToPath(new URL("./DualAxisBarLine.svelte", import.meta.url)),
    "utf8",
  );

  it("wraps the LEFT_TICKS <text> label node in a {#if t > 0} guard", () => {
    // The each-block at LEFT_TICKS must contain a `{#if t > 0}` guard
    // that wraps the `<text>` node emitting `bar_format(t)`.
    const each_start = SVELTE_SRC.indexOf("{#each LEFT_TICKS as t");
    expect(each_start, "LEFT_TICKS each-block present").toBeGreaterThan(-1);
    const each_end = SVELTE_SRC.indexOf("{/each}", each_start);
    expect(each_end, "LEFT_TICKS each-block closes").toBeGreaterThan(each_start);
    const block = SVELTE_SRC.slice(each_start, each_end);
    expect(block, "LEFT_TICKS carries the {#if t > 0} guard").toContain(
      "{#if t > 0}",
    );
    expect(block, "LEFT_TICKS guard wraps the bar_format(t) label").toMatch(
      /\{#if t > 0\}[\s\S]*?\{bar_format\(t\)\}[\s\S]*?\{\/if\}/,
    );
  });

  it("wraps the RIGHT_TICKS <text> label node in a {#if t > 0} guard", () => {
    const each_start = SVELTE_SRC.indexOf("{#each RIGHT_TICKS as t");
    expect(each_start, "RIGHT_TICKS each-block present").toBeGreaterThan(-1);
    const each_end = SVELTE_SRC.indexOf("{/each}", each_start);
    expect(each_end, "RIGHT_TICKS each-block closes").toBeGreaterThan(each_start);
    const block = SVELTE_SRC.slice(each_start, each_end);
    expect(block, "RIGHT_TICKS carries the {#if t > 0} guard").toContain(
      "{#if t > 0}",
    );
    expect(block, "RIGHT_TICKS guard wraps the line_format(t) label").toMatch(
      /\{#if t > 0\}[\s\S]*?\{line_format\(t\)\}[\s\S]*?\{\/if\}/,
    );
  });

  it("keeps the LEFT_TICKS gridline <line> outside the guard so the baseline still renders at t === 0", () => {
    const each_start = SVELTE_SRC.indexOf("{#each LEFT_TICKS as t");
    const each_end = SVELTE_SRC.indexOf("{/each}", each_start);
    const block = SVELTE_SRC.slice(each_start, each_end);
    // The `<line ... y1={left_y_scale(t)} ...>` node must appear in
    // the each-block BEFORE the `{#if t > 0}` guard so that t === 0
    // still emits the gridline (the chart baseline).
    const line_idx = block.indexOf("<line");
    const guard_idx = block.indexOf("{#if t > 0}");
    expect(line_idx, "gridline <line> present").toBeGreaterThan(-1);
    expect(guard_idx, "label guard present").toBeGreaterThan(-1);
    expect(
      line_idx,
      "gridline appears before the label guard (so t === 0 still renders the gridline)",
    ).toBeLessThan(guard_idx);
  });
});
