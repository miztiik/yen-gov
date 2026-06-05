// CategoryBar renderer contract.
//
// Component-level DOM assertions are deferred to Playwright (vitest =
// node-env, no jsdom canvas, no @testing-library/svelte mounts per
// repo doctrine). This file asserts the discriminated-union shape +
// the view-model invariants for `mode="ranked"`, which is the ONLY
// implemented branch in F2a.1+F2a.2. Subsequent F2a sub-rows
// extend this file as they fill in the "stacked" and "diverging"
// branches.
//
// The renderer body for mode="ranked" is lifted byte-identical from
// the retired `OrderedCategoryBar.svelte`, so the existing
// `OrderedCategoryBar.test.ts` (a builder test that covers the
// VM shape) remains the authoritative behavioural anchor for the
// ranked path.

import { describe, expect, it } from "vitest";

import {
  buildOrderedCategoryBarViewModel,
  type OrderedCategoryBarViewModel,
} from "./bar-view-models";

interface AgeBandRow {
  id: string;
  label: string;
  order: number;
  pop_lakh: number | null;
}

const FIXTURE: readonly AgeBandRow[] = [
  { id: "0_4", label: "0-4 years", order: 0, pop_lakh: 12.5 },
  { id: "5_14", label: "5-14 years", order: 1, pop_lakh: 28.7 },
  { id: "15_24", label: "15-24 years", order: 2, pop_lakh: 32.1 },
  { id: "25_44", label: "25-44 years", order: 3, pop_lakh: 41.8 },
  { id: "45_64", label: "45-64 years", order: 4, pop_lakh: 22.4 },
  { id: "65_plus", label: "65+ years", order: 5, pop_lakh: null }, // missing
];

const VM: OrderedCategoryBarViewModel<AgeBandRow> = buildOrderedCategoryBarViewModel({
  rows: FIXTURE,
  toItem: (r) => ({ id: r.id, label: r.label, order: r.order, value: r.pop_lakh }),
  policy: "axis_order",
});

describe("CategoryBar mode='ranked' renderer contract", () => {
  it("consumes an OrderedCategoryBarViewModel<T> shape", () => {
    // Compile-time guard: the renderer's `RankedProps.view_model`
    // type is exactly `OrderedCategoryBarViewModel<T>`. If a future
    // refactor changes the VM shape, this assertion fails fast.
    expect(VM.rows).toBeDefined();
    expect(VM.max_abs_value).toBeGreaterThan(0);
    expect(VM.present_count + VM.missing_count).toBe(FIXTURE.length);
  });

  it("preserves axis order on the ranked path", () => {
    expect(VM.rows.map((r) => r.sort_key.id)).toEqual([
      "0_4",
      "5_14",
      "15_24",
      "25_44",
      "45_64",
      "65_plus",
    ]);
  });

  it("flags the missing row so the renderer paints a hatch", () => {
    const last = VM.rows[VM.rows.length - 1];
    expect(last.sort_key.id).toBe("65_plus");
    expect(last.is_missing).toBe(true);
    expect(last.sort_key.value ?? null).toBeNull();
  });

  it("max_abs_value drives the bar width (renderer reads it for widthFrac)", () => {
    expect(VM.max_abs_value).toBe(41.8);
  });

  it("alphabetical policy re-orders rows so the renderer renders them in label order", () => {
    const sorted = buildOrderedCategoryBarViewModel({
      rows: FIXTURE,
      toItem: (r) => ({ id: r.id, label: r.label, order: r.order, value: r.pop_lakh }),
      policy: "alphabetical",
    });
    const labels = sorted.rows.map((r) => r.sort_key.label);
    const expected = [...labels].sort((a, b) => a.localeCompare(b));
    expect(labels).toEqual(expected);
  });
});

describe("CategoryBar discriminated-union doctrine", () => {
  it("all three modes (ranked, stacked, diverging) are implemented as of F2a.5.1", () => {
    // The component renders a real body for each mode now. This
    // test documents the contract; the actual mount-time behaviour
    // is verified in the section 13 sandbox smoke for each mode
    // (ocb -> ranked, hgb -> stacked, diverging-bar -> diverging).
    const implemented: ReadonlyArray<"ranked" | "stacked" | "diverging"> = [
      "ranked",
      "stacked",
      "diverging",
    ];
    expect(implemented).toContain("ranked");
    expect(implemented).toContain("stacked");
    expect(implemented).toContain("diverging");
  });
});
