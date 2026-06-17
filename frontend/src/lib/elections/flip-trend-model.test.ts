/**
 * Unit tests for flip-trend-model (PR5 of
 * TODO/20260617-election-compare-ux-overhaul-plan.md).
 *
 * Pins the flip-trend delta contract:
 *  - flips_this (from -> to) and flips_prior (prevPrev -> from) counts;
 *  - delta = flips_this - flips_prior;
 *  - intersection-only counting (a seat present in only one event of a
 *    pair never counts);
 *  - null-party exclusion (a seat with an unknown winner on either side of
 *    a pair is non-comparable - dropped from BOTH comparable + flips);
 *  - first-transition pin: an empty prevPrev set yields flips_prior 0 +
 *    comparable_prior 0 (the route omits the pill in that case).
 *
 * Pure model -> no Svelte mount, runs in the node env.
 */

import { describe, it, expect } from "vitest";
import {
  computeFlipTrend,
  type FlipTrendWinner,
} from "./flip-trend-model";

// Minimal winner-row factory.
function w(entity_id: string, party_id: string | null): FlipTrendWinner {
  return { entity_id, party_id };
}

describe("computeFlipTrend: basic delta", () => {
  // prevPrev -> from: a1 holds, a2 flips inc->dmk            => 1 prior flip
  // from -> to:       a1 flips dmk->bjp, a2 flips dmk->admk  => 2 this flips
  const prevPrev = [w("a1", "dmk"), w("a2", "inc")];
  const from = [w("a1", "dmk"), w("a2", "dmk")];
  const to = [w("a1", "bjp"), w("a2", "admk")];

  it("counts flips for both transitions", () => {
    const t = computeFlipTrend({
      prevPrevWinners: prevPrev,
      fromWinners: from,
      toWinners: to,
    });
    expect(t.flips_this).toBe(2);
    expect(t.flips_prior).toBe(1);
  });

  it("delta is flips_this - flips_prior", () => {
    const t = computeFlipTrend({
      prevPrevWinners: prevPrev,
      fromWinners: from,
      toWinners: to,
    });
    expect(t.delta).toBe(1);
  });

  it("reports comparable-seat base per pair", () => {
    const t = computeFlipTrend({
      prevPrevWinners: prevPrev,
      fromWinners: from,
      toWinners: to,
    });
    expect(t.comparable_this).toBe(2);
    expect(t.comparable_prior).toBe(2);
  });

  it("yields a negative delta when flipping cooled off", () => {
    // this: a1 holds, a2 holds => 0 flips; prior: a1 flips => 1 flip.
    const t = computeFlipTrend({
      prevPrevWinners: [w("a1", "inc"), w("a2", "dmk")],
      fromWinners: [w("a1", "dmk"), w("a2", "dmk")],
      toWinners: [w("a1", "dmk"), w("a2", "dmk")],
    });
    expect(t.flips_this).toBe(0);
    expect(t.flips_prior).toBe(1);
    expect(t.delta).toBe(-1);
  });
});

describe("computeFlipTrend: intersection-only counting", () => {
  it("ignores seats present in only one event of a pair", () => {
    // a3 exists only in `to`; a0 exists only in prevPrev. Neither is in
    // its pair's intersection, so neither inflates comparable or flips.
    const t = computeFlipTrend({
      prevPrevWinners: [w("a0", "xxx"), w("a1", "inc")],
      fromWinners: [w("a1", "dmk")],
      toWinners: [w("a1", "bjp"), w("a3", "ind")],
    });
    // current pair intersection = {a1}: flip dmk->bjp.
    expect(t.flips_this).toBe(1);
    expect(t.comparable_this).toBe(1);
    // prior pair intersection = {a1}: flip inc->dmk.
    expect(t.flips_prior).toBe(1);
    expect(t.comparable_prior).toBe(1);
    expect(t.delta).toBe(0);
  });
});

describe("computeFlipTrend: null-party exclusion", () => {
  it("drops a seat with an unknown winner on either side of a pair", () => {
    // current pair: a1 flips (dmk->bjp); a2 has null on the `to` side ->
    // non-comparable; a3 has null on the `from` side -> non-comparable.
    const t = computeFlipTrend({
      prevPrevWinners: [],
      fromWinners: [w("a1", "dmk"), w("a2", "inc"), w("a3", null)],
      toWinners: [w("a1", "bjp"), w("a2", null), w("a3", "ind")],
    });
    expect(t.flips_this).toBe(1);
    // Only a1 is comparable; a2 + a3 are excluded by the null party.
    expect(t.comparable_this).toBe(1);
  });

  it("does not count a null==null seat as a flip or as comparable", () => {
    const t = computeFlipTrend({
      prevPrevWinners: [],
      fromWinners: [w("a1", null)],
      toWinners: [w("a1", null)],
    });
    expect(t.flips_this).toBe(0);
    expect(t.comparable_this).toBe(0);
  });
});

describe("computeFlipTrend: first-transition (empty prevPrev)", () => {
  it("yields flips_prior 0 and comparable_prior 0", () => {
    const t = computeFlipTrend({
      prevPrevWinners: [],
      fromWinners: [w("a1", "dmk"), w("a2", "inc")],
      toWinners: [w("a1", "bjp"), w("a2", "inc")],
    });
    expect(t.flips_prior).toBe(0);
    expect(t.comparable_prior).toBe(0);
    // delta == flips_this when there is no prior transition.
    expect(t.flips_this).toBe(1);
    expect(t.delta).toBe(1);
  });
});
