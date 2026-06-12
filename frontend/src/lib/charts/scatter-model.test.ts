// Vitest suite for scatter-model.ts (PR-W4c, 2026-06-10).
//
// Covers the 4 brief tests verbatim:
//   1. 50 mock rows pass through applyFilters({}) unchanged.
//   2. sqrt-correct radius: electors ratio 4 -> radius ratio 2.
//   3. Click handler dispatch: tested via Playwright (this suite is pure).
//   4. Filter narrowing: reservation, body, margin_band, event, state.
//
// Per the W4a precedent (year-pill-strip-model.test.ts +
// inline-swing-model.ts), the click-dispatch contract is exercised in
// `frontend/e2e/elections-scatter.spec.ts` (G2 gate), NOT here, because
// the project intentionally does not install `@testing-library/svelte`.
// The Svelte component itself is a thin renderer over `applyFilters`,
// `sqrtRadius`, and `marginBandOf` — every test here is end-to-end
// proof that the visible rows / dot sizes / band assignments the
// component shows are correct.

import { describe, it, expect } from "vitest";

import {
  applyFilters,
  computeYMax,
  marginBandOf,
  maxElectors,
  maxMarginVotes,
  sqrtRadius,
  type ScatterDatum,
  type ScatterFilters,
} from "./scatter-model";
import { SCATTER_FIXTURES } from "./scatter-fixtures";

describe("scatter-model: fixture sanity", () => {
  it("ships 50 rows so the 50-dots brief oracle is testable", () => {
    expect(SCATTER_FIXTURES.length).toBe(50);
  });

  it("every row has the brief-mandated fields populated", () => {
    for (const d of SCATTER_FIXTURES) {
      expect(d.entity_id).toBeTruthy();
      expect(d.state_slug).toBeTruthy();
      expect(d.constituency_slug).toBeTruthy();
      expect(d.constituency_name).toBeTruthy();
      expect(d.event_id).toBeTruthy();
      expect(Number.isFinite(d.turnout_pct)).toBe(true);
      expect(Number.isFinite(d.margin_pct)).toBe(true);
      expect(Number.isFinite(d.electors)).toBe(true);
      // TODO/20260612 Row B: margin_votes is the new radius-encoding
      // field. Fixtures synthesise it deterministically; assert it is
      // finite (>=0) so the radius-scale tests have non-null inputs.
      expect(d.margin_votes).not.toBeNull();
      expect(Number.isFinite(d.margin_votes as number)).toBe(true);
      expect(d.margin_votes as number).toBeGreaterThanOrEqual(0);
      expect(d.winner_party_id).toMatch(/^parties\.IN\./);
      expect(d.winner_party_short).toBeTruthy();
      expect(["GEN", "SC", "ST"]).toContain(d.reservation);
      expect(["parliament", "assembly"]).toContain(d.body);
    }
  });
});

describe("applyFilters: brief test 1 (50 rows -> 50 dots)", () => {
  it("returns every row when no filter is set", () => {
    expect(applyFilters(SCATTER_FIXTURES, {}).length).toBe(50);
  });

  it("treats `all` literals as no-narrowing", () => {
    const filters: ScatterFilters = {
      reservation: "all",
      body: "all",
      margin_band: "all",
    };
    expect(applyFilters(SCATTER_FIXTURES, filters).length).toBe(50);
  });

  it("does not mutate the input array", () => {
    const before = SCATTER_FIXTURES.map((d) => d.entity_id);
    applyFilters(SCATTER_FIXTURES, { reservation: "ST" });
    const after = SCATTER_FIXTURES.map((d) => d.entity_id);
    expect(after).toEqual(before);
  });
});

