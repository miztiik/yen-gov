/**
 * Unit tests for compare-table-filter (PR3 of
 * TODO/20260617-election-compare-ux-overhaul-plan.md).
 *
 * Pins the combined filter + search + sort contract for the
 * election-compare table:
 *  - filter chip predicate (all / flips / holds) preserved exactly;
 *  - search is a case-insensitive substring over entity_name AND both
 *    winner party short codes (from_party / to_party);
 *  - the three controls compose;
 *  - sort is null-coalesced and direction-aware.
 *
 * Pure model -> no Svelte mount, runs in the node env.
 */

import { describe, it, expect } from "vitest";
import {
  filterAndSortCompareRows,
  type CompareTableRow,
} from "./compare-table-filter";

// Minimal compare-row factory; only the fields the model reads are set.
function row(
  entity_name: string,
  from_party: string | null,
  to_party: string | null,
  is_flip: boolean,
  is_orphan = false,
  is_new_party = false,
): CompareTableRow {
  return { entity_name, from_party, to_party, is_flip, is_orphan, is_new_party };
}

const ROWS: CompareTableRow[] = [
  row("Chennai South", "DMK", "DMK", false), // hold
  row("Madurai", "ADMK", "DMK", true), // flip
  row("Coimbatore", "DMK", "BJP", true, false, true), // flip (to a NEW party)
  row("Salem", "ADMK", "ADMK", false), // hold
  row("Theni (new)", null, "DMK", false, true), // orphan (new seat)
  row("Vellore (gone)", "INC", null, false, true), // orphan (boundary)
];

describe("filterAndSortCompareRows: filter chip", () => {
  it("all returns every row", () => {
    const out = filterAndSortCompareRows(ROWS, "", "all", "entity_name", "asc");
    expect(out).toHaveLength(ROWS.length);
  });

  it("flips returns only is_flip rows", () => {
    const out = filterAndSortCompareRows(
      ROWS,
      "",
      "flips",
      "entity_name",
      "asc",
    );
    expect(out.map((r) => r.entity_name)).toEqual(["Coimbatore", "Madurai"]);
  });

  it("holds returns only non-flip non-orphan rows (orphans excluded)", () => {
    const out = filterAndSortCompareRows(
      ROWS,
      "",
      "holds",
      "entity_name",
      "asc",
    );
    expect(out.map((r) => r.entity_name)).toEqual(["Chennai South", "Salem"]);
  });
});

describe("filterAndSortCompareRows: search", () => {
  it("matches a substring of the constituency name (case-insensitive)", () => {
    const out = filterAndSortCompareRows(
      ROWS,
      "chen",
      "all",
      "entity_name",
      "asc",
    );
    expect(out.map((r) => r.entity_name)).toEqual(["Chennai South"]);
  });

  it("matches the From-winner short code", () => {
    const out = filterAndSortCompareRows(ROWS, "ADMK", "all", "entity_name", "asc");
    expect(out.map((r) => r.entity_name).sort()).toEqual(["Madurai", "Salem"]);
  });

  it("matches the To-winner short code", () => {
    const out = filterAndSortCompareRows(ROWS, "bjp", "all", "entity_name", "asc");
    expect(out.map((r) => r.entity_name)).toEqual(["Coimbatore"]);
  });

  it("is case-insensitive on the party code", () => {
    const lower = filterAndSortCompareRows(ROWS, "dmk", "all", "entity_name", "asc");
    const upper = filterAndSortCompareRows(ROWS, "DMK", "all", "entity_name", "asc");
    expect(lower.map((r) => r.entity_name)).toEqual(
      upper.map((r) => r.entity_name),
    );
    // Substring semantics: "dmk" is also a substring of "admk", so the ADMK
    // rows (Madurai, Salem) match alongside the DMK rows. 5 of the 6 rows
    // touch a DMK-substring party code; only Vellore (INC -> null) is out.
    expect(lower.map((r) => r.entity_name).sort()).toEqual([
      "Chennai South",
      "Coimbatore",
      "Madurai",
      "Salem",
      "Theni (new)",
    ]);
  });

  it("trims surrounding whitespace before matching", () => {
    const out = filterAndSortCompareRows(
      ROWS,
      "   salem  ",
      "all",
      "entity_name",
      "asc",
    );
    expect(out.map((r) => r.entity_name)).toEqual(["Salem"]);
  });

  it("an empty / whitespace query is a no-op (subject to the chip)", () => {
    const out = filterAndSortCompareRows(ROWS, "   ", "all", "entity_name", "asc");
    expect(out).toHaveLength(ROWS.length);
  });

  it("does not throw on null party codes (orphan rows)", () => {
    // "vellore" only matches an orphan whose to_party is null.
    const out = filterAndSortCompareRows(
      ROWS,
      "vellore",
      "all",
      "entity_name",
      "asc",
    );
    expect(out.map((r) => r.entity_name)).toEqual(["Vellore (gone)"]);
  });
});

