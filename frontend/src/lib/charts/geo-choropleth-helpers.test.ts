// F2b.3 vitest unit for `geo-choropleth-helpers.ts`. Node-env (no jsdom)
// per CLAUDE.md section 14 + /memories/lessons.md.
//
// Covers:
//   - rowsByFeatureKey: Map shape correctness, stringification, last-wins
//   - deriveDomain: min/max from value column, null skipping,
//     empty/all-null fallback, single-value collapse to degenerate

import { describe, expect, test } from "vitest";
import {
  deriveDomain,
  rowsByFeatureKey,
  type GeoChoroplethRow,
} from "./geo-choropleth-helpers";

describe("rowsByFeatureKey", () => {
  test("groups rows by stringified entity_key", () => {
    const rows: GeoChoroplethRow[] = [
      { entity_key: 553, value: 24.1 },
      { entity_key: "552", value: 18.7 },
      { entity_key: 23, value: 9.4 },
    ];
    const out = rowsByFeatureKey(rows);
    expect(out.get("553")).toBe(24.1);
    expect(out.get("552")).toBe(18.7);
    expect(out.get("23")).toBe(9.4);
    expect(out.size).toBe(3);
  });

  test("stringification matches int vs string entity keys", () => {
    // Topojson carries int dist_lgd; row carries string entity_key.
    // Both must compare equal after String().
    const rows: GeoChoroplethRow[] = [{ entity_key: "553", value: 1.0 }];
    const out = rowsByFeatureKey(rows);
    expect(out.get(String(553))).toBe(1.0);
  });

  test("last-wins on duplicate keys", () => {
    const rows: GeoChoroplethRow[] = [
      { entity_key: "K", value: 1.0 },
      { entity_key: "K", value: 2.0 },
      { entity_key: "K", value: 3.0 },
    ];
    const out = rowsByFeatureKey(rows);
    expect(out.get("K")).toBe(3.0);
    expect(out.size).toBe(1);
  });

  test("preserves null values", () => {
    const rows: GeoChoroplethRow[] = [{ entity_key: "X", value: null }];
    const out = rowsByFeatureKey(rows);
    expect(out.get("X")).toBeNull();
    expect(out.has("X")).toBe(true);
  });

  test("empty input -> empty map", () => {
    expect(rowsByFeatureKey([]).size).toBe(0);
  });
});

describe("deriveDomain", () => {
  test("computes min/max from value column", () => {
    const rows: GeoChoroplethRow[] = [
      { entity_key: "A", value: 10 },
      { entity_key: "B", value: 50 },
      { entity_key: "C", value: 30 },
    ];
    expect(deriveDomain(rows)).toEqual({ min: 10, max: 50 });
  });

  test("skips null values", () => {
    const rows: GeoChoroplethRow[] = [
      { entity_key: "A", value: 10 },
      { entity_key: "B", value: null },
      { entity_key: "C", value: 30 },
    ];
    expect(deriveDomain(rows)).toEqual({ min: 10, max: 30 });
  });

  test("skips NaN / non-finite values", () => {
    const rows: GeoChoroplethRow[] = [
      { entity_key: "A", value: 10 },
      { entity_key: "B", value: NaN },
      { entity_key: "C", value: Infinity },
      { entity_key: "D", value: 30 },
    ];
    expect(deriveDomain(rows)).toEqual({ min: 10, max: 30 });
  });

  test("empty input -> {0, 1} fallback", () => {
    expect(deriveDomain([])).toEqual({ min: 0, max: 1 });
  });

  test("all-null input -> {0, 1} fallback", () => {
    const rows: GeoChoroplethRow[] = [
      { entity_key: "A", value: null },
      { entity_key: "B", value: null },
    ];
    expect(deriveDomain(rows)).toEqual({ min: 0, max: 1 });
  });

  test("single-value collapses to degenerate domain", () => {
    const rows: GeoChoroplethRow[] = [{ entity_key: "A", value: 42 }];
    // The degenerate-domain branch of binnedSequential() handles
    // this; deriveDomain just reports min == max honestly.
    expect(deriveDomain(rows)).toEqual({ min: 42, max: 42 });
  });

  test("negative values handled correctly", () => {
    const rows: GeoChoroplethRow[] = [
      { entity_key: "A", value: -10 },
      { entity_key: "B", value: 50 },
    ];
    expect(deriveDomain(rows)).toEqual({ min: -10, max: 50 });
  });
});
