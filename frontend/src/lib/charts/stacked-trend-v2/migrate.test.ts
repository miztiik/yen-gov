// Unit tests for the v1 → v2 migration adapter (Track-D D10).
//
// The adapter is pure / sync / no side effects. These tests exercise:
//   - schema_version literal stamping
//   - verbatim pass-through of every shape v1 and v2 share
//   - sources replacement (v1 dropped entirely; v2 ledger rows copied)
//   - immutability (input arrays not mutated)
//   - parsing the resulting object through the v2 zod model

import { describe, expect, it } from "vitest";
import { stackedTrendModelToV2 } from "./migrate";
import { StackedTrendV2Model, type StackedTrendV2Source } from "./types";
import type { StackedTrendModel } from "../stacked-trend/types";

// A minimal but representative v1 model — one category, two bars, full
// honesty + headline, retired-shape sources.
const V1_MODEL: StackedTrendModel = Object.freeze({
  unit: { id: "seats", label: "Seats won", value_kind: "count" },
  x_axis_label: "Year",
  bar_sort: "by_order_ascending",
  categories: [
    { id: "dmk", label: "DMK", fill: "#cc0000", order: 1 },
    { id: "aiadmk", label: "AIADMK", fill: "#006633", order: 2 },
  ],
  bars: [
    {
      period_id: "AcGenApr2021",
      period_label: "Apr 2021",
      order: 1,
      segments: [
        { category_id: "dmk", value: 125, availability: "present" },
        { category_id: "aiadmk", value: 75, availability: "present" },
      ],
    },
    {
      period_id: "AcGenMay2026",
      period_label: "May 2026",
      order: 2,
      segments: [
        { category_id: "dmk", value: 133, availability: "present" },
        { category_id: "aiadmk", value: 66, availability: "present" },
      ],
    },
  ],
  headline: {
    rule: "max_latest_with_streak",
    text: "DMK leads in 2026",
    highlight_category_id: "dmk",
  },
  honesty: {
    comparability: "comparable_across_states",
    methodology_vintage: "ECI Statistical Report Section 10",
    notes: "Vote-share rounded to 0.1pp.",
  },
  sources: [
    {
      url: "https://eci.gov.in/results/tn-2026.xlsx",
      fetched_at: "2026-05-20T10:00:00Z",
    },
  ],
  dimension: "party",
  default_mode: "percent",
}) as StackedTrendModel;

// V2 publisher pills resolved by a view-model JOIN against taxonomy.sources
// + dedupeToPills. The shape mirrors PublisherPill from $lib/sources.
const V2_SOURCES: readonly StackedTrendV2Source[] = Object.freeze([
  Object.freeze({
    label: "ECI Statistical Report Section 10",
    vintage_summary: "AcGenMay2026",
    url: "https://eci.gov.in/statistical-reports",
    count: 1,
  }),
  Object.freeze({
    label: "ECI Statistical Report Section 10",
    vintage_summary: "AcGenApr2021",
    url: "https://eci.gov.in/statistical-reports",
    count: 1,
  }),
]);

describe("stackedTrendModelToV2 — schema_version stamping", () => {
  it("stamps schema_version: \"2.0\" on the output", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    expect(out.schema_version).toBe("2.0");
  });
});

describe("stackedTrendModelToV2 — verbatim pass-through", () => {
  it("copies unit verbatim", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    expect(out.unit).toEqual(V1_MODEL.unit);
  });

  it("copies x_axis_label verbatim", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    expect(out.x_axis_label).toBe(V1_MODEL.x_axis_label);
  });

  it("copies bar_sort verbatim", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    expect(out.bar_sort).toBe(V1_MODEL.bar_sort);
  });

  it("copies categories verbatim (preserves order, fill, label)", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    expect(out.categories).toEqual(V1_MODEL.categories);
  });

  it("copies bars (period_id, period_label, order) and segment core fields", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    // PR-B5: bars are no longer reference-verbatim because each segment now
    // carries a computed `delta`. Compare the stable scaffold + core fields.
    expect(out.bars).toHaveLength(V1_MODEL.bars.length);
    out.bars.forEach((bar, i) => {
      const src = V1_MODEL.bars[i];
      expect(bar.period_id).toBe(src.period_id);
      expect(bar.period_label).toBe(src.period_label);
      expect(bar.order).toBe(src.order);
      bar.segments.forEach((seg, j) => {
        expect(seg.category_id).toBe(src.segments[j].category_id);
        expect(seg.value).toBe(src.segments[j].value);
        expect(seg.availability).toBe(src.segments[j].availability);
      });
    });
  });

  it("copies headline verbatim", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    expect(out.headline).toEqual(V1_MODEL.headline);
  });

  it("copies honesty verbatim", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    expect(out.honesty).toEqual(V1_MODEL.honesty);
  });

  it("copies dimension verbatim", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    expect(out.dimension).toBe(V1_MODEL.dimension);
  });

  it("copies default_mode verbatim", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    expect(out.default_mode).toBe(V1_MODEL.default_mode);
  });
});