describe("filterAndSortCompareRows: search composes with chip", () => {
  it("flips chip + DMK search keeps only flips TO/FROM DMK", () => {
    const out = filterAndSortCompareRows(
      ROWS,
      "dmk",
      "flips",
      "entity_name",
      "asc",
    );
    // Coimbatore (DMK -> BJP) and Madurai (ADMK -> DMK) are the two flips
    // touching DMK; both stay.
    expect(out.map((r) => r.entity_name)).toEqual(["Coimbatore", "Madurai"]);
  });

  it("holds chip + BJP search yields nothing (BJP only appears in a flip)", () => {
    const out = filterAndSortCompareRows(
      ROWS,
      "bjp",
      "holds",
      "entity_name",
      "asc",
    );
    expect(out).toHaveLength(0);
  });
});

describe("filterAndSortCompareRows: new-party filter", () => {
  it("new returns only is_new_party rows", () => {
    const out = filterAndSortCompareRows(ROWS, "", "new", "entity_name", "asc");
    expect(out.map((r) => r.entity_name)).toEqual(["Coimbatore"]);
  });

  it("excludes flips/holds that are not new-party entries", () => {
    // Madurai is a flip (ADMK -> DMK) but DMK is not a new party, so the
    // "new" chip must drop it.
    const out = filterAndSortCompareRows(ROWS, "", "new", "entity_name", "asc");
    expect(out.map((r) => r.entity_name)).not.toContain("Madurai");
  });

  it("composes with search (new chip + name query)", () => {
    const hit = filterAndSortCompareRows(
      ROWS,
      "coim",
      "new",
      "entity_name",
      "asc",
    );
    expect(hit.map((r) => r.entity_name)).toEqual(["Coimbatore"]);
    const miss = filterAndSortCompareRows(
      ROWS,
      "madurai",
      "new",
      "entity_name",
      "asc",
    );
    expect(miss).toHaveLength(0);
  });
});

describe("filterAndSortCompareRows: sort", () => {
  it("sorts ascending by entity_name", () => {
    const out = filterAndSortCompareRows(ROWS, "", "all", "entity_name", "asc");
    expect(out.map((r) => r.entity_name)).toEqual([
      "Chennai South",
      "Coimbatore",
      "Madurai",
      "Salem",
      "Theni (new)",
      "Vellore (gone)",
    ]);
  });

  it("sorts descending by entity_name", () => {
    const out = filterAndSortCompareRows(ROWS, "", "all", "entity_name", "desc");
    expect(out.map((r) => r.entity_name)).toEqual([
      "Vellore (gone)",
      "Theni (new)",
      "Salem",
      "Madurai",
      "Coimbatore",
      "Chennai South",
    ]);
  });

  it("sorts by from_party with nulls coalesced to first (asc)", () => {
    const out = filterAndSortCompareRows(ROWS, "", "all", "from_party", "asc");
    // null from_party ("Theni (new)") coalesces to "" and sorts first.
    expect(out[0].entity_name).toBe("Theni (new)");
    expect(out.map((r) => r.from_party)).toEqual([
      null,
      "ADMK",
      "ADMK",
      "DMK",
      "DMK",
      "INC",
    ]);
  });

  it("sorts by to_party descending", () => {
    const out = filterAndSortCompareRows(ROWS, "", "all", "to_party", "desc");
    expect(out.map((r) => r.to_party)).toEqual([
      "DMK",
      "DMK",
      "DMK",
      "BJP",
      "ADMK",
      null,
    ]);
  });

  it("does not mutate the input array", () => {
    const input = [...ROWS];
    const snapshot = input.map((r) => r.entity_name);
    filterAndSortCompareRows(input, "", "all", "entity_name", "desc");
    expect(input.map((r) => r.entity_name)).toEqual(snapshot);
  });
});
