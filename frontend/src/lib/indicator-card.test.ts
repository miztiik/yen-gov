import { describe, it, expect } from "vitest";
import {
  latestForEntity,
  seriesForEntity,
  rankForEntity,
  canShowRank,
  ordinal,
} from "./indicator-card";
import type { IndicatorMeta, IndicatorRow } from "./indicators";

const META_HIGHER: IndicatorMeta = {
  id: "test/foo",
  title: "Foo",
  entity_kind: "state",
  time_grain: "year",
  value_kind: "count",
  direction: "higher_is_better",
  unit: "MW",
};

const ROWS: IndicatorRow[] = [
  { entity_id: "S22", time: "2022", value: 100, facet: null },
  { entity_id: "S22", time: "2023", value: 150, facet: null },
  { entity_id: "S22", time: "2024", value: 200, facet: null },
  { entity_id: "S11", time: "2024", value: 300, facet: null },
  { entity_id: "S13", time: "2024", value: 50, facet: null },
  { entity_id: "S03", time: "2024", value: null, facet: null },
];

describe("latestForEntity", () => {
  it("returns the most-recent non-null observation", () => {
    expect(latestForEntity(ROWS, "S22")).toEqual({ time: "2024", value: 200 });
  });
  it("returns null when the entity has no non-null rows", () => {
    expect(latestForEntity(ROWS, "S03")).toBeNull();
    expect(latestForEntity(ROWS, "ZZ")).toBeNull();
  });
});

describe("seriesForEntity", () => {
  it("returns ascending (time, value) for the entity, skipping nulls", () => {
    expect(seriesForEntity(ROWS, "S22")).toEqual([
      { time: "2022", value: 100 },
      { time: "2023", value: 150 },
      { time: "2024", value: 200 },
    ]);
  });
  it("returns an empty array for an unknown entity", () => {
    expect(seriesForEntity(ROWS, "ZZ")).toEqual([]);
  });
});

describe("rankForEntity", () => {
  it("ranks higher_is_better descending; S11 > S22 > S13 ⇒ S22 rank 2/3", () => {
    expect(rankForEntity(ROWS, "S22", "higher_is_better", true)).toEqual({
      rank: 2, total: 3, time: "2024",
    });
  });
  it("ranks lower_is_better ascending; lowest value = rank 1", () => {
    expect(rankForEntity(ROWS, "S13", "lower_is_better", true)).toEqual({
      rank: 1, total: 3, time: "2024",
    });
  });
  it("returns null when can_rank is false", () => {
    expect(rankForEntity(ROWS, "S22", "higher_is_better", false)).toBeNull();
  });
  it("returns null when the entity has no value at any time", () => {
    expect(rankForEntity(ROWS, "S03", "higher_is_better", true)).toBeNull();
  });
});

describe("canShowRank", () => {
  it("returns true for the default comparable case", () => {
    expect(canShowRank(META_HIGHER)).toBe(true);
  });
  it("respects renderer_rules: no_rank_table", () => {
    const m = { ...META_HIGHER, renderer_rules: ["no_rank_table"] } as IndicatorMeta;
    expect(canShowRank(m)).toBe(false);
  });
  it("suppresses for comparability=not_comparable_across_states", () => {
    const m = { ...META_HIGHER, comparability: "not_comparable_across_states" } as IndicatorMeta;
    expect(canShowRank(m)).toBe(false);
  });
  it("suppresses for v1.5 comparability=directional_only", () => {
    const m = { ...META_HIGHER, comparability: "directional_only" } as IndicatorMeta;
    expect(canShowRank(m)).toBe(false);
  });
  it("suppresses for v1.5 comparability=comparable_within_state_over_time (Hans: trace one state, do NOT rank)", () => {
    const m = { ...META_HIGHER, comparability: "comparable_within_state_over_time" } as IndicatorMeta;
    expect(canShowRank(m)).toBe(false);
  });
  it("permits rank for v1.5 comparability=comparable_across_states_and_time", () => {
    const m = { ...META_HIGHER, comparability: "comparable_across_states_and_time" } as IndicatorMeta;
    expect(canShowRank(m)).toBe(true);
  });
  it("permits rank for v1.5 comparability=comparable_across_states_snapshot_only (snapshot rank OK; trend lines should be suppressed elsewhere)", () => {
    const m = { ...META_HIGHER, comparability: "comparable_across_states_snapshot_only" } as IndicatorMeta;
    expect(canShowRank(m)).toBe(true);
  });
});

describe("ordinal", () => {
  it("handles the common cases", () => {
    expect(ordinal(1)).toBe("1st");
    expect(ordinal(2)).toBe("2nd");
    expect(ordinal(3)).toBe("3rd");
    expect(ordinal(4)).toBe("4th");
    expect(ordinal(21)).toBe("21st");
    expect(ordinal(22)).toBe("22nd");
    expect(ordinal(23)).toBe("23rd");
  });
  it("handles the 11/12/13 exception", () => {
    expect(ordinal(11)).toBe("11th");
    expect(ordinal(12)).toBe("12th");
    expect(ordinal(13)).toBe("13th");
    expect(ordinal(113)).toBe("113th");
  });
});
