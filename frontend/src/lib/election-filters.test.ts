// Contract tests for the election-filter URL grammar (PR-B8).
//
// This is the executable form of Gregor's URL-grammar verdict and is what
// the national route (PR-B9) leans on. Round-trip + clamp + passthrough +
// defaults-empty are the four load-bearing guarantees.

import { describe, expect, it } from "vitest";
import {
  DEFAULT_ELECTION_FILTERS,
  activeFilterCount,
  matchesMarginBand,
  parseElectionFilters,
  serializeElectionFilters,
  type ElectionFilters,
} from "./election-filters";

describe("parseElectionFilters", () => {
  it("returns all defaults for an empty query string", () => {
    expect(parseElectionFilters("")).toEqual(DEFAULT_ELECTION_FILTERS);
  });

  it("parses comma-delimited party codes preserving order", () => {
    expect(parseElectionFilters("party=BJP,INC").parties).toEqual(["BJP", "INC"]);
  });

  it("ignores empty tokens from stray commas", () => {
    expect(parseElectionFilters("party=BJP,,INC,").parties).toEqual([
      "BJP",
      "INC",
    ]);
  });

  it("clamps an unknown mode to the winner default (forward-degradation)", () => {
    expect(parseElectionFilters("mode=swing").mode).toBe("winner");
  });

  it("clamps an unknown margin band to all", () => {
    expect(parseElectionFilters("margin=xyz").margin).toBe("all");
  });

  it("keeps an unknown-but-well-formed party code verbatim", () => {
    expect(parseElectionFilters("party=ZZZ").parties).toEqual(["ZZZ"]);
  });

  it("accepts a URLSearchParams instance", () => {
    const sp = new URLSearchParams("mode=turnout&margin=lt2");
    expect(parseElectionFilters(sp)).toEqual({
      parties: [],
      margin: "lt2",
      mode: "turnout",
    });
  });
});

describe("serializeElectionFilters", () => {
  it("omits every default → empty string (clean shareable link)", () => {
    expect(serializeElectionFilters(DEFAULT_ELECTION_FILTERS)).toBe("");
  });

  it("emits only the params that differ from the default", () => {
    const f: ElectionFilters = { parties: ["BJP"], margin: "all", mode: "margin" };
    const qs = serializeElectionFilters(f);
    const sp = new URLSearchParams(qs);
    expect(sp.get("party")).toBe("BJP");
    expect(sp.get("mode")).toBe("margin");
    expect(sp.has("margin")).toBe(false);
  });

  it("preserves a non-owned param passed via base (view-safe)", () => {
    const base = new URLSearchParams("view=hex");
    const qs = serializeElectionFilters(
      { parties: [], margin: "lt2", mode: "winner" },
      base,
    );
    const sp = new URLSearchParams(qs);
    expect(sp.get("view")).toBe("hex");
    expect(sp.get("margin")).toBe("lt2");
  });

  it("round-trips parse(serialize(f)) === f across the vocabulary", () => {
    const cases: ElectionFilters[] = [
      DEFAULT_ELECTION_FILTERS,
      { parties: ["BJP", "INC", "DMK"], margin: "lt2", mode: "turnout" },
      { parties: ["AITC"], margin: "gt20", mode: "age" },
      { parties: [], margin: "all", mode: "margin" },
    ];
    for (const f of cases) {
      expect(parseElectionFilters(serializeElectionFilters(f))).toEqual(f);
    }
  });
});

describe("matchesMarginBand", () => {
  it("matches everything for the all band", () => {
    expect(matchesMarginBand(0.5, "all")).toBe(true);
    expect(matchesMarginBand(null, "all")).toBe(true);
  });

  it("close = |margin| < 2 pts", () => {
    expect(matchesMarginBand(1.9, "lt2")).toBe(true);
    expect(matchesMarginBand(2, "lt2")).toBe(false);
    expect(matchesMarginBand(-1.2, "lt2")).toBe(true);
  });

  it("landslide = |margin| > 20 pts", () => {
    expect(matchesMarginBand(25, "gt20")).toBe(true);
    expect(matchesMarginBand(20, "gt20")).toBe(false);
  });

  it("excludes null margins from non-all bands", () => {
    expect(matchesMarginBand(null, "lt2")).toBe(false);
    expect(matchesMarginBand(undefined, "gt20")).toBe(false);
  });
});

describe("activeFilterCount", () => {
  it("is zero for the default", () => {
    expect(activeFilterCount(DEFAULT_ELECTION_FILTERS)).toBe(0);
  });

  it("counts each non-default dimension once", () => {
    expect(
      activeFilterCount({ parties: ["BJP", "INC"], margin: "lt2", mode: "age" }),
    ).toBe(3);
    expect(
      activeFilterCount({ parties: [], margin: "all", mode: "margin" }),
    ).toBe(1);
  });
});
