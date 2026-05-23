// Vitest gate for the temporal-viewport pure helpers shipped in PR-34
// of the chart-modernisation plan (Phase 1.5 task list — pure helper
// foundation).
//
// vitest is node-env across the frontend workspace (no jsdom — see
// the comment in `IndicatorChoropleth.boundaries.test.ts:4`). These
// helpers are 100% pure: no DOM, no Svelte, no Blob, no clipboard.

import { describe, expect, it } from "vitest";

import {
  KNOWN_DOMAIN_KINDS,
  KNOWN_PRESETS,
  buildDomain,
  clampWindow,
  filterItemsToWindow,
  fullWindow,
  isFullWindow,
  parseLeadingYear,
  presetWindow,
  windowIndices,
} from "./helpers";

// --- Constants -------------------------------------------------------

describe("KNOWN_PRESETS / KNOWN_DOMAIN_KINDS", () => {
  it("KNOWN_PRESETS is the documented closed enum in canonical order", () => {
    expect(KNOWN_PRESETS).toEqual(["all", "recent", "5y", "10y", "25y"]);
  });

  it("KNOWN_PRESETS is frozen", () => {
    expect(Object.isFrozen(KNOWN_PRESETS)).toBe(true);
  });

  it("KNOWN_DOMAIN_KINDS is the documented closed enum", () => {
    expect(KNOWN_DOMAIN_KINDS).toEqual([
      "year",
      "election_cycle",
      "month",
      "fiscal_year",
      "custom",
    ]);
  });

  it("KNOWN_DOMAIN_KINDS is frozen", () => {
    expect(Object.isFrozen(KNOWN_DOMAIN_KINDS)).toBe(true);
  });
});

// --- parseLeadingYear ------------------------------------------------

describe("parseLeadingYear", () => {
  it("parses bare 4-digit year ids", () => {
    expect(parseLeadingYear("1977")).toBe(1977);
    expect(parseLeadingYear("2024")).toBe(2024);
  });

  it("parses fiscal-year ids", () => {
    expect(parseLeadingYear("FY2021")).toBe(2021);
    expect(parseLeadingYear("FY 2021-22")).toBe(2021);
  });

  it("parses month ids", () => {
    expect(parseLeadingYear("2024-05")).toBe(2024);
    expect(parseLeadingYear("2024/05")).toBe(2024);
  });

  it("returns null for election-cycle ids", () => {
    // "AcGenMay2023" has 2023 embedded but not as a leading bounded
    // token — the regex needs a leading non-letter boundary on the
    // RIGHT side too, which "May2023" doesn't have.
    expect(parseLeadingYear("AcGenMay2023")).toBe(null);
    expect(parseLeadingYear("GeJun2024")).toBe(null);
  });

  it("returns null for ids outside the sane year range", () => {
    expect(parseLeadingYear("1600")).toBe(null);
    expect(parseLeadingYear("2300")).toBe(null);
  });

  it("returns null for non-year garbage", () => {
    expect(parseLeadingYear("")).toBe(null);
    expect(parseLeadingYear("abc")).toBe(null);
    expect(parseLeadingYear("12345")).toBe(null); // 5 digits
  });
});

// --- buildDomain -----------------------------------------------------

describe("buildDomain", () => {
  it("throws on empty period_ids", () => {
    expect(() => buildDomain([], "year")).toThrow(/non-empty/);
  });

  it("returns a frozen domain with frozen ordered_period_ids", () => {
    const d = buildDomain(["2000", "2001", "2002"], "year");
    expect(Object.isFrozen(d)).toBe(true);
    expect(Object.isFrozen(d.ordered_period_ids)).toBe(true);
  });

  it("year domain computes min_year / max_year from ids", () => {
    const d = buildDomain(["1977", "1980", "2014", "2024"], "year");
    expect(d.min_year).toBe(1977);
    expect(d.max_year).toBe(2024);
  });

  it("fiscal_year domain parses FY prefix", () => {
    const d = buildDomain(["FY2018", "FY2019", "FY2020"], "fiscal_year");
    expect(d.min_year).toBe(2018);
    expect(d.max_year).toBe(2020);
  });

  it("month domain parses YYYY-MM ids", () => {
    const d = buildDomain(["2021-03", "2022-04", "2023-05"], "month");
    expect(d.min_year).toBe(2021);
    expect(d.max_year).toBe(2023);
  });

  it("election_cycle domain leaves min_year / max_year null", () => {
    const d = buildDomain(
      ["AcGenMay2018", "AcGenMay2023"],
      "election_cycle",
    );
    expect(d.min_year).toBe(null);
    expect(d.max_year).toBe(null);
  });

  it("custom domain leaves min_year / max_year null", () => {
    const d = buildDomain(["A", "B", "C"], "custom");
    expect(d.min_year).toBe(null);
    expect(d.max_year).toBe(null);
  });

  it("year-derivable domain with NO parseable ids leaves years null", () => {
    const d = buildDomain(["junk-a", "junk-b"], "year");
    expect(d.min_year).toBe(null);
    expect(d.max_year).toBe(null);
  });

  it("snapshots the input array (mutating the input doesn't affect domain)", () => {
    const input = ["2000", "2001"];
    const d = buildDomain(input, "year");
    input.push("2002");
    expect(d.ordered_period_ids).toEqual(["2000", "2001"]);
  });
});

