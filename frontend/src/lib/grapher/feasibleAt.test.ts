// Unit tests for `feasibleAt()` - the pure-function source of truth for
// the chart-switcher picker (plan section 21.9; chart-index.md section 2).
//
// The chart-drift gate at `chart-index.drift.test.ts` asserts the
// 1:1 contract between three artifacts:
//   (A) the `ChartType` union at `catalogue.ts`,
//   (B) the renderer rows in `docs/reference/chart-index.md` section 1,
//   (C) the matrix rows in section 2 of that doc, encoded by THIS function.
// These unit tests lock the third artifact's invariants:
//   1. Every `DataShape` branch returns a non-empty list.
//   2. `ranked` is the GUARANTEED terminal fallback in every branch
//      (plan section 23.5).
//   3. When `geometryAvailable === false`, both `choropleth` and
//      `choropleth-symbol` are silently stripped.
//   4. `intersectWithCatalogue` preserves catalogue order and shrinks
//      to the intersection with the feasible set.

import { describe, it, expect } from "vitest";
import {
  feasibleAt,
  intersectWithCatalogue,
  type DataShape,
  type FeasibleAtInput,
} from "./feasibleAt";
import type { ChartType } from "./catalogue";

const ALL_SHAPES: readonly DataShape[] = [
  "one-measure-over-geo-one-slice",
  "one-measure-over-geo-many-slices",
  "one-measure-named-series-over-time",
  "two-measures-joined-per-entity",
  "one-measure-split-by-facet",
  "part-to-whole-precise-compare",
  "magnitude-clusters-shallow-hierarchy",
  "start-end-pair-per-entity",
  "one-measure-over-geo-glyph-honest",
];

const defaultInput = (
  over: Partial<FeasibleAtInput> = {},
): FeasibleAtInput => ({
  dataShape: "one-measure-over-geo-one-slice",
  grain: "state",
  geometryAvailable: true,
  hasFacet: false,
  hasTimeAxis: false,
  ...over,
});

describe("feasibleAt - chart-index matrix coverage", () => {
  it.each(ALL_SHAPES)(
    "%s returns a non-empty list",
    (shape) => {
      const out = feasibleAt(defaultInput({ dataShape: shape }));
      expect(out.length).toBeGreaterThan(0);
    },
  );

  it.each(ALL_SHAPES)(
    "%s lists `ranked` as a feasible encoding (guaranteed fallback)",
    (shape) => {
      const out = feasibleAt(defaultInput({ dataShape: shape }));
      expect(out).toContain("ranked");
    },
  );
});

describe("feasibleAt - per-shape preference order (chart-index section 2)", () => {
  it("one-measure-over-geo-one-slice -> [choropleth, ranked]", () => {
    expect(feasibleAt(defaultInput())).toEqual(["choropleth", "ranked"]);
  });

  it("one-measure-over-geo-many-slices -> [matrix, line, choropleth, ranked]", () => {
    expect(
      feasibleAt(
        defaultInput({
          dataShape: "one-measure-over-geo-many-slices",
          hasTimeAxis: true,
        }),
      ),
    ).toEqual(["matrix", "line", "choropleth", "ranked"]);
  });

  it("one-measure-named-series-over-time -> [line, matrix, ranked]", () => {
    expect(
      feasibleAt(
        defaultInput({
          dataShape: "one-measure-named-series-over-time",
          hasTimeAxis: true,
        }),
      ),
    ).toEqual(["line", "matrix", "ranked"]);
  });

  it("two-measures-joined-per-entity -> [scatter, ranked]", () => {
    expect(
      feasibleAt(defaultInput({ dataShape: "two-measures-joined-per-entity" })),
    ).toEqual(["scatter", "ranked"]);
  });

  it("one-measure-split-by-facet -> [diverging, ranked]", () => {
    expect(
      feasibleAt(
        defaultInput({
          dataShape: "one-measure-split-by-facet",
          hasFacet: true,
        }),
      ),
    ).toEqual(["diverging", "ranked"]);
  });

  it("part-to-whole-precise-compare -> [treemap, stacked, ranked]", () => {
    expect(
      feasibleAt(defaultInput({ dataShape: "part-to-whole-precise-compare" })),
    ).toEqual(["treemap", "stacked", "ranked"]);
  });

  it("magnitude-clusters-shallow-hierarchy -> [circle-pack, treemap, ranked]", () => {
    expect(
      feasibleAt(
        defaultInput({ dataShape: "magnitude-clusters-shallow-hierarchy" }),
      ),
    ).toEqual(["circle-pack", "treemap", "ranked"]);
  });

  it("start-end-pair-per-entity -> [dumbbell-dot, dumbbell-arrow, ranked]", () => {
    expect(
      feasibleAt(defaultInput({ dataShape: "start-end-pair-per-entity" })),
    ).toEqual(["dumbbell-dot", "dumbbell-arrow", "ranked"]);
  });

  it("one-measure-over-geo-glyph-honest -> [choropleth-symbol, ranked]", () => {
    expect(
      feasibleAt(
        defaultInput({ dataShape: "one-measure-over-geo-glyph-honest" }),
      ),
    ).toEqual(["choropleth-symbol", "ranked"]);
  });
});

