// StackedTrendV2 helpers — unit tests (Phase 2.1).
//
// Per TODO/20260518-frontend-charting-modernisation-plan.md Phase 2.1:
//
// > Unit tests cover percent and absolute modes, zero totals,
// > `__OTHER__`, missing values, and `not_applicable`.
//
// One describe-block per helper. Real fixtures, no mocks (Holy Law #7).
// The fixtures live inline rather than under `__fixtures__/` because each
// case is small and self-contained — the named fixture would be re-read
// at every assertion site for no clarity gain.

import { describe, expect, it } from "vitest";

import {
  DEFAULT_LABEL_THRESHOLD_PCT,
  MODE_LABELS,
  barTotal,
  isLabelEligible,
  maxBarTotal,
  readoutRows,
  resolveInitialMode,
  segmentSharePct,
  segmentVisualHeightPct,
  visibleCategoryIds,
} from "./helpers";
import type {
  StackedTrendV2Bar,
  StackedTrendV2Category,
  StackedTrendV2Model,
  StackedTrendV2Segment,
} from "./types";
import { OTHER_CATEGORY_ID_V2 } from "./types";

// ---------- fixture factories -----------------------------------------------

function seg(
  category_id: string,
  value: number | null,
  availability: StackedTrendV2Segment["availability"] = "present",
  availability_label?: string,
): StackedTrendV2Segment {
  return availability_label
    ? { category_id, value, availability, availability_label }
    : { category_id, value, availability };
}

function bar(
  period_id: string,
  segments: StackedTrendV2Segment[],
  opts?: { total?: number; order?: number },
): StackedTrendV2Bar {
  return {
    period_id,
    period_label: period_id,
    order: opts?.order ?? 0,
    segments,
    ...(opts?.total != null ? { total: opts.total } : {}),
  };
}

function cat(
  id: string,
  label: string,
  order?: number,
): StackedTrendV2Category {
  return order != null ? { id, label, order } : { id, label };
}

function model(
  categories: StackedTrendV2Category[],
  bars: StackedTrendV2Bar[],
): StackedTrendV2Model {
  return {
    schema_version: "2.0",
    unit: { id: "MW", label: "MW", value_kind: "count" },
    x_axis_label: "year",
    bar_sort: "by_order_ascending",
    categories,
    bars,
    sources: [],
    dimension: "fuel_type",
    default_mode: "percent",
  };
}

// ---------- barTotal --------------------------------------------------------

describe("barTotal", () => {
  it("sums every present non-null segment value", () => {
    const b = bar("2024", [
      seg("coal", 100),
      seg("gas", 30),
      seg("solar", 20),
    ]);
    expect(barTotal(b)).toBe(150);
  });

  it("ignores missing segments", () => {
    const b = bar("2024", [
      seg("coal", 100),
      seg("gas", 30, "missing"),
      seg("solar", 20),
    ]);
    expect(barTotal(b)).toBe(120);
  });

  it("ignores not_applicable segments", () => {
    const b = bar("2024", [
      seg("coal", 100),
      seg("nuclear", 50, "not_applicable"),
    ]);
    expect(barTotal(b)).toBe(100);
  });

  it("ignores present-but-null segments", () => {
    const b = bar("2024", [
      seg("coal", 100),
      seg("gas", null),
    ]);
    expect(barTotal(b)).toBe(100);
  });

  it("returns 0 when every segment is missing or null", () => {
    const b = bar("2024", [
      seg("coal", null),
      seg("gas", null, "missing"),
      seg("solar", null, "not_applicable"),
    ]);
    expect(barTotal(b)).toBe(0);
  });

  it("includes the __OTHER__ collapsed bucket like any other present segment", () => {
    const b = bar("2024", [
      seg("coal", 100),
      seg(OTHER_CATEGORY_ID_V2, 20),
    ]);
    expect(barTotal(b)).toBe(120);
  });

  it("uses bar.total when set, even if it differs from the segment sum", () => {
    // Adapter has pre-pinned a denominator that includes un-classified
    // residue not represented as a segment.
    const b = bar("2024", [seg("coal", 100), seg("gas", 30)], { total: 200 });
    expect(barTotal(b)).toBe(200);
  });

  it("respects bar.total === 0 as an explicit zero (not a fallback signal)", () => {
    const b = bar("2024", [seg("coal", 100)], { total: 0 });
    expect(barTotal(b)).toBe(0);
  });
});