// --- fullWindow / isFullWindow --------------------------------------

describe("fullWindow / isFullWindow", () => {
  const d = buildDomain(["1977", "1980", "2014", "2024"], "year");

  it("returns first..last", () => {
    const w = fullWindow(d);
    expect(w.from_period_id).toBe("1977");
    expect(w.to_period_id).toBe("2024");
  });

  it("isFullWindow detects the canonical full window", () => {
    expect(isFullWindow(fullWindow(d), d)).toBe(true);
  });

  it("isFullWindow rejects a partial window", () => {
    expect(
      isFullWindow({ from_period_id: "1980", to_period_id: "2024" }, d),
    ).toBe(false);
  });
});

// --- windowIndices ---------------------------------------------------

describe("windowIndices", () => {
  const d = buildDomain(["2018", "2019", "2020", "2021"], "year");

  it("returns the resolved indices", () => {
    const r = windowIndices(
      { from_period_id: "2019", to_period_id: "2020" },
      d,
    );
    expect(r).toEqual({ from_idx: 1, to_idx: 2 });
  });

  it("returns -1/-1 when from is unknown", () => {
    const r = windowIndices(
      { from_period_id: "1900", to_period_id: "2020" },
      d,
    );
    expect(r).toEqual({ from_idx: -1, to_idx: -1 });
  });

  it("returns -1/-1 when to is unknown", () => {
    const r = windowIndices(
      { from_period_id: "2019", to_period_id: "9999" },
      d,
    );
    expect(r).toEqual({ from_idx: -1, to_idx: -1 });
  });
});

// --- clampWindow -----------------------------------------------------

describe("clampWindow", () => {
  const d = buildDomain(["2018", "2019", "2020", "2021"], "year");

  it("returns the input window verbatim when canonical", () => {
    const r = clampWindow(
      { from_period_id: "2019", to_period_id: "2020" },
      d,
    );
    expect(r).toEqual({ from_period_id: "2019", to_period_id: "2020" });
  });

  it("swaps a reversed window", () => {
    const r = clampWindow(
      { from_period_id: "2020", to_period_id: "2019" },
      d,
    );
    expect(r).toEqual({ from_period_id: "2019", to_period_id: "2020" });
  });

  it("falls back to fullWindow when an id is unknown", () => {
    const r = clampWindow(
      { from_period_id: "stale", to_period_id: "2020" },
      d,
    );
    expect(r).toEqual({ from_period_id: "2018", to_period_id: "2021" });
  });

  it("preserves a single-period window", () => {
    const r = clampWindow(
      { from_period_id: "2020", to_period_id: "2020" },
      d,
    );
    expect(r).toEqual({ from_period_id: "2020", to_period_id: "2020" });
  });
});

// --- presetWindow ----------------------------------------------------

