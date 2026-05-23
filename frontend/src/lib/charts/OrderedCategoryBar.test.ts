import { describe, expect, it } from "vitest";

import {
  buildOrderedCategoryBarViewModel,
  type OrderedCategoryBarViewModel,
} from "./bar-view-models";

// Renderer contract for OrderedCategoryBar.svelte. Component-level DOM
// assertions are deferred to Playwright (vitest = node-env, no jsdom).

interface AgeBandRow {
  id: string;
  label: string;
  order: number;
  pop_lakh: number | null;
}

const FIXTURE: readonly AgeBandRow[] = [
  { id: "0_4",   label: "0–4 years",   order: 0, pop_lakh: 12.5 },
  { id: "5_14",  label: "5–14 years",  order: 1, pop_lakh: 28.7 },
  { id: "15_24", label: "15–24 years", order: 2, pop_lakh: 32.1 },
  { id: "25_44", label: "25–44 years", order: 3, pop_lakh: 41.8 },
  { id: "45_64", label: "45–64 years", order: 4, pop_lakh: 22.4 },
  { id: "65_plus", label: "65+ years", order: 5, pop_lakh: null }, // missing
];

const VM: OrderedCategoryBarViewModel<AgeBandRow> = buildOrderedCategoryBarViewModel({
  rows: FIXTURE,
  toItem: r => ({ id: r.id, label: r.label, order: r.order, value: r.pop_lakh }),
  policy: "axis_order",
});

describe("OrderedCategoryBar renderer contract", () => {
  it("preserves axis order — rows render in the supplied order", () => {
    expect(VM.rows.map(r => r.sort_key.id)).toEqual([
      "0_4", "5_14", "15_24", "25_44", "45_64", "65_plus",
    ]);
  });

  it("flags the missing row", () => {
    const last = VM.rows[VM.rows.length - 1];
    expect(last.sort_key.id).toBe("65_plus");
    expect(last.is_missing).toBe(true);
    expect(last.sort_key.value ?? null).toBeNull();
  });

  it("max_abs_value is the largest present value", () => {
    expect(VM.max_abs_value).toBe(41.8);
  });

  it("present_count + missing_count = total rows", () => {
    expect(VM.present_count + VM.missing_count).toBe(FIXTURE.length);
    expect(VM.missing_count).toBe(1);
  });

  it("alphabetical policy re-orders by label", () => {
    const sorted = buildOrderedCategoryBarViewModel({
      rows: FIXTURE,
      toItem: r => ({ id: r.id, label: r.label, order: r.order, value: r.pop_lakh }),
      policy: "alphabetical",
    });
    const labels = sorted.rows.map(r => r.sort_key.label);
    const expected = [...labels].sort((a, b) => a.localeCompare(b));
    expect(labels).toEqual(expected);
  });
});
