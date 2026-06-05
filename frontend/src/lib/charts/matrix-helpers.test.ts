// F2b.4 vitest unit for `matrix-helpers.ts`. Node-env (no jsdom)
// per CLAUDE.md section 14.
//
// Covers:
//   - rowsByEntityByTime: Map<entity, Map<time, value>> shape,
//     stringification, last-wins on (entity, time) collision
//   - entityOrder: stable sort of stringified ids
//   - timeOrder: numeric-vs-lexical sort heuristic
//   - deriveDomain: same semantics as geo-choropleth-helpers

import { describe, expect, test } from "vitest";
import {
  deriveDomain,
  entityOrder,
  rowsByEntityByTime,
  timeOrder,
  type MatrixRow,
} from "./matrix-helpers";

describe("rowsByEntityByTime", () => {
  test("pivots rows into Map<entity, Map<time, value>>", () => {
    const rows: MatrixRow[] = [
      { entity_id: "KA", time: "2020", value: 1.0 },
      { entity_id: "KA", time: "2021", value: 2.0 },
      { entity_id: "TN", time: "2020", value: 3.0 },
      { entity_id: "TN", time: "2021", value: 4.0 },
    ];
    const out = rowsByEntityByTime(rows);
    expect(out.get("KA")?.get("2020")).toBe(1.0);
    expect(out.get("KA")?.get("2021")).toBe(2.0);
    expect(out.get("TN")?.get("2020")).toBe(3.0);
    expect(out.get("TN")?.get("2021")).toBe(4.0);
  });

  test("stringification dodges int-vs-string mis-join", () => {
    const rows: MatrixRow[] = [
      { entity_id: 29, time: 2020, value: 1.0 },
    ];
    const out = rowsByEntityByTime(rows);
    expect(out.get("29")?.get("2020")).toBe(1.0);
  });

  test("last-wins on duplicate (entity, time)", () => {
    const rows: MatrixRow[] = [
      { entity_id: "K", time: "Y", value: 1.0 },
      { entity_id: "K", time: "Y", value: 2.0 },
      { entity_id: "K", time: "Y", value: 3.0 },
    ];
    const out = rowsByEntityByTime(rows);
    expect(out.get("K")?.get("Y")).toBe(3.0);
    expect(out.get("K")?.size).toBe(1);
  });

  test("preserves null values", () => {
    const rows: MatrixRow[] = [
      { entity_id: "K", time: "2020", value: null },
    ];
    const out = rowsByEntityByTime(rows);
    expect(out.get("K")?.get("2020")).toBeNull();
    expect(out.get("K")?.has("2020")).toBe(true);
  });

  test("empty input -> empty map", () => {
    expect(rowsByEntityByTime([]).size).toBe(0);
  });
});

describe("entityOrder", () => {
  test("returns unique stringified ids in sorted order", () => {
    const rows: MatrixRow[] = [
      { entity_id: "TN", time: "2020", value: 1 },
      { entity_id: "KA", time: "2020", value: 2 },
      { entity_id: "TN", time: "2021", value: 3 },
      { entity_id: "AP", time: "2020", value: 4 },
    ];
    expect(entityOrder(rows)).toEqual(["AP", "KA", "TN"]);
  });

  test("stringifies numeric ids", () => {
    const rows: MatrixRow[] = [
      { entity_id: 33, time: "2020", value: 1 },
      { entity_id: 29, time: "2020", value: 2 },
    ];
    // Lexical sort of "29", "33" gives ["29", "33"] which also
    // happens to be the numeric order; the contract is "sorted
    // stringified", not "numerically sorted".
    expect(entityOrder(rows)).toEqual(["29", "33"]);
  });

  test("empty -> empty", () => {
    expect(entityOrder([])).toEqual([]);
  });
});

describe("timeOrder", () => {
  test("numeric strings sort numerically", () => {
    const rows: MatrixRow[] = [
      { entity_id: "K", time: "2021", value: 1 },
      { entity_id: "K", time: "2020", value: 2 },
      { entity_id: "K", time: "2019", value: 3 },
    ];
    expect(timeOrder(rows)).toEqual(["2019", "2020", "2021"]);
  });

  test("int times come back as strings, numerically sorted", () => {
    const rows: MatrixRow[] = [
      { entity_id: "K", time: 2021, value: 1 },
      { entity_id: "K", time: 2020, value: 2 },
    ];
    expect(timeOrder(rows)).toEqual(["2020", "2021"]);
  });

  test("mixed non-numeric strings sort lexically", () => {
    const rows: MatrixRow[] = [
      { entity_id: "K", time: "FY 2021-22", value: 1 },
      { entity_id: "K", time: "FY 2020-21", value: 2 },
    ];
    expect(timeOrder(rows)).toEqual(["FY 2020-21", "FY 2021-22"]);
  });

  test("empty -> empty", () => {
    expect(timeOrder([])).toEqual([]);
  });
});

describe("deriveDomain", () => {
  test("computes min/max from value column", () => {
    const rows: MatrixRow[] = [
      { entity_id: "A", time: "Y", value: 10 },
      { entity_id: "B", time: "Y", value: 50 },
      { entity_id: "C", time: "Y", value: 30 },
    ];
    expect(deriveDomain(rows)).toEqual({ min: 10, max: 50 });
  });

  test("skips null + non-finite", () => {
    const rows: MatrixRow[] = [
      { entity_id: "A", time: "Y", value: 10 },
      { entity_id: "B", time: "Y", value: null },
      { entity_id: "C", time: "Y", value: NaN },
      { entity_id: "D", time: "Y", value: Infinity },
      { entity_id: "E", time: "Y", value: 30 },
    ];
    expect(deriveDomain(rows)).toEqual({ min: 10, max: 30 });
  });

  test("empty input -> {0, 1} fallback", () => {
    expect(deriveDomain([])).toEqual({ min: 0, max: 1 });
  });

  test("all-null input -> {0, 1} fallback", () => {
    const rows: MatrixRow[] = [
      { entity_id: "A", time: "Y", value: null },
      { entity_id: "B", time: "Y", value: null },
    ];
    expect(deriveDomain(rows)).toEqual({ min: 0, max: 1 });
  });
});
