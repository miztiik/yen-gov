// Pure-logic contract for the map coverage caption (PR-A of
// TODO/20260622-undivided-state-election-history-proposal.md). Per the repo
// vitest doctrine (node-env, no jsdom, no @testing-library/svelte mounts),
// this covers the pure module; the rendered <p> (auto-hide DOM + placement
// inside the map card) is covered by the CLAUDE.md section 13 browser smoke
// in the PR body.

import { describe, expect, test } from "vitest";

import {
  computeCoverage,
  coverageNoteText,
  delimVintageFromPath,
  hasCoverageGap,
  type MapCoverage,
} from "./map-coverage";

describe("computeCoverage", () => {
  test("counts features that bind a result; total is feature count", () => {
    const keys = ["S07_1", "S07_2", "S07_3", "S07_4"];
    const present = new Set(["S07_1", "S07_3"]);
    expect(computeCoverage(keys, (k) => present.has(String(k)))).toEqual({
      matched: 2,
      total: 4,
    });
  });

  test("null / undefined feature keys count toward total but never match", () => {
    const keys = ["a", null, undefined, "b"];
    const present = new Set(["a", "b"]);
    expect(computeCoverage(keys, (k) => present.has(String(k)))).toEqual({
      matched: 2,
      total: 4,
    });
  });

  test("numeric keys (eci_no) are supported for the AC join", () => {
    const keys = [1, 2, 3];
    const present = new Set([1, 3]);
    expect(computeCoverage(keys, (k) => present.has(Number(k)))).toEqual({
      matched: 2,
      total: 3,
    });
  });

  test("full match -> matched === total", () => {
    const keys = ["x", "y"];
    expect(computeCoverage(keys, () => true)).toEqual({ matched: 2, total: 2 });
  });

  test("empty geometry -> zero total", () => {
    expect(computeCoverage([], () => true)).toEqual({ matched: 0, total: 0 });
  });
});

describe("delimVintageFromPath", () => {
  test("extracts the delim year from an electoral path", () => {
    expect(
      delimVintageFromPath("boundaries/electoral/delim=2024/pc/all.geojson"),
    ).toBe("2024");
    expect(
      delimVintageFromPath("boundaries/electoral/delim=2008/ac/all.topojson"),
    ).toBe("2008");
  });

  test("returns null for admin paths with no delim marker", () => {
    expect(delimVintageFromPath("boundaries/in/states/all.geojson")).toBeNull();
  });

  test("returns null for null / undefined", () => {
    expect(delimVintageFromPath(null)).toBeNull();
    expect(delimVintageFromPath(undefined)).toBeNull();
  });
});

describe("hasCoverageGap (the auto-hide rule)", () => {
  test("true only when something rendered and not everything matched", () => {
    expect(hasCoverageGap({ matched: 217, total: 542 })).toBe(true);
  });

  test("false on full coverage (caption auto-hides on the normal case)", () => {
    expect(hasCoverageGap({ matched: 543, total: 543 })).toBe(false);
  });

  test("false when nothing rendered", () => {
    expect(hasCoverageGap({ matched: 0, total: 0 })).toBe(false);
  });

  test("false for null / undefined", () => {
    expect(hasCoverageGap(null)).toBe(false);
    expect(hasCoverageGap(undefined)).toBe(false);
  });
});

describe("coverageNoteText", () => {
  test("old-geometry partial coverage renders the ratified line with the vintage clause", () => {
    const cov: MapCoverage = { matched: 217, total: 542 };
    expect(coverageNoteText(cov, "constituencies", "2024", true)).toBe(
      "217 of 542 constituencies matched \u00b7 older years use 2024 boundaries \u2014 coverage drops with each delimitation",
    );
  });

  test("omits the vintage clause when the geometry year is unknown", () => {
    const cov: MapCoverage = { matched: 30, total: 40 };
    expect(coverageNoteText(cov, "districts", null, true)).toBe(
      "30 of 40 districts matched \u2014 coverage drops with each delimitation",
    );
  });

  test("current-vintage map never captions, even with structural misses (auto-hide)", () => {
    // e.g. general-2024 on 2024 geometry: 541/545 (2 J&K placeholders +
    // edge cases) must NOT surface a caption - it is not an old election.
    expect(
      coverageNoteText({ matched: 541, total: 545 }, "constituencies", "2024", false),
    ).toBeNull();
  });

  test("old geometry but full coverage returns null (e.g. a state whose names all matched)", () => {
    expect(
      coverageNoteText({ matched: 25, total: 25 }, "constituencies", "2024", true),
    ).toBeNull();
  });

  test("nothing rendered returns null", () => {
    expect(coverageNoteText({ matched: 0, total: 0 }, "constituencies", "2024", true)).toBeNull();
    expect(coverageNoteText(null)).toBeNull();
  });

  test("unit is parameterized (districts)", () => {
    expect(coverageNoteText({ matched: 1, total: 2 }, "districts", "2011", true)).toContain(
      "1 of 2 districts matched",
    );
  });
});
