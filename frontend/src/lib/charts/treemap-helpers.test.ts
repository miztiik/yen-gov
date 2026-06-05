// F2b.5 vitest unit for `treemap-helpers.ts`. Node-env (no jsdom).
//
// Covers:
//   - treemapLayout: one tile per non-null leaf, sqrt-proportional
//     area, parent grouping, flat-list shortcut, empty/null inputs
//   - shouldRenderTileLabel: predicate at width/height boundaries
//   - totalValue: sum of non-null + non-negative rows

import { describe, expect, test } from "vitest";
import {
  shouldRenderTileLabel,
  totalValue,
  treemapLayout,
  type TreemapRow,
} from "./treemap-helpers";

describe("treemapLayout", () => {
  test("returns one tile per non-null leaf row", () => {
    const rows: TreemapRow[] = [
      { id: "A", label: "Alpha", value: 100 },
      { id: "B", label: "Bravo", value: 50 },
      { id: "C", label: "Charlie", value: 25 },
    ];
    const tiles = treemapLayout(rows, { width: 200, height: 200 });
    expect(tiles).toHaveLength(3);
    const ids = tiles.map(t => t.id).sort();
    expect(ids).toEqual(["A", "B", "C"]);
  });

  test("skips null and non-positive values", () => {
    const rows: TreemapRow[] = [
      { id: "A", label: "A", value: 100 },
      { id: "B", label: "B", value: null },
      { id: "C", label: "C", value: 0 },
      { id: "D", label: "D", value: -10 },
      { id: "E", label: "E", value: 50 },
    ];
    const tiles = treemapLayout(rows, { width: 200, height: 200 });
    const ids = tiles.map(t => t.id).sort();
    expect(ids).toEqual(["A", "E"]);
  });

  test("tile areas are roughly value-proportional (sqrt scale honesty)", () => {
    // 2x value -> 2x area (not 4x).
    const rows: TreemapRow[] = [
      { id: "small", label: "small", value: 50 },
      { id: "big", label: "big", value: 100 },
    ];
    const tiles = treemapLayout(rows, { width: 400, height: 400 });
    const small = tiles.find(t => t.id === "small")!;
    const big = tiles.find(t => t.id === "big")!;
    const smallArea = small.width * small.height;
    const bigArea = big.width * big.height;
    // d3 treemap targets value-proportional areas; the ratio should
    // hover around 2.0 within a wide tolerance (treemap squarification
    // does not produce exact ratios).
    const ratio = bigArea / smallArea;
    expect(ratio).toBeGreaterThan(1.4);
    expect(ratio).toBeLessThan(2.6);
  });

  test("tiles do not overlap", () => {
    const rows: TreemapRow[] = [
      { id: "A", label: "A", value: 100 },
      { id: "B", label: "B", value: 50 },
      { id: "C", label: "C", value: 25 },
    ];
    const tiles = treemapLayout(rows, { width: 200, height: 200 });
    for (let i = 0; i < tiles.length; i += 1) {
      for (let j = i + 1; j < tiles.length; j += 1) {
        const a = tiles[i];
        const b = tiles[j];
        const overlapX = a.x0 < b.x1 && b.x0 < a.x1;
        const overlapY = a.y0 < b.y1 && b.y0 < a.y1;
        expect(overlapX && overlapY).toBe(false);
      }
    }
  });

  test("handles two-level grouping via parent_id", () => {
    const rows: TreemapRow[] = [
      { id: "AP", label: "Andhra", value: 40, parent_id: "South" },
      { id: "KA", label: "Karnataka", value: 60, parent_id: "South" },
      { id: "UP", label: "UP", value: 80, parent_id: "North" },
      { id: "MP", label: "MP", value: 20, parent_id: "Central" },
    ];
    const tiles = treemapLayout(rows, { width: 400, height: 400 });
    expect(tiles).toHaveLength(4);
    const sumByParent = new Map<string, number>();
    for (const t of tiles) {
      const p = t.parent_id ?? "";
      sumByParent.set(p, (sumByParent.get(p) ?? 0) + t.width * t.height);
    }
    // South + North + Central all non-zero area.
    expect(sumByParent.size).toBe(3);
  });

  test("flat list (no parent_id) renders as single-level", () => {
    const rows: TreemapRow[] = [
      { id: "A", label: "A", value: 10 },
      { id: "B", label: "B", value: 20 },
    ];
    const tiles = treemapLayout(rows, { width: 100, height: 100 });
    expect(tiles).toHaveLength(2);
    for (const t of tiles) expect(t.parent_id).toBeNull();
  });

  test("empty rows -> empty tiles", () => {
    expect(treemapLayout([], { width: 100, height: 100 })).toEqual([]);
  });

  test("zero-sized box -> empty tiles", () => {
    const rows: TreemapRow[] = [{ id: "A", label: "A", value: 100 }];
    expect(treemapLayout(rows, { width: 0, height: 100 })).toEqual([]);
    expect(treemapLayout(rows, { width: 100, height: 0 })).toEqual([]);
  });
});

describe("shouldRenderTileLabel", () => {
  test("renders when tile exceeds both thresholds", () => {
    expect(shouldRenderTileLabel({ width: 60, height: 30 })).toBe(true);
  });

  test("hides when tile is too narrow", () => {
    expect(shouldRenderTileLabel({ width: 20, height: 30 })).toBe(false);
  });

  test("hides when tile is too short", () => {
    expect(shouldRenderTileLabel({ width: 60, height: 10 })).toBe(false);
  });

  test("at-threshold renders (lower-inclusive)", () => {
    expect(shouldRenderTileLabel({ width: 40, height: 18 })).toBe(true);
  });

  test("one-pixel-below-threshold hides", () => {
    expect(shouldRenderTileLabel({ width: 39, height: 18 })).toBe(false);
    expect(shouldRenderTileLabel({ width: 40, height: 17 })).toBe(false);
  });

  test("custom thresholds apply", () => {
    expect(shouldRenderTileLabel({ width: 50, height: 25 }, 60, 30)).toBe(false);
    expect(shouldRenderTileLabel({ width: 80, height: 40 }, 60, 30)).toBe(true);
  });
});

describe("totalValue", () => {
  test("sums non-null + non-negative values", () => {
    const rows: TreemapRow[] = [
      { id: "A", label: "A", value: 10 },
      { id: "B", label: "B", value: 20 },
      { id: "C", label: "C", value: null },
      { id: "D", label: "D", value: -5 },
      { id: "E", label: "E", value: 30 },
    ];
    expect(totalValue(rows)).toBe(60);
  });

  test("empty -> 0", () => {
    expect(totalValue([])).toBe(0);
  });

  test("all-null -> 0", () => {
    const rows: TreemapRow[] = [
      { id: "A", label: "A", value: null },
      { id: "B", label: "B", value: null },
    ];
    expect(totalValue(rows)).toBe(0);
  });
});
