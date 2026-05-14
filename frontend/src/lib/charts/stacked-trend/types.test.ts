import { describe, it, expect } from "vitest";
import {
  StackedTrendModel,
  StackedTrendSegment,
  OTHER_CATEGORY_ID,
  OTHER_CATEGORY_FILL,
} from "./types";

const minimalValid = {
  unit: { id: "mw", label: "MW", value_kind: "raw" as const },
  x_axis_label: "State",
  categories: [
    { id: "coal", label: "Coal" },
    { id: "hydro", label: "Hydro" },
  ],
  bars: [
    {
      period_id: "S22",
      period_label: "TN",
      order: 0,
      segments: [
        { category_id: "coal", value: 5000 },
        { category_id: "hydro", value: 2000 },
      ],
    },
  ],
  sources: [
    { url: "https://cea.nic.in/x", fetched_at: "2026-05-13T21:54:16Z" },
  ],
  dimension: "power_source",
};

describe("StackedTrendModel zod schema", () => {
  it("accepts a minimal valid model and applies defaults", () => {
    const parsed = StackedTrendModel.parse(minimalValid);
    expect(parsed.bar_sort).toBe("by_order_ascending");
    expect(parsed.default_mode).toBe("percent");
    expect(parsed.bars[0].segments[0].availability).toBe("present");
  });

  it("rejects empty bars", () => {
    expect(() => StackedTrendModel.parse({ ...minimalValid, bars: [] })).toThrow();
  });

  it("rejects empty categories", () => {
    expect(() => StackedTrendModel.parse({ ...minimalValid, categories: [] })).toThrow();
  });

  it("rejects bad hex on category fill", () => {
    expect(() =>
      StackedTrendModel.parse({
        ...minimalValid,
        categories: [{ id: "x", label: "X", fill: "not-a-hex" }],
      }),
    ).toThrow();
  });

  it("accepts 6-digit lowercase or uppercase hex", () => {
    expect(
      StackedTrendModel.parse({
        ...minimalValid,
        categories: [{ id: "x", label: "X", fill: "#A1B2C3" }],
      }).categories[0].fill,
    ).toBe("#A1B2C3");
  });

  it("rejects empty dimension", () => {
    expect(() => StackedTrendModel.parse({ ...minimalValid, dimension: "" })).toThrow();
  });

  it("requires sources array (CLAUDE.md §12) but allows empty", () => {
    expect(() =>
      StackedTrendModel.parse({ ...minimalValid, sources: [] }),
    ).not.toThrow();
    const noSources = { ...minimalValid } as Record<string, unknown>;
    delete noSources.sources;
    expect(() => StackedTrendModel.parse(noSources)).toThrow();
  });

  it("rejects non-https/http url in sources", () => {
    expect(() =>
      StackedTrendModel.parse({
        ...minimalValid,
        sources: [{ url: "not a url", fetched_at: "2026-05-13T21:54:16Z" }],
      }),
    ).toThrow();
  });

  it("accepts null value with availability != present", () => {
    const seg = StackedTrendSegment.parse({
      category_id: "coal",
      value: null,
      availability: "missing",
    });
    expect(seg.value).toBeNull();
    expect(seg.availability).toBe("missing");
  });

  it("accepts value 0 with availability present (different from missing)", () => {
    const seg = StackedTrendSegment.parse({ category_id: "coal", value: 0 });
    expect(seg.value).toBe(0);
    expect(seg.availability).toBe("present");
  });

  it("rejects unknown availability value", () => {
    expect(() =>
      StackedTrendSegment.parse({
        category_id: "coal",
        value: 1,
        availability: "weird",
      }),
    ).toThrow();
  });

  it("accepts headline with rule=none and empty text", () => {
    const m = StackedTrendModel.parse({
      ...minimalValid,
      headline: { rule: "none", text: "" },
    });
    expect(m.headline?.rule).toBe("none");
  });

  it("accepts honesty.unit_changed_at + series_breaks", () => {
    const m = StackedTrendModel.parse({
      ...minimalValid,
      honesty: {
        series_breaks: [
          { at_period_id: "AcGen2008", kind: "delimitation", note: "Boundaries changed" },
        ],
        unit_changed_at: [
          { at_period_id: "FY2017-18", from_unit: "INR cr", to_unit: "INR lakh cr", note: "Promotion" },
        ],
      },
    });
    expect(m.honesty?.series_breaks?.[0].note).toBe("Boundaries changed");
    expect(m.honesty?.unit_changed_at?.[0].to_unit).toBe("INR lakh cr");
  });

  it("rejects unknown bar_sort", () => {
    expect(() =>
      StackedTrendModel.parse({ ...minimalValid, bar_sort: "by_alphabetical" }),
    ).toThrow();
  });

  it("OTHER constants are stable", () => {
    expect(OTHER_CATEGORY_ID).toBe("__OTHER__");
    expect(OTHER_CATEGORY_FILL).toBe("#9ca3af");
  });
});
