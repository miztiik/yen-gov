import { describe, expect, it } from "vitest";

import {
  KNOWN_SORT_POLICIES,
  applySortPolicy,
  sortDirectionForPolicy,
} from "./helpers";
import type { SortItem, SortPolicy } from "./types";

describe("KNOWN_SORT_POLICIES", () => {
  it("is the closed-enum vocabulary", () => {
    expect(KNOWN_SORT_POLICIES).toEqual([
      "value_asc",
      "value_desc",
      "axis_order",
      "chronological",
      "pinned_then_value",
      "rank_best_first",
      "latest_change",
      "alphabetical",
    ]);
  });

  it("is frozen", () => {
    expect(Object.isFrozen(KNOWN_SORT_POLICIES)).toBe(true);
  });
});

describe("applySortPolicy — purity + stability", () => {
  it("returns a new array (does not mutate input)", () => {
    const input: SortItem[] = [
      { id: "a", label: "A", value: 3 },
      { id: "b", label: "B", value: 1 },
    ];
    const snapshot = input.map((r) => r.id);
    const out = applySortPolicy(input, "value_asc");
    expect(out).not.toBe(input);
    expect(input.map((r) => r.id)).toEqual(snapshot);
  });

  it("is stable for tied keys (preserves insertion order)", () => {
    const input: SortItem[] = [
      { id: "first", label: "A", value: 5 },
      { id: "second", label: "B", value: 5 },
      { id: "third", label: "C", value: 5 },
    ];
    const out = applySortPolicy(input, "value_desc");
    expect(out.map((r) => r.id)).toEqual(["first", "second", "third"]);
  });
});

describe("applySortPolicy — value_asc / value_desc", () => {
  const rows: SortItem[] = [
    { id: "a", label: "Alpha", value: 10 },
    { id: "b", label: "Beta", value: null },
    { id: "c", label: "Gamma", value: 3 },
    { id: "d", label: "Delta", value: 7 },
  ];

  it("value_asc — present values ascending, nulls last", () => {
    const out = applySortPolicy(rows, "value_asc");
    expect(out.map((r) => r.id)).toEqual(["c", "d", "a", "b"]);
  });

  it("value_desc — present values descending, nulls last", () => {
    const out = applySortPolicy(rows, "value_desc");
    expect(out.map((r) => r.id)).toEqual(["a", "d", "c", "b"]);
  });

  it("treats NaN as missing (nulls-last)", () => {
    const out = applySortPolicy(
      [
        { id: "a", label: "A", value: Number.NaN },
        { id: "b", label: "B", value: 1 },
      ],
      "value_asc",
    );
    expect(out.map((r) => r.id)).toEqual(["b", "a"]);
  });

  it("all-null array sorts stably (no swap)", () => {
    const out = applySortPolicy(
      [
        { id: "a", label: "A", value: null },
        { id: "b", label: "B", value: null },
      ],
      "value_desc",
    );
    expect(out.map((r) => r.id)).toEqual(["a", "b"]);
  });
});

describe("applySortPolicy — axis_order", () => {
  it("orders by integer order, missing last", () => {
    const out = applySortPolicy(
      [
        { id: "high", label: "High income", order: 3 },
        { id: "low", label: "Low income", order: 1 },
        { id: "unknown", label: "Unknown" }, // missing order
        { id: "mid", label: "Middle income", order: 2 },
      ],
      "axis_order",
    );
    expect(out.map((r) => r.id)).toEqual(["low", "mid", "high", "unknown"]);
  });

  it("ties preserve insertion order", () => {
    const out = applySortPolicy(
      [
        { id: "a", label: "A", order: 1 },
        { id: "b", label: "B", order: 1 },
      ],
      "axis_order",
    );
    expect(out.map((r) => r.id)).toEqual(["a", "b"]);
  });
});

describe("applySortPolicy — chronological", () => {
  it("orders by parsed leading year, unparseable last", () => {
    const out = applySortPolicy(
      [
        { id: "x", label: "x", period_id: "FY2022" },
        { id: "y", label: "y", period_id: "2024-05" },
        { id: "z", label: "z", period_id: "no-year-here" }, // unparseable
        { id: "w", label: "w", period_id: "2020" },
      ],
      "chronological",
    );
    expect(out.map((r) => r.id)).toEqual(["w", "x", "y", "z"]);
  });

  it("same year falls back to lexical period_id", () => {
    const out = applySortPolicy(
      [
        { id: "sep", label: "Sep", period_id: "2024-09" },
        { id: "jan", label: "Jan", period_id: "2024-01" },
        { id: "may", label: "May", period_id: "2024-05" },
      ],
      "chronological",
    );
    expect(out.map((r) => r.id)).toEqual(["jan", "may", "sep"]);
  });

  it("rows with no period_id sort last", () => {
    const out = applySortPolicy(
      [
        { id: "no-key", label: "x" },
        { id: "y22", label: "y", period_id: "2022" },
      ],
      "chronological",
    );
    expect(out.map((r) => r.id)).toEqual(["y22", "no-key"]);
  });
});

