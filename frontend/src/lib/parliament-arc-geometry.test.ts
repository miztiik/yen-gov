// Load-bearing oracle for ParliamentArc geometry (Request G).
//
// Pure vitest (node-env) - imports computeArcGeometry directly, no component
// mount (@testing-library/svelte is NOT installed). Three invariants:
//
//   1. Reconciliation - a 234-seat chamber renders exactly 234 dots, and a
//      2-party split keeps per-party seat counts after the rounding walk.
//   2. Compactness - a small chamber's horizontal span is <= 0.7x a large
//      one (reverting the radius scale flips this RED).
//   3. Large-chamber unchanged - scale clamps to 1 at >= 140 seats, so the
//      TN layout's outer radius equals ARC_R_OUTER.

import { describe, it, expect } from "vitest";
import type { PartyResult } from "./psephlab/types";
import { computeArcGeometry, ARC_R_OUTER } from "./parliament-arc-geometry";

// Synthetic PartyResult. Brand fields null so partyColourHex resolves via the
// algorithmic fallback tier (pure, node-env safe - no DOM, no I/O).
function party(party_eci_code: string, seats_won: number): PartyResult {
  return {
    party_eci_code,
    party_short: party_eci_code,
    seats_won,
    votes: 0,
    vote_share_pct: 0,
    party_id: `parties.IN.${party_eci_code}`,
    brand_colour_hex: null,
    brand_colour_confidence: null,
  };
}

const oneParty = (seats: number): PartyResult[] => [party("A", seats)];

const span = (g: { dots: ReadonlyArray<{ x: number }> }): number =>
  Math.max(...g.dots.map((d) => d.x)) - Math.min(...g.dots.map((d) => d.x));

describe("computeArcGeometry", () => {
  it("reconciles a single 234-seat party to exactly 234 dots (TN invariant)", () => {
    const g = computeArcGeometry({ parties: oneParty(234), total_seats: 234 });
    expect(
      g.dots.length,
      `expected 234 dots for a 234-seat chamber, got ${g.dots.length}`,
    ).toBe(234);
  });

  it("honours per-party seat counts after the party walk + rounding reconciliation", () => {
    const parties = [party("A", 200), party("B", 34)];
    const g = computeArcGeometry({ parties, total_seats: 234 });
    const countA = g.dots.filter((d) => d.party_eci_code === "A").length;
    const countB = g.dots.filter((d) => d.party_eci_code === "B").length;
    expect(g.dots.length, "total dots must equal total_seats (234)").toBe(234);
    expect(countA, `party A must own exactly 200 dots, got ${countA}`).toBe(200);
    expect(countB, `party B must own exactly 34 dots, got ${countB}`).toBe(34);
  });

  it("renders a small chamber COMPACT - span(20) <= 0.7 * span(234)", () => {
    const small = computeArcGeometry({ parties: oneParty(20), total_seats: 20 });
    const large = computeArcGeometry({ parties: oneParty(234), total_seats: 234 });
    const ratio = span(small) / span(large);
    expect(
      span(small),
      `compact arc span ${span(small).toFixed(1)} must be <= 0.7 * full span ` +
        `${span(large).toFixed(1)} (observed ratio ${ratio.toFixed(3)}); ` +
        `reverting the radius scale (fixed radii) flips this RED`,
    ).toBeLessThanOrEqual(0.7 * span(large));
  });

  it("leaves large chambers (>= 140 seats) at the unscaled outer radius", () => {
    const g = computeArcGeometry({ parties: oneParty(234), total_seats: 234 });
    expect(
      g.max_radius,
      `scale clamps to 1 at >= 140 seats, so max_radius must equal ARC_R_OUTER ` +
        `(${ARC_R_OUTER}); got ${g.max_radius}`,
    ).toBe(ARC_R_OUTER);
  });
});