describe("presetWindow", () => {
  const d_year = buildDomain(
    ["1977", "1980", "1984", "1989", "1991", "1996", "1998", "1999", "2004", "2009", "2014", "2019", "2024"],
    "year",
  );
  const d_election = buildDomain(
    ["AcGenMay2013", "AcGenMay2018", "AcGenMay2023"],
    "election_cycle",
  );

  it("all → fullWindow", () => {
    expect(presetWindow("all", d_year)).toEqual(fullWindow(d_year));
    expect(presetWindow("all", d_election)).toEqual(fullWindow(d_election));
  });

  it("recent → last N periods (default 5)", () => {
    // Domain length = 13; last 5 indices = 8..12 → [2004, 2009, 2014, 2019, 2024].
    const r = presetWindow("recent", d_year);
    expect(r).toEqual({ from_period_id: "2004", to_period_id: "2024" });
  });

  it("recent → respects recent_count override", () => {
    const r = presetWindow("recent", d_year, { recent_count: 2 });
    expect(r).toEqual({ from_period_id: "2019", to_period_id: "2024" });
  });

  it("recent → returns full domain when count > domain length", () => {
    const small = buildDomain(["2022", "2023"], "year");
    const r = presetWindow("recent", small, { recent_count: 10 });
    expect(r).toEqual(fullWindow(small));
  });

  it("recent → works on election_cycle (no year arithmetic needed)", () => {
    const r = presetWindow("recent", d_election, { recent_count: 2 });
    expect(r).toEqual({
      from_period_id: "AcGenMay2018",
      to_period_id: "AcGenMay2023",
    });
  });

  it("5y → last 5 calendar years inclusive", () => {
    // max_year=2024, cutoff = 2020; ids >= 2020 are [2024] only
    // (the 2019 and 2014 are excluded).
    const r = presetWindow("5y", d_year);
    expect(r).toEqual({ from_period_id: "2024", to_period_id: "2024" });
  });

  it("10y → spans the requested window", () => {
    // max_year=2024, cutoff=2015; qualifying ids: [2019, 2024]
    const r = presetWindow("10y", d_year);
    expect(r).toEqual({ from_period_id: "2019", to_period_id: "2024" });
  });

  it("25y → spans the requested window", () => {
    // max_year=2024, cutoff=2000; qualifying ids: 2004..2024
    const r = presetWindow("25y", d_year);
    expect(r).toEqual({ from_period_id: "2004", to_period_id: "2024" });
  });

  it("25y clamps to last bar when full domain is shorter than window", () => {
    const short = buildDomain(["2020", "2021"], "year");
    const r = presetWindow("25y", short);
    // 2020 / 2021 both >= 2024-25+1 = 2000, so qualifying = full
    expect(r).toEqual(fullWindow(short));
  });

  it("10y → null on election_cycle domain (year-arithmetic unavailable)", () => {
    expect(presetWindow("10y", d_election)).toBe(null);
    expect(presetWindow("25y", d_election)).toBe(null);
    expect(presetWindow("5y", d_election)).toBe(null);
  });

  it("clamps year-window preset to last id when nothing qualifies", () => {
    // Manufacture: ids include only old years; max_year is 1990, but
    // we ask for a window that ends before 1990.
    const old = buildDomain(["1980", "1985", "1990"], "year");
    // Override the max_year to a value that makes the cutoff exceed
    // every id — we test the clamp branch.
    const synthetic_domain = {
      ...old,
      max_year: 2050,
    };
    // 5y window: cutoff = 2046; no id qualifies → clamps to last id.
    const r = presetWindow("5y", synthetic_domain);
    expect(r).toEqual({ from_period_id: "1990", to_period_id: "1990" });
  });
});

// --- filterItemsToWindow --------------------------------------------

describe("filterItemsToWindow", () => {
  const d = buildDomain(["2018", "2019", "2020", "2021"], "year");

  it("returns items whose period_id falls inside the window inclusive", () => {
    const items = [
      { id: "a", period: "2018" },
      { id: "b", period: "2019" },
      { id: "c", period: "2020" },
      { id: "d", period: "2021" },
    ];
    const r = filterItemsToWindow(
      items,
      it => it.period,
      { from_period_id: "2019", to_period_id: "2020" },
      d,
    );
    expect(r.map(x => x.id)).toEqual(["b", "c"]);
  });

  it("drops items whose period_id is not in the domain (stale data)", () => {
    const items = [
      { id: "a", period: "2018" },
      { id: "x", period: "1900" }, // not in domain
      { id: "b", period: "2019" },
    ];
    const r = filterItemsToWindow(
      items,
      it => it.period,
      { from_period_id: "2018", to_period_id: "2020" },
      d,
    );
    expect(r.map(x => x.id)).toEqual(["a", "b"]);
  });

  it("returns the full items list (cloned) when window has unknown ids", () => {
    const items = [
      { id: "a", period: "2018" },
      { id: "b", period: "2019" },
    ];
    const r = filterItemsToWindow(
      items,
      it => it.period,
      { from_period_id: "stale", to_period_id: "also-stale" },
      d,
    );
    expect(r.map(x => x.id)).toEqual(["a", "b"]);
  });

  it("returns empty when no items match the window", () => {
    const items = [
      { id: "a", period: "2018" },
      { id: "b", period: "2019" },
    ];
    const r = filterItemsToWindow(
      items,
      it => it.period,
      { from_period_id: "2020", to_period_id: "2021" },
      d,
    );
    expect(r).toEqual([]);
  });

  it("preserves input order (stable)", () => {
    const items = [
      { id: "c", period: "2020" },
      { id: "b", period: "2019" },
      { id: "a", period: "2018" },
    ];
    const r = filterItemsToWindow(
      items,
      it => it.period,
      { from_period_id: "2018", to_period_id: "2021" },
      d,
    );
    expect(r.map(x => x.id)).toEqual(["c", "b", "a"]);
  });
});
