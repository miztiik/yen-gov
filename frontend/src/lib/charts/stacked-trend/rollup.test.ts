import { describe, it, expect } from "vitest";
import { applyGlobalUnion, fillNotApplicable, buildCategories, type RollupInputBar } from "./rollup";
import { OTHER_CATEGORY_ID } from "./types";

const cfg = { coverage_ceiling: 0.85, max_named_categories: 10 };

const bar = (period_id: string, segs: Record<string, number | null>, order = 0): RollupInputBar => ({
  period_id,
  period_label: period_id,
  order,
  segments: Object.entries(segs).map(([category_id, value]) => ({
    category_id,
    value,
    availability: value == null ? ("missing" as const) : ("present" as const),
  })),
});

describe("applyGlobalUnion", () => {
  it("single bar — top categories until 85% land in union", () => {
    const r = applyGlobalUnion([bar("S22", { coal: 50, gas: 30, hydro: 10, nuclear: 5, other: 5 })], cfg);
    expect(new Set(r.named_category_ids)).toEqual(new Set(["coal", "gas", "hydro"]));
    expect(r.other_present).toBe(true);
  });

  it("two bars — global union of each bar's top contributors", () => {
    const r = applyGlobalUnion(
      [
        bar("S22", { coal: 50, gas: 30, hydro: 10, solar: 10 }, 0),
        bar("S07", { coal: 10, hydro: 50, nuclear: 30, solar: 10 }, 1),
      ],
      cfg,
    );
    expect(new Set(r.named_category_ids)).toEqual(new Set(["coal", "gas", "hydro", "nuclear"]));
  });

  it("ceiling exact-hit stops at the contributing category", () => {
    const r = applyGlobalUnion([bar("X", { a: 85, b: 10, c: 5 })], cfg);
    expect(new Set(r.named_category_ids)).toEqual(new Set(["a"]));
  });

  it("max_named_categories cap binds before ceiling", () => {
    const segs: Record<string, number> = {};
    for (let i = 0; i < 15; i++) segs[`c${i}`] = 100 - i;
    const r = applyGlobalUnion([bar("X", segs)], { coverage_ceiling: 0.99, max_named_categories: 4 });
    expect(r.named_category_ids).toHaveLength(4);
    expect(r.other_present).toBe(true);
  });

  it("empty bar segments yield no named categories and no OTHER", () => {
    const r = applyGlobalUnion([bar("X", {})], cfg);
    expect(r.named_category_ids).toHaveLength(0);
    expect(r.other_present).toBe(false);
    expect(r.bars[0].segments).toHaveLength(0);
  });

  it("all-zero values: no OTHER segment created", () => {
    const r = applyGlobalUnion([bar("X", { a: 0, b: 0 })], cfg);
    expect(r.other_present).toBe(false);
  });

  it("all values fall outside union -> OTHER carries the sum", () => {
    const r = applyGlobalUnion(
      [bar("X", { a: 100 }), bar("Y", { b: 100 })],
      { coverage_ceiling: 0.5, max_named_categories: 1 },
    );
    expect(r.named_category_ids).toHaveLength(1);
    const yBar = r.bars.find((b) => b.period_id === "Y");
    expect(yBar?.segments.some((s) => s.category_id === OTHER_CATEGORY_ID)).toBe(true);
  });

  it("non-monotonic across bars: union still stable per category", () => {
    const r = applyGlobalUnion(
      [bar("A", { x: 60, y: 40 }, 0), bar("B", { x: 10, y: 90 }, 1), bar("C", { x: 90, y: 10 }, 2)],
      cfg,
    );
    expect(new Set(r.named_category_ids)).toEqual(new Set(["x", "y"]));
    for (const b of r.bars) {
      expect(b.segments.some((s) => s.category_id === "x")).toBe(true);
      expect(b.segments.some((s) => s.category_id === "y")).toBe(true);
    }
  });

  it("not_applicable segments carry through as null when category drops out", () => {
    const inputBars: RollupInputBar[] = [
      {
        period_id: "X",
        period_label: "X",
        order: 0,
        segments: [
          { category_id: "main", value: 90, availability: "present" },
          { category_id: "tiny", value: null, availability: "not_applicable" },
        ],
      },
    ];
    const r = applyGlobalUnion(inputBars, { coverage_ceiling: 0.85, max_named_categories: 1 });
    const seg = r.bars[0].segments.find((s) => s.category_id === OTHER_CATEGORY_ID);
    expect(seg?.availability).toBe("not_applicable");
    expect(seg?.value).toBeNull();
  });

  it("present trumps not_applicable when both fall outside union", () => {
    const inputBars: RollupInputBar[] = [
      {
        period_id: "X",
        period_label: "X",
        order: 0,
        segments: [
          { category_id: "main", value: 90, availability: "present" },
          { category_id: "tiny", value: 5, availability: "present" },
          { category_id: "ghost", value: null, availability: "not_applicable" },
        ],
      },
    ];
    const r = applyGlobalUnion(inputBars, { coverage_ceiling: 0.85, max_named_categories: 1 });
    const seg = r.bars[0].segments.find((s) => s.category_id === OTHER_CATEGORY_ID);
    expect(seg?.availability).toBe("present");
    expect(seg?.value).toBe(5);
  });
});

describe("fillNotApplicable", () => {
  it("adds null not_applicable segments for missing union members", () => {
    const r = fillNotApplicable([bar("X", { a: 1 })], ["a", "b", "c"]);
    expect(r[0].segments).toHaveLength(3);
    const b = r[0].segments.find((s) => s.category_id === "b");
    expect(b?.availability).toBe("not_applicable");
    expect(b?.value).toBeNull();
  });
});

describe("buildCategories", () => {
  it("creates categories in order; appends OTHER when present", () => {
    const cats = buildCategories(["a", "b"], { a: "Alpha", b: "Beta" }, true);
    expect(cats).toHaveLength(3);
    expect(cats[2].id).toBe(OTHER_CATEGORY_ID);
    expect(cats[0].label).toBe("Alpha");
  });

  it("falls back to id when label missing", () => {
    const cats = buildCategories(["a"], {}, false);
    expect(cats[0].label).toBe("a");
  });
});