describe("applyFilters: brief test 4 (filter narrowing)", () => {
  it("reservation=ST narrows to the 5 ST rows", () => {
    const out = applyFilters(SCATTER_FIXTURES, { reservation: "ST" });
    expect(out.length).toBe(5);
    for (const d of out) expect(d.reservation).toBe("ST");
  });

  it("reservation=SC narrows to the 8 SC rows", () => {
    const out = applyFilters(SCATTER_FIXTURES, { reservation: "SC" });
    expect(out.length).toBe(8);
    for (const d of out) expect(d.reservation).toBe("SC");
  });

  it("reservation=GEN narrows to the 37 GEN rows", () => {
    const out = applyFilters(SCATTER_FIXTURES, { reservation: "GEN" });
    expect(out.length).toBe(37);
    for (const d of out) expect(d.reservation).toBe("GEN");
  });

  it("body=parliament narrows to the 25 PC rows", () => {
    const out = applyFilters(SCATTER_FIXTURES, { body: "parliament" });
    expect(out.length).toBe(25);
    for (const d of out) expect(d.body).toBe("parliament");
  });

  it("body=assembly narrows to the 25 AC rows", () => {
    const out = applyFilters(SCATTER_FIXTURES, { body: "assembly" });
    expect(out.length).toBe(25);
    for (const d of out) expect(d.body).toBe("assembly");
  });

  it("margin_band=lt2 narrows to the 5 close-fight rows", () => {
    const out = applyFilters(SCATTER_FIXTURES, { margin_band: "lt2" });
    expect(out.length).toBe(5);
    for (const d of out) expect(d.margin_pct).toBeLessThan(2);
  });

  it("margin_band=gt10 narrows to the 25 wide-margin rows", () => {
    const out = applyFilters(SCATTER_FIXTURES, { margin_band: "gt10" });
    expect(out.length).toBe(25);
    for (const d of out) expect(d.margin_pct).toBeGreaterThanOrEqual(10);
  });

  it("state=tamil-nadu narrows to the 10 Tamil Nadu rows (5 PC + 5 AC)", () => {
    const out = applyFilters(SCATTER_FIXTURES, { state: "tamil-nadu" });
    expect(out.length).toBe(10);
    for (const d of out) expect(d.state_slug).toBe("tamil-nadu");
  });

  it("event=general-2024 narrows to the 25 PC parliament rows", () => {
    const out = applyFilters(SCATTER_FIXTURES, { event: "general-2024" });
    expect(out.length).toBe(25);
    for (const d of out) expect(d.event_id).toBe("general-2024");
  });

  it("composite narrows monotonically (intersection of all filters)", () => {
    const out = applyFilters(SCATTER_FIXTURES, {
      body: "parliament",
      state: "tamil-nadu",
      reservation: "GEN",
    });
    // 5 TN PCs total: PC-1 (GEN), PC-2 (GEN), PC-3 (SC), PC-4 (GEN), PC-5 (GEN) -> 4 GEN
    expect(out.length).toBe(4);
    for (const d of out) {
      expect(d.body).toBe("parliament");
      expect(d.state_slug).toBe("tamil-nadu");
      expect(d.reservation).toBe("GEN");
    }
  });
});

describe("marginBandOf: 4-band binning", () => {
  it.each([
    [0, "lt2"],
    [1.9, "lt2"],
    [2, "2to5"],
    [4.9, "2to5"],
    [5, "5to10"],
    [9.9, "5to10"],
    [10, "gt10"],
    [50, "gt10"],
  ] as const)("%f%% -> %s", (pct, expected) => {
    expect(marginBandOf(pct)).toBe(expected);
  });
});

describe("sqrtRadius: brief test 2 (sqrt-correct ratio)", () => {
  it("ratio of radii equals sqrt(ratio of electors) for the canonical 1M/4M case", () => {
    const e1 = 1_000_000;
    const e2 = 4_000_000;
    // Domain max == e2 so the larger dot lands on the configured radius
    // ceiling; the smaller dot's radius is `max_r * sqrt(0.25) = max_r/2`.
    const r1 = sqrtRadius(e1, e2);
    const r2 = sqrtRadius(e2, e2);
    expect(r2 / r1).toBeCloseTo(2, 5);
  });

  it("ratio is general: ratio_radii == sqrt(ratio_electors)", () => {
    const max = 4_000_000;
    const cases: Array<[number, number, number]> = [
      [1_000_000, 4_000_000, Math.sqrt(4)],
      [500_000, 2_000_000, Math.sqrt(4)],
      [100_000, 900_000, 3],
      [1_000_000, 1_000_000, 1],
    ];
    for (const [a, b, expected_ratio] of cases) {
      const ratio = sqrtRadius(b, max) / sqrtRadius(a, max);
      expect(ratio).toBeCloseTo(expected_ratio, 5);
    }
  });

  it("the largest dot lands on max_r", () => {
    expect(sqrtRadius(1, 1)).toBeCloseTo(22, 5);
    expect(sqrtRadius(2_000_000, 2_000_000, 30)).toBeCloseTo(30, 5);
  });

  it("an empty domain returns 0 instead of NaN", () => {
    expect(sqrtRadius(123, 0)).toBe(0);
    expect(sqrtRadius(123, -5)).toBe(0);
  });

  it("a negative or zero `electors` value returns 0 instead of NaN", () => {
    expect(sqrtRadius(0, 1_000_000)).toBe(0);
    expect(sqrtRadius(-50, 1_000_000)).toBe(0);
  });
});

