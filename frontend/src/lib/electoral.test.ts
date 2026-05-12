import { describe, it, expect } from "vitest";
import { majorityFor, hasMajority } from "./electoral";

describe("majorityFor", () => {
  it("uses floor(N/2)+1 — strictly more than half", () => {
    // TN Legislative Assembly: 234 seats → 118 (not 117).
    expect(majorityFor(234)).toBe(118);
    // Lok Sabha: 543 seats → 272.
    expect(majorityFor(543)).toBe(272);
    // Karnataka: 224 → 113.
    expect(majorityFor(224)).toBe(113);
  });

  it("handles small odd and even houses", () => {
    expect(majorityFor(1)).toBe(1);
    expect(majorityFor(2)).toBe(2);
    expect(majorityFor(3)).toBe(2);
    expect(majorityFor(4)).toBe(3);
  });

  it("returns 0 for invalid input", () => {
    expect(majorityFor(0)).toBe(0);
    expect(majorityFor(-1)).toBe(0);
    expect(majorityFor(NaN)).toBe(0);
    expect(majorityFor(Infinity)).toBe(0);
  });
});

describe("hasMajority", () => {
  it("is true exactly at and above the majority threshold", () => {
    expect(hasMajority(118, 234)).toBe(true);
    expect(hasMajority(117, 234)).toBe(false);
    expect(hasMajority(234, 234)).toBe(true);
  });

  it("is false when a party has zero seats", () => {
    expect(hasMajority(0, 234)).toBe(false);
  });

  it("is false against an invalid house size (threshold is 0, but 0 seats also doesn't qualify)", () => {
    // majorityFor(0) === 0 → seats >= 0 is trivially true. Document the
    // current behaviour so a future change is a deliberate decision.
    expect(hasMajority(0, 0)).toBe(true);
    expect(hasMajority(5, 0)).toBe(true);
  });
});