describe("applySortPolicy — pinned_then_value", () => {
  it("pinned rows first in pinned_rank order, then value_desc", () => {
    const out = applySortPolicy(
      [
        { id: "compare", label: "compare", value: 5, pinned_rank: 1 },
        { id: "other", label: "other", value: 30 },
        { id: "home", label: "home", value: 10, pinned_rank: 0 },
        { id: "another", label: "another", value: 20 },
      ],
      "pinned_then_value",
    );
    expect(out.map((r) => r.id)).toEqual([
      "home", // pinned_rank 0
      "compare", // pinned_rank 1
      "other", // value 30
      "another", // value 20
    ]);
  });

  it("null pinned_rank is unpinned", () => {
    const out = applySortPolicy(
      [
        { id: "a", label: "a", value: 1, pinned_rank: null },
        { id: "b", label: "b", value: 2, pinned_rank: 0 },
      ],
      "pinned_then_value",
    );
    expect(out.map((r) => r.id)).toEqual(["b", "a"]);
  });
});

describe("applySortPolicy — rank_best_first", () => {
  const rows: SortItem[] = [
    { id: "a", label: "A", value: 10 },
    { id: "b", label: "B", value: 90 },
    { id: "c", label: "C", value: 50 },
  ];

  it("best_is_high (default) → value_desc", () => {
    const out = applySortPolicy(rows, "rank_best_first");
    expect(out.map((r) => r.id)).toEqual(["b", "c", "a"]);
  });

  it("best_is_high=true → value_desc", () => {
    const out = applySortPolicy(rows, "rank_best_first", { best_is_high: true });
    expect(out.map((r) => r.id)).toEqual(["b", "c", "a"]);
  });

  it("best_is_high=false → value_asc", () => {
    const out = applySortPolicy(rows, "rank_best_first", { best_is_high: false });
    expect(out.map((r) => r.id)).toEqual(["a", "c", "b"]);
  });

  it("nulls always last regardless of direction", () => {
    const out = applySortPolicy(
      [
        { id: "n", label: "n", value: null },
        { id: "x", label: "x", value: 1 },
      ],
      "rank_best_first",
      { best_is_high: false },
    );
    expect(out.map((r) => r.id)).toEqual(["x", "n"]);
  });
});

describe("applySortPolicy — latest_change", () => {
  it("sorts by absolute delta descending, missing endpoints last", () => {
    const out = applySortPolicy(
      [
        { id: "small", label: "small", latest_two: [100, 102] }, // |Δ|=2
        { id: "big", label: "big", latest_two: [100, 130] }, // |Δ|=30
        { id: "drop", label: "drop", latest_two: [100, 90] }, // |Δ|=10
        { id: "broken", label: "broken", latest_two: [100, null] },
        { id: "no-pair", label: "no-pair" },
      ],
      "latest_change",
    );
    expect(out.map((r) => r.id)).toEqual([
      "big",
      "drop",
      "small",
      "broken",
      "no-pair",
    ]);
  });

  it("missing previous endpoint also sorts last", () => {
    const out = applySortPolicy(
      [
        { id: "x", label: "x", latest_two: [null, 10] },
        { id: "y", label: "y", latest_two: [1, 2] },
      ],
      "latest_change",
    );
    expect(out.map((r) => r.id)).toEqual(["y", "x"]);
  });
});

describe("applySortPolicy — alphabetical", () => {
  it("orders case-insensitively, empty labels last", () => {
    const out = applySortPolicy(
      [
        { id: "z", label: "Zebra", value: 1 },
        { id: "a", label: "apple", value: 2 },
        { id: "blank", label: "", value: 3 },
        { id: "b", label: "Banana", value: 4 },
      ],
      "alphabetical",
    );
    expect(out.map((r) => r.id)).toEqual(["a", "b", "z", "blank"]);
  });
});

describe("sortDirectionForPolicy", () => {
  const expectations: Array<[SortPolicy, "asc" | "desc" | "neutral"]> = [
    ["value_asc", "asc"],
    ["value_desc", "desc"],
    ["axis_order", "neutral"],
    ["chronological", "neutral"],
    ["pinned_then_value", "neutral"],
    ["latest_change", "desc"],
    ["alphabetical", "neutral"],
  ];

  for (const [policy, expected] of expectations) {
    it(`${policy} → ${expected}`, () => {
      expect(sortDirectionForPolicy(policy)).toBe(expected);
    });
  }

  it("rank_best_first → desc by default", () => {
    expect(sortDirectionForPolicy("rank_best_first")).toBe("desc");
  });

  it("rank_best_first + best_is_high=false → asc", () => {
    expect(sortDirectionForPolicy("rank_best_first", { best_is_high: false })).toBe(
      "asc",
    );
  });
});