// --------------------------------------------------------------------
// TODO/20260612 Row A.3 + B helpers - computeYMax + maxMarginVotes
// --------------------------------------------------------------------

describe("computeYMax: dynamic Y-axis upper bound", () => {
  function row(margin_pct: number, overrides: Partial<ScatterDatum> = {}): ScatterDatum {
    return {
      entity_id: "X",
      state_slug: "x",
      constituency_slug: "x",
      constituency_name: "X",
      event_id: "e",
      turnout_pct: 60,
      margin_pct,
      electors: 1000,
      margin_votes: 100,
      winner_party_id: "parties.IN.UNK",
      winner_party_short: "UNK",
      reservation: "GEN",
      body: "assembly",
      ...overrides,
    };
  }

  it("returns 40 for an empty input (Rosling floor)", () => {
    expect(computeYMax([])).toBe(40);
  });

  it("returns 40 when every margin is below the floor", () => {
    expect(computeYMax([row(5), row(12), row(30)])).toBe(40);
  });

  it("rounds up to the next multiple of 10 with 10% headroom", () => {
    // max=45 -> ceil(45 * 1.1 / 10) * 10 = ceil(4.95) * 10 = 50
    expect(computeYMax([row(20), row(45)])).toBe(50);
  });

  it("keeps the result at the floor for small datasets that span the floor", () => {
    // max=35 -> ceil(38.5 / 10) * 10 = 40 -> floor wins
    expect(computeYMax([row(35)])).toBe(40);
  });

  it("caps at 100 (the chart's hard upper bound)", () => {
    expect(computeYMax([row(99)])).toBe(100);
    expect(computeYMax([row(100)])).toBe(100);
  });

  it("always returns a multiple of 10 (clean tick rendering)", () => {
    for (let m = 5; m <= 95; m += 7) {
      expect(computeYMax([row(m)]) % 10).toBe(0);
    }
  });

  it("is monotonically non-decreasing as the largest margin grows", () => {
    let prev = 0;
    for (const m of [5, 18, 30, 45, 60, 75, 90]) {
      const y = computeYMax([row(m)]);
      expect(y).toBeGreaterThanOrEqual(prev);
      prev = y;
    }
  });
});

describe("maxMarginVotes: convenience reduce over margin_votes", () => {
  function row(margin_votes: number | null, overrides: Partial<ScatterDatum> = {}): ScatterDatum {
    return {
      entity_id: "X",
      state_slug: "x",
      constituency_slug: "x",
      constituency_name: "X",
      event_id: "e",
      turnout_pct: 60,
      margin_pct: 5,
      electors: 1000,
      margin_votes,
      winner_party_id: "parties.IN.UNK",
      winner_party_short: "UNK",
      reservation: "GEN",
      body: "assembly",
      ...overrides,
    };
  }

  it("returns 0 for an empty array", () => {
    expect(maxMarginVotes([])).toBe(0);
  });

  it("returns the largest non-null value", () => {
    expect(maxMarginVotes([row(100), row(50), row(425)])).toBe(425);
  });

  it("skips nulls (uncontested seats)", () => {
    expect(maxMarginVotes([row(100), row(null), row(50)])).toBe(100);
  });

  it("returns 0 when every row is null / negative", () => {
    expect(maxMarginVotes([row(null), row(-5), row(null)])).toBe(0);
  });

  it("is non-zero on the bundled SCATTER_FIXTURES (50 rows)", () => {
    expect(maxMarginVotes(SCATTER_FIXTURES)).toBeGreaterThan(0);
  });
});

describe("maxElectors", () => {
  it("returns the largest electors value across a row set", () => {
    const max = maxElectors(SCATTER_FIXTURES);
    // PC-6 (Bangalore South) has 2,410,315 electors — the largest in
    // the fixture set.
    expect(max).toBe(2_410_315);
  });

  it("returns 0 on an empty array", () => {
    expect(maxElectors([])).toBe(0);
  });

  it("returns the single value on a 1-row input", () => {
    const row: ScatterDatum = {
      entity_id: "x",
      state_slug: "x",
      constituency_slug: "x",
      constituency_name: "x",
      event_id: "general-2024",
      turnout_pct: 50,
      margin_pct: 5,
      electors: 12345,
      // TODO/20260612 Row B contract: ScatterDatum now requires the
      // margin_votes field (drives the radius encoding). The maxElectors
      // helper ignores it, but the type-check needs it populated.
      margin_votes: 250,
      winner_party_id: "parties.IN.BJP",
      winner_party_short: "BJP",
      reservation: "GEN",
      body: "parliament",
    };
    expect(maxElectors([row])).toBe(12345);
  });
});
