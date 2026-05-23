import { describe, expect, it } from "vitest";

import {
  buildOrderedCategoryBarViewModel,
  buildRankedBarViewModel,
} from "./builders";

// Sample domain shape (state indicator row).
interface StateRow {
  readonly code: string;
  readonly name: string;
  readonly literacy_pct: number | null;
}

const SAMPLE_ROWS: StateRow[] = [
  { code: "KL", name: "Kerala", literacy_pct: 94.0 },
  { code: "BR", name: "Bihar", literacy_pct: 61.8 },
  { code: "TN", name: "Tamil Nadu", literacy_pct: 80.1 },
  { code: "MP", name: "Madhya Pradesh", literacy_pct: 69.3 },
  { code: "XX", name: "Unknown", literacy_pct: null }, // missing
];

const TO_LITERACY_ITEM = (r: StateRow) => ({
  id: r.code,
  label: r.name,
  value: r.literacy_pct,
});

describe("buildRankedBarViewModel — value_desc", () => {
  it("sorts present rows desc, missing last, ranks 1..N over present", () => {
    const vm = buildRankedBarViewModel({
      rows: SAMPLE_ROWS,
      toItem: TO_LITERACY_ITEM,
      policy: "value_desc",
    });
    expect(vm.rows.map((r) => r.sort_key.id)).toEqual(["KL", "TN", "MP", "BR", "XX"]);
    expect(vm.rows.map((r) => r.rank)).toEqual([1, 2, 3, 4, null]);
    expect(vm.rows[0].is_max).toBe(true);
    expect(vm.rows[1].is_max).toBe(false);
    expect(vm.rows[4].is_missing).toBe(true);
    expect(vm.max_abs_value).toBe(94.0);
    expect(vm.present_count).toBe(4);
    expect(vm.missing_count).toBe(1);
    expect(vm.direction).toBe("desc");
  });

  it("preserves original row reference (identity)", () => {
    const vm = buildRankedBarViewModel({
      rows: SAMPLE_ROWS,
      toItem: TO_LITERACY_ITEM,
      policy: "value_desc",
    });
    expect(vm.rows[0].row).toBe(SAMPLE_ROWS[0]); // Kerala
    expect(vm.rows[4].row).toBe(SAMPLE_ROWS[4]); // Unknown
  });
});

describe("buildRankedBarViewModel — value_asc", () => {
  it("sorts present rows asc, missing last; rank 1 = smallest", () => {
    const vm = buildRankedBarViewModel({
      rows: SAMPLE_ROWS,
      toItem: TO_LITERACY_ITEM,
      policy: "value_asc",
    });
    expect(vm.rows.map((r) => r.sort_key.id)).toEqual(["BR", "MP", "TN", "KL", "XX"]);
    expect(vm.rows.map((r) => r.rank)).toEqual([1, 2, 3, 4, null]);
    expect(vm.direction).toBe("asc");
  });
});

describe("buildRankedBarViewModel — rank_best_first", () => {
  it("best_is_high (default) → desc", () => {
    const vm = buildRankedBarViewModel({
      rows: SAMPLE_ROWS,
      toItem: TO_LITERACY_ITEM,
      policy: "rank_best_first",
    });
    expect(vm.rows[0].sort_key.id).toBe("KL");
    expect(vm.direction).toBe("desc");
  });

  it("best_is_high=false (IMR-style) → asc", () => {
    const vm = buildRankedBarViewModel({
      rows: SAMPLE_ROWS,
      toItem: TO_LITERACY_ITEM,
      policy: "rank_best_first",
      options: { best_is_high: false },
    });
    expect(vm.rows[0].sort_key.id).toBe("BR");
    expect(vm.direction).toBe("asc");
  });
});

