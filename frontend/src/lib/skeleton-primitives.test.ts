// Unit tests for the 3 content-shaped skeleton primitives (perf plan
// Row 6). Pins the structure-determining pure helpers (the frontend
// vitest runner is node-env, so the Svelte bodies are not mounted; the
// module-scope helpers are the testable surface, mirroring
// Skeleton.test.ts -> skeletonStyle).

import { describe, it, expect } from "vitest";
import { kpiTileCount } from "./KpiGridSkeleton.svelte";
import { tableSkeletonRows } from "./TableSkeleton.svelte";
import { mapFrameStyle } from "./MapFrameSkeleton.svelte";

describe("KpiGridSkeleton.kpiTileCount", () => {
  it("defaults to 4 for nullish / non-positive / non-finite input", () => {
    expect(kpiTileCount(undefined)).toBe(4);
    expect(kpiTileCount(0)).toBe(4);
    expect(kpiTileCount(-3)).toBe(4);
    expect(kpiTileCount(Number.NaN)).toBe(4);
  });

  it("floors a valid positive count", () => {
    expect(kpiTileCount(6)).toBe(6);
    expect(kpiTileCount(3.7)).toBe(3);
  });
});

describe("TableSkeleton.tableSkeletonRows", () => {
  it("defaults to 8 for nullish / non-positive input", () => {
    expect(tableSkeletonRows(undefined)).toBe(8);
    expect(tableSkeletonRows(0)).toBe(8);
    expect(tableSkeletonRows(-1)).toBe(8);
  });

  it("floors a valid positive count", () => {
    expect(tableSkeletonRows(12)).toBe(12);
    expect(tableSkeletonRows(5.9)).toBe(5);
  });
});

describe("MapFrameSkeleton.mapFrameStyle", () => {
  it("builds a width + height inline style", () => {
    expect(mapFrameStyle({ width: "100%", height: "440px" })).toBe(
      "width: 100%; height: 440px;",
    );
  });

  it("omits absent dimensions and returns empty when both omitted", () => {
    expect(mapFrameStyle({ height: "300px" })).toBe("height: 300px;");
    expect(mapFrameStyle({ width: "50%" })).toBe("width: 50%;");
    expect(mapFrameStyle({})).toBe("");
  });
});