// ---------- maxBarTotal -----------------------------------------------------

describe("maxBarTotal", () => {
  it("returns the largest bar total across the series", () => {
    const bars = [
      bar("2022", [seg("coal", 100)]),
      bar("2023", [seg("coal", 200)]),
      bar("2024", [seg("coal", 150)]),
    ];
    expect(maxBarTotal(bars)).toBe(200);
  });

  it("floors at 1 when every bar is zero", () => {
    const bars = [
      bar("2022", [seg("coal", 0)]),
      bar("2023", [seg("gas", null, "missing")]),
    ];
    expect(maxBarTotal(bars)).toBe(1);
  });

  it("returns 1 for an empty series (defensive)", () => {
    expect(maxBarTotal([])).toBe(1);
  });

  it("uses bar.total override when set", () => {
    const bars = [
      bar("2022", [seg("coal", 100)], { total: 500 }),
      bar("2023", [seg("coal", 200)]),
    ];
    expect(maxBarTotal(bars)).toBe(500);
  });
});

// ---------- segmentSharePct -------------------------------------------------

describe("segmentSharePct", () => {
  it("returns the percent share of a present segment", () => {
    expect(segmentSharePct(seg("coal", 25), 100)).toBe(25);
  });

  it("returns a fractional share (not rounded)", () => {
    expect(segmentSharePct(seg("coal", 33), 100)).toBe(33);
    expect(segmentSharePct(seg("coal", 1), 3)).toBeCloseTo(33.333, 2);
  });

  it("returns 0 for missing segments", () => {
    expect(segmentSharePct(seg("gas", 30, "missing"), 100)).toBe(0);
  });

  it("returns 0 for not_applicable segments", () => {
    expect(segmentSharePct(seg("nuclear", 50, "not_applicable"), 100)).toBe(0);
  });

  it("returns 0 for null-valued segments", () => {
    expect(segmentSharePct(seg("gas", null), 100)).toBe(0);
  });

  it("returns 0 when total is 0 (avoid divide-by-zero)", () => {
    expect(segmentSharePct(seg("coal", 100), 0)).toBe(0);
  });

  it("returns 0 when total is negative (defensive)", () => {
    expect(segmentSharePct(seg("coal", 100), -1)).toBe(0);
  });
});

// ---------- segmentVisualHeightPct ------------------------------------------

describe("segmentVisualHeightPct", () => {
  describe("percent mode", () => {
    it("returns segment share of bar total", () => {
      // 25 / 100 of bar = 25% of canvas (because bars are 100% tall)
      expect(
        segmentVisualHeightPct(seg("coal", 25), 100, 200, "percent"),
      ).toBe(25);
    });

    it("returns 0 when bar total is 0", () => {
      expect(
        segmentVisualHeightPct(seg("coal", 25), 0, 200, "percent"),
      ).toBe(0);
    });

    it("returns 0 for missing segments", () => {
      expect(
        segmentVisualHeightPct(seg("gas", 30, "missing"), 100, 200, "percent"),
      ).toBe(0);
    });

    it("returns 0 for not_applicable segments", () => {
      expect(
        segmentVisualHeightPct(
          seg("nuclear", 50, "not_applicable"),
          100,
          200,
          "percent",
        ),
      ).toBe(0);
    });
  });

  describe("absolute mode", () => {
    it("returns segment value as share of max total", () => {
      // 25 / 200 of canvas = 12.5%
      expect(
        segmentVisualHeightPct(seg("coal", 25), 100, 200, "absolute"),
      ).toBe(12.5);
    });

    it("scales a tall bar segment correctly", () => {
      // bar = 200, max = 200 → bar fills canvas; segment = 100 = 50%
      expect(
        segmentVisualHeightPct(seg("coal", 100), 200, 200, "absolute"),
      ).toBe(50);
    });

    it("returns 0 when max total is 0", () => {
      expect(
        segmentVisualHeightPct(seg("coal", 25), 100, 0, "absolute"),
      ).toBe(0);
    });

    it("returns 0 for null segment value", () => {
      expect(
        segmentVisualHeightPct(seg("coal", null), 100, 200, "absolute"),
      ).toBe(0);
    });
  });
});

// ---------- visibleCategoryIds ----------------------------------------------

