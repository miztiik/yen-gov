// PR-4 vitest for `DualAxisBarLine.svelte`.
//
// Per project doctrine (`@testing-library/svelte` is NOT installed):
// pure helpers are extracted to the `<script module>` block so vitest
// can pin the contract without mounting Svelte. The Svelte template
// is covered by the e2e spec (`frontend/e2e/party-detail.spec.ts`)
// and the CLAUDE.md section 13 in-browser smoke.

import { describe, expect, it } from "vitest";
import {
  buildMethodologyTooltip,
  buildScales,
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

// --- pickLabelStride ------------------------------------------------------

describe("pickLabelStride", () => {
  it("returns the mobile stride when the viewport is < 640px", () => {
    expect(pickLabelStride(360, 14, 4)).toBe(4);
    expect(pickLabelStride(639, 6, 3)).toBe(3);
  });

  it("returns stride 1 above 640px when the year count is <= 12", () => {
    expect(pickLabelStride(900, 5, 4)).toBe(1);
    expect(pickLabelStride(900, 12, 4)).toBe(1);
  });

  it("returns stride 2 above 640px when the year count is > 12 (label density rule)", () => {
    expect(pickLabelStride(900, 13, 4)).toBe(2);
    expect(pickLabelStride(1280, 20, 4)).toBe(2);
  });

  it("returns 1 for an empty year list (defensive)", () => {
    expect(pickLabelStride(900, 0, 4)).toBe(1);
  });

  it("clamps a zero / negative mobile_stride up to 1", () => {
    expect(pickLabelStride(360, 14, 0)).toBe(1);
    expect(pickLabelStride(360, 14, -3)).toBe(1);
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