describe("buildRankedBarViewModel — pinned_then_value", () => {
  it("pinned first in pinned_rank order, then value_desc", () => {
    const vm = buildRankedBarViewModel({
      rows: SAMPLE_ROWS,
      toItem: (r) => ({
        id: r.code,
        label: r.name,
        value: r.literacy_pct,
        pinned_rank:
          r.code === "MP" ? 0 : r.code === "BR" ? 1 : null,
      }),
      policy: "pinned_then_value",
    });
    expect(vm.rows.map((r) => r.sort_key.id)).toEqual([
      "MP", // pinned_rank 0
      "BR", // pinned_rank 1
      "KL", // then value_desc
      "TN",
      "XX",
    ]);
    expect(vm.rows[0].is_pinned).toBe(true);
    expect(vm.rows[1].is_pinned).toBe(true);
    expect(vm.rows[2].is_pinned).toBe(false);
  });
});

describe("buildRankedBarViewModel — latest_change", () => {
  it("sorts by |Δ| desc; missing endpoint last", () => {
    interface MoverRow {
      readonly id: string;
      readonly prev: number | null;
      readonly latest: number | null;
    }
    const rows: MoverRow[] = [
      { id: "small", prev: 100, latest: 102 },
      { id: "big", prev: 100, latest: 130 },
      { id: "drop", prev: 100, latest: 90 },
      { id: "broken", prev: 100, latest: null },
    ];
    const vm = buildRankedBarViewModel({
      rows,
      toItem: (r) => ({
        id: r.id,
        label: r.id,
        value: r.latest,
        latest_two: [r.prev, r.latest],
      }),
      policy: "latest_change",
    });
    expect(vm.rows.map((r) => r.sort_key.id)).toEqual([
      "big",
      "drop",
      "small",
      "broken",
    ]);
  });
});

describe("buildRankedBarViewModel — alphabetical", () => {
  it("sorts by label asc, case-insensitive", () => {
    const vm = buildRankedBarViewModel({
      rows: SAMPLE_ROWS,
      toItem: TO_LITERACY_ITEM,
      policy: "alphabetical",
    });
    expect(vm.rows.map((r) => r.sort_key.id)).toEqual([
      "BR", // Bihar
      "KL", // Kerala
      "MP", // Madhya Pradesh
      "TN", // Tamil Nadu
      "XX", // Unknown
    ]);
    expect(vm.direction).toBe("neutral");
  });
});

describe("buildRankedBarViewModel — show_value_label threshold", () => {
  it("default threshold 0.05 hides labels for rows < 5 % of max", () => {
    const rows = [
      { id: "big", v: 100 },
      { id: "mid", v: 10 },
      { id: "tiny", v: 2 },
    ];
    const vm = buildRankedBarViewModel({
      rows,
      toItem: (r) => ({ id: r.id, label: r.id, value: r.v }),
      policy: "value_desc",
    });
    const flags = Object.fromEntries(
      vm.rows.map((r) => [r.sort_key.id, r.show_value_label]),
    );
    expect(flags.big).toBe(true);
    expect(flags.mid).toBe(true); // 10/100 = 0.10 >= 0.05
    expect(flags.tiny).toBe(false); // 2/100 = 0.02 < 0.05
  });

  it("custom threshold honoured", () => {
    const rows = [
      { id: "big", v: 100 },
      { id: "mid", v: 30 },
    ];
    const vm = buildRankedBarViewModel({
      rows,
      toItem: (r) => ({ id: r.id, label: r.id, value: r.v }),
      policy: "value_desc",
      label_threshold: 0.5,
    });
    expect(vm.rows.find((r) => r.sort_key.id === "mid")?.show_value_label).toBe(false);
  });

  it("missing rows never carry a label", () => {
    const vm = buildRankedBarViewModel({
      rows: SAMPLE_ROWS,
      toItem: TO_LITERACY_ITEM,
      policy: "value_desc",
    });
    expect(vm.rows[4].show_value_label).toBe(false);
  });

  it("all-zero set: max_abs_value === 0 → no labels", () => {
    const rows = [
      { id: "a", v: 0 },
      { id: "b", v: 0 },
    ];
    const vm = buildRankedBarViewModel({
      rows,
      toItem: (r) => ({ id: r.id, label: r.id, value: r.v }),
      policy: "value_desc",
    });
    expect(vm.max_abs_value).toBe(0);
    expect(vm.rows.every((r) => r.show_value_label === false)).toBe(true);
    expect(vm.rows.every((r) => r.is_max === false)).toBe(true);
  });
});