describe("visibleCategoryIds", () => {
  it("returns categories that have at least one present non-zero value", () => {
    const m = model(
      [cat("coal", "Coal"), cat("gas", "Gas"), cat("solar", "Solar")],
      [
        bar("2022", [seg("coal", 100), seg("gas", 30), seg("solar", 0)]),
        bar("2023", [seg("coal", 100), seg("gas", 0), seg("solar", 50)]),
      ],
    );
    expect(visibleCategoryIds(m)).toEqual(["coal", "gas", "solar"]);
  });

  it("excludes a category that is always zero", () => {
    const m = model(
      [cat("coal", "Coal"), cat("nuclear", "Nuclear")],
      [
        bar("2022", [seg("coal", 100), seg("nuclear", 0)]),
        bar("2023", [seg("coal", 200), seg("nuclear", 0)]),
      ],
    );
    expect(visibleCategoryIds(m)).toEqual(["coal"]);
  });

  it("excludes a category that is always missing", () => {
    const m = model(
      [cat("coal", "Coal"), cat("hydro", "Hydro")],
      [
        bar("2022", [seg("coal", 100), seg("hydro", 50, "missing")]),
        bar("2023", [seg("coal", 200), seg("hydro", null, "missing")]),
      ],
    );
    expect(visibleCategoryIds(m)).toEqual(["coal"]);
  });

  it("excludes a category that is always not_applicable", () => {
    const m = model(
      [cat("coal", "Coal"), cat("nuclear", "Nuclear")],
      [
        bar("2022", [seg("coal", 100), seg("nuclear", null, "not_applicable")]),
      ],
    );
    expect(visibleCategoryIds(m)).toEqual(["coal"]);
  });

  it("preserves model.categories order", () => {
    const m = model(
      [cat("solar", "Solar"), cat("coal", "Coal"), cat("gas", "Gas")],
      [bar("2022", [seg("coal", 100), seg("gas", 30), seg("solar", 50)])],
    );
    // Even though the segments are in coal/gas/solar order, the helper
    // returns the model.categories order.
    expect(visibleCategoryIds(m)).toEqual(["solar", "coal", "gas"]);
  });

  it("returns an empty array when every category is invisible", () => {
    const m = model(
      [cat("coal", "Coal"), cat("gas", "Gas")],
      [bar("2022", [seg("coal", 0), seg("gas", null, "missing")])],
    );
    expect(visibleCategoryIds(m)).toEqual([]);
  });
});

// ---------- isLabelEligible -------------------------------------------------

describe("isLabelEligible", () => {
  it("is eligible at exactly the default threshold", () => {
    expect(isLabelEligible(DEFAULT_LABEL_THRESHOLD_PCT)).toBe(true);
  });

  it("is eligible above the default threshold", () => {
    expect(isLabelEligible(50)).toBe(true);
  });

  it("is not eligible below the default threshold", () => {
    expect(isLabelEligible(DEFAULT_LABEL_THRESHOLD_PCT - 0.01)).toBe(false);
  });

  it("honours a route-specific lifted threshold (dense mobile)", () => {
    expect(isLabelEligible(10, 12)).toBe(false);
    expect(isLabelEligible(12, 12)).toBe(true);
  });

  it("returns false for a negative visual height", () => {
    expect(isLabelEligible(-1)).toBe(false);
  });
});

// ---------- readoutRows -----------------------------------------------------

