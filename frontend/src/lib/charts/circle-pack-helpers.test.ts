// F2b.6 vitest unit for `circle-pack-helpers.ts`. Node-env (no jsdom).
//
// Covers:
//   - packLayout: one circle per non-null leaf; mode discriminator
//     (pack respects parent_id, bubble ignores it); sqrt-proportional
//     area; non-overlap invariant; empty/zero-box handling
//   - shouldRenderCircleLabel: predicate at threshold boundary
//   - hierarchy traversal in pack mode

import { describe, expect, test } from "vitest";
import {
  packLayout,
  shouldRenderCircleLabel,
  type CirclePackRow,
} from "./circle-pack-helpers";

describe("packLayout - pack mode", () => {
  test("returns one circle per non-null leaf", () => {
    const rows: CirclePackRow[] = [
      { id: "A", label: "A", value: 10 },
      { id: "B", label: "B", value: 20 },
      { id: "C", label: "C", value: 30 },
    ];
    const out = packLayout(rows, { width: 200, height: 200, mode: "pack" });
    expect(out).toHaveLength(3);
    expect(out.map(c => c.id).sort()).toEqual(["A", "B", "C"]);
  });

  test("skips null + non-positive values", () => {
    const rows: CirclePackRow[] = [
      { id: "A", label: "A", value: 10 },
      { id: "B", label: "B", value: null },
      { id: "C", label: "C", value: 0 },
      { id: "D", label: "D", value: -5 },
      { id: "E", label: "E", value: 25 },
    ];
    const out = packLayout(rows, { width: 200, height: 200, mode: "pack" });
    expect(out.map(c => c.id).sort()).toEqual(["A", "E"]);
  });

  test("respects parent_id (hierarchical grouping)", () => {
    const rows: CirclePackRow[] = [
      { id: "AP", label: "AP", value: 40, parent_id: "South" },
      { id: "KA", label: "KA", value: 60, parent_id: "South" },
      { id: "UP", label: "UP", value: 100, parent_id: "North" },
    ];
    const out = packLayout(rows, { width: 400, height: 400, mode: "pack" });
    expect(out).toHaveLength(3);
    const parentIds = out.map(c => c.parent_id).sort();
    expect(parentIds).toEqual(["North", "South", "South"]);
  });

  test("circle areas are roughly value-proportional", () => {
    const rows: CirclePackRow[] = [
      { id: "small", label: "small", value: 50 },
      { id: "big",   label: "big",   value: 200 },
    ];
    const out = packLayout(rows, { width: 400, height: 400, mode: "pack" });
    const small = out.find(c => c.id === "small")!;
    const big = out.find(c => c.id === "big")!;
    // Pi*r^2 ratio for 4x value should be ~4x area; allow tolerance.
    const ratio = (big.r * big.r) / (small.r * small.r);
    expect(ratio).toBeGreaterThan(3.0);
    expect(ratio).toBeLessThan(5.0);
  });

  test("circles do not overlap", () => {
    const rows: CirclePackRow[] = [
      { id: "A", label: "A", value: 100 },
      { id: "B", label: "B", value: 50 },
      { id: "C", label: "C", value: 25 },
      { id: "D", label: "D", value: 10 },
    ];
    const circles = packLayout(rows, { width: 300, height: 300, mode: "pack" });
    for (let i = 0; i < circles.length; i += 1) {
      for (let j = i + 1; j < circles.length; j += 1) {
        const a = circles[i];
        const b = circles[j];
        const dx = a.cx - b.cx;
        const dy = a.cy - b.cy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        // Allow a small tolerance for floating-point + d3 padding.
        expect(dist).toBeGreaterThanOrEqual(a.r + b.r - 1);
      }
    }
  });

  test("empty rows -> empty result", () => {
    expect(packLayout([], { width: 200, height: 200, mode: "pack" })).toEqual([]);
  });

  test("zero-sized box -> empty result", () => {
    const rows: CirclePackRow[] = [{ id: "A", label: "A", value: 10 }];
    expect(packLayout(rows, { width: 0, height: 200, mode: "pack" })).toEqual([]);
    expect(packLayout(rows, { width: 200, height: 0, mode: "pack" })).toEqual([]);
  });
});

describe("packLayout - bubble mode", () => {
  test("ignores parent_id (flat children)", () => {
    const rows: CirclePackRow[] = [
      { id: "A", label: "A", value: 10, parent_id: "X" },
      { id: "B", label: "B", value: 20, parent_id: "Y" },
      { id: "C", label: "C", value: 30, parent_id: "Z" },
    ];
    const out = packLayout(rows, { width: 200, height: 200, mode: "bubble" });
    expect(out).toHaveLength(3);
    // All parent_ids should be null in bubble mode (flat).
    for (const c of out) expect(c.parent_id).toBeNull();
  });

  test("uses wider padding than pack mode", () => {
    // Identical input, two modes -> bubble's circles must be more
    // spaced (smaller r OR larger centre distances).
    const rows: CirclePackRow[] = [
      { id: "A", label: "A", value: 100 },
      { id: "B", label: "B", value: 100 },
    ];
    const packed = packLayout(rows, { width: 400, height: 400, mode: "pack" });
    const bubbled = packLayout(rows, { width: 400, height: 400, mode: "bubble" });
    expect(packed).toHaveLength(2);
    expect(bubbled).toHaveLength(2);
    // The bubble-mode circles should be smaller (more padding eats space).
    expect(bubbled[0].r).toBeLessThan(packed[0].r);
  });
});

describe("shouldRenderCircleLabel", () => {
  test("renders when radius >= threshold", () => {
    expect(shouldRenderCircleLabel({ r: 30 })).toBe(true);
  });

  test("hides when radius < threshold", () => {
    expect(shouldRenderCircleLabel({ r: 20 })).toBe(false);
  });

  test("at-threshold renders (lower-inclusive)", () => {
    expect(shouldRenderCircleLabel({ r: 24 })).toBe(true);
  });

  test("one-pixel-below-threshold hides", () => {
    expect(shouldRenderCircleLabel({ r: 23.999 })).toBe(false);
  });

  test("custom threshold applies", () => {
    expect(shouldRenderCircleLabel({ r: 30 }, 40)).toBe(false);
    expect(shouldRenderCircleLabel({ r: 50 }, 40)).toBe(true);
  });
});
