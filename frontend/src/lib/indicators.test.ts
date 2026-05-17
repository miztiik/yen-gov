import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import {
  uniqueTimes,
  rollupByEntity,
  seriesByEntity,
  facetsByEntity,
  hueForDirection,
  normalise,
  sequentialSwatch,
  fillForValue,
  formatValue,
  formatCompact,
  cadenceWord,
  buildTemporalCaption,
  deriveTemporalRange,
  type IndicatorRow,
  type IndicatorMeta,
  type TemporalRange,
} from "./indicators";

const ROWS: IndicatorRow[] = [
  { entity_id: "S22", time: "2019", value: 11190, facet: "coal_power_plant" },
  { entity_id: "S22", time: "2019", value: 1778, facet: "hydro_power_plant" },
  { entity_id: "S11", time: "2019", value: 1856, facet: "hydro_power_plant" },
  { entity_id: "S11", time: "2019", value: 524, facet: "natural_gas_power_plant" },
  { entity_id: "S11", time: "2018", value: 500, facet: "hydro_power_plant" },
  { entity_id: "S03", time: "2019", value: null, facet: null },
];

describe("uniqueTimes", () => {
  it("returns sorted unique times", () => {
    expect(uniqueTimes(ROWS)).toEqual(["2018", "2019"]);
  });
  it("handles empty input", () => {
    expect(uniqueTimes([])).toEqual([]);
  });
});

describe("rollupByEntity", () => {
  it("sums values per entity at the given time, skipping nulls", () => {
    const m = rollupByEntity(ROWS, "2019");
    expect(m.get("S22")).toBe(11190 + 1778);
    expect(m.get("S11")).toBe(1856 + 524);
    expect(m.has("S03")).toBe(false); // only null row
  });
  it("filters by time", () => {
    const m = rollupByEntity(ROWS, "2018");
    expect([...m.keys()]).toEqual(["S11"]);
    expect(m.get("S11")).toBe(500);
  });
});

describe("facetsByEntity", () => {
  it("returns facet breakdown sorted desc by value", () => {
    const m = facetsByEntity(ROWS, "2019");
    const tn = m.get("S22")!;
    expect(tn[0].facet).toBe("coal_power_plant");
    expect(tn[0].value).toBe(11190);
    expect(tn[1].facet).toBe("hydro_power_plant");
  });
});

describe("seriesByEntity", () => {
  it("returns per-entity time-series sorted ascending in time", () => {
    const m = seriesByEntity(ROWS);
    const s11 = m.get("S11")!;
    expect(s11.map(p => p.time)).toEqual(["2018", "2019"]);
    expect(s11[0].value).toBe(500);
    expect(s11[1].value).toBe(1856 + 524);
    const s22 = m.get("S22")!;
    expect(s22).toEqual([{ time: "2019", value: 11190 + 1778 }]);
  });
  it("omits entities whose only rows are null", () => {
    const m = seriesByEntity(ROWS);
    expect(m.has("S03")).toBe(false);
  });
});

describe("hueForDirection", () => {
  it("picks distinct hues per direction", () => {
    const a = hueForDirection("higher_is_better");
    const b = hueForDirection("lower_is_better");
    const c = hueForDirection("neutral");
    expect(a).not.toBe(b);
    expect(b).not.toBe(c);
    expect(a).not.toBe(c);
  });
});

describe("normalise", () => {
  it("linear-scales values into 0..1", () => {
    expect(normalise(0, 0, 10)).toBe(0);
    expect(normalise(5, 0, 10)).toBe(0.5);
    expect(normalise(10, 0, 10)).toBe(1);
  });
  it("handles degenerate domain by returning 0.5", () => {
    expect(normalise(5, 5, 5)).toBe(0.5);
  });
  it("returns null for null input", () => {
    expect(normalise(null, 0, 10)).toBe(null);
  });
  it("log scale for positive values", () => {
    const t = normalise(10, 1, 100, "log");
    expect(t).toBeCloseTo(0.5, 5);
  });
  it("falls back to linear when log would be undefined", () => {
    const t = normalise(5, 0, 10, "log");
    expect(t).toBe(0.5);
  });
});

