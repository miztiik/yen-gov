import { describe, it, expect } from "vitest";
import {
  uniqueTimes,
  rollupByEntity,
  facetsByEntity,
  hueForDirection,
  normalise,
  sequentialSwatch,
  fillForValue,
  formatValue,
  formatCompact,
  type IndicatorRow,
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
