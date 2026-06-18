// Row E of TODO/20260617-party-page-polish-and-cdn-config-plan.md
// (Jony P1 + Citizen). Pure-helper oracle for the strongholds
// strike-rate sort + badge tier on /parties/<slug>.
//
// The strongholds lists now order best-to-least by STRIKE-RATE
// (wins/contested), with a colour-coded badge per row. The math lives
// in three pure helpers so it is testable without mounting the page:
//   - `strongholdStrikeRate` + `compareStrongholdsByStrikeRate`
//     (in `./party-detail`, applied to the mart-returned arrays);
//   - `strikeRateTierClass` (in `../parties/StrongholdList.svelte`,
//     mirrors the sanctioned `DataCompleteness` tier palette).
import { describe, expect, it } from "vitest";
import {
  compareStrongholdsByStrikeRate,
  strongholdStrikeRate,
  type PartyStronghold,
} from "./party-detail";
import { strikeRateTierClass } from "../parties/StrongholdList.svelte";

/** Minimal PartyStronghold factory - the comparator only reads
 *  `wins`, `contested`, `last_won_year`, `entity_id`; the rest are
 *  filled with inert defaults. */
function sh(overrides: Partial<PartyStronghold> = {}): PartyStronghold {
  return {
    entity_id: "IN-AC-2008-S22-1",
    constituency_name: "Test AC",
    state: "tamil-nadu",
    wins: 1,
    contested: 1,
    results: ["W"],
    last_won_year: 2024,
    source_ids: ["src-aaaaaaaaaaaa"],
    pc_slug: null,
    href: null,
    ...overrides,
  };
}

describe("strongholdStrikeRate", () => {
  it("rounds wins/contested to a whole percent", () => {
    expect(strongholdStrikeRate({ wins: 3, contested: 4 })).toBe(75);
    expect(strongholdStrikeRate({ wins: 8, contested: 8 })).toBe(100);
    expect(strongholdStrikeRate({ wins: 1, contested: 1 })).toBe(100);
  });

  it("rounds half up like the rest of the page (7/8 -> 88, 2/3 -> 67)", () => {
    expect(strongholdStrikeRate({ wins: 7, contested: 8 })).toBe(88);
    expect(strongholdStrikeRate({ wins: 2, contested: 3 })).toBe(67);
  });

  it("returns 0 when contested is 0 (defensive) and when wins is 0", () => {
    expect(strongholdStrikeRate({ wins: 0, contested: 0 })).toBe(0);
    expect(strongholdStrikeRate({ wins: 0, contested: 5 })).toBe(0);
  });
});

describe("compareStrongholdsByStrikeRate", () => {
  it("orders best-to-least by LITERAL strike-rate, overriding wins (thin sample)", () => {
    // A 1-of-1 (100%) floats ABOVE a 7-of-8 (88%) despite far fewer
    // wins - the intended literal strike-rate sort, NOT wins-primary.
    const rows = [
      sh({ entity_id: "MID", wins: 2, contested: 3 }), // 67%
      sh({ entity_id: "STRONG", wins: 7, contested: 8 }), // 88%, most wins
      sh({ entity_id: "SWEEP", wins: 1, contested: 1 }), // 100%, fewest wins
    ];
    expect(
      [...rows].sort(compareStrongholdsByStrikeRate).map((s) => s.entity_id),
    ).toEqual(["SWEEP", "STRONG", "MID"]);
  });

  it("breaks an equal strike-rate by wins desc", () => {
    const rows = [
      sh({ entity_id: "ONE", wins: 1, contested: 1 }), // 100%, 1 win
      sh({ entity_id: "TWO", wins: 2, contested: 2 }), // 100%, 2 wins
    ];
    expect(
      [...rows].sort(compareStrongholdsByStrikeRate).map((s) => s.entity_id),
    ).toEqual(["TWO", "ONE"]);
  });

  it("breaks an equal strike-rate + wins by last_won_year desc, nulls last", () => {
    const recent = sh({ entity_id: "RECENT", wins: 2, contested: 2, last_won_year: 2024 });
    const older = sh({ entity_id: "OLD", wins: 2, contested: 2, last_won_year: 1980 });
    const nully = sh({ entity_id: "NULLY", wins: 2, contested: 2, last_won_year: null });
    expect(
      [nully, older, recent]
        .sort(compareStrongholdsByStrikeRate)
        .map((s) => s.entity_id),
    ).toEqual(["RECENT", "OLD", "NULLY"]);
  });

  it("uses entity_id asc as the final deterministic tiebreak", () => {
    const a = sh({ entity_id: "AAA", wins: 2, contested: 2, last_won_year: 2024 });
    const b = sh({ entity_id: "BBB", wins: 2, contested: 2, last_won_year: 2024 });
    expect(
      [b, a].sort(compareStrongholdsByStrikeRate).map((s) => s.entity_id),
    ).toEqual(["AAA", "BBB"]);
    // Fully-identical keys compare equal (stable, transitive).
    expect(compareStrongholdsByStrikeRate(a, a)).toBe(0);
  });
});

describe("strikeRateTierClass", () => {
  const EMERALD = "bg-emerald-100 text-emerald-900 border-emerald-300";
  const AMBER = "bg-amber-100 text-amber-900 border-amber-300";
  const ROSE = "bg-rose-100 text-rose-900 border-rose-300";

  it("emerald at >= 80, amber at 50-79, rose at < 50 (band boundaries)", () => {
    expect(strikeRateTierClass(80)).toBe(EMERALD);
    expect(strikeRateTierClass(79)).toBe(AMBER);
    expect(strikeRateTierClass(50)).toBe(AMBER);
    expect(strikeRateTierClass(49)).toBe(ROSE);
  });

  it("covers the extremes", () => {
    expect(strikeRateTierClass(100)).toBe(EMERALD);
    expect(strikeRateTierClass(0)).toBe(ROSE);
  });
});