describe("sequentialSwatch", () => {
  it("returns a hex color", () => {
    expect(sequentialSwatch(0, 160)).toMatch(/^#[0-9a-f]{6}$/);
    expect(sequentialSwatch(1, 160)).toMatch(/^#[0-9a-f]{6}$/);
  });
  it("differs at t=0 vs t=1", () => {
    expect(sequentialSwatch(0, 160)).not.toBe(sequentialSwatch(1, 160));
  });
  it("clamps t outside 0..1", () => {
    expect(sequentialSwatch(-1, 160)).toBe(sequentialSwatch(0, 160));
    expect(sequentialSwatch(2, 160)).toBe(sequentialSwatch(1, 160));
  });
});

describe("fillForValue", () => {
  it("returns fallback for null", () => {
    expect(fillForValue(null, 0, 10, "neutral")).toBe("#e2e8f0");
  });
  it("returns hex for valid", () => {
    expect(fillForValue(5, 0, 10, "neutral")).toMatch(/^#[0-9a-f]{6}$/);
  });
});

describe("formatCompact", () => {
  it("formats by magnitude", () => {
    expect(formatCompact(0.5)).toBe("0.50");
    expect(formatCompact(42)).toBe("42");
    expect(formatCompact(1500)).toBe("1.5k");
    expect(formatCompact(12_345_678)).toBe("12.3M");
    expect(formatCompact(3.4e9)).toBe("3.4B");
  });
});

describe("formatValue", () => {
  it("handles count with unit", () => {
    expect(formatValue(11190, { value_kind: "count", unit: "MW" })).toContain("MW");
  });
  it("handles share stored as fraction", () => {
    expect(formatValue(0.625, { value_kind: "share", unit: "share" })).toBe("62.5%");
  });
  it("handles share stored as percentage", () => {
    expect(formatValue(62.5, { value_kind: "share", unit: "%" })).toBe("62.5%");
  });
  it("handles null", () => {
    expect(formatValue(null, { value_kind: "raw", unit: "MW" })).toBe("—");
  });
  it("handles raw with unit", () => {
    const s = formatValue(11190, { value_kind: "raw", unit: "MW" });
    expect(s).toContain("MW");
    expect(s).toContain("11.2k");
  });
});

// -- Temporal range + caption ------------------------------------------------

describe("cadenceWord", () => {
  it("prefers cadence over time_grain", () => {
    expect(cadenceWord("annual_fy", "year")).toBe("annual (fiscal year)");
    expect(cadenceWord("decennial", "year")).toBe("every 10 years");
    expect(cadenceWord("ad_hoc", "year")).toBe("irregular updates");
  });
  it("falls back to time_grain when cadence absent", () => {
    expect(cadenceWord(undefined, "year")).toBe("annual");
    expect(cadenceWord(undefined, "fiscal_year")).toBe("annual (fiscal year)");
    expect(cadenceWord(undefined, "month")).toBe("monthly");
    expect(cadenceWord(undefined, "quarter")).toBe("quarterly");
  });
  it("returns empty string for date snapshots with no cadence", () => {
    expect(cadenceWord(undefined, "date")).toBe("");
  });
});

describe("buildTemporalCaption", () => {
  const baseMulti: TemporalRange = {
    min_time: "2018",
    max_time: "2022",
    min_period_label: "2018",
    max_period_label: "2022",
    time_grain: "year",
  };
  it("multi-period uses arrow + middle-dot + cadence word", () => {
    expect(buildTemporalCaption(baseMulti)).toBe("2018 \u2192 2022 \u00b7 annual");
  });
  it("single-period collapses to 'As of ...'", () => {
    expect(
      buildTemporalCaption({
        ...baseMulti,
        min_time: "2024",
        max_time: "2024",
        min_period_label: "2024",
        max_period_label: "2024",
      }),
    ).toBe("As of 2024 \u00b7 annual");
  });
  it("decennial cadence uses 'every 10 years'", () => {
    expect(
      buildTemporalCaption({
        ...baseMulti,
        min_time: "1991",
        max_time: "2011",
        min_period_label: "1991",
        max_period_label: "2011",
        cadence: "decennial",
      }),
    ).toBe("1991 \u2192 2011 \u00b7 every 10 years");
  });
  it("ad_hoc cadence uses 'irregular updates'", () => {
    expect(
      buildTemporalCaption({
        ...baseMulti,
        cadence: "ad_hoc",
      }),
    ).toBe("2018 \u2192 2022 \u00b7 irregular updates");
  });
  it("FY publisher labels round-trip verbatim", () => {
    expect(
      buildTemporalCaption({
        min_time: "2018-04",
        max_time: "2020-04",
        min_period_label: "FY 2018-19",
        max_period_label: "FY 2020-21",
        time_grain: "fiscal_year",
      }),
    ).toBe("FY 2018-19 \u2192 FY 2020-21 \u00b7 annual (fiscal year)");
  });
  it("snapshot date with no cadence drops the cadence segment", () => {
    expect(
      buildTemporalCaption({
        min_time: "2026-05-14",
        max_time: "2026-05-14",
        min_period_label: "as on 14 May 2026",
        max_period_label: "as on 14 May 2026",
        time_grain: "date",
      }),
    ).toBe("As of as on 14 May 2026");
  });
});

// Shared-fixture parity: same cases drive backend pytest
// (`test_derive_temporal_range_shared_fixture`) so any rule drift between
// the Python derivation and the TS mirror fails BOTH suites. Per
// TODO/20260517-coverage-temporal-range-plan.md Phase #3.
interface FixtureCase {
  name: string;
  indicator: Pick<IndicatorMeta, "id" | "time_grain" | "cadence">;
  rows: IndicatorRow[];
  expected: TemporalRange | null;
}
interface FixtureFile { cases: FixtureCase[]; }

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const FIXTURES_PATH = resolve(
  __dirname,
  "../../../datasets/_test/temporal-range-fixtures/cases.json",
);
const FIXTURES: FixtureFile = JSON.parse(readFileSync(FIXTURES_PATH, "utf-8"));

describe("deriveTemporalRange (shared-fixture parity with Python)", () => {
  for (const fc of FIXTURES.cases) {
    it(fc.name, () => {
      const got = deriveTemporalRange(fc.rows, fc.indicator);
      expect(got).toEqual(fc.expected);
    });
  }
});