describe("stackedTrendModelToV2 — sources replacement (post 2026-06-11)", () => {
  it("drops v1 sources entirely (no url, no fetched_at on output)", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    for (const src of out.sources) {
      expect(src).not.toHaveProperty("fetched_at");
      // v1's `url` field was a different concept (free-form link with
      // fetched_at). The post 2026-06-11 pill ALSO has a `url` field
      // but it is now a publisher landing URL (or null). Either way
      // the v1 mixture of url+fetched_at is gone.
    }
  });

  it("copies v2 publisher pills verbatim onto output.sources", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    expect(out.sources).toEqual(V2_SOURCES);
    expect(out.sources).toHaveLength(V2_SOURCES.length);
  });

  it("handles zero v2 sources (hand-authored / no ledger lookup)", () => {
    const out = stackedTrendModelToV2(V1_MODEL, []);
    expect(out.sources).toEqual([]);
  });

  it("preserves pill order", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    expect(out.sources[0].vintage_summary).toBe("AcGenMay2026");
    expect(out.sources[1].vintage_summary).toBe("AcGenApr2021");
  });
});

describe("stackedTrendModelToV2 — swing deltas (PR-B5)", () => {
  it("first bar segments always carry delta: null (no predecessor)", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    for (const seg of out.bars[0].segments) {
      expect(seg.delta).toBeNull();
    }
  });

  it("computes delta = current.value − previous-bar same-category value", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    const second = out.bars[1];
    const dmk = second.segments.find((s) => s.category_id === "dmk");
    const aiadmk = second.segments.find((s) => s.category_id === "aiadmk");
    expect(dmk?.delta).toBe(8); // 133 − 125
    expect(aiadmk?.delta).toBe(-9); // 66 − 75
  });

  it("yields null delta when the current value is missing", () => {
    const withGap: StackedTrendModel = {
      ...V1_MODEL,
      bars: [
        V1_MODEL.bars[0],
        {
          ...V1_MODEL.bars[1],
          segments: [
            { category_id: "dmk", value: null, availability: "missing" },
            { category_id: "aiadmk", value: 66, availability: "present" },
          ],
        },
      ],
    } as StackedTrendModel;
    const out = stackedTrendModelToV2(withGap, V2_SOURCES);
    const dmk = out.bars[1].segments.find((s) => s.category_id === "dmk");
    expect(dmk?.delta).toBeNull();
  });

  it("carries the baseline across a missing year (does not reset to null)", () => {
    // dmk: 125 (bar0) → missing (bar1) → 140 (bar2). Bar2's delta must be
    // 140 − 125 = 15, computed against the last PRESENT value, not bar1.
    const threeBar: StackedTrendModel = {
      ...V1_MODEL,
      bars: [
        V1_MODEL.bars[0],
        {
          period_id: "AcGenMay2026",
          period_label: "May 2026",
          order: 2,
          segments: [
            { category_id: "dmk", value: null, availability: "missing" },
            { category_id: "aiadmk", value: 66, availability: "present" },
          ],
        },
        {
          period_id: "AcGenMay2031",
          period_label: "May 2031",
          order: 3,
          segments: [
            { category_id: "dmk", value: 140, availability: "present" },
            { category_id: "aiadmk", value: 60, availability: "present" },
          ],
        },
      ],
    } as StackedTrendModel;
    const out = stackedTrendModelToV2(threeBar, V2_SOURCES);
    const dmk = out.bars[2].segments.find((s) => s.category_id === "dmk");
    expect(dmk?.delta).toBe(15);
  });

  it("does not mutate the input model bars/segments", () => {
    const before = JSON.stringify(V1_MODEL.bars);
    stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    expect(JSON.stringify(V1_MODEL.bars)).toBe(before);
  });

  it("preserves the caller's original bar ordering in the output", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    expect(out.bars.map((b) => b.period_id)).toEqual(
      V1_MODEL.bars.map((b) => b.period_id),
    );
  });
});

describe("stackedTrendModelToV2 — immutability", () => {
  it("does not mutate the input v2 sources array", () => {
    const arr: StackedTrendV2Source[] = [...V2_SOURCES];
    const before = arr.length;
    stackedTrendModelToV2(V1_MODEL, arr);
    expect(arr).toHaveLength(before);
  });

  it("returns a fresh sources array (not aliased to input)", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    // Reference inequality — copying via [...x] gives a new array
    expect(out.sources).not.toBe(V2_SOURCES);
  });
});

describe("stackedTrendModelToV2 — zod round-trip", () => {
  it("output parses cleanly through StackedTrendV2Model", () => {
    const out = stackedTrendModelToV2(V1_MODEL, V2_SOURCES);
    const parsed = StackedTrendV2Model.safeParse(out);
    const message = parsed.success
      ? ""
      : JSON.stringify(parsed.error.issues, null, 2);
    expect(parsed.success, message).toBe(true);
  });

  it("output parses cleanly with an editorial-only pill (no vintage, no URL)", () => {
    const editorialSources: StackedTrendV2Source[] = [
      {
        label: "yen-gov Editorial",
        vintage_summary: "",
        url: null,
        count: 1,
      },
    ];
    const out = stackedTrendModelToV2(V1_MODEL, editorialSources);
    const parsed = StackedTrendV2Model.safeParse(out);
    const message = parsed.success
      ? ""
      : JSON.stringify(parsed.error.issues, null, 2);
    expect(parsed.success, message).toBe(true);
  });
});