describe("readoutRows", () => {
  const categories = [
    cat("coal", "Coal", 0),
    cat("gas", "Gas", 1),
    cat("solar", "Solar", 2),
    cat("hydro", "Hydro", 3),
    cat(OTHER_CATEGORY_ID_V2, "Other", 99),
  ];

  it("returns one row per segment, joined to the category label", () => {
    const b = bar("2024", [
      seg("coal", 100),
      seg("gas", 30),
      seg("solar", 20),
    ]);
    const rows = readoutRows(b, categories);
    expect(rows.map((r) => r.category_id)).toEqual(["coal", "gas", "solar"]);
    expect(rows.find((r) => r.category_id === "coal")?.label).toBe("Coal");
  });

  it("sorts rows by share descending", () => {
    const b = bar("2024", [
      seg("solar", 20),
      seg("coal", 100),
      seg("gas", 30),
    ]);
    const rows = readoutRows(b, categories);
    expect(rows.map((r) => r.category_id)).toEqual(["coal", "gas", "solar"]);
  });

  it("computes share_pct as percent (0–100) using bar total", () => {
    const b = bar("2024", [
      seg("coal", 100),
      seg("gas", 50),
      seg("solar", 50),
    ]);
    // total = 200
    const rows = readoutRows(b, categories);
    expect(rows.find((r) => r.category_id === "coal")?.share_pct).toBe(50);
    expect(rows.find((r) => r.category_id === "gas")?.share_pct).toBe(25);
  });

  it("sinks missing / not_applicable rows to the bottom with share_pct 0", () => {
    const b = bar("2024", [
      seg("coal", 100),
      seg("gas", 30, "missing", "No data this year"),
      seg("solar", null, "not_applicable"),
    ]);
    const rows = readoutRows(b, categories);
    expect(rows.map((r) => r.category_id)).toEqual(["coal", "gas", "solar"]);
    expect(rows[1].share_pct).toBe(0);
    expect(rows[1].availability).toBe("missing");
    expect(rows[1].availability_label).toBe("No data this year");
    expect(rows[1].value).toBeNull();
    expect(rows[2].share_pct).toBe(0);
    expect(rows[2].availability).toBe("not_applicable");
  });

  it("breaks ties between equal-share rows by category order, then id", () => {
    const b = bar("2024", [
      seg("solar", 50),
      seg("gas", 50),
      seg("coal", 50),
    ]);
    // all 33% — tie-break uses category.order (coal=0, gas=1, solar=2)
    const rows = readoutRows(b, categories);
    expect(rows.map((r) => r.category_id)).toEqual(["coal", "gas", "solar"]);
  });

  it("skips segments referencing an unknown category id", () => {
    const b = bar("2024", [
      seg("coal", 100),
      seg("ghost", 50),
    ]);
    const rows = readoutRows(b, categories);
    expect(rows.map((r) => r.category_id)).toEqual(["coal"]);
  });

  it("handles the __OTHER__ collapsed bucket like any present segment", () => {
    const b = bar("2024", [
      seg("coal", 100),
      seg(OTHER_CATEGORY_ID_V2, 25),
    ]);
    const rows = readoutRows(b, categories);
    expect(rows.map((r) => r.category_id)).toEqual([
      "coal",
      OTHER_CATEGORY_ID_V2,
    ]);
    expect(
      rows.find((r) => r.category_id === OTHER_CATEGORY_ID_V2)?.share_pct,
    ).toBeCloseTo(20, 5);
  });

  it("returns an empty array when bar has no segments", () => {
    const b = bar("2024", []);
    expect(readoutRows(b, categories)).toEqual([]);
  });

  it("uses bar.total override when computing shares", () => {
    // bar.total = 400 but segments only sum to 150 → coal share = 25%
    const b = bar("2024", [seg("coal", 100), seg("gas", 50)], { total: 400 });
    const rows = readoutRows(b, categories);
    expect(rows.find((r) => r.category_id === "coal")?.share_pct).toBe(25);
    expect(rows.find((r) => r.category_id === "gas")?.share_pct).toBeCloseTo(
      12.5,
      5,
    );
  });
});

describe("MODE_LABELS", () => {
  it("maps every mode to a citizen-readable label", () => {
    expect(MODE_LABELS.percent).toBe("Share");
    expect(MODE_LABELS.absolute).toBe("Total");
  });

  it("covers every member of the mode union (compile-time exhaustiveness)", () => {
    // If a future PR adds a third mode token, this assertion forces the
    // dictionary to grow alongside it. Iterating Object.keys is the
    // cheapest run-time stand-in for an exhaustive `satisfies` check on
    // the dictionary value type.
    const keys = Object.keys(MODE_LABELS).sort();
    expect(keys).toEqual(["absolute", "percent"]);
  });
});

describe("resolveInitialMode", () => {
  it("returns the override when one is provided", () => {
    expect(resolveInitialMode("absolute", "percent")).toBe("absolute");
    expect(resolveInitialMode("percent", "absolute")).toBe("percent");
  });

  it("falls back to the model default when no override is given", () => {
    expect(resolveInitialMode(undefined, "percent")).toBe("percent");
    expect(resolveInitialMode(undefined, "absolute")).toBe("absolute");
  });

  it("does not coerce or normalise — the union types pre-constrain the inputs", () => {
    // Sanity: no defensive lowercasing, no falsy coercion. The function
    // exists to make the precedence rule unit-testable, not to validate.
    expect(resolveInitialMode("percent", "absolute")).toBe("percent");
  });
});