describe("buildRankedBarViewModel — edge cases", () => {
  it("empty input → empty view-model", () => {
    const vm = buildRankedBarViewModel<{ id: string }>({
      rows: [],
      toItem: (r) => ({ id: r.id, label: r.id, value: null }),
      policy: "value_desc",
    });
    expect(vm.rows).toEqual([]);
    expect(vm.max_abs_value).toBe(0);
    expect(vm.present_count).toBe(0);
    expect(vm.missing_count).toBe(0);
  });

  it("all rows missing → all rows present, no ranks, no labels", () => {
    const rows = [
      { id: "a" as const },
      { id: "b" as const },
    ];
    const vm = buildRankedBarViewModel({
      rows,
      toItem: (r) => ({ id: r.id, label: r.id, value: null }),
      policy: "value_desc",
    });
    expect(vm.rows.length).toBe(2);
    expect(vm.rows.every((r) => r.rank === null)).toBe(true);
    expect(vm.rows.every((r) => r.is_missing === true)).toBe(true);
    expect(vm.missing_count).toBe(2);
    expect(vm.present_count).toBe(0);
  });

  it("ties preserve insertion order", () => {
    const rows = [
      { id: "first", v: 50 },
      { id: "second", v: 50 },
      { id: "third", v: 50 },
    ];
    const vm = buildRankedBarViewModel({
      rows,
      toItem: (r) => ({ id: r.id, label: r.id, value: r.v }),
      policy: "value_desc",
    });
    expect(vm.rows.map((r) => r.sort_key.id)).toEqual([
      "first",
      "second",
      "third",
    ]);
  });
});

describe("buildOrderedCategoryBarViewModel", () => {
  interface EconRow {
    readonly id: string;
    readonly label: string;
    readonly order: number;
    readonly value: number | null;
  }
  const ECON_ROWS: EconRow[] = [
    { id: "high", label: "High income", order: 3, value: 12 },
    { id: "low", label: "Low income", order: 1, value: 47 },
    { id: "mid", label: "Middle income", order: 2, value: 28 },
  ];

  it("axis_order — preserves order field even when values differ", () => {
    const vm = buildOrderedCategoryBarViewModel({
      rows: ECON_ROWS,
      toItem: (r) => ({ id: r.id, label: r.label, order: r.order, value: r.value }),
      policy: "axis_order",
    });
    expect(vm.rows.map((r) => r.sort_key.id)).toEqual(["low", "mid", "high"]);
    // Rank is by value desc regardless of axis order.
    expect(vm.rows.find((r) => r.sort_key.id === "low")?.rank).toBe(1);
    expect(vm.rows.find((r) => r.sort_key.id === "mid")?.rank).toBe(2);
    expect(vm.rows.find((r) => r.sort_key.id === "high")?.rank).toBe(3);
    expect(vm.direction).toBe("neutral");
  });

  it("alphabetical — by label asc", () => {
    const vm = buildOrderedCategoryBarViewModel({
      rows: ECON_ROWS,
      toItem: (r) => ({ id: r.id, label: r.label, order: r.order, value: r.value }),
      policy: "alphabetical",
    });
    expect(vm.rows.map((r) => r.sort_key.id)).toEqual(["high", "low", "mid"]);
  });

  it("missing axis order sorts last", () => {
    const rows = [
      { id: "a", label: "A", order: 2, value: 10 },
      { id: "b", label: "B", value: 5 }, // missing order
      { id: "c", label: "C", order: 1, value: 8 },
    ];
    const vm = buildOrderedCategoryBarViewModel({
      rows,
      toItem: (r) => ({ id: r.id, label: r.label, order: r.order, value: r.value }),
      policy: "axis_order",
    });
    expect(vm.rows.map((r) => r.sort_key.id)).toEqual(["c", "a", "b"]);
  });
});