describe("feasibleAt - geometry gate", () => {
  it("strips `choropleth` when geometryAvailable is false", () => {
    const out = feasibleAt(
      defaultInput({
        dataShape: "one-measure-over-geo-one-slice",
        geometryAvailable: false,
      }),
    );
    expect(out).not.toContain("choropleth");
    expect(out).toContain("ranked");
  });

  it("strips `choropleth-symbol` when geometryAvailable is false", () => {
    const out = feasibleAt(
      defaultInput({
        dataShape: "one-measure-over-geo-glyph-honest",
        geometryAvailable: false,
      }),
    );
    expect(out).not.toContain("choropleth-symbol");
    expect(out).toContain("ranked");
  });

  it("never returns an empty list even when geometry is absent (ranked survives)", () => {
    for (const shape of ALL_SHAPES) {
      const out = feasibleAt(
        defaultInput({ dataShape: shape, geometryAvailable: false }),
      );
      expect(out.length).toBeGreaterThan(0);
      expect(out).toContain("ranked");
    }
  });

  it("preserves `choropleth` when geometryAvailable is true", () => {
    expect(
      feasibleAt(
        defaultInput({
          dataShape: "one-measure-over-geo-one-slice",
          geometryAvailable: true,
        }),
      ),
    ).toContain("choropleth");
  });
});

describe("intersectWithCatalogue", () => {
  it("returns the feasible list as-is when catalogue list is undefined", () => {
    const feasible: ChartType[] = ["choropleth", "ranked"];
    expect(intersectWithCatalogue(feasible, undefined)).toEqual([
      "choropleth",
      "ranked",
    ]);
  });

  it("returns the feasible list as-is when catalogue list is empty", () => {
    const feasible: ChartType[] = ["choropleth", "ranked"];
    expect(intersectWithCatalogue(feasible, [])).toEqual([
      "choropleth",
      "ranked",
    ]);
  });

  it("preserves catalogue order over feasible order", () => {
    const feasible: ChartType[] = ["matrix", "line", "ranked"];
    const cat: ChartType[] = ["line", "ranked", "matrix"];
    expect(intersectWithCatalogue(feasible, cat)).toEqual([
      "line",
      "ranked",
      "matrix",
    ]);
  });

  it("returns only members present in both lists", () => {
    const feasible: ChartType[] = ["choropleth", "ranked"];
    const cat: ChartType[] = ["choropleth", "treemap", "ranked"];
    expect(intersectWithCatalogue(feasible, cat)).toEqual([
      "choropleth",
      "ranked",
    ]);
  });

  it("returns an empty array when no catalogue member is feasible", () => {
    const feasible: ChartType[] = ["ranked"];
    const cat: ChartType[] = ["choropleth"];
    expect(intersectWithCatalogue(feasible, cat)).toEqual([]);
  });

  it("intersected with feasibleAt result for a real shape produces a non-empty catalogue-ordered list", () => {
    const feasible = feasibleAt(
      defaultInput({ dataShape: "one-measure-over-geo-one-slice" }),
    );
    const cat: ChartType[] = ["ranked", "choropleth", "treemap"];
    const out = intersectWithCatalogue(feasible, cat);
    expect(out).toEqual(["ranked", "choropleth"]);
  });
});
